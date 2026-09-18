#!/usr/bin/env python3
"""
AI News Daily — Self-Healing Bootstrap
=======================================
Run this FIRST on every pipeline run. It rebuilds /workspace/notes/ from the
GitHub repo (the source of truth), so a wiped workspace can never stop the
daily pipeline.

Usage: python3 bootstrap.py
Exit 0 = ready. Exit 1 = broken (pipeline must alert, not proceed blindly).
"""
import base64
import gzip
import hashlib
import json
import os
import sys
import urllib.request

REPO_RAW = "https://raw.githubusercontent.com/Dilip457/ai-news-daily/main"
NOTES = "/workspace/notes"

SCRIPTS = [
    "generate_briefing_fixed.py",
    "template_validator.py",
    "telegram_deliver.py",
    "pipeline_validator.py",
    "bootstrap.py",
]

TEMPLATE_MARKERS = [
    "--bg:#070710",
    "--accent:#7c3aed",
    "bg-canvas",
    'class="kicker"',
    "three.min.js",
    "Inter",
    "Instrument Serif",
]


def fetch(url, binary=False):
    req = urllib.request.Request(url, headers={"User-Agent": "ai-news-bootstrap"})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = r.read()
    return data if binary else data.decode("utf-8")


def sha256(data):
    if isinstance(data, str):
        data = data.encode()
    return hashlib.sha256(data).hexdigest()


def main():
    os.makedirs(NOTES, exist_ok=True)
    failures = []

    # --- 1. Fetch checksum manifest ---
    try:
        manifest = json.loads(fetch(f"{REPO_RAW}/scripts/checksums.json"))
    except Exception as e:
        print(f"FATAL: cannot fetch checksums.json: {e}")
        sys.exit(1)

    # --- 2. Download + verify pipeline scripts ---
    for name in SCRIPTS:
        expected = manifest.get(name)
        try:
            content = fetch(f"{REPO_RAW}/scripts/{name}")
            if expected and sha256(content) != expected:
                failures.append(f"{name}: checksum mismatch (expected {expected[:12]}...)")
                continue
            path = os.path.join(NOTES, name)
            with open(path, "w") as f:
                f.write(content)
            print(f"OK  scripts/{name} ({len(content):,} bytes)")
        except Exception as e:
            failures.append(f"{name}: {e}")

    # --- 3. Download + verify master template ---
    # The backup on GitHub may be raw gzip (despite the .b64 name) or real
    # base64 text. Handle both, verify markers, write the decompressed HTML.
    try:
        raw = fetch(f"{REPO_RAW}/master_template.html.gz.b64", binary=True)
        html = None
        # Try 1: raw gzip binary
        try:
            html = gzip.decompress(raw)
        except Exception:
            pass
        # Try 2: base64 text -> gzip
        if html is None:
            try:
                html = gzip.decompress(base64.b64decode(raw, validate=False))
            except Exception:
                pass
        # Try 3: plain text
        if html is None:
            try:
                html = raw
            except Exception:
                pass
        if html is None:
            failures.append("master_template: undecodable backup")
        else:
            if isinstance(html, bytes):
                html = html.decode("utf-8", errors="replace")
            missing = [m for m in TEMPLATE_MARKERS if m not in html]
            if missing:
                failures.append(f"master_template: missing markers {missing}")
            else:
                expected = manifest.get("master_template.html")
                if expected and sha256(html) != expected:
                    failures.append("master_template: checksum mismatch")
                else:
                    with open(os.path.join(NOTES, "master_template.html"), "w") as f:
                        f.write(html)
                    print(f"OK  master_template.html ({len(html):,} bytes, markers verified)")
    except Exception as e:
        failures.append(f"master_template: {e}")

    # --- 4. Delivery log (empty default if absent) ---
    log_path = os.path.join(NOTES, "telegram_delivery_log.json")
    if not os.path.exists(log_path):
        try:
            log = fetch(f"{REPO_RAW}/telegram_delivery_log.json")
            with open(log_path, "w") as f:
                f.write(log)
            print("OK  telegram_delivery_log.json (from repo)")
        except Exception:
            with open(log_path, "w") as f:
                json.dump({"sent": []}, f)
            print("OK  telegram_delivery_log.json (fresh)")

    # --- Verdict ---
    if failures:
        print("\nBOOTSTRAP FAILED:")
        for f_ in failures:
            print(f"  - {f_}")
        sys.exit(1)
    print(f"\nBOOTSTRAP READY — {NOTES} fully restored and verified.")


if __name__ == "__main__":
    main()
