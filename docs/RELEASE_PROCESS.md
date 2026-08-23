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

### v2.0 promotion override

The generic checklist below is necessary but not sufficient for the Shadow DB
release track. Current runtime defaults, Read Only behavior, external-cache location,
health, and fallback are owned by the canonical
[v2 operator contract](knowledge/architecture/shadow-db.md); this document owns only
release mechanics and maintainer authority gates. The fail-closed decision record is
[`quality/issue-bodies/v2-rc-stable-readiness.md`](quality/issue-bodies/v2-rc-stable-readiness.md):

- do not tag or publish a release candidate until its exact preparation commit
  has passed the full release gate;
- do not treat the exact `2.0.0b1` soak as proof of the later default-on,
  external-cache implementation;
- after publishing each RC, collect Gate B against that exact installed public
  artifact; rc.1 evidence never transfers to rc.2;
- do not tag or publish stable `v2.0.0` until every Gate B row is complete.

Release preparation, tag creation, publication, and the final stable decision
remain separate maintainer authority gates.

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
git tag vX.Y.Z
git push origin main
git push origin vX.Y.Z
```

### 4. CI does the rest

On tag push, [`.github/workflows/release.yml`](../.github/workflows/release.yml):

1. Builds the Sovereign UI frontend
2. Builds the frontend in a clean tracked-source snapshot, then builds an sdist and derives the wheel from that sdist with `make release-build`
3. Creates a GitHub Release with notes from `scripts/extract_changelog.py`
4. Publishes to PyPI (trusted publishing)

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| Release workflow fails on “extract changelog” | Ensure `## [X.Y.Z]` exists in `CHANGELOG.md` and matches the tag (`v1.6.2` → section `[1.6.2]`). |
| PyPI version already exists | Bump patch version; never re-use a published version. |
| Notes on GitHub look wrong | Re-run locally: `python scripts/extract_changelog.py vX.Y.Z` and compare to the file. |

---

## Related

- [`CHANGELOG.md`](../CHANGELOG.md)
- [`CONTRIBUTING.md`](../CONTRIBUTING.md) — quality gates before tag
- [`scripts/extract_changelog.py`](../scripts/extract_changelog.py)
