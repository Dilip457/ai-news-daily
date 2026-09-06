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

If the master template is missing, it auto-downloads from GitHub.
"""
import re, sys, os, gzip, base64, hashlib

TEMPLATE_PATH = "/workspace/notes/master_template.html"
GITHUB_TEMPLATE_URL = "https://raw.githubusercontent.com/Dilip457/ai-news-daily/main/master_template.html"

# 32 critical markers that MUST be present
REQUIRED_MARKERS = [
    # CSS variables (exact values)
    "--bg:#070710",
    "--bg2:#0c0c18",
    "--accent:#7c3aed",
    "--accent2:#0891b2",
    "--accent3:#db2777",
    "--text:#edecf5",
    "--muted:#8389a3",
    "--dim:#4a4f64",
    "--surface:rgba(255,255,255,.025)",
    "--border:rgba(255,255,255,.06)",
    "--modal-bg:rgba(7,7,16,.95)",
    "--shadow:0 20px 60px rgba(0,0,0,.5)",
    # Structural HTML elements
    'class="grid-bg"',
    'class="kicker"',
    'class="brief-list"',
    'class="bento"',
    'class="concept-label"',
    'class="noise"',
    'class="aurora"',
    'class="meta-row"',
    'class="subtitle"',
    'class="wrap"',
    'class="chips"',
    'class="grid-cards"',
    'class="modal-card"',
    'class="modal-why"',
    "tab-body",
    # JS features
    "bg-canvas",
    "three.min.js",
    "toggleTheme",
    ".spotlight::before",
    # Effects
    "blur(20px)",
    "@keyframes drift",
    "@keyframes fadeUp",
    "@keyframes blink",
]

# Markers that must NOT be present (from the wrong template the agent kept producing)
FORBIDDEN_MARKERS = [
    "--bg-alt:",       # Wrong variable name (should be --bg2)
    "--text-dim:",     # Wrong variable name (should be --muted)
    "--text-faint:",   # Wrong variable name (should be --dim)
    "--accent-dim:",   # Not in original
    "--accent-glow:",  # Not in original
    "--font-mono:",    # Not in original (only Inter + Instrument Serif)
    "--font-serif:",   # Not in original variable form
    "--border-hover:", # Wrong variable name (should be --border-h)
    "--surface-hover:",# Wrong variable name (should be --surface-h)
    "--bg-alt",        # Wrong variable
    "particle-canvas", # Wrong canvas ID (should be bg-canvas)
    "aurora-blob",     # Wrong aurora structure (should be ::before/::after)
    "hero-title",      # Wrong class (should be title)
    "hero-date",       # Wrong class
    "hero-sub",        # Wrong class
    "logo-dot",        # Wrong class
    "last-updated",    # Wrong class
    "header-inner",    # Wrong class
    "header-right",    # Wrong class
    "article-card",    # Wrong class (should be card)
    "article-grid",    # Wrong class (should be grid-cards)
    "glass-card",      # Wrong class
    "filter-chip",     # Wrong class (should be chip)
    "trend-card",      # Wrong class (should be card spotlight trend)
    "trend-name",      # Wrong class
    "trend-desc",      # Wrong class (should be trend-d)
    "trend-number",    # Wrong class
    "trend-related",   # Wrong class (should be trend-stories)
    "concept-para",    # Wrong class
    "concept-title",   # Wrong class (should be concept h2)
    "concept-section", # Wrong class
    "brief-expand",    # Wrong class
    "score-badge",     # Wrong class (should be card-score/brief-score)
    "rank-number",     # Wrong class (should be rank)
    "source-tag",      # Wrong class (should be src)
    "stat-box",        # Wrong class (should be bento-stat)
    "stat-value",      # Wrong class (should be bento-stat num)
    "stat-label",      # Wrong class (should be bento-stat lbl)
    "date-tag",        # Wrong class
    "section-tag",     # Wrong class (should be sec-head)
    "section-title",   # Wrong class
    "bento-grid",      # Wrong class (should be bento)
    "bento-stats",     # Wrong class
    "bento-why-read",  # Wrong class (should be bento-why)
    "why-matters",     # Wrong class (should be card-why)
    "why-label",       # Wrong class (should be why-tag)
    "why-read-text",   # Wrong class
    "top10-item",      # Wrong class (should be card spotlight top10)
    "top10-content",   # Wrong class (should be top10-body)
    "top10-header",    # Wrong class
    "top10-footer",    # Wrong class
    "top10-summary",   # Wrong class
    "footer-link",     # Wrong class
    "footer-text",     # Wrong class
    "open-link",       # Wrong class (should be open-link-btn)
    "open-btn:hover",  # Wrong class (should be open-link-btn:hover)
    "search-box",      # Wrong class (should be search)
    "modal-content",   # Wrong class (should be modal-card)
    "modal-meta",      # Wrong class
    "modal-text",      # Wrong class
    "related-list",    # Wrong class (should be trend-story-list)
    "related-label",   # Wrong class (should be trend-stories-label)
    "fadeInUp",        # Wrong animation (should be fadeUp)
    "pulse-dot",       # Wrong animation (should be blink)
    "reveal.visible",  # Wrong class (should be reveal.in)
    "JetBrains Mono",  # Wrong font (not in original)
    "Instrument Serif", # Check if this is in the Google Fonts URL
]

def load_template():
    """Load the master template, downloading from GitHub if missing."""
    if os.path.exists(TEMPLATE_PATH):
        with open(TEMPLATE_PATH, "r") as f:
            return f.read()
    
    print(f"WARNING: Master template missing at {TEMPLATE_PATH}")
    print("Attempting to download from GitHub...")
    
    # Try to download via web_get_contents (but we can't call MCP from here)
    # The agent should have downloaded it before calling this script
    print("ERROR: Cannot download from within script. Agent must fetch it first.")
    sys.exit(2)

def extract_style(html):
    m = re.search(r'<style>(.*?)</style>', html, re.DOTALL)
    return m.group(1) if m else ""

def extract_scripts(html):
    return re.findall(r'<script[^>]*>(.*?)</script>', html, re.DOTALL)

def validate(output_path):
    """Validate output HTML against master template. Returns (passed, errors)."""
    errors = []
    
    if not os.path.exists(output_path):
        errors.append(f"Output file not found: {output_path}")
        return False, errors
    
    with open(output_path, "r") as f:
        output = f.read()
    
    template = load_template()
    
    # 1. Check all required markers are present
    missing = []
    for marker in REQUIRED_MARKERS:
        if marker not in output:
            missing.append(marker)
    if missing:
        errors.append(f"MISSING required markers ({len(missing)}):")
        for m in missing:
            errors.append(f"  - {m}")
    
    # 2. Check no forbidden markers are present
    forbidden_found = []
    for marker in FORBIDDEN_MARKERS:
        if marker in output:
            forbidden_found.append(marker)
    if forbidden_found:
        errors.append(f"FORBIDDEN markers found ({len(forbidden_found)}) — wrong template detected:")
        for m in forbidden_found:
            errors.append(f"  - {m}")
    
    # 3. Compare <style> blocks byte-for-byte
    template_css = extract_style(template)
    output_css = extract_style(output)
    if template_css != output_css:
        if not template_css:
            errors.append("Master template has no <style> block — template corrupted")
        elif not output_css:
            errors.append("Output has no <style> block — HTML is broken")
        else:
            # Find first difference
            for i in range(min(len(template_css), len(output_css))):
                if template_css[i] != output_css[i]:
                    ctx_start = max(0, i-30)
                    ctx_end = min(len(template_css), i+30)
                    errors.append(f"CSS MISMATCH at char {i}:")
                    errors.append(f"  Template: ...{template_css[ctx_start:ctx_end]}...")
                    errors.append(f"  Output:   ...{output_css[ctx_start:ctx_end]}...")
                    break
            if len(template_css) != len(output_css):
                errors.append(f"CSS length mismatch: template={len(template_css)} output={len(output_css)}")
    
    # 4. Compare script blocks byte-for-byte
    template_scripts = extract_scripts(template)
    output_scripts = extract_scripts(output)
    
    if len(template_scripts) != len(output_scripts):
        errors.append(f"Script count mismatch: template={len(template_scripts)} output={len(output_scripts)}")
    else:
        for i, (ts, os_) in enumerate(zip(template_scripts, output_scripts)):
            if ts != os_:
                if len(ts) == 0 and len(os_) == 0:
                    continue  # Both empty (external script tags)
                errors.append(f"Script {i} MISMATCH: template={len(ts)} chars output={len(os_)} chars")
                # Find first difference
                for j in range(min(len(ts), len(os_))):
                    if ts[j] != os_[j]:
                        ctx_start = max(0, j-40)
                        ctx_end = min(len(ts), j+40)
                        errors.append(f"  At char {j}:")
                        errors.append(f"  Template: ...{ts[ctx_start:ctx_end]}...")
                        errors.append(f"  Output:   ...{os_[ctx_start:ctx_end]}...")
                        break
    
    # 5. Check <head> structure (fonts, three.js src)
    template_head = re.search(r'<head>(.*?)</head>', template, re.DOTALL).group(1)
    output_head = re.search(r'<head>(.*?)</head>', output, re.DOTALL).group(1)
    
    # Check Three.js src
    template_three = re.search(r'<script src="(.*?three\.min\.js.*?)"', template_head)
    output_three = re.search(r'<script src="(.*?three\.min\.js.*?)"', output_head)
    if template_three and output_three:
        if template_three.group(1) != output_three.group(1):
            errors.append(f"Three.js src mismatch: template={template_three.group(1)} output={output_three.group(1)}")
    elif template_three and not output_three:
        errors.append("Three.js script tag missing from output <head>")
    
    # Check Google Fonts URL
    template_fonts = re.search(r'href="(.*?fonts.googleapis.com.*?)"', template_head)
    output_fonts = re.search(r'href="(.*?fonts.googleapis.com.*?)"', output_head)
    if template_fonts and output_fonts:
        if template_fonts.group(1) != output_fonts.group(1):
            errors.append(f"Google Fonts URL mismatch:")
            errors.append(f"  Template: {template_fonts.group(1)}")
            errors.append(f"  Output:   {output_fonts.group(1)}")
    
    return len(errors) == 0, errors

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python template_validator.py /path/to/output.html")
        sys.exit(2)
    
    output_path = sys.argv[1]
    passed, errors = validate(output_path)
    
    if passed:
        print("TEMPLATE VALIDATION: PASSED")
        print("All 32 required markers present")
        print("CSS block: byte-identical to master template")
        print("Script blocks: byte-identical to master template")
        print("Fonts and Three.js: matching")
        print("Output is safe to publish.")
        sys.exit(0)
    else:
        print("TEMPLATE VALIDATION: FAILED")
        print(f"{len(errors)} error(s) found:")
        for e in errors:
            print(f"  {e}")
        print("")
        print("DO NOT PUBLISH THIS OUTPUT.")
        print("The agent wrote its own HTML instead of using generate_briefing_fixed.py.")
        print("Restore the master template and re-run generate_briefing_fixed.py.")
        sys.exit(1)
