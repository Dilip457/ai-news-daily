# Pipeline run notes

Append-only log of pipeline incidents and the workarounds adopted. Read this before
touching the publish step.

## 2026-10-31 — GITHUB_CREATE_A_TREE collapsed the repository tree

**What happened.** The chunked publish built 4 verified blobs (all SHA-matched) and then
called `GITHUB_CREATE_A_TREE` with `base_tree` set to the current main tree plus 4 blob
entries. The returned tree contained only `workflows/deploy.yml` — every other file
(scripts, template, index.html, updates/, delivery log) was dropped from the tree, and
the ref update to that commit briefly emptied main.

**Recovery.** Re-created a commit whose `tree` was the known-good tree SHA from the
preceding commit (67 paths) with the broken commit as parent, then fast-forwarded main.
No history rewrite and no force push was needed. The full tree was verified before
proceeding.

**Workaround now in use.** Do not use `GITHUB_CREATE_A_TREE` for the publish step.
Instead:

1. `GITHUB_CREATE_A_BLOB` for each of `data.gz.b64.part1..4`, verifying each returned
   SHA against the locally computed `sha1("blob <len>\0" + content)`.
2. `GITHUB_CREATE_OR_UPDATE_FILE_CONTENTS` to write each part to its path. This path is
   proven safe — it preserves the rest of the tree.
3. `GITHUB_CREATE_A_WORKFLOW_DISPATCH_EVENT` on `deploy.yml` only if the push-triggered
   run did not fire. Note that pushing the parts already triggers `deploy.yml` (its
   trigger is `push` on `data.gz.b64.part*`), so an extra dispatch usually produces a
   redundant run that fails harmlessly because the parts are already cleaned up.
4. Verify by reading the tree of `main` — expect 68 paths, no `data.gz.b64.part*`
   remaining, `index.html` present, and `updates/<DATE>.html` present.

**Always verify the tree after any tree/commit write.** A tree write that silently drops
entries is indistinguishable from success at the API level.

## Environment note

`/workspace` is not writable in this sandbox. The bootstrap and generator scripts
hardcode `/workspace/notes/...` paths, so after downloading them, rewrite those paths to
`/scratch/work/notes/...` (`bootstrap.py`, `generate_briefing_fixed.py`,
`template_validator.py`, `telegram_deliver.py`, `pipeline_validator.py`) before running.
