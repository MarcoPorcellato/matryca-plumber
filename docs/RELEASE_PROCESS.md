---
type: Document
---
# Release process

**Matryca Plumber** (Marco Porcellato · [Matryca.ai](https://matryca.ai)) uses a **curated** [`CHANGELOG.md`](../CHANGELOG.md) (Keep a Changelog). GitHub Release notes are **not** auto-generated from commits — CI copies the matching changelog section when you push a `v*` tag.

---

## During development

Add user-facing bullets under **`## [Unreleased]`** (`Added` / `Changed` / `Fixed` / `Removed`). One line per notable change.

---

## Release day (local)

Replace `X.Y.Z` with the semver you are shipping (no `v` prefix in `pyproject.toml`; use `vX.Y.Z` for the git tag).

### v2 release qualification rule

The generic checklist below is necessary but not sufficient for the Shadow DB
release track. Current runtime defaults, Read Only behavior, external-cache location,
health, and fallback are owned by the canonical
[v2 operator contract](knowledge/architecture/shadow-db.md); this document owns only
release mechanics and maintainer authority gates. The fail-closed decision record is
[`quality/issue-bodies/v2-rc-stable-readiness.md`](quality/issue-bodies/v2-rc-stable-readiness.md):

- do not tag or publish a release candidate until its exact preparation commit
  has passed the full release gate;
- bind every Gate B campaign to the exact installed public candidate wheel and its
  runner, profiles, digest, checkpoints, and valid elapsed time;
- do not transfer RC, stable, benchmark, or observation evidence to changed source
  bytes or a later artifact, even for a patch release;
- do not tag or publish a stable v2 patch until its candidate-specific qualification
  plan records every applicable gate as terminal or explicitly dispositioned.

Release preparation, tag creation, publication, and the final stable decision
remain separate maintainer authority gates.

For the current maintenance track, follow the
[v2.0.1 qualification plan](quality/V2_0_1_RELEASE_QUALIFICATION_PLAN_2026-08-23.md).
It is deliberately a candidate plan, not a publication record.

### Publication prerequisites

A `v*` tag ruleset and a registered maintainer GPG key are external
prerequisites. The tag must be annotated, GitHub-verified, and reachable from
protected `main`. The release workflow imports the committed public release key
into an isolated keyring, confirms fingerprint
`FDF72C53A848EBA83AEFA0294F2221BBB930513B`, and cryptographically verifies
the tag before publication can continue.

### 1. Prepare (Cursor or manual)

- [ ] Move everything from `[Unreleased]` to `## [X.Y.Z] - YYYY-MM-DD` in `CHANGELOG.md`
- [ ] Leave an empty `## [Unreleased]` section at the top
- [ ] Set `version = "X.Y.Z"` in `pyproject.toml`
- [ ] Run `uv lock`
- [ ] Run `make check` on CI-equivalent paths, or for a fast local gate before tag: `make test-fast` plus `uv run ruff check src tests` and `uv run mypy src tests` (see `make test-fast` — default 4 workers, no coverage, skips `tests/slow/` and `test_security_remediation.py`; override with `NUM_WORKERS=auto make test-fast`)
- [ ] For performance-heavy releases (e.g. **1.8.x**): optionally run `make perf` (`pytest -m slow`, no coverage gate) and note results in the GitHub release; see [`v1.8-OPTIMIZATION-PLAN.md`](v1.8-OPTIMIZATION-PLAN.md#verification-matrix)
- [ ] If CLI subcommands or flags changed: sync [`llms.txt`](../llms.txt) and [`.well-known/llms.txt`](../.well-known/llms.txt) (must stay identical); see [`openspec/agent-onboarding.md`](openspec/agent-onboarding.md)

**Cursor shortcut:** ask the agent to *“prepare release vX.Y.Z”* (see [`.cursor/rules/05-release-preparation.mdc`](../.cursor/rules/05-release-preparation.mdc)).

### 2. Verify release notes (optional but recommended)

```bash
python scripts/extract_changelog.py vX.Y.Z | less
```

You should see exactly the section that will appear on GitHub.

### 3. Commit, tag, push

```bash
git add CHANGELOG.md pyproject.toml uv.lock
git commit -m "chore: release X.Y.Z"
git tag -s -a vX.Y.Z -m "Release X.Y.Z"
git push origin main
git push origin vX.Y.Z
```

### 4. CI does the rest

On tag push, [`.github/workflows/release.yml`](../.github/workflows/release.yml):

1. `verify` checks the signed annotated tag, GitHub verification, protected-main
   reachability, the isolated-keyring fingerprint, and the required CI context.
2. `destination-preflight` stops if GitHub Releases or PyPI already contains the
   version.
3. `build-release` builds exactly one wheel and one sdist, writes a two-line
   SHA-256 manifest, attests both distributions, and uploads that release bundle.
4. `publish-release` downloads the bundle, verifies the exact two-file set and
   manifest, verifies the attestations against the downloaded subjects, then
   promotes only those downloaded bytes to GitHub Releases and PyPI.

The workflow is fail-closed on existing destinations: do not rerun a release
after GitHub or PyPI already contains the version. Partial publication requires
a separate recovery decision. Package publication still does not replace
risk-selected Gate B or post-release evidence.

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| Release workflow fails on “extract changelog” | Ensure `## [X.Y.Z]` exists in `CHANGELOG.md` and matches the tag (`v1.6.2` → section `[1.6.2]`). |
| GitHub Release or PyPI version already exists | Stop; do not rerun. A partial publication needs a separate recovery decision, while a completed version is never re-used. |
| Notes on GitHub look wrong | Re-run locally: `python scripts/extract_changelog.py vX.Y.Z` and compare to the file. |

---

## Related

- [`CHANGELOG.md`](../CHANGELOG.md)
- [`CONTRIBUTING.md`](../CONTRIBUTING.md) — quality gates before tag
- [`scripts/extract_changelog.py`](../scripts/extract_changelog.py)
