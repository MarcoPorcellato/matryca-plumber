# Strict Read Only end-to-end immutability gate

**Status:** `PASS` for the deterministic source-tree qualification merged in
[#364](https://github.com/MarcoPorcellato/matryca-plumber/pull/364). The merge gate
also completed full CI with 1,559 passed, 2 skipped, and 1 expected failure.
This is source-level evidence; exact installed-wheel/default-on qualification
remains a separate Gate A requirement.

This release gate proves that `MATRYCA_READ_ONLY=true` leaves the complete Logseq graph
tree unchanged while public read surfaces and the external Shadow observer remain usable.
It complements, and does not replace, the exact-wheel Shadow soak.

## Run

```bash
uv run python scripts/qualify_read_only_immutability.py \
  --output /tmp/matryca-read-only-immutability.json
```

The command exits zero only when the dedicated integration qualification passes and emits
deterministic JSON with `status: PASS`. Paths, timestamps, note bodies, and other private graph
content are not included.

## Covered contract

- The baseline manifest records every relative entry, type, file-content SHA-256, POSIX mode,
  size, and symlink target without following symlinks. Directory timestamps are intentionally
  excluded because they are unstable and do not describe durable graph content.
- CLI and MCP reads run successfully. Every public CLI/MCP mutator is rejected before its
  dispatcher, while explicitly dry-run operations remain available.
- UI state startup and the foreground read-only Shadow observer start without graph-local PID,
  lock, state, log, hook, cache, or Git writes. Detached startup fails closed.
- Shadow data, WAL/SHM files, writer locks, and operational logs may change only below the
  validated external cache/log roots.
- Hidden files, pre-existing lock/temp files, Git metadata, executable hooks, an escaping
  symlink, and an external target are byte-for-byte represented or checked.
- A cache symlink resolving back into the graph is rejected, and unset read-only mode retains
  its existing writable policy.

The final graph manifest must equal the baseline exactly. Any missing, added, modified,
retyped, retargeted, or mode-changed entry makes the gate fail.
