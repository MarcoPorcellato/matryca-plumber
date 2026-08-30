# Exact-Artifact Release Promotion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build Matryca Plumber release distributions once, verify and attest those exact bytes, and publish the same artifacts to GitHub Releases and PyPI under fail-closed tag and destination controls.

**Architecture:** A signed-tag workflow first verifies source, the exact maintainer signing key, GitHub tag recognition, protected-main reachability, required CI, and empty release destinations. A dedicated build job creates one sdist-derived wheel set, writes a SHA-256 manifest, generates required provenance attestations, and uploads a one-day workflow artifact. A publication job downloads the artifact, rejects file-set drift, verifies the manifest and provenance against the exact subjects, and sends the same bytes to GitHub Releases and PyPI without rebuilding.

**Tech Stack:** GitHub Actions YAML, Git/GitHub REST API, uv, existing `scripts/build_release_artifacts.py`, SHA-256 manifest verification, GitHub artifact attestations, GitHub Releases, PyPI Trusted Publishing.

**Spec:** `docs/superpowers/specs/2026-08-30-github-actions-authority-design.md`

## Global Constraints

- Start only after Delivery A is merged and its exact `Ironclad Gatekeeper` results are stable on pull requests and `main`.
- Use a separate clean worktree and branch from the then-current `origin/main`.
- Do not invoke CCP for verification.
- Do not create or push any release tag while implementing this plan.
- Build distributions exactly once per workflow run; never rebuild in the publish job.
- `actions/upload-artifact`, `actions/download-artifact`, `actions/attest`, and every existing Action use a reviewed full commit SHA.
- Per-tag concurrency uses `cancel-in-progress: false`.
- Exact maintainer-key tag signature, GitHub signature recognition, protected-main reachability, exact required CI, destination absence, manifest verification, exact file-set validation, and attestation verification are blocking.
- A partial GitHub/PyPI publication stops and requires a separate maintainer recovery decision.
- The repository currently has no GitHub environments and no tag ruleset; do not add `environment: pypi` until both GitHub and PyPI trusted-publisher settings are coordinated.
- Remote environment/ruleset/key changes, push, PR, merge, tag, and publication require separate exact authorization.

## File Structure

### Create

- `.github/release-signing-key.asc` — maintainer public release key used only for fail-closed tag verification.
- `tests/test_release_workflow_contract.py` — semantic tag, build-once, manifest, attestation, permission, and publication contract.

### Modify

- `.github/workflows/release.yml` — fail-closed four-job exact-artifact pipeline.
- `docs/RELEASE_PROCESS.md` — exact-artifact promotion, maintainer-key tag trust, attestation verification, retry, and recovery boundary.
- `docs/quality/RELEASE_QUALIFICATION_GATE_MAP.md` — exact workflow artifact and provenance evidence boundary.
- `CHANGELOG.md` — release operator and supply-chain improvement.
- `docs/knowledge/log.md` — material release-documentation evolution.
- `docs/knowledge/inventory.json` and `docs/knowledge/inventory.md` — register the new test only if the inventory scope detects it; otherwise regenerate to prove no documentation drift.

## Accepted Action Pins

Re-resolve before editing and stop on drift.

| Action release | Accepted commit on 2026-08-30 |
| --- | --- |
| `actions/checkout@v7` | `3d3c42e5aac5ba805825da76410c181273ba90b1` |
| `actions/setup-node@v7` | `820762786026740c76f36085b0efc47a31fe5020` |
| `astral-sh/setup-uv@v9.0.0` | `c771a70e6277c0a99b617c7a806ffedaca235ff9` |
| `actions/upload-artifact@v4` | `ea165f8d65b6e75b540449e92b4886f43607fa02` |
| `actions/download-artifact@v5` | `634f93cb2916e3fdff6788551b99b062d0335ce0` |
| `actions/attest@v4` | `1e69f48acb82d1966a394da916b4c1698aa569d6` |
| `pypa/gh-action-pypi-publish@release/v1` | `dc37677b2e1c63e2034f94d8a5b11f265b73ba33` |

### Task 1: Define the exact release workflow contract

**Files:**
- Create: `tests/test_release_workflow_contract.py`

**Interfaces:**
- Consumes: `.github/workflows/release.yml` as YAML and text.
- Produces: `_load_release() -> dict[str, Any]` and blocking workflow-architecture tests.

- [ ] **Step 1: Write the failing semantic contract test**

```python
from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import yaml

ROOT = Path(__file__).resolve().parents[1]
RELEASE_WORKFLOW = ROOT / ".github" / "workflows" / "release.yml"


def _load_release() -> dict[str, Any]:
    loaded = yaml.load(RELEASE_WORKFLOW.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)
    assert isinstance(loaded, dict)
    return cast(dict[str, Any], loaded)


def _step(job: dict[str, Any], name: str) -> dict[str, Any]:
    steps = job["steps"]
    selected = next(item for item in steps if item.get("name") == name)
    return cast(dict[str, Any], selected)


def test_release_is_serial_per_tag_and_never_cancels_publication() -> None:
    workflow = _load_release()
    assert workflow["on"]["push"]["tags"] == ["v*"]
    assert workflow["concurrency"] == {
        "group": "release-${{ github.ref }}",
        "cancel-in-progress": "false",
    }


def test_release_job_graph_builds_once_then_promotes() -> None:
    workflow = _load_release()
    jobs = workflow["jobs"]
    assert set(jobs) == {"verify", "destination-preflight", "build-release", "publish-release"}
    assert jobs["destination-preflight"]["needs"] == "verify"
    assert jobs["build-release"]["needs"] == "destination-preflight"
    assert jobs["publish-release"]["needs"] == "build-release"
    rendered = RELEASE_WORKFLOW.read_text(encoding="utf-8")
    assert rendered.count("make release-build") == 1


def test_tag_identity_and_empty_destinations_are_blocking() -> None:
    jobs = _load_release()["jobs"]
    assert jobs["verify"]["permissions"] == {"checks": "read", "contents": "read"}
    verify_script = _step(jobs["verify"], "Verify signed tag and protected-main reachability")["run"]
    assert "verification.verified" in verify_script
    assert "git verify-tag --raw" in verify_script
    assert "FDF72C53A848EBA83AEFA0294F2221BBB930513B" in verify_script
    assert ".github/release-signing-key.asc" in verify_script
    assert "git merge-base --is-ancestor" in verify_script
    assert "GITHUB_SHA" in verify_script
    assert "check-runs" in verify_script
    assert "Ironclad Gatekeeper" in verify_script
    assert "15368" in verify_script
    preflight = _step(jobs["destination-preflight"], "Require empty release destinations")["run"]
    assert 'test "$GITHUB_STATUS" = 404' in preflight
    assert 'test "$PYPI_STATUS" = 404' in preflight


def test_build_writes_manifest_attests_and_uploads_one_day_artifact() -> None:
    build = _load_release()["jobs"]["build-release"]
    assert build["permissions"] == {
        "attestations": "write",
        "contents": "read",
        "id-token": "write",
    }
    manifest = _step(build, "Create distribution digest manifest")["run"]
    assert "sha256sum" in manifest
    assert "release-manifest/SHA256SUMS" in manifest
    attest = _step(build, "Attest release distributions")
    assert attest["uses"] == "actions/attest@1e69f48acb82d1966a394da916b4c1698aa569d6"
    upload = _step(build, "Upload verified release bundle")
    assert upload["uses"] == "actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02"
    assert upload["with"]["retention-days"] == "1"
    assert upload["with"]["if-no-files-found"] == "error"


def test_publish_verifies_manifest_and_never_rebuilds() -> None:
    publish = _load_release()["jobs"]["publish-release"]
    assert publish["permissions"] == {
        "attestations": "read",
        "contents": "write",
        "id-token": "write",
    }
    download = _step(publish, "Download verified release bundle")
    assert download["uses"] == "actions/download-artifact@634f93cb2916e3fdff6788551b99b062d0335ce0"
    verify = _step(publish, "Verify downloaded distribution digests")["run"]
    assert "sha256sum --check" in verify
    assert "find dist -maxdepth 1 -type f" in verify
    assert "release-manifest/SHA256SUMS" in verify
    provenance = _step(publish, "Verify downloaded provenance attestations")["run"]
    assert "gh attestation verify" in provenance
    assert "--signer-workflow" in provenance
    assert "dist/*.whl" in provenance
    assert "dist/*.tar.gz" in provenance
    rendered = "\n".join(str(step.get("run", "")) for step in publish["steps"])
    assert "make release-build" not in rendered
```

- [ ] **Step 2: Run the targeted test and prove the current workflow fails**

Run `rtk uv run pytest -q tests/test_release_workflow_contract.py`.

Expected: FAIL because concurrency, tag verification, destination preflight, build/publish separation, manifest, artifact transfer, and attestation do not yet exist.

### Task 2: Implement tag, source, and destination preflight

**Files:**
- Modify: `.github/workflows/release.yml`
- Test: `tests/test_release_workflow_contract.py`

**Interfaces:**
- Consumes: signed `v*` tag event, protected `main`, GitHub REST, PyPI JSON API.
- Produces: verified exact tag/source identity and proven-empty destinations before any artifact or release mutation.

- [ ] **Step 1: Add per-tag non-cancelling concurrency**

```yaml
concurrency:
  group: release-${{ github.ref }}
  cancel-in-progress: false
```

- [ ] **Step 2: Strengthen `verify` with complete source history and tag validation**

Before editing, re-resolve the accepted releases through fail-closed assertions:

```bash
rtk gh api repos/actions/checkout/commits/v7 --jq 'if .sha == "3d3c42e5aac5ba805825da76410c181273ba90b1" then .sha else error("actions/checkout v7 drift") end'
rtk gh api repos/actions/setup-node/commits/v7 --jq 'if .sha == "820762786026740c76f36085b0efc47a31fe5020" then .sha else error("actions/setup-node v7 drift") end'
rtk gh api repos/astral-sh/setup-uv/commits/v9.0.0 --jq 'if .sha == "c771a70e6277c0a99b617c7a806ffedaca235ff9" then .sha else error("setup-uv v9.0.0 drift") end'
rtk gh api repos/actions/upload-artifact/commits/v4 --jq 'if .sha == "ea165f8d65b6e75b540449e92b4886f43607fa02" then .sha else error("upload-artifact v4 drift") end'
rtk gh api repos/actions/download-artifact/commits/v5 --jq 'if .sha == "634f93cb2916e3fdff6788551b99b062d0335ce0" then .sha else error("download-artifact v5 drift") end'
rtk gh api repos/actions/attest/commits/v4 --jq 'if .sha == "1e69f48acb82d1966a394da916b4c1698aa569d6" then .sha else error("actions/attest v4 drift") end'
rtk gh api repos/pypa/gh-action-pypi-publish/commits/release/v1 --jq 'if .sha == "dc37677b2e1c63e2034f94d8a5b11f265b73ba33" then .sha else error("PyPI publish release/v1 drift") end'
```

Export fingerprint `FDF72C53A848EBA83AEFA0294F2221BBB930513B` as ASCII-armored public key material and validate the committed bytes before staging:

```bash
rtk proxy gpg --armor --export FDF72C53A848EBA83AEFA0294F2221BBB930513B > .github/release-signing-key.asc
rtk proxy gpg --batch --with-colons --show-keys .github/release-signing-key.asc
rtk proxy gpg --batch --list-packets .github/release-signing-key.asc
```

The output must contain public packets only and the exact primary fingerprint.

Set checkout `fetch-depth: 0`. Add a step named `Verify signed tag and protected-main reachability` with `GH_TOKEN: ${{ github.token }}` and a fail-closed script that:

```bash
set -euo pipefail
TAG_REF="repos/${GITHUB_REPOSITORY}/git/ref/tags/${GITHUB_REF_NAME}"
TAG_OBJECT_SHA="$(gh api "$TAG_REF" --jq '.object.sha')"
TAG_OBJECT_TYPE="$(gh api "$TAG_REF" --jq '.object.type')"
test "$TAG_OBJECT_TYPE" = tag
test "$(git rev-parse "${GITHUB_REF_NAME}^{tag}")" = "$TAG_OBJECT_SHA"
test "$(gh api "repos/${GITHUB_REPOSITORY}/git/tags/${TAG_OBJECT_SHA}" --jq '.verification.verified')" = true
EXPECTED_RELEASE_FINGERPRINT="FDF72C53A848EBA83AEFA0294F2221BBB930513B"
export GNUPGHOME="${RUNNER_TEMP}/matryca-release-gpg"
install -d -m 0700 "$GNUPGHOME"
gpg --batch --import .github/release-signing-key.asc
test "$(gpg --batch --with-colons --fingerprint "$EXPECTED_RELEASE_FINGERPRINT" | awk -F: '$1 == "fpr" { print $10; exit }')" = "$EXPECTED_RELEASE_FINGERPRINT"
git verify-tag --raw "$GITHUB_REF_NAME"
test "$(git rev-list -n 1 "$GITHUB_REF_NAME")" = "$GITHUB_SHA"
git fetch --no-tags origin main
git merge-base --is-ancestor "$GITHUB_SHA" origin/main
REQUIRED_CHECK_COUNT="$(gh api \
  "repos/${GITHUB_REPOSITORY}/commits/${GITHUB_SHA}/check-runs?check_name=Ironclad%20Gatekeeper&filter=latest" \
  --jq ".check_runs | map(select(.name == \"Ironclad Gatekeeper\" and .app.id == 15368 and .head_sha == \"${GITHUB_SHA}\" and .status == \"completed\" and .conclusion == \"success\")) | length")"
test "$REQUIRED_CHECK_COUNT" -ge 1
```

Give `verify` only `checks: read` and `contents: read`. Keep frontend and `make ci` source verification in this job. The local tag-object check binds the checkout to the API object. The isolated keyring contains only the reviewed maintainer public key, so `git verify-tag --raw` binds the tag cryptographically to that key. GitHub's separate `verification.verified` result proves that the public platform recognizes it. The check-run query is also part of the acceptance boundary: a same-named result from another app, another SHA, or a non-success conclusion is not accepted.

- [ ] **Step 3: Add the destination preflight job**

Create `destination-preflight`, `needs: verify`, `contents: read`, and use `curl` to capture exact HTTP status without printing response bodies:

```bash
set -euo pipefail
VERSION="${GITHUB_REF_NAME#v}"
GITHUB_STATUS="$(curl --silent --show-error --output /dev/null --write-out '%{http_code}' \
  --header "Authorization: Bearer ${GH_TOKEN}" \
  --header 'Accept: application/vnd.github+json' \
  "${GITHUB_API_URL}/repos/${GITHUB_REPOSITORY}/releases/tags/${GITHUB_REF_NAME}")"
PYPI_STATUS="$(curl --silent --show-error --output /dev/null --write-out '%{http_code}' \
  "https://pypi.org/pypi/matryca-plumber/${VERSION}/json")"
test "$GITHUB_STATUS" = 404
test "$PYPI_STATUS" = 404
```

Bind only `GH_TOKEN: ${{ github.token }}`. A network error, authentication error, 200, or status other than 404 fails the job.

- [ ] **Step 4: Run the focused tests**

Run `rtk uv run pytest -q tests/test_release_workflow_contract.py`.

Expected: tag/concurrency/destination tests pass; build and publish tests still fail.

### Task 3: Build, manifest, attest, and upload one artifact set

**Files:**
- Modify: `.github/workflows/release.yml`
- Test: `tests/test_release_workflow_contract.py`

**Interfaces:**
- Consumes: terminal `destination-preflight` success.
- Produces: workflow artifact `release-bundle` containing `dist/*.whl`, `dist/*.tar.gz`, `release-manifest/SHA256SUMS`, and `release-manifest/release_notes.md`.

- [ ] **Step 1: Create `build-release` with exact permissions and accepted pins**

Use:

```yaml
  build-release:
    name: Build and attest release distributions
    needs: destination-preflight
    runs-on: ubuntu-latest
    timeout-minutes: 20
    permissions:
      attestations: write
      contents: read
      id-token: write
```

Checkout with `fetch-depth: 0`, install uv/Python 3.12 and Node.js 22 using accepted pins, then run `make release-build` exactly once.

- [ ] **Step 2: Create notes and the deterministic digest manifest**

```bash
mkdir -p release-manifest
uv run python scripts/extract_changelog.py "$GITHUB_REF_NAME" > release-manifest/release_notes.md
(
  cd dist
  sha256sum -- *.whl *.tar.gz
) > release-manifest/SHA256SUMS
test "$(wc -l < release-manifest/SHA256SUMS | tr -d ' ')" = 2
```

The two-line invariant binds exactly one wheel and one sdist; any missing or additional distribution fails before attestation.

- [ ] **Step 3: Attest the distributions as a blocking step**

```yaml
      - name: Attest release distributions
        uses: actions/attest@1e69f48acb82d1966a394da916b4c1698aa569d6 # v4
        with:
          subject-path: |
            dist/*.whl
            dist/*.tar.gz
```

Do not add `continue-on-error`.

- [ ] **Step 4: Upload the short-lived promotion bundle**

```yaml
      - name: Upload verified release bundle
        uses: actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02 # v4
        with:
          name: release-bundle
          path: |
            dist/*.whl
            dist/*.tar.gz
            release-manifest/SHA256SUMS
            release-manifest/release_notes.md
          if-no-files-found: error
          retention-days: 1
          compression-level: 0
```

- [ ] **Step 5: Run focused tests**

Run `rtk uv run pytest -q tests/test_release_workflow_contract.py`.

Expected: build and attestation tests pass; publish tests still fail.

### Task 4: Publish only the downloaded verified bytes

**Files:**
- Modify: `.github/workflows/release.yml`
- Test: `tests/test_release_workflow_contract.py`

**Interfaces:**
- Consumes: the `release-bundle` artifact from the same workflow run.
- Produces: GitHub Release assets and PyPI distributions with identical manifest-bound bytes.

- [ ] **Step 1: Create the publication job with isolated permissions**

```yaml
  publish-release:
    name: Publish verified release
    needs: build-release
    runs-on: ubuntu-latest
    timeout-minutes: 15
    permissions:
      attestations: read
      contents: write
      id-token: write
```

Do not add a GitHub environment yet: live inspection on 2026-08-30 found zero repository environments, and changing the environment claim without the matching PyPI trusted-publisher setting would break OIDC publication.

- [ ] **Step 2: Download and verify the bundle**

```yaml
      - name: Download verified release bundle
        uses: actions/download-artifact@634f93cb2916e3fdff6788551b99b062d0335ce0 # v5
        with:
          name: release-bundle

      - name: Verify downloaded distribution digests
        run: |
          set -euo pipefail
          test "$(find dist -maxdepth 1 -type f | wc -l | tr -d ' ')" = 2
          test "$(find dist -maxdepth 1 -type f -name '*.whl' | wc -l | tr -d ' ')" = 1
          test "$(find dist -maxdepth 1 -type f -name '*.tar.gz' | wc -l | tr -d ' ')" = 1
          test "$(wc -l < release-manifest/SHA256SUMS | tr -d ' ')" = 2
          cd dist
          sha256sum --check ../release-manifest/SHA256SUMS
```

- [ ] **Step 3: Verify provenance for the downloaded subjects**

Add a blocking step with `GH_TOKEN: ${{ github.token }}`:

```yaml
      - name: Verify downloaded provenance attestations
        env:
          GH_TOKEN: ${{ github.token }}
        run: |
          set -euo pipefail
          gh attestation verify dist/*.whl \
            --repo "$GITHUB_REPOSITORY" \
            --signer-workflow "${GITHUB_REPOSITORY}/.github/workflows/release.yml"
          gh attestation verify dist/*.tar.gz \
            --repo "$GITHUB_REPOSITORY" \
            --signer-workflow "${GITHUB_REPOSITORY}/.github/workflows/release.yml"
```

This verifies the attestations against the exact downloaded subjects after checksum validation and before either publication destination is mutated.

- [ ] **Step 4: Create the GitHub Release from downloaded files**

Reuse the existing prerelease suffix decision, but point `--notes-file` to `release-manifest/release_notes.md` and assets to `dist/*.whl dist/*.tar.gz`. Bind only `GH_TOKEN: ${{ github.token }}`.

- [ ] **Step 5: Publish the downloaded distributions to PyPI**

```yaml
      - name: Publish package to PyPI
        uses: pypa/gh-action-pypi-publish@dc37677b2e1c63e2034f94d8a5b11f265b73ba33 # release/v1
        with:
          packages-dir: dist/
```

No checkout, build, dependency sync, or artifact mutation occurs in `publish-release`.

- [ ] **Step 6: Run the targeted and package tests**

```bash
rtk uv run pytest -q tests/test_release_workflow_contract.py tests/test_build_release_artifacts.py tests/test_extract_changelog.py
```

Expected: PASS.

- [ ] **Step 7: Commit the exact-artifact workflow**

```bash
rtk git add .github/release-signing-key.asc .github/workflows/release.yml tests/test_release_workflow_contract.py
rtk git commit -S -m "ci(release): promote exact verified artifacts"
```

### Task 5: Update release documentation and evidence boundaries

**Files:**
- Modify: `docs/RELEASE_PROCESS.md`
- Modify: `docs/quality/RELEASE_QUALIFICATION_GATE_MAP.md`
- Modify: `CHANGELOG.md`
- Modify: `docs/knowledge/log.md`
- Modify: `docs/knowledge/inventory.json`
- Modify: `docs/knowledge/inventory.md`

**Interfaces:**
- Consumes: final release job names and artifact paths.
- Produces: current operator documentation that matches the exact workflow.

- [ ] **Step 1: Update the release process**

Document these exact facts:

- tag must be annotated, GitHub-verified, and reachable from protected `main`;
- the committed public release key must import to fingerprint `FDF72C53A848EBA83AEFA0294F2221BBB930513B`, and the isolated keyring must verify the tag cryptographically;
- a `v*` tag ruleset and registered maintainer GPG key are external prerequisites;
- one workflow run builds one wheel and one sdist, verifies a two-line SHA-256 manifest and the exact downloaded file set, attests both, verifies those attestations against the downloaded subjects, and promotes only those bytes;
- reruns stop when GitHub or PyPI already contains the version;
- partial publication requires a separate recovery decision;
- package publication still does not replace risk-selected Gate B or post-release evidence.

- [ ] **Step 2: Update the gate map and changelog**

Change the release-publication gate row to name `verify`, `destination-preflight`, `build-release`, and `publish-release`, plus the manifest and attestation. Add under `[Unreleased] / Changed`:

```markdown
- **Exact-artifact release promotion** — build each wheel and sdist once, verify and attest their SHA-256-bound bytes, and publish the same downloaded distributions to GitHub Releases and PyPI under fail-closed tag, destination, and retry controls.
```

Add the corresponding newest-first knowledge-log entry without rewriting historical release evidence.

- [ ] **Step 3: Synchronize and validate documentation**

```bash
rtk make docs-inventory-sync
rtk make docs-inventory-md
rtk make agents-check
rtk make docs-check
```

Expected: PASS with no inventory drift.

- [ ] **Step 4: Commit the documentation slice**

```bash
rtk git add CHANGELOG.md docs/RELEASE_PROCESS.md docs/quality/RELEASE_QUALIFICATION_GATE_MAP.md docs/knowledge
rtk git commit -S -m "docs(release): define exact-artifact promotion"
```

### Task 6: Qualify Delivery B without publishing

**Files:**
- Review: all Delivery B changes.

**Interfaces:**
- Consumes: Tasks 1–5.
- Produces: an exact-head PR candidate; no tag or release.

- [ ] **Step 1: Run direct local verification without CCP**

```bash
rtk uv run pytest -q tests/test_release_workflow_contract.py tests/test_build_release_artifacts.py tests/test_extract_changelog.py
rtk make release-build
rtk make agents-check
rtk make docs-check
rtk make ci
```

Expected: PASS and exactly one wheel plus one sdist in local `dist/`. These local bytes are test output, not future publication artifacts.

- [ ] **Step 2: Review scope and release non-mutation**

```bash
rtk git diff --check origin/main...HEAD
rtk git diff --name-status origin/main...HEAD
rtk git tag --points-at HEAD
rtk gh release view "$(rtk uv run python -c 'import tomllib; print("v" + tomllib.load(open("pyproject.toml", "rb"))["project"]["version"])')"
```

Expected: only planned paths; no new local tag; no release created by this work. An already existing release for the current package version is historical state and must not be mutated.

- [ ] **Step 3: Run local code-graph diff audit and signature checks**

Run `detect_changes(scope="compare", base_ref="origin/main")`, `rtk git diff --check`, `rtk git log --format=%B origin/main..HEAD`, and `rtk git verify-commit` for each commit. Stop on unexpected runtime impact, attribution, invalid signatures, or scope drift.

- [ ] **Step 4: Stop before push, PR, tag settings, or publication**

Record exact base, head, pins, tests, package filenames, and local digests. Obtain separate authorization for push and PR creation.

### Task 7: Establish external release prerequisites after PR merge

**Files:**
- Remote settings only; no repository file edit.

**Interfaces:**
- Consumes: merged Delivery B workflow and observed GitHub check contexts.
- Produces: enforceable release-key identity and immutable `v*` tags before the first new tag.

- [ ] **Step 1: Register and verify the maintainer public GPG key**

Export only public key fingerprint `FDF72C53A848EBA83AEFA0294F2221BBB930513B` and add it to Marco Porcellato's GitHub account through **Settings → SSH and GPG keys → New GPG key**. Never upload or expose the private key. Create a disposable signed annotated test tag only in a separately authorized private/disposable context, or verify the next authorized release tag before push; GitHub must report `verification.verified: true`.

- [ ] **Step 2: Create the active release-tag ruleset through GitHub Settings**

Create a tag-target ruleset named `release-tags`, enforcement `Active`, include pattern `refs/tags/v*`, prevent deletion and update/non-fast-forward replacement, and retain only an explicitly reviewed maintainer bypass. Do not change either branch ruleset.

- [ ] **Step 3: Re-read the created ruleset and verify exact enforcement**

Use `rtk gh api repos/MarcoPorcellato/matryca-plumber/rulesets --paginate`, then read the new ruleset by ID. Confirm target `tag`, active enforcement, include `refs/tags/v*`, and the intended immutability rules. Stop on any broader ref scope or unexpected bypass.

- [ ] **Step 4: Keep PyPI environment adoption separate**

The repository had zero GitHub environments on 2026-08-30. If a protected `pypi` environment is desired, first configure the same environment claim in the PyPI Trusted Publisher, then create the GitHub environment, then deliver `environment: pypi` in a separate reviewed PR. Do not change only one side.

- [ ] **Step 5: Stop before the first tag**

Record the merged workflow SHA, verified key state, ruleset ID and scope, current `main` SHA, and terminal required CI. Obtain an exact release authorization before creating or pushing any tag.
