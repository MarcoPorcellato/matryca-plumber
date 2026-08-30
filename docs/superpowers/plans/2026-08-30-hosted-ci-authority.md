# Hosted CI Authority Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make GitHub Actions the sole active pull-request qualification authority while preserving the exact protected `Ironclad Gatekeeper` status and making every declared compatibility lane blocking.

**Architecture:** Independent Python 3.12, frontend, Python 3.13, dependency-review, macOS Shadow, and Windows Shadow jobs run in parallel. A small `if: always()` aggregation job retains the exact protected status name and fails on every failed, cancelled, or unexpected skipped dependency. The obsolete local receipt control plane is removed from the active tree, while Git history preserves the experiment.

**Tech Stack:** GitHub Actions YAML, Python 3.12/3.13, uv, pytest, PyYAML `BaseLoader`, Node.js 22, npm, CodeQL, OKF v0.2 documentation inventory.

**Spec:** `docs/superpowers/specs/2026-08-30-github-actions-authority-design.md`

## Global Constraints

- Work in a clean isolated worktree based on the exact latest `origin/main`; never reuse or overwrite the dirty `codex/remove-public-ccp-observer-v1` or release-qualification worktrees.
- Do not invoke CCP `run`, `benchmark`, or `guard exec`; standard GitHub-hosted CI is the selected public-repository authority.
- Preserve the exact required check name `Ironclad Gatekeeper` and GitHub Actions integration ID `15368`.
- Keep `.github/workflows/ci.yml` free of top-level `paths` and `paths-ignore` filters.
- Use exact `merge_group: { types: [checks_requested] }` semantics.
- Python 3.13 and both Shadow matrix children are blocking.
- Every external `uses:` reference is pinned to one reviewed full 40-hex commit SHA.
- Public files, commits, PR text, and documentation contain no assistant, model, vendor-tool authorship, local paths, secrets, or co-author trailers.
- Local verification runs directly through repository commands; fresh hosted CI on the exact PR head is still required.
- Remote push, PR creation, ruleset mutation, and merge remain separately authorized actions.

## File Structure

### Create

- `docs/decisions/2026-08-30-github-actions-qualification-authority.md` — current hosted-CI authority decision and supersession boundary.

### Modify

- `.github/workflows/ci.yml` — parallel required job graph and stable aggregator.
- `.github/workflows/codeql.yml` — merge-group support, immutable pins, least privilege.
- `.github/workflows/release.yml` — immutable pins only; behavioral release changes belong to Delivery B.
- `.github/workflows/dependabot-uv-fix.yml` — immutable pins only.
- `.github/workflows/metrics-saver.yml` — immutable pins only; no behavioral redesign.
- `.github/dependabot.yml` — retain the weekly grouped `github-actions` updater and add no new ecosystem.
- `tests/test_ci_workflow_contract.py` — semantic hosted-CI and immutable-pin contract.
- `.gitignore` — remove only obsolete local receipt and writable-mount entries.
- `Makefile` — remove only local receipt/preflight/savings targets and `.PHONY` names.
- `CHANGELOG.md` — replace the active hybrid-CI bootstrap bullet with the hosted-authority change.
- `docs/decisions/index.md` — link the new active decision.
- `docs/knowledge/index.md` — remove the obsolete active runbook route.
- `docs/knowledge/log.md` — add a newest-first 2026-08-30 supersession entry; preserve older chronology.
- `docs/quality/EVIDENCE_INDEX.md` — remove entries whose active evidence files are deleted.
- `docs/knowledge/inventory.json` — curate added and removed document records.
- `docs/knowledge/inventory.md` — regenerate, never hand-edit.

### Delete

- `.commit-ci-preflight.toml`
- `.commit-ci-policy.toml`
- `.github/workflows/receipt-gate.yml`
- `scripts/ccp_savings_report.py`
- `tests/test_ccp_adoption_contract.py`
- `tests/test_ccp_savings_report.py`
- `tests/fixtures/ccp-savings/valid-baseline.json`
- `tests/fixtures/ccp-savings/valid-eligible-pr.json`
- `tests/fixtures/ccp-savings/valid-fallback.json`
- `tests/fixtures/ccp-savings/invalid-billing-claim.json`
- `docs/quality/ccp-savings/schema-v1.json`
- `docs/quality/ccp-savings/baseline/2026-08-24-pr-linux.json`
- `docs/quality/CCP_GITHUB_ACTIONS_SAVINGS_BASELINE_2026-08-24.md`
- `docs/quality/CCP_GITHUB_ACTIONS_SAVINGS_CASE_STUDY.md`
- `docs/quality/CCP_HYBRID_CI_RUNBOOK.md`
- `docs/superpowers/specs/2026-08-24-ccp-hybrid-ci-adoption-design.md`
- `docs/superpowers/plans/2026-08-24-ccp-hybrid-ci-adoption.md`

## Accepted Action Pins

Re-resolve each named release immediately before editing. Stop on drift and review the new commit instead of silently substituting it.

| Action release | Accepted commit on 2026-08-30 |
| --- | --- |
| `actions/checkout@v7` | `3d3c42e5aac5ba805825da76410c181273ba90b1` |
| `actions/setup-node@v7` | `820762786026740c76f36085b0efc47a31fe5020` |
| `actions/setup-python@v7` | `5fda3b95a4ea91299a34e894583c3862153e4b97` |
| `actions/dependency-review-action@v5` | `a1d282b36b6f3519aa1f3fc636f609c47dddb294` |
| `github/codeql-action@v4` | `cdf488f595d80d6e07e03d4674febd5ab45fa938` |
| `astral-sh/setup-uv@v9.0.0` | `c771a70e6277c0a99b617c7a806ffedaca235ff9` |
| `pypa/gh-action-pypi-publish@release/v1` | `dc37677b2e1c63e2034f94d8a5b11f265b73ba33` |

### Task 1: Replace the obsolete workflow tests with the hosted authority contract

**Files:**
- Modify: `tests/test_ci_workflow_contract.py`

**Interfaces:**
- Consumes: GitHub workflow YAML and `Makefile` as repository text.
- Produces: `_load_workflow(path: Path) -> dict[str, Any]`, `_external_uses(value: object) -> list[str]`, and blocking regression tests used by every later task.

- [ ] **Step 1: Replace the old monolithic/non-blocking assertions with semantic helpers and failing tests**

Use `yaml.BaseLoader` so the YAML key `on` remains a string. Add these exact structural assertions:

```python
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, cast

import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"
CI_WORKFLOW = WORKFLOWS / "ci.yml"
CODEQL_WORKFLOW = WORKFLOWS / "codeql.yml"
MAKEFILE = ROOT / "Makefile"

REQUIRED_NEEDS = {
    "dependency-review",
    "python-312-quality",
    "frontend-quality",
    "python-313-compatibility",
    "shadow-cross-platform",
}
PINNED_ACTION = re.compile(r"^[^./][^@]*@[0-9a-f]{40}$")


def _load_workflow(path: Path) -> dict[str, Any]:
    loaded = yaml.load(path.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)
    assert isinstance(loaded, dict)
    return cast(dict[str, Any], loaded)


def _external_uses(value: object) -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            if key == "uses" and isinstance(child, str) and not child.startswith("./"):
                found.append(child)
            found.extend(_external_uses(child))
    elif isinstance(value, list):
        for child in value:
            found.extend(_external_uses(child))
    return found


def test_required_ci_always_reports_for_pr_push_and_merge_queue() -> None:
    workflow = _load_workflow(CI_WORKFLOW)
    triggers = workflow["on"]
    assert triggers["pull_request"] == {}
    assert triggers["push"]["branches"] == ["main"]
    assert triggers["merge_group"]["types"] == ["checks_requested"]
    assert "paths" not in triggers
    assert "paths-ignore" not in triggers
    assert workflow["concurrency"] == {
        "group": "ci-${{ github.workflow }}-${{ github.ref }}",
        "cancel-in-progress": "true",
    }


def test_ironclad_gatekeeper_aggregates_every_blocking_lane() -> None:
    jobs = _load_workflow(CI_WORKFLOW)["jobs"]
    assert jobs["dependency-review"]["if"] == "github.event_name == 'pull_request'"
    gate = jobs["ironclad-gatekeeper"]
    assert gate["name"] == "Ironclad Gatekeeper"
    assert set(gate["needs"]) == REQUIRED_NEEDS
    assert gate["if"] == "always()"
    assert "continue-on-error" not in gate
    assert "needs.python-313-compatibility.result" in gate["steps"][0]["env"].values()
    assert "needs.shadow-cross-platform.result" in gate["steps"][0]["env"].values()


def test_python_313_and_shadow_contract_are_blocking() -> None:
    jobs = _load_workflow(CI_WORKFLOW)["jobs"]
    python_313 = jobs["python-313-compatibility"]
    assert "continue-on-error" not in python_313
    assert "if" not in python_313
    assert python_313["timeout-minutes"] == "15"
    shadow = jobs["shadow-cross-platform"]
    assert shadow["strategy"]["matrix"]["os"] == ["macos-latest", "windows-latest"]
    assert "continue-on-error" not in shadow


def test_codeql_supports_exact_merge_group_event() -> None:
    workflow = _load_workflow(CODEQL_WORKFLOW)
    assert workflow["on"]["merge_group"]["types"] == ["checks_requested"]
    assert workflow["permissions"] == {"contents": "read", "security-events": "write"}


def test_all_external_actions_are_full_sha_pinned() -> None:
    references: list[str] = []
    for path in sorted(WORKFLOWS.glob("*.yml")):
        references.extend(_external_uses(_load_workflow(path)))
    assert references
    assert all(PINNED_ACTION.fullmatch(reference) for reference in references)


def test_local_receipt_control_plane_is_absent() -> None:
    assert not (ROOT / ".commit-ci-preflight.toml").exists()
    assert not (ROOT / ".commit-ci-policy.toml").exists()
    assert not (WORKFLOWS / "receipt-gate.yml").exists()
    makefile = MAKEFILE.read_text(encoding="utf-8")
    assert "ccp-" not in makefile
    assert "commit-ci-preflight" not in makefile
    assert all("pull_request_target" not in path.read_text(encoding="utf-8") for path in WORKFLOWS.glob("*.yml"))
```

- [ ] **Step 2: Run the targeted test and prove the old contract fails**

Run:

```bash
rtk uv run pytest -q tests/test_ci_workflow_contract.py
```

Expected: FAIL because `merge_group`, the aggregator dependency graph, blocking Python 3.13, immutable pins, and removal conditions do not yet exist.

### Task 2: Implement the parallel required CI graph

**Files:**
- Modify: `.github/workflows/ci.yml`
- Modify: `tests/test_ci_workflow_contract.py`

**Interfaces:**
- Consumes: `make ci`, frontend npm scripts, the existing named Shadow test list.
- Produces: five independent job results and the exact protected `Ironclad Gatekeeper` result.

- [ ] **Step 1: Add exact triggers and retain minimum workflow permissions**

Use this trigger and workflow envelope:

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request: {}
  merge_group:
    types: [checks_requested]

permissions:
  contents: read

env:
  FORCE_JAVASCRIPT_ACTIONS_TO_NODE24: true

concurrency:
  group: ci-${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true
```

- [ ] **Step 2: Split Python 3.12 and frontend work into independent jobs**

Keep `dependency-review` explicitly limited to `github.event_name == 'pull_request'`. Create `python-312-quality` with checkout, `setup-uv` for Python 3.12, locked sync, informational `make docs-audit`, and `make ci`. Create `frontend-quality` with checkout, `setup-node` 22, `npm ci`, lint, test, and build. Use the accepted full-SHA pins and preserve 20- and 10-minute timeouts respectively.

- [ ] **Step 3: Make Python 3.13 and the Shadow matrix unconditionally blocking**

Rename the Python job ID to `python-313-compatibility`, remove its `if` and `continue-on-error`, keep full pytest and the 15-minute timeout. Preserve the exact eight named Shadow tests and the two-platform matrix without `continue-on-error`.

- [ ] **Step 4: Add the stable final aggregator**

Add this job after all producer jobs:

```yaml
  ironclad-gatekeeper:
    name: Ironclad Gatekeeper
    runs-on: ubuntu-latest
    timeout-minutes: 5
    if: always()
    needs:
      - dependency-review
      - python-312-quality
      - frontend-quality
      - python-313-compatibility
      - shadow-cross-platform
    steps:
      - name: Require every applicable qualification lane
        env:
          EVENT_NAME: ${{ github.event_name }}
          DEPENDENCY_REVIEW_RESULT: ${{ needs.dependency-review.result }}
          PYTHON_312_RESULT: ${{ needs.python-312-quality.result }}
          FRONTEND_RESULT: ${{ needs.frontend-quality.result }}
          PYTHON_313_RESULT: ${{ needs.python-313-compatibility.result }}
          SHADOW_RESULT: ${{ needs.shadow-cross-platform.result }}
        run: |
          set -euo pipefail
          test "$PYTHON_312_RESULT" = success
          test "$FRONTEND_RESULT" = success
          test "$PYTHON_313_RESULT" = success
          test "$SHADOW_RESULT" = success
          if test "$EVENT_NAME" = pull_request; then
            test "$DEPENDENCY_REVIEW_RESULT" = success
          else
            test "$DEPENDENCY_REVIEW_RESULT" = skipped
          fi
```

- [ ] **Step 5: Run the focused contract**

Run `rtk uv run pytest -q tests/test_ci_workflow_contract.py`.

Expected: failures remain only for immutable pins and local receipt retirement; the trigger, graph, and blocking-lane tests pass.

### Task 3: Harden every active Action dependency and CodeQL trigger

**Files:**
- Modify: `.github/workflows/ci.yml`
- Modify: `.github/workflows/codeql.yml`
- Modify: `.github/workflows/release.yml`
- Modify: `.github/workflows/dependabot-uv-fix.yml`
- Modify: `.github/workflows/metrics-saver.yml`
- Verify: `.github/dependabot.yml`
- Test: `tests/test_ci_workflow_contract.py`

**Interfaces:**
- Consumes: accepted Action-pin table in this plan.
- Produces: immutable `uses:` references and merge-queue-aware CodeQL analysis.

- [ ] **Step 1: Re-resolve each accepted release ref and compare it with the table**

Run each exact repository/ref lookup as a fail-closed assertion against the accepted table:

```bash
rtk gh api repos/actions/checkout/commits/v7 --jq 'if .sha == "3d3c42e5aac5ba805825da76410c181273ba90b1" then .sha else error("actions/checkout v7 drift") end'
rtk gh api repos/actions/setup-node/commits/v7 --jq 'if .sha == "820762786026740c76f36085b0efc47a31fe5020" then .sha else error("actions/setup-node v7 drift") end'
rtk gh api repos/actions/setup-python/commits/v7 --jq 'if .sha == "5fda3b95a4ea91299a34e894583c3862153e4b97" then .sha else error("actions/setup-python v7 drift") end'
rtk gh api repos/actions/dependency-review-action/commits/v5 --jq 'if .sha == "a1d282b36b6f3519aa1f3fc636f609c47dddb294" then .sha else error("dependency-review v5 drift") end'
rtk gh api repos/github/codeql-action/commits/v4 --jq 'if .sha == "cdf488f595d80d6e07e03d4674febd5ab45fa938" then .sha else error("CodeQL v4 drift") end'
rtk gh api repos/astral-sh/setup-uv/commits/v9.0.0 --jq 'if .sha == "c771a70e6277c0a99b617c7a806ffedaca235ff9" then .sha else error("setup-uv v9.0.0 drift") end'
rtk gh api repos/pypa/gh-action-pypi-publish/commits/release/v1 --jq 'if .sha == "dc37677b2e1c63e2034f94d8a5b11f265b73ba33" then .sha else error("PyPI publish release/v1 drift") end'
```

Expected: the exact commit in the Accepted Action Pins table. Stop and review any drift.

- [ ] **Step 2: Replace every mutable Action ref with its accepted SHA**

Use the form:

```yaml
uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7
```

Apply the same pattern to every external Action in all five active workflows. Do not change workflow behavior in `release.yml`, `dependabot-uv-fix.yml`, or `metrics-saver.yml` beyond immutable pins.

- [ ] **Step 3: Add exact merge-group support to CodeQL**

Add:

```yaml
  merge_group:
    types: [checks_requested]
```

Keep `contents: read`, `security-events: write`, weekly schedule, two-language matrix, concurrency cancellation, and existing timeout.

- [ ] **Step 4: Run immutable-pin and CodeQL contract tests**

Run `rtk uv run pytest -q tests/test_ci_workflow_contract.py`.

Expected: only local receipt retirement assertions may remain failing.

- [ ] **Step 5: Commit the hosted workflow graph and pins**

```bash
rtk git add .github/workflows tests/test_ci_workflow_contract.py
rtk git commit -S -m "ci: make hosted qualification authoritative"
```

### Task 4: Retire the active local receipt control plane

**Files:**
- Delete: every file listed in the plan's Delete section.
- Modify: `.gitignore`
- Modify: `Makefile`
- Test: `tests/test_ci_workflow_contract.py`

**Interfaces:**
- Consumes: the already-green hosted producer jobs from Task 2.
- Produces: no active local receipt, verifier, savings, or preflight route in the current tree.

- [ ] **Step 1: Remove the obsolete files exactly**

Delete only the paths listed under `### Delete`. Do not delete existing remote evidence branches, Git history, unrelated evaluation receipts, Gate B evidence, or local coordinator state.

- [ ] **Step 2: Remove obsolete Make targets and ignore rules**

Remove `ccp-plan`, `ccp-doctor`, `ccp-dry-run`, `ccp-verify`, and `ccp-savings-check` from `.PHONY` and delete their recipes. Remove only `.ccp/receipt.json`, `.ccp-mounts/`, and their dedicated comment from `.gitignore`.

- [ ] **Step 3: Run the hosted authority test**

Run `rtk uv run pytest -q tests/test_ci_workflow_contract.py`.

Expected: PASS.

- [ ] **Step 4: Search for active routing residue**

Run:

```bash
rtk rg -n "commit-ci-preflight|ccp-|receipt-gate|CCP_HYBRID" .github Makefile .gitignore scripts tests docs/knowledge/index.md docs/quality/EVIDENCE_INDEX.md
```

Expected before Task 5: matches only in documentation surfaces scheduled for reconciliation; no active workflow, Make target, script, or test match.

- [ ] **Step 5: Commit the retirement slice**

```bash
rtk git add -A .commit-ci-preflight.toml .commit-ci-policy.toml .github/workflows/receipt-gate.yml .gitignore Makefile scripts tests docs/quality docs/superpowers/specs/2026-08-24-ccp-hybrid-ci-adoption-design.md docs/superpowers/plans/2026-08-24-ccp-hybrid-ci-adoption.md
rtk git commit -S -m "ci: retire the local receipt control plane"
```

### Task 5: Publish the current authority decision and reconcile documentation

**Files:**
- Create: `docs/decisions/2026-08-30-github-actions-qualification-authority.md`
- Modify: `CHANGELOG.md`
- Modify: `docs/decisions/index.md`
- Modify: `docs/knowledge/index.md`
- Modify: `docs/knowledge/log.md`
- Modify: `docs/quality/EVIDENCE_INDEX.md`
- Modify: `docs/knowledge/inventory.json`
- Modify: `docs/knowledge/inventory.md`

**Interfaces:**
- Consumes: implemented Delivery A state and exact hosted check names.
- Produces: one active decision record and a deterministic current documentation inventory.

- [ ] **Step 1: Write the decision record**

Use frontmatter `type: Decision`, `status: stable`, `classification: active`, `owner: quality`, audiences `maintainer`, `contributor`, and `operator`, `last_verified: 2026-08-30`, and `stale_after: 2027-02-26`. The body must state:

- standard hosted runners are the public-repository authority;
- `Ironclad Gatekeeper` remains the protected context;
- local receipt routing is retired from the active tree;
- Git history preserves the experiment;
- ordinary CI does not replace package, Gate B, benchmark, or publication evidence;
- CodeQL ruleset enforcement remains a separate observed-context mutation.

- [ ] **Step 2: Reconcile indexes, log, and changelog**

Link the decision from `docs/decisions/index.md`, remove the obsolete runbook link from `docs/knowledge/index.md`, remove the two deleted evidence rows from `docs/quality/EVIDENCE_INDEX.md`, and add a newest-first `2026-08-30` knowledge-log entry that explicitly supersedes the earlier hybrid route without rewriting the older chronology.

Under `CHANGELOG.md` `[Unreleased] / Changed`, replace the hybrid local-CI bootstrap bullet with:

```markdown
- **Hosted qualification authority** — consolidate public pull-request checks on parallel GitHub-hosted Python 3.12, Python 3.13, frontend, dependency-review, and macOS/Windows Shadow lanes behind the stable `Ironclad Gatekeeper` context; retire the redundant local receipt path and pin every active Action dependency to reviewed immutable commits.
```

- [ ] **Step 3: Regenerate and curate the documentation inventory**

Run:

```bash
rtk make docs-inventory-sync
rtk make docs-inventory-md
```

Curate the new decision record as `Decision`, `active`, owner `quality`, action `keep`, and remove missing entries for deleted active documents. Never hand-edit `inventory.md`.

- [ ] **Step 4: Run documentation gates**

Run:

```bash
rtk make agents-check
rtk make docs-check
rtk make docs-audit
```

Expected: blocking gates PASS; the informational audit may report established legacy classifications but no new missing-path error.

- [ ] **Step 5: Commit the documentation reconciliation**

```bash
rtk git add CHANGELOG.md docs/decisions docs/knowledge docs/quality/EVIDENCE_INDEX.md
rtk git commit -S -m "docs(ci): record hosted qualification authority"
```

### Task 6: Final Delivery A verification and PR boundary

**Files:**
- Review: every Delivery A changed path.

**Interfaces:**
- Consumes: Tasks 1–5.
- Produces: one exact-head, locally verified Delivery A candidate ready for separately authorized push and PR creation.

- [ ] **Step 1: Run focused and full direct checks without CCP**

```bash
rtk uv run pytest -q tests/test_ci_workflow_contract.py
rtk make agents-check
rtk make docs-check
rtk make ci
```

Expected: all commands PASS.

- [ ] **Step 2: Validate workflow syntax and scope**

Run:

```bash
rtk git diff --check origin/main...HEAD
rtk git diff --name-status origin/main...HEAD
rtk rg -n "pull_request_target|@[A-Za-z][A-Za-z0-9._/-]*$" .github/workflows
```

Expected: no diff error, only planned paths, no `pull_request_target`, and no mutable Action ref.

- [ ] **Step 3: Run the required diff-level code audit**

Run the local code graph's `detect_changes(scope="compare", base_ref="origin/main")`. Expected risk: low for workflow, test, deletion, and documentation-only changes; stop on unexpected runtime symbols or HIGH/CRITICAL risk.

- [ ] **Step 4: Verify commit identity and public metadata**

Run `rtk git log --format=%B origin/main..HEAD` and `rtk git verify-commit` for each local commit. Expected: valid maintainer signatures, no assistant/tool attribution, and no co-author trailers.

- [ ] **Step 5: Stop before external mutation**

Record exact branch, full HEAD, base SHA, diff scope, and check results. Obtain explicit authorization before push or PR creation. After PR creation, fresh hosted CI must be terminal green at the exact head. Do not claim merge-queue support until one actual hosted `merge_group` result is observed.
