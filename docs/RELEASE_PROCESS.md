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

- classify the release delta before selecting operational gates, using the
  [risk-based qualification decision](quality/RISK_BASED_RELEASE_QUALIFICATION_DECISION_2026-08-24.md);
- do not tag or publish a release candidate until its exact preparation commit
  has passed its required pre-publication gates (Stage A in the RC4 plan);
- when the selected risk tier requires Gate B, bind the campaign to the exact
  installed public candidate wheel and its runner, profiles, digest, checkpoints,
  and valid elapsed time;
- do not transfer RC, stable, benchmark, or observation evidence to changed source
  bytes or a later artifact, even for a patch release;
- do not tag or publish a stable v2 patch until its candidate-specific qualification
  plan records every applicable gate as terminal or explicitly dispositioned.

Evidence non-transferability and gate applicability are separate decisions. Every
release needs fresh source, CI, package, and publication evidence. A fresh 72-hour
soak is required only when the classified delta reaches the durable-state,
concurrency, recovery, parser/I/O, lifecycle, migration, default, or equivalent
high-risk boundary. Lower-risk changes use the smaller exact-artifact gate set
defined by the gate map; they never inherit an earlier soak and never claim a new
durability result.

Release preparation, tag creation, publication, and the final stable decision
remain separate maintainer authority gates.

The [v2.0.1-rc.1 qualification plan](quality/V2_0_1_RELEASE_QUALIFICATION_PLAN_2026-08-23.md)
and [release record](releases/v2.0.1-rc.1-GITHUB.md) are immutable historical records
for that exact prerelease. They do not classify or qualify a later `main`. Every new
maintenance candidate or stable decision must select a fresh exact source and artifact,
classify its complete delta, and record the applicable gates before publication.

The [v2.0.1-rc.2 attempt](releases/v2.0.1-rc.2-FAILED-PUBLICATION.md) is immutable
terminal failed-publication history: its signed tag and workflow passed source,
destination-preflight, build, attestation, and bundle-verification stages, but it
published neither destination. [RC3](releases/v2.0.1-rc.3-GITHUB.md) is a published,
historical prerelease; its source, artifacts, and qualification evidence do not transfer
to RC4 or stable `v2.0.1`. Its [qualification plan](quality/V2_0_1_RC3_RELEASE_QUALIFICATION_PLAN_2026-08-31.md)
is historical, not a proposal for the next candidate.

The active [RC4 qualification plan](quality/V2_0_1_RC4_RELEASE_QUALIFICATION_PLAN_2026-09-06.md)
defines two stages. Stage A is pre-publication GO/NO-GO for an exact source and
independently built artifact, required source/platform/resource/TCK controls, and
independent review; a GO permits only separate authorization to publish an experimental
RC4 prerelease. Stage B begins after publication: verify the exact workflow-built public
wheel against the frozen manifest, then run fresh exact-artifact Gate B for both required
profiles. Gate B is not a prerequisite to publish the experimental artifact, but both
terminal profile results and review of all other applicable gates are required for a
separate final RC4 qualification decision. Neither stage authorizes stable promotion.

### RC4 Stage A on-demand package qualification

Use the proposed manual package-qualification workflow only after its implementation
has landed on protected `main` and is available for dispatch. First select the exact,
reachable, clean `main` commit and record its full commit and tree IDs. The workflow's
own merge changes `main`; earlier diagnostic source and local build results remain
historical and cannot be relabeled as evidence for the new commit. Confirm ordinary
required hosted CI is terminal green for that exact commit before dispatch.

Before any dispatch, inspect the workflow at that exact `main`: its sdist lane must
authenticate the original sdist, record the complete observed private PEP 517 build
environment before and after, verify static and backend-returned dynamic requirements
against already installed packages, build a temporary wheel with
`uv build --wheel --no-build-isolation`, and bind that wheel's name, size, and SHA-256.
It must install the temporary wheel with `--no-deps` in the separate sdist runtime
environment while `verify-installed` continues to authenticate the original bound
sdist. The temporary wheel is not part of canonical `dist`. A recorded generated
wheel hash proves only this run's exact output, not reproducible builds. Generator
metadata alone does not prove the full build environment.

The required Windows row must also be genuinely qualified. Until complete launcher
installer/template provenance and native Windows x64 package/process evidence exist,
Windows remains NO-GO. A deliberately failing Windows step is not a qualification
result: do not dispatch such a workflow, call Stage A PASS, or infer stable-release
readiness.

The qualification workflow pins official uv `0.12.19`, which is outside the
affected range in the [official GHSA-2cv4-cqwr-gwf7 advisory](https://github.com/astral-sh/uv/security/advisories/GHSA-2cv4-cqwr-gwf7).
The [0.12.19 release page](https://github.com/astral-sh/uv/releases/tag/0.12.19)
links verified release commit `bea138450f0e620a4ce5765b0e38cff7b9f0799f`; the
official [Windows x64 archive checksum](https://releases.astral.sh/github/uv/releases/download/0.12.19/uv-x86_64-pc-windows-msvc.zip.sha256)
is `6dbb02d79e419522f1c500f0adb1cddcff0cda7d59b0d66ea7f5e3b4a1b2f5f0`.
The former `0.12.16` pin falls in the affected `>=0.12.7,<0.12.18` range and is
historical only; do not use it for Windows wheel installation. The new tool pin
does not qualify the generated launcher. Exact tag-to-commit resolution, the
tag-pinned launcher source/content, and executable-template provenance remain
unverified. `RECORD` and an `MZ`/PE header alone do not authenticate generated
launcher bytes. Lifting NO-GO requires that exact source/template chain, an
independent architecture-specific template/payload verifier (including
interpreter binding, entry-point payload and trailing bytes), process-tree
containment review, and native Windows x64 install and lifecycle tests.

The SHA-pinned `astral-sh/setup-uv` action is a trusted bootstrap boundary:
action-internal code runs before explicit workflow verification. Independently
verify the official uv `0.12.19` artifact and active executable before every
workflow-owned uv command, including `uv sync`, and repeat verification in the
aggregate job before its own `uv sync`. State only that uv was verified before
workflow-owned use, not before action-internal code. The aggregate check is now
locally implemented; its 14 focused workflow tests pass. This is local
implementation evidence only, not hosted qualification or dispatch readiness.
After repair of raw PEP 517 dynamic-expression and extras handling, the focused
integrated package suite was 225 passed with 1 expected skip before final typing
additions. The subsequent exact clone-local, locked/offline full `make ci`
passed: 2443 passed, 6 skipped, 4 warnings, and 84.73% coverage, using four
pytest workers; all static, documentation, and type gates were green. Earlier
sandbox `ps` and shared-primary-venv coverage failures are diagnostic history,
not the final run. Sol's final quality and security reviews are PASS_WITH_NOTES;
process-containment review separately passed with notes after 21 focused tests.
Review notes: PEP 518 environment
records observe package names/versions but not package artifact hashes; two
official uv archive downloads lack a byte-count cap before digest verification;
and tested process containment is not a hostile-code sandbox. These scoped
local checks do not establish hosted qualification. Windows remains NO-GO and
no hosted dispatch or Stage A result is claimed.

Before dispatch, obtain separate authorization bound to this workflow,
`refs/heads/main`, the selected full SHA, and exactly one attempt. Green CI or
approved documentation does not authorize a run; any rerun requires new
authorization.

Dispatch from `refs/heads/main` and enter the full lowercase 40-character SHA for that
same `main` commit in the workflow's expected-commit input. The workflow must reject a
different ref, SHA, tree, version, or dirty checkout. One Linux build produces exactly
one canonical wheel and one canonical source distribution. Every platform verifies
both original archive byte identities. Install the canonical wheel directly. For the
sdist lane, build one temporary wheel from the authenticated original sdist in a
private PEP 517 build environment, then install that temporary output in the separate
sdist runtime environment; pass the original sdist—not the temporary wheel—to
`verify-installed`. Keep the temporary wheel outside `dist`. Require terminal success
and one complete, matching platform receipt for each platform. A missing, skipped,
failed, cancelled, timed-out, or mismatched required job or receipt is NO-GO; preserve
that attempt and its run identity. Any rerun is a distinct attempt, not a replacement
for a failed receipt.

Link the sanitized evidence record to issue #582. It must bind the workflow run and
event SHA/ref; source/tree and artifact identities; the one wheel/sdist pair and its
hashes; all three runner OS/architectures and terminal job conclusions; installed
metadata, `RECORD`, resource and TCK results; focused test counts; and any explicit
platform disposition. For each sdist row, also bind the complete observed build-env
package manifest before and after, static and dynamic requirement satisfiers, and the
temporary wheel's name/size/SHA-256. This is exact one-attempt evidence, not a
reproducible-build claim. Keep local paths, raw graph content, private logs, tokens,
and workstation state out of public evidence. Request independent human Stage A
GO/NO-GO against the complete RC4 plan; a green workflow alone is not that decision.

After a Stage A GO, obtain separate authorization before creating a signed tag or
publishing the experimental RC4 prerelease. Stage A-built bytes are not assumed to
match the later public release-workflow artifacts. Stage B starts only after authorized
publication and independently verifies those exact public artifacts against the frozen
manifest before either Gate B profile begins. Gate B and final RC4 disposition remain
separate from Stage A and publication; neither grants stable `v2.0.1` support.

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
   promotes only those downloaded bytes to GitHub Releases and PyPI. GitHub Release
   creation binds `gh` explicitly to `GITHUB_REPOSITORY`; the checkout-free promotion
   job must not rely on local Git repository discovery.

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
| GitHub Release creation reports `not a git repository` | Do not rerun the unchanged tag workflow. Confirm that the checkout-free publish job passes `--repo "$GITHUB_REPOSITORY"` to `gh release create`, preserve the failed run and tag, then prepare a fresh candidate after the correction reaches protected `main`. |
| Notes on GitHub look wrong | Re-run locally: `python scripts/extract_changelog.py vX.Y.Z` and compare to the file. |

---

## Related

- [`CHANGELOG.md`](../CHANGELOG.md)
- [`CONTRIBUTING.md`](../CONTRIBUTING.md) — quality gates before tag
- [`scripts/extract_changelog.py`](../scripts/extract_changelog.py)
