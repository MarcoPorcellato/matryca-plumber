---
description: GitHub issue/PR/milestone standards for Matryca Plumber (OSS maintainer rigor)
alwaysApply: false
---

# GitHub Workflow Standards (Matryca Plumber)

When creating, updating, or closing GitHub issues, pull requests, milestones, or releases, follow these **official GitHub best practices** so the repository maintains authoritative project management.

**Rule routing:** Complements `05-release-preparation.mdc` (semver releases), `06-auto-changelog.mdc` (user-visible bullets), and the user rule for `gh pr create`.

## Issue taxonomy

### Title format

Use a **category prefix** + concise description + optional audit marker:

```text
[Security] Path traversal on read in link verification [v1.9.x Audit #01]
[Bug] Hub pages written without OCC or page_rmw_lock
[Performance] AST cache full-reload on delete or parser failure
[Tech Debt] Centralize _env_bool / _env_int (8+ duplicates)
```

- Prefix must match the primary label category.
- Audit-track issues include `[v1.9.x Audit #NN]` for idempotent bulk scripts.

### Body structure (mandatory sections)

Every substantive issue body MUST use these headers (in order):

```markdown
## Problem Description
## Proposed Architectural Solution
## Estimated Impact
## Files Involved
```

Add metadata footer when from audit or epic:

```markdown
---
**Audit metadata** / **Epic link**
_Closes when merged with tests green (`make check`) and CHANGELOG updated._
```

### Labels (semantic, lowercase)

| Label | When to use |
|-------|-------------|
| `security` | Sandbox, auth, secret handling, SSRF |
| `bug` | Incorrect behavior, race, data loss |
| `performance` | I/O, memory, latency |
| `tech-debt` | Refactor, DRY, typing, module split |
| `v1.9.x` | Pre-v2.0 perfection track |
| `v2.0` | Shadow DB / Safe-Sync epic |
| `v2-prep` | Phase 0–1: prerequisites, GraphRepository ports |
| `v2-alpha` | Phase 2–3: shadow sync, read routing flag |
| `v2-memory` | Biological memory layer |
| `v2-safesync` | Logseq DB Safe-Sync write bridge |
| `audit-2026` | Bulk-created from perfection audit |

Create missing labels via `gh label create` before assigning. Use `scripts/github_audit_tracker.sh` as the canonical bulk importer.

### Milestones

- **Patch perfection track:** `v1.9.9 — Security & Sandbox` → `v1.9.12 — Code Perfection & Tech Debt`
- **Major architecture:** `v2.0.0 — Shadow DB & Safe-Sync Architecture`
- Every open issue MUST have a milestone unless it is a `question` or `wontfix`.
- Create milestones via API when `gh milestone` is insufficient:

```bash
gh api repos/{owner}/{repo}/milestones -f title="..." -f description="..."
```

## Pull request standards

### PR ↔ Issue linking (closes on merge)

In PR body, use GitHub keywords so issues auto-close:

```markdown
## Summary
- ...

## Test plan
- [ ] `make check`

Closes #123
Fixes #124
```

For partial work: `Refs #123` (does not auto-close).

### PR title

Mirror issue prefix when fixing a tracked issue:

```text
fix(security): sandbox asset path reads in link verification (#1)
perf(ast): incremental delete instead of full vault reload (#20)
```

### Branch naming

```text
[v2 Phase 0] v1.9.12 prerequisites for Shadow DB
[v2] GraphReadPort + MarkdownGraphRepository parity tests
fix(v2): shadow open_shadow_db connection helper (#NNN)
```

v2 phase parents use `[v2 Phase N]`; slices use `[v2]` prefix. Link `Refs #20` on epic and `Fixes #N` on slice issues.

## Automation scripts

| Script | Purpose |
|--------|---------|
| `scripts/github_audit_tracker.sh` | Bulk-create v1.9.x audit milestones + 38 issues |
| `scripts/github-reorg/apply.sh` | v2.0 epic/milestone reorganization |

**Before running bulk scripts:** always `--dry-run` first; require `--yes` only in CI.

**Idempotency:** scripts must skip existing milestones (by title) and issues (by exact title match).

**Rate limiting:** `sleep 2` between `gh issue create` calls.

## Agent workflow (when implementing audit issues)

1. **Pick issue** from current milestone (Security → Concurrency → Performance → Tech Debt).
2. **Branch** per naming convention above.
3. **Implement** surgically per `00-karpathy-agent-behavior.mdc`.
4. **Verify** `make check` (or ruff + mypy + pytest).
5. **CHANGELOG** per `06-auto-changelog.mdc` (Security fixes → `### Security`).
6. **PR** with `Closes #N`, test plan checklist, milestone unchanged.
7. **Do not** push or merge unless user explicitly requests.

## Release coordination

- Cutting `v1.9.9` etc.: follow `05-release-preparation.mdc`; close milestone when all issues merged.
- GitHub Release notes: extract from `CHANGELOG.md` via `scripts/extract_changelog.py` — never `--generate-notes`.
- After release: verify milestone `%` complete in GitHub UI.

## Closing issues

When closing without a merge (already shipped):

```bash
gh issue close N --reason completed
gh issue comment N --body "Closing as delivered in **v1.9.X**.

Evidence: \`path/to/module.py\`, \`tests/test_foo.py\`, \`CHANGELOG.md\` [X.Y.Z]."
```

Always cite file evidence — never close silently.

## What NOT to do

- Do not create duplicate issues (search `gh issue list --search` first).
- Do not assign issues without labels + milestone.
- Do not use vague titles ("fix bug", "improve performance").
- Do not commit or push `.env`, tokens, or graph paths in issue/PR bodies.
- Do not run `scripts/github_audit_tracker.sh` without explicit user approval.
- **Do not add Cursor, AI, or agent attribution** on GitHub — see `09-github-identity-marco-porcellato.mdc` (Marco Porcellato only, zero tool footprint).
