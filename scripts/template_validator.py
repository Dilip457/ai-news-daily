#!/usr/bin/env python3
"""
Strict Template Validator
==========================
Validates that an HTML file uses the EXACT approved template by:
1. Checking all critical CSS/JS/structural markers
2. Comparing the <style> block byte-for-byte against the master template
3. Comparing all <script> blocks byte-for-byte against the master template
4. Verifying CSS variable names and values match exactly
5. Security gate: identical Content-Security-Policy, no inline event handlers,
   only http(s) links, no extra script/iframe/object/embed/form/base tags, and
   no external origins beyond those the template already loads

Usage:
    python template_validator.py /path/to/output.html [--template /path/to/master_template.html]

The template defaults to $AI_NEWS_HOME/master_template.html
(AI_NEWS_HOME defaults to /scratch/work/notes).

Exit codes:
    0 = Valid (template matches)
    1 = Invalid (template does not match — DO NOT PUBLISH)
    2 = Usage error or master template missing
"""
import os
import re
import sys

AI_NEWS_HOME = os.environ.get("AI_NEWS_HOME", "/scratch/work/notes")
TEMPLATE_PATH = os.path.join(AI_NEWS_HOME, "master_template.html")

REQUIRED_MARKERS = [
    "--bg:#070710", "--bg2:#0c0c18", "--accent:#7c3aed", "--accent2:#0891b2",
    "--accent3:#db2777", "--text:#edecf5", "--muted:#8389a3", "--dim:#4a4f64",
    "--surface:rgba(255,255,255,.025)", "--border:rgba(255,255,255,.06)",
    "--modal-bg:rgba(7,7,16,.95)", "--shadow:0 20px 60px rgba(0,0,0,.5)",
    'class="grid-bg"', 'class="kicker"', 'class="brief-list"', 'class="bento"',
    'class="concept-label"', 'class="noise"', 'class="aurora"', 'class="meta-row"',
    'class="subtitle"', 'class="wrap"', 'class="chips"', 'class="grid-cards"',
    'class="modal-card"', "mk('div','modal-why')", "tab-body", "bg-canvas",
    "three.min.js", "toggleTheme", ".spotlight::before", "blur(20px)",
    "@keyframes drift", "@keyframes fadeUp", "@keyframes blink",
    'http-equiv="Content-Security-Policy"', 'integrity="sha384-',
]

FORBIDDEN_MARKERS = [
    "--bg-alt:", "--text-dim:", "--text-faint:", "--accent-dim:", "--accent-glow:",
    "--font-mono:", "--font-serif:", "--border-hover:", "--surface-hover:",
    "particle-canvas", "aurora-blob", "hero-title", "hero-date", "hero-sub",
    "logo-dot", "last-updated", "header-inner", "header-right",
    "article-card", "article-grid", "glass-card", "filter-chip",
    "trend-card", "trend-name", "trend-desc", "trend-number", "trend-related",
    "concept-para", "concept-title", "concept-section", "brief-expand",
    "score-badge", "rank-number", "source-tag", "stat-box", "stat-value",
    "stat-label", "date-tag", "section-tag", "section-title",
    "bento-grid", "bento-stats", "bento-why-read", "why-matters", "why-read-text",
    "top10-item", "top10-content", "top10-header", "top10-footer", "top10-summary",
    "footer-link", "footer-text", "search-box", "modal-content", "modal-meta",
    "modal-text", "related-list", "related-label", "fadeInUp", "pulse-dot",
    "reveal.visible",
]

# Tags that must never appear more often than in the master template
DANGEROUS_TAGS = ["script", "iframe", "object", "embed", "form", "base", "meta", "link"]

CSP_RE = re.compile(r'<meta http-equiv="Content-Security-Policy" content="([^"]*)">')
INLINE_HANDLER_RE = re.compile(r"""\son[a-z]+\s*=\s*["']""", re.I)
ATTR_URL_RE = re.compile(r'\s(?:href|src|action|formaction|poster|data)\s*=\s*"([^"]*)"', re.I)
EXTERNAL_RE = re.compile(r'<(?:script|link)\b[^>]*\s(?:src|href)="(https?://[^"]+)"', re.I)


def load_template(path=None):
    path = path or TEMPLATE_PATH
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    print(f"ERROR: Master template missing at {path}")
    print("Run bootstrap.py to restore it from GitHub repo Dilip457/ai-news-daily")
    sys.exit(2)


def extract_style(html):
    m = re.search(r'<style>(.*?)</style>', html, re.DOTALL)
    return m.group(1) if m else ""


def extract_scripts(html):
    return re.findall(r'<script[^>]*>(.*?)</script>', html, re.DOTALL)


def extract_head(html):
    m = re.search(r'<head>(.*?)</head>', html, re.DOTALL)
    return m.group(1) if m else ""


def security_errors(template, output):
    """Checks that hold regardless of what the content generator did."""
    errors = []

    t_csp, o_csp = CSP_RE.findall(template), CSP_RE.findall(output)
    if len(o_csp) != 1 or t_csp != o_csp:
        errors.append("Content-Security-Policy missing or different from the master template")

    if INLINE_HANDLER_RE.search(output):
        errors.append("Inline event handler attribute found (on*=)")

    bad_urls = sorted({u for u in ATTR_URL_RE.findall(output)
                       if not re.match(r"(https?://|#)", u.strip(), re.I)})
    if bad_urls:
        errors.append(f"Non-http(s) URLs in attributes ({len(bad_urls)}): {[u[:60] for u in bad_urls[:5]]}")

    for tag in DANGEROUS_TAGS:
        pattern = re.compile(r"<%s\b" % tag, re.I)
        t_n, o_n = len(pattern.findall(template)), len(pattern.findall(output))
        if o_n > t_n:
            errors.append(f"<{tag}> count {o_n} exceeds master template ({t_n})")

    t_ext, o_ext = set(EXTERNAL_RE.findall(template)), set(EXTERNAL_RE.findall(output))
    if o_ext - t_ext:
        errors.append(f"New external script/stylesheet sources: {sorted(o_ext - t_ext)}")
    return errors


def validate(output_path, template_path=None):
    errors = []
    if not os.path.exists(output_path):
        return False, [f"Output file not found: {output_path}"]
    with open(output_path, "r", encoding="utf-8") as f:
        output = f.read()
    template = load_template(template_path)

    missing = [m for m in REQUIRED_MARKERS if m not in output]
    if missing:
        errors.append(f"MISSING required markers ({len(missing)}):")
        for m in missing:
            errors.append(f"  - {m}")

    forbidden = [m for m in FORBIDDEN_MARKERS if m in output]
    if forbidden:
        errors.append(f"FORBIDDEN markers found ({len(forbidden)}) — wrong template:")
        for m in forbidden:
            errors.append(f"  - {m}")

    t_css, o_css = extract_style(template), extract_style(output)
    if t_css != o_css:
        if not t_css:
            errors.append("Master template has no <style> block")
        elif not o_css:
            errors.append("Output has no <style> block")
        else:
            for i in range(min(len(t_css), len(o_css))):
                if t_css[i] != o_css[i]:
                    s, e = max(0, i - 30), min(len(t_css), i + 30)
                    errors.append(f"CSS MISMATCH at char {i}:")
                    errors.append(f"  Template: ...{t_css[s:e]}...")
                    errors.append(f"  Output:   ...{o_css[s:e]}...")
                    break
            if len(t_css) != len(o_css):
                errors.append(f"CSS length: template={len(t_css)} output={len(o_css)}")

    t_scripts, o_scripts = extract_scripts(template), extract_scripts(output)
    if len(t_scripts) != len(o_scripts):
        errors.append(f"Script count: template={len(t_scripts)} output={len(o_scripts)}")
    else:
        for i, (ts, os_) in enumerate(zip(t_scripts, o_scripts)):
            if ts != os_:
                errors.append(f"Script {i} MISMATCH: template={len(ts)} output={len(os_)}")

    t_head, o_head = extract_head(template), extract_head(output)
    if not o_head:
        errors.append("Output has no <head> block")
    # The Three.js tag sits at the end of <body>, so search the whole document
    t_three = re.findall(r'<script src="[^"]*three\.min\.js[^"]*"[^>]*>', template)
    o_three = re.findall(r'<script src="[^"]*three\.min\.js[^"]*"[^>]*>', output)
    if len(t_three) != 1 or t_three != o_three:
        errors.append("Three.js script tag (src/integrity) differs from the master template")
    t_fonts = re.search(r'href="(.*?fonts.googleapis.com.*?)"', t_head)
    o_fonts = re.search(r'href="(.*?fonts.googleapis.com.*?)"', o_head)
    if t_fonts and o_fonts and t_fonts.group(1) != o_fonts.group(1):
        errors.append("Google Fonts URL mismatch")

    errors.extend(security_errors(template, output))
    return len(errors) == 0, errors


if __name__ == "__main__":
    args = sys.argv[1:]
    template_arg = None
    if "--template" in args:
        i = args.index("--template")
        if i + 1 >= len(args):
            print("Usage: python template_validator.py /path/to/output.html [--template PATH]")
            sys.exit(2)
        template_arg = args[i + 1]
        del args[i:i + 2]
    if len(args) != 1:
        print("Usage: python template_validator.py /path/to/output.html [--template PATH]")
        sys.exit(2)
    passed, errors = validate(args[0], template_arg)
    if passed:
        print("TEMPLATE VALIDATION: PASSED")
        print(f"All {len(REQUIRED_MARKERS)} required markers present")
        print("CSS block: byte-identical to master template")
        print("Script blocks: byte-identical to master template")
        print("Security: CSP intact, no inline handlers, http(s) links only, no injected tags")
        print("Output is safe to publish.")
        sys.exit(0)
    else:
        print("TEMPLATE VALIDATION: FAILED")
        print(f"{len(errors)} error(s) found:")
        for e in errors:
            print(f"  {e}")
        print("\nDO NOT PUBLISH THIS OUTPUT.")
        sys.exit(1)
