## Problem Description

- `gitnexus explain` returns **no taint layer** — requires `gitnexus analyze --pdg` (security audit gap).
- `gitnexus check --cycles` is not run in CI; stale index can report resolved import cycles after merges.

## Proposed Architectural Solution

1. Document in `CONTRIBUTING.md`: `./scripts/gitnexus-analyze-embeddings.sh` + `--pdg` for maintainer security audits.
2. Optional CI step: `npx gitnexus check --cycles` on `main` (non-blocking warning, or blocking once index is fresh).

## Estimated Impact

Basso — contributor DX and security review posture; no runtime daemon change.

## Files Involved

- `scripts/gitnexus-analyze-embeddings.sh`
- `.github/workflows/` (extend existing workflow)
- `CONTRIBUTING.md`

---

**Audit metadata**
- Source: GitNexus bug hunt 2026-06-23 (`docs/quality/GITHUB_BUG_BACKLOG.md`)
- Milestone: v1.9.12 — Code Perfection & Tech Debt

_Closes when merged with tests green (`make check`) and CHANGELOG updated per `06-auto-changelog.mdc`._
