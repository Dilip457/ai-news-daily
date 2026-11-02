#!/usr/bin/env python3
"""
Prepare the chunked publish of a validated briefing.

Usage:
    python3 prepare_publish.py /scratch/work/ai-news-YYYY-MM-DD.html YYYY-MM-DD

Writes to $AI_NEWS_WORK (default /scratch/work):
    data.gz.b64.part1..4   gzip+base64 of the HTML, split into 4 parts
    data.manifest.json     date + SHA-256 of the HTML and of every part

Prints JSON with each part's git blob SHA-1 so the agent can verify the SHA
returned by GITHUB_CREATE_A_BLOB. Push the 4 parts first and data.manifest.json
LAST: pushing the manifest is what triggers deploy.yml, and the deploy gate
re-verifies every hash and re-runs the template validator before going live.
"""
import base64
import gzip
import hashlib
import json
import os
import re
import sys

PARTS = 4
AI_NEWS_WORK = os.environ.get("AI_NEWS_WORK", "/scratch/work")


def git_blob_sha1(data):
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def main():
    if len(sys.argv) != 3 or not re.match(r"^\d{4}-\d{2}-\d{2}$", sys.argv[2]):
        print(__doc__)
        sys.exit(2)
    html_path, date_str = sys.argv[1], sys.argv[2]
    with open(html_path, "rb") as f:
        html = f.read()
    if f"<title>AI News Daily — {date_str}</title>".encode() not in html:
        print(f"ERROR: {html_path} is not the briefing for {date_str} (title mismatch)")
        sys.exit(1)

    encoded = base64.b64encode(gzip.compress(html, 9, mtime=0))
    size = -(-len(encoded) // PARTS)
    chunks = [encoded[i * size:(i + 1) * size] for i in range(PARTS)]

    os.makedirs(AI_NEWS_WORK, exist_ok=True)
    manifest = {
        "date": date_str,
        "html_sha256": hashlib.sha256(html).hexdigest(),
        "html_bytes": len(html),
        "parts": [],
    }
    report = []
    for i, chunk in enumerate(chunks, 1):
        name = f"data.gz.b64.part{i}"
        with open(os.path.join(AI_NEWS_WORK, name), "wb") as f:
            f.write(chunk)
        manifest["parts"].append({"path": name, "sha256": hashlib.sha256(chunk).hexdigest()})
        report.append({"path": name, "local_file": os.path.join(AI_NEWS_WORK, name),
                       "bytes": len(chunk), "git_blob_sha1": git_blob_sha1(chunk)})

    manifest_bytes = (json.dumps(manifest, indent=2) + "\n").encode()
    manifest_path = os.path.join(AI_NEWS_WORK, "data.manifest.json")
    with open(manifest_path, "wb") as f:
        f.write(manifest_bytes)
    report.append({"path": "data.manifest.json", "local_file": manifest_path,
                   "bytes": len(manifest_bytes), "git_blob_sha1": git_blob_sha1(manifest_bytes),
                   "push_last": True})
    print(json.dumps({"date": date_str, "files": report}, indent=2))


if __name__ == "__main__":
    main()
