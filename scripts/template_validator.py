#!/usr/bin/env python3
"""
Strict Template Validator
==========================
Validates that an HTML file uses the EXACT approved template by:
1. Checking all 32 critical CSS/JS/structural markers
2. Comparing the <style> block byte-for-byte against the master template
3. Comparing all <script> blocks byte-for-byte against the master template
4. Verifying CSS variable names and values match exactly

Usage:
    python template_validator.py /path/to/output.html

Exit codes:
    0 = Valid (template matches)
    1 = Invalid (template does not match — DO NOT PUBLISH)
"""
import re, sys, os

TEMPLATE_PATH = "/workspace/notes/master_template.html"

REQUIRED_MARKERS = [
    "--bg:#070710", "--bg2:#0c0c18", "--accent:#7c3aed", "--accent2:#0891b2",
    "--accent3:#db2777", "--text:#edecf5", "--muted:#8389a3", "--dim:#4a4f64",
    "--surface:rgba(255,255,255,.025)", "--border:rgba(255,255,255,.06)",
    "--modal-bg:rgba(7,7,16,.95)", "--shadow:0 20px 60px rgba(0,0,0,.5)",
    'class="grid-bg"', 'class="kicker"', 'class="brief-list"', 'class="bento"',
    'class="concept-label"', 'class="noise"', 'class="aurora"', 'class="meta-row"',
    'class="subtitle"', 'class="wrap"', 'class="chips"', 'class="grid-cards"',
    'class="modal-card"', 'class="modal-why"', "tab-body", "bg-canvas",
    "three.min.js", "toggleTheme", ".spotlight::before", "blur(20px)",
    "@keyframes drift", "@keyframes fadeUp", "@keyframes blink",
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

def load_template():
    if os.path.exists(TEMPLATE_PATH):
        with open(TEMPLATE_PATH, "r") as f:
            return f.read()
    print(f"ERROR: Master template missing at {TEMPLATE_PATH}")
    print("Download from: https://raw.githubusercontent.com/Dilip457/ai-news-daily/main/master_template.html.gz.b64")
    sys.exit(2)

def extract_style(html):
    m = re.search(r'<style>(.*?)</style>', html, re.DOTALL)
    return m.group(1) if m else ""

def extract_scripts(html):
    return re.findall(r'<script[^>]*>(.*?)</script>', html, re.DOTALL)

def validate(output_path):
    errors = []
    if not os.path.exists(output_path):
        return False, [f"Output file not found: {output_path}"]
    with open(output_path, "r") as f:
        output = f.read()
    template = load_template()
    
    missing = [m for m in REQUIRED_MARKERS if m not in output]
    if missing:
        errors.append(f"MISSING required markers ({len(missing)}):")
        for m in missing: errors.append(f"  - {m}")
    
    forbidden = [m for m in FORBIDDEN_MARKERS if m in output]
    if forbidden:
        errors.append(f"FORBIDDEN markers found ({len(forbidden)}) — wrong template:")
        for m in forbidden: errors.append(f"  - {m}")
    
    t_css, o_css = extract_style(template), extract_style(output)
    if t_css != o_css:
        if not t_css: errors.append("Master template has no <style> block")
        elif not o_css: errors.append("Output has no <style> block")
        else:
            for i in range(min(len(t_css), len(o_css))):
                if t_css[i] != o_css[i]:
                    s, e = max(0,i-30), min(len(t_css),i+30)
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
            if ts != os_ and not (len(ts) == 0 and len(os_) == 0):
                errors.append(f"Script {i} MISMATCH: template={len(ts)} output={len(os_)}")
    
    t_head = re.search(r'<head>(.*?)</head>', template, re.DOTALL).group(1)
    o_head = re.search(r'<head>(.*?)</head>', output, re.DOTALL).group(1)
    t_three = re.search(r'<script src="(.*?three\.min\.js.*?)"', t_head)
    o_three = re.search(r'<script src="(.*?three\.min\.js.*?)"', o_head)
    if t_three and o_three and t_three.group(1) != o_three.group(1):
        errors.append(f"Three.js src mismatch")
    t_fonts = re.search(r'href="(.*?fonts.googleapis.com.*?)"', t_head)
    o_fonts = re.search(r'href="(.*?fonts.googleapis.com.*?)"', o_head)
    if t_fonts and o_fonts and t_fonts.group(1) != o_fonts.group(1):
        errors.append(f"Google Fonts URL mismatch")
    
    return len(errors) == 0, errors

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python template_validator.py /path/to/output.html")
        sys.exit(2)
    passed, errors = validate(sys.argv[1])
    if passed:
        print("TEMPLATE VALIDATION: PASSED")
        print("All 32 required markers present")
        print("CSS block: byte-identical to master template")
        print("Script blocks: byte-identical to master template")
        print("Output is safe to publish.")
        sys.exit(0)
    else:
        print("TEMPLATE VALIDATION: FAILED")
        print(f"{len(errors)} error(s) found:")
        for e in errors: print(f"  {e}")
        print("\nDO NOT PUBLISH THIS OUTPUT.")
        sys.exit(1)
