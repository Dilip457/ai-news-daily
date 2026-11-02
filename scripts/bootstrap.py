#!/usr/bin/env python3
"""
AI News Daily — Self-Healing Bootstrap
=======================================
Run this FIRST on every pipeline run. It rebuilds $AI_NEWS_HOME from the
GitHub repo (the source of truth), so a wiped workspace can never stop the
daily pipeline.

Environment:
  AI_NEWS_HOME  where scripts + template are written (default /scratch/work/notes)
  AI_NEWS_REF   git ref to fetch scripts/template from (default main).
                Pin this to a reviewed commit SHA so a bad push to main cannot
                change what the pipeline executes. The delivery log is always
                read from main because it changes every day.

Every pipeline file must be listed in scripts/checksums.json and match its
SHA-256; anything unlisted or mismatched fails the bootstrap.

Usage: python3 bootstrap.py
Exit 0 = ready. Exit 1 = broken (pipeline must alert, not proceed blindly).
"""
import base64
import gzip
import hashlib
import json
import os
import re
import sys
import urllib.request

REPO = "Dilip457/ai-news-daily"
NOTES = os.environ.get("AI_NEWS_HOME", "/scratch/work/notes")
REF = os.environ.get("AI_NEWS_REF", "main").strip()
MAX_DOWNLOAD = 2 * 1024 * 1024
MAX_TEMPLATE = 1024 * 1024

SCRIPTS = [
    "generate_briefing_fixed.py",
    "template_validator.py",
    "telegram_deliver.py",
    "pipeline_validator.py",
    "prepare_publish.py",
    "bootstrap.py",
]

TEMPLATE_MARKERS = [
    "--bg:#070710",
    "--bg2:#0c0c18",
    "--accent:#7c3aed",
    "--accent2:#0891b2",
    "--accent3:#db2777",
    "--text:#edecf5",
    "bg-canvas",
    'class="kicker"',
    'class="brief-list"',
    'class="bento"',
    "three.min.js",
    "Inter",
    'http-equiv="Content-Security-Policy"',
]


def raw_url(ref, path):
    return f"https://raw.githubusercontent.com/{REPO}/{ref}/{path}"


def fetch(url, binary=False, limit=MAX_DOWNLOAD):
    req = urllib.request.Request(url, headers={"User-Agent": "ai-news-bootstrap"})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = r.read(limit + 1)
    if len(data) > limit:
        raise ValueError(f"download exceeds {limit} bytes")
    return data if binary else data.decode("utf-8")


def sha256(data):
    if isinstance(data, str):
        data = data.encode()
    return hashlib.sha256(data).hexdigest()


def write_file(name, content):
    path = os.path.join(NOTES, name)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="") as f:
        f.write(content)
    os.replace(tmp, path)


def decode_template(raw):
    """The backup may be raw gzip (despite the .b64 name), base64 gzip, or plain HTML."""
    try:
        return gzip.decompress(raw)
    except (OSError, EOFError):
        pass
    try:
        return gzip.decompress(base64.b64decode(raw, validate=False))
    except (OSError, EOFError, ValueError):
        pass
    return raw


def main():
    if not re.match(r"^[A-Za-z0-9._/-]{1,100}$", REF) or ".." in REF:
        print(f"FATAL: invalid AI_NEWS_REF {REF!r}")
        sys.exit(1)
    os.makedirs(NOTES, exist_ok=True)
    failures = []
    print(f"Bootstrapping from {REPO}@{REF} into {NOTES}")

    # --- 1. Fetch checksum manifest ---
    try:
        manifest = json.loads(fetch(raw_url(REF, "scripts/checksums.json")))
        if not isinstance(manifest, dict):
            raise ValueError("manifest is not an object")
    except Exception as e:
        print(f"FATAL: cannot fetch checksums.json: {e}")
        sys.exit(1)

    # --- 2. Download + verify pipeline scripts (every file MUST be in the manifest) ---
    for name in SCRIPTS:
        expected = manifest.get(name)
        if not expected:
            failures.append(f"{name}: not listed in checksums.json")
            continue
        try:
            content = fetch(raw_url(REF, f"scripts/{name}"))
            if sha256(content) != expected:
                failures.append(f"{name}: checksum mismatch (expected {expected[:12]}...)")
                continue
            write_file(name, content)
            print(f"OK  scripts/{name} ({len(content):,} bytes)")
        except Exception as e:
            failures.append(f"{name}: {e}")

    # --- 3. Download + verify master template ---
    expected = manifest.get("master_template.html")
    try:
        if not expected:
            raise ValueError("not listed in checksums.json")
        html = decode_template(fetch(raw_url(REF, "master_template.html.gz.b64"), binary=True))
        if len(html) > MAX_TEMPLATE:
            raise ValueError("decoded template too large")
        html = html.decode("utf-8")
        missing = [m for m in TEMPLATE_MARKERS if m not in html]
        if missing:
            failures.append(f"master_template: missing markers {missing}")
        elif sha256(html) != expected:
            failures.append("master_template: checksum mismatch")
        else:
            write_file("master_template.html", html)
            print(f"OK  master_template.html ({len(html):,} bytes, markers + checksum verified)")
    except Exception as e:
        failures.append(f"master_template: {e}")

    # --- 4. Delivery log: always refresh from main so a stale local copy can't cause a double send ---
    try:
        log = json.loads(fetch(raw_url("main", "telegram_delivery_log.json")))
        if not isinstance(log, dict) or not isinstance(log.get("sent"), list):
            raise ValueError("unexpected format")
        write_file("telegram_delivery_log.json", json.dumps(log, indent=2) + "\n")
        print(f"OK  telegram_delivery_log.json (from repo, {len(log['sent'])} entries)")
    except Exception as e:
        if os.path.exists(os.path.join(NOTES, "telegram_delivery_log.json")):
            print(f"WARN telegram_delivery_log.json: repo fetch failed ({e}); keeping local copy")
        else:
            failures.append(f"telegram_delivery_log.json: {e} (refusing to start with an empty log)")

    # --- Verdict ---
    if failures:
        print("\nBOOTSTRAP FAILED:")
        for f_ in failures:
            print(f"  - {f_}")
        sys.exit(1)
    print(f"\nBOOTSTRAP READY — {NOTES} fully restored and verified.")


if __name__ == "__main__":
    main()
