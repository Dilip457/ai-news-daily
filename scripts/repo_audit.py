#!/usr/bin/env python3
"""
Repo audit — run by .github/workflows/checks.yml on every push and pull request.

  1. Every file in scripts/checksums.json matches its SHA-256 (bootstrap would
     otherwise refuse to start the next run).
  2. No credentials are committed: Telegram bot tokens, GitHub tokens, AWS keys,
     private keys. Matches are reported redacted.

Usage (from the repo root): python3 scripts/repo_audit.py
Exit 0 = clean, 1 = problems found.
"""
import gzip
import hashlib
import json
import os
import re
import subprocess
import sys

SECRET_PATTERNS = {
    "Telegram bot token": re.compile(rb"\b\d{8,10}:[A-Za-z0-9_-]{35}\b"),
    "GitHub token": re.compile(rb"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{36}\b|\bgithub_pat_[A-Za-z0-9_]{60,}\b"),
    "AWS access key": re.compile(rb"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"),
    "Private key": re.compile(rb"-----BEGIN (?:[A-Z]+ )?PRIVATE KEY-----"),
}


def tracked_files():
    out = subprocess.run(["git", "ls-files", "-z"], capture_output=True, check=True).stdout
    return [p.decode() for p in out.split(b"\0") if p]


def check_checksums():
    problems = []
    with open("scripts/checksums.json", encoding="utf-8") as f:
        manifest = json.load(f)
    for name, expected in manifest.items():
        if name == "master_template.html":
            with open("master_template.html.gz.b64", "rb") as f:
                data = gzip.decompress(f.read())
        else:
            path = os.path.join("scripts", name)
            if not os.path.exists(path):
                problems.append(f"checksums.json lists missing file scripts/{name}")
                continue
            with open(path, "rb") as f:
                data = f.read()
        if hashlib.sha256(data).hexdigest() != expected:
            problems.append(f"checksum mismatch: {name} (update scripts/checksums.json)")
    return problems


def check_secrets():
    problems = []
    for path in tracked_files():
        try:
            with open(path, "rb") as f:
                data = f.read()
        except OSError:
            continue
        for label, pattern in SECRET_PATTERNS.items():
            for m in pattern.finditer(data):
                line = data.count(b"\n", 0, m.start()) + 1
                token = m.group(0).decode(errors="replace")
                problems.append(f"{label} in {path}:{line}: {token[:4]}…{token[-2:]} (redacted)")
    return problems


def main():
    problems = check_checksums() + check_secrets()
    if problems:
        print("REPO AUDIT: FAILED")
        for p in problems:
            print("  - " + p)
        sys.exit(1)
    print("REPO AUDIT: PASSED (checksums verified, no credentials found)")


if __name__ == "__main__":
    main()
