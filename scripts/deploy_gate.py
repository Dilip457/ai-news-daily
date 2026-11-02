#!/usr/bin/env python3
"""
Deploy gate — runs inside GitHub Actions (deploy.yml) before anything goes live.

Usage (from the repo root):
    python3 scripts/deploy_gate.py OUTPUT_HTML

Checks, in order, failing closed on the first problem:
  1. data.manifest.json is well-formed (date, 4 parts with fixed names, hashes)
  2. every part matches its SHA-256 in the manifest
  3. the joined parts are strict base64 and gunzip within a size cap (no zip bombs)
  4. the HTML matches html_sha256 and its <title> carries the manifest date
  5. the master template matches scripts/checksums.json
  6. template_validator passes (byte-identical CSS/JS, CSP, no injected tags/handlers/URLs)

On success writes OUTPUT_HTML and prints date=YYYY-MM-DD (also to $GITHUB_OUTPUT).
"""
import base64
import binascii
import gzip
import hashlib
import json
import os
import re
import sys
import tempfile
import zlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import template_validator  # noqa: E402

PART_NAMES = [f"data.gz.b64.part{i}" for i in range(1, 5)]
MAX_ENCODED = 4 * 1024 * 1024
MAX_HTML = 3 * 1024 * 1024
HEX64 = re.compile(r"^[0-9a-f]{64}$")


class GateError(Exception):
    pass


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def gunzip_capped(data, limit):
    d = zlib.decompressobj(16 + zlib.MAX_WBITS)
    out = d.decompress(data, limit + 1)
    if len(out) > limit or d.unconsumed_tail:
        raise GateError(f"decompressed HTML exceeds {limit} bytes")
    if not d.eof:
        raise GateError("truncated gzip stream")
    if d.unused_data:
        raise GateError("trailing data after gzip stream")
    return out


def load_manifest(root):
    path = os.path.join(root, "data.manifest.json")
    if os.path.getsize(path) > 10_000:
        raise GateError("manifest too large")
    with open(path, encoding="utf-8") as f:
        m = json.load(f)
    if not isinstance(m, dict) or not re.match(r"^\d{4}-\d{2}-\d{2}$", str(m.get("date", ""))):
        raise GateError("manifest: bad date")
    if not HEX64.match(str(m.get("html_sha256", ""))):
        raise GateError("manifest: bad html_sha256")
    parts = m.get("parts")
    if not isinstance(parts, list) or [p.get("path") for p in parts if isinstance(p, dict)] != PART_NAMES:
        raise GateError(f"manifest: parts must be exactly {PART_NAMES}")
    if not all(HEX64.match(str(p.get("sha256", ""))) for p in parts):
        raise GateError("manifest: bad part sha256")
    return m


def assemble(root, manifest):
    encoded = b""
    for part in manifest["parts"]:
        with open(os.path.join(root, part["path"]), "rb") as f:
            data = f.read(MAX_ENCODED + 1)
        if sha256(data) != part["sha256"]:
            raise GateError(f"{part['path']}: sha256 mismatch (stale or corrupted part)")
        encoded += data
        if len(encoded) > MAX_ENCODED:
            raise GateError("encoded payload too large")
    try:
        compressed = base64.b64decode(encoded, validate=True)
    except binascii.Error as e:
        raise GateError(f"invalid base64: {e}")
    html = gunzip_capped(compressed, MAX_HTML)
    if sha256(html) != manifest["html_sha256"]:
        raise GateError("assembled HTML does not match html_sha256")
    title = f"<title>AI News Daily — {manifest['date']}</title>".encode()
    if title not in html:
        raise GateError("HTML <title> does not carry the manifest date")
    return html


def load_verified_template(root):
    with open(os.path.join(root, "scripts", "checksums.json"), encoding="utf-8") as f:
        expected = json.load(f).get("master_template.html")
    with open(os.path.join(root, "master_template.html.gz.b64"), "rb") as f:
        template = gzip.decompress(f.read())
    if not expected or sha256(template) != expected:
        raise GateError("master template does not match scripts/checksums.json")
    return template


def run(root, output_path):
    manifest = load_manifest(root)
    html = assemble(root, manifest)
    template = load_verified_template(root)
    with tempfile.TemporaryDirectory() as tmp:
        t_path = os.path.join(tmp, "master_template.html")
        o_path = os.path.join(tmp, "out.html")
        with open(t_path, "wb") as f:
            f.write(template)
        with open(o_path, "wb") as f:
            f.write(html)
        passed, errors = template_validator.validate(o_path, t_path)
    if not passed:
        raise GateError("template validation failed:\n  " + "\n  ".join(errors))
    with open(output_path, "wb") as f:
        f.write(html)
    return manifest["date"]


def main():
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    try:
        date_str = run(os.getcwd(), sys.argv[1])
    except (GateError, OSError, ValueError) as e:
        print(f"DEPLOY GATE: REJECTED — {e}")
        sys.exit(1)
    print(f"DEPLOY GATE: PASSED for {date_str}")
    print(f"date={date_str}")
    gh_out = os.environ.get("GITHUB_OUTPUT")
    if gh_out:
        with open(gh_out, "a", encoding="utf-8") as f:
            f.write(f"date={date_str}\n")


if __name__ == "__main__":
    main()
