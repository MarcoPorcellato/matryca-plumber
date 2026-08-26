---
type: Roadmap
title: Hybrid Commit CI Preflight adoption implementation plan
description: Dependency-ordered implementation, qualification, routing, measurement, and case-study publication plan for Matryca Plumber's hybrid CCP path.
status: draft
classification: active
audience: [maintainer, contributor, operator, agent]
owner: quality
last_verified: 2026-08-26
stale_after: 2027-02-20
---

# Hybrid Commit CI Preflight Adoption Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:subagent-driven-development` (recommended) or
> `superpowers:executing-plans` to implement this plan task by task. Steps use
> checkbox syntax for durable tracking.

**Goal:** Replace duplicated pull-request Linux checks with exact-head local CCP
receipts for eligible maintainer branches while retaining fail-closed hosted
fallbacks, full `main` qualification, and publication-grade savings evidence.

**Architecture:** A three-runtime CCP v2 matrix produces one receipt for Python
3.12, Python 3.13, and Node.js 22 checks. A trusted `pull_request_target`
workflow verifies only base policy and receipt data. An observation-first router
later skips hosted Linux jobs only when the exact PR head has a valid receipt;
every uncertain or external path executes hosted CI.

**Tech Stack:** Commit CI Preflight 0.1.0 at reviewed source
`3fccc197e5055a2759ee7afe51b91133938ec904`, TOML schema 2.0, OCI
digest-pinned Linux images, GitHub Actions, Python 3.12 standard library, JSON
Schema, pytest, uv, Node.js 22, GitHub rulesets, OKF v0.2, and Matryca profile
v1.0.

**Spec:**
[`docs/superpowers/specs/2026-08-24-ccp-hybrid-ci-adoption-design.md`](../specs/2026-08-24-ccp-hybrid-ci-adoption-design.md)

## Global constraints

- Reverify `origin/main` before every implementation branch or retarget; the
  planning base is `48eae93b1152c9fe7d1f19d63de3f781b686932e`.
- Preserve the dirty primary checkout. Use isolated worktrees and never reset,
  clean, stash, or overwrite it.
- Public artifacts are English, maintainer-authored, and contain no assistant
  attribution or private local paths.
- `pull_request_target` may not execute, import, source, build, or test PR-head
  code. Evidence is bounded untrusted data.
- CCP receipts prove integrity and policy, not cryptographic producer identity.
- Fork and Dependabot PRs use hosted fallback. Fork receipts are never trusted.
- CodeQL, Dependency Review, native macOS/Windows checks, release work, and the
  exact merged-commit `main` CI remain hosted.
- Hosted Linux jobs are not skipped until parity, negative cases, routing
  observation, and separate ruleset authorization are terminal.
- Task 6 Step 0 accepts a matrix-aware CCP source boundary; an official heavy
  matrix run remains blocked until Steps 1–5 have their own fresh evidence and
  authorization.
- Unknown, denied, unsafe, malformed, stale, mismatched, cancelled, or
  non-terminal state fails closed.
- Never delete or reinterpret CCP coordinator locks, tickets, leases, journals,
  or historical receipts.
- Provider billing and monetary savings remain `null` without an independent
  provider export.
- Commit, push, PR, ruleset mutation, merge, and cross-repository publication
  are separate gates.
- Added or moved Markdown requires inventory synchronization, generated
  inventory regeneration, `make docs-check`, and `make docs-audit`.

## Delivery topology

| Delivery | Contents | Authority after merge |
| --- | --- | --- |
| PR A — Bootstrap | Config, policy, tests, runbook, observation gate, and measurement tooling; hosted CI unchanged | Hosted CI remains authoritative |
| Operational pilot | Exact-head local receipts, hosted parity, negative cases, and fallbacks | Evidence only; no skip authority |
| PR B — Routing activation | Job-level routing and required-status transition | Hybrid path after explicit authorization |
| Measurement epoch | Immutable observations and generated report | Public Matryca case-study evidence |
| CCP case-study PR | Bounded export to `commit-ci-preflight` | Separate cross-repository gate |

---

### Task 1: Finalize design, plan, and historical baseline

**Files:**

- Create: `docs/superpowers/specs/2026-08-24-ccp-hybrid-ci-adoption-design.md`
- Create: `docs/superpowers/plans/2026-08-24-ccp-hybrid-ci-adoption.md`
- Create: `docs/quality/CCP_GITHUB_ACTIONS_SAVINGS_BASELINE_2026-08-24.md`
- Modify: `docs/knowledge/log.md`
- Modify: `docs/quality/EVIDENCE_INDEX.md`
- Generate: `docs/knowledge/inventory.json`
- Generate: `docs/knowledge/inventory.md`

**Interfaces:**

- Consumes: approved design, GitHub run timestamps, CCP source anchor, active
  rulesets, and the repository documentation profile.
- Produces: canonical design, execution plan, historical baseline, evidence
  pointer, and chronology used by every later task.

- [x] **Step 1: Verify the documentation facts**

  Confirm exact base and CCP SHAs, six baseline workflow IDs, median `319`
  seconds, verifier sample `50` seconds, estimated net `269` seconds, and the
  explicit absence of billing or monetary claims.

- [x] **Step 2: Add evidence and chronology records**

  Add `CCP-SAVINGS-BASELINE-001` to `EVIDENCE_INDEX.md` with status
  `historical` and the limitation that no Matryca PR has skipped hosted work.
  Add a newest-first 2026-08-24 knowledge-log entry linking the design and
  baseline and preserving hosted CI as current authority.

- [x] **Step 3: Synchronize and verify documentation**

  ```bash
  make docs-inventory-sync
  make docs-inventory-md
  make docs-check
  make docs-audit
  git diff --check
  ```

  Expected: blocking commands exit `0`; the audit remains informational; the
  generated inventory is byte-consistent.

- [x] **Step 4: Commit only when locally authorized**

  ```bash
  git add docs/superpowers/specs/2026-08-24-ccp-hybrid-ci-adoption-design.md \
    docs/superpowers/plans/2026-08-24-ccp-hybrid-ci-adoption.md \
    docs/quality/CCP_GITHUB_ACTIONS_SAVINGS_BASELINE_2026-08-24.md \
    docs/quality/EVIDENCE_INDEX.md docs/knowledge/log.md \
    docs/knowledge/inventory.json docs/knowledge/inventory.md
  git commit --no-gpg-sign -m "docs(quality): design hybrid local CI qualification"
  ```

  Do not push in this task.

### Task 2: Add the multi-runtime CCP repository contract

**Files:**

- Create: `.commit-ci-preflight.toml`
- Create: `.commit-ci-policy.toml`
- Modify: `.gitignore`
- Create: `tests/test_ccp_adoption_contract.py`

**Interfaces:**

- Consumes: CCP schema 2.0 and the three immutable image digests in the spec.
- Produces: runtime IDs `python312`, `python313`, `node22`; stable check IDs;
  exact plan digests; and trusted repository policy.

- [x] **Step 1: Write failing contract tests**

  Use `tomllib` and these exact constants:

  ```python
  EXPECTED_IMAGES = {
      "python312": "ghcr.io/astral-sh/uv@sha256:e5b65587bce7de595f299855d7385fe7fca39b8a74baa261ba1b7147afa78e58",
      "python313": "ghcr.io/astral-sh/uv@sha256:531f855bda2c73cd6ef67d56b733b357cea384185b3022bd09f05e002cd144ca",
      "node22": "docker.io/library/node@sha256:d649c27dae7ba0137b3cef5dd75baa422c08dc3d9e3fc0c23dfb172dc3cc6436",
  }
  ```

  Reject mutable tags, shell-string commands, unknown runtimes, missing required
  checks, absolute or overlapping cache mounts, inherited secrets, and
  policy/config/image/check drift.

- [x] **Step 2: Confirm the expected RED state**

  ```bash
  uv run pytest -q tests/test_ccp_adoption_contract.py
  ```

  Expected: FAIL because the contract files do not exist.

- [x] **Step 3: Create `.commit-ci-preflight.toml`**

  Use project `MarcoPorcellato/matryca-plumber`, receipt
  `.ccp/receipt.json`, freshness `86400`, and these initial bounds:

  - Python 3.12: 4 CPUs, 6144 MiB, 512 PIDs;
  - Python 3.13: 4 CPUs, 6144 MiB, 512 PIDs;
  - Node 22: 2 CPUs, 3072 MiB, 256 PIDs.

  Enable network only for locked cold-cache dependency acquisition. Declare
  writable mounts for uv cache, two venvs, mypy, coverage, Hypothesis, npm,
  `frontend/node_modules`, and `frontend/dist`. Use explicit argv with
  `UV_CACHE_DIR`, `UV_PROJECT_ENVIRONMENT`, `UV_LINK_MODE=copy`,
  `PYTHONDONTWRITEBYTECODE=1`, and `COVERAGE_FILE`. Invoke the commands behind
  `make ci` directly. The Node runtime executes `npm ci`, lint, test, and build.

- [x] **Step 4: Freeze policy from the reviewed plan**

  ```bash
  commit-ci-preflight plan --config .commit-ci-preflight.toml --json
  ```

  Copy the emitted outer and per-runtime digests into
  `.commit-ci-policy.toml`. Bind each check to one runtime, exact image, host
  `macos`, architecture `aarch64`, runtime kind `docker_compatible`, and age
  `86400`. Never derive policy from a completed receipt.

- [x] **Step 5: Ignore only CCP-owned local state**

  Add `.ccp/receipt.json` and `.ccp-mounts/` to `.gitignore`.

- [x] **Step 6: Verify the contract and record the upstream preflight gap**

  ```bash
  uv run pytest -q tests/test_ccp_adoption_contract.py
  commit-ci-preflight plan --config .commit-ci-preflight.toml --json
  git diff --check
  ```

  Expected: tests and plan PASS. Preserve the verified source finding that
  matrix `doctor` and `dry-run` reject `runtime_id`; do not relabel a v1 render
  as v2 evidence. Block Task 6 until reviewed CCP source closes this gap.

- [x] **Step 7: Commit when authorized**

  ```bash
  git add .commit-ci-preflight.toml .commit-ci-policy.toml .gitignore \
    tests/test_ccp_adoption_contract.py
  git commit --no-gpg-sign -m "ci: define hybrid local qualification contract"
  ```

### Task 3: Add immutable savings observations and reporting

**Files:**

- Create: `docs/quality/ccp-savings/schema-v1.json`
- Create: `docs/quality/ccp-savings/baseline/2026-08-24-pr-linux.json`
- Create: `scripts/ccp_savings_report.py`
- Create: `tests/test_ccp_savings_report.py`
- Create: `tests/fixtures/ccp-savings/valid-baseline.json`
- Create: `tests/fixtures/ccp-savings/valid-eligible-pr.json`
- Create: `tests/fixtures/ccp-savings/valid-fallback.json`
- Create: `tests/fixtures/ccp-savings/invalid-billing-claim.json`
- Generate: `docs/quality/CCP_GITHUB_ACTIONS_SAVINGS_CASE_STUDY.md`

**Interfaces:**

- Consumes: immutable JSON observations in `baseline/` and `observations/`.
- Produces: `load_records`, `summarize`, `render_markdown`, and the CLI commands
  `validate`, `render`, `check`, and `promotion-status`.

- [x] **Step 1: Write failing tests**

  Require exact lowercase 40-hex SHAs, positive run/PR IDs, UTC timestamps,
  bounded elapsed seconds, PASS comparability for `ccp_saved`, exclusion of
  failed/cancelled/skipped/fallback/superseded records from the numerator,
  `max(0, candidate - verifier)` net seconds, explicit billing-source binding,
  stable sorting, and byte-identical Markdown.

- [x] **Step 2: Confirm RED**

  ```bash
  uv run pytest -q tests/test_ccp_savings_report.py
  ```

- [x] **Step 3: Implement with the Python standard library**

  Use `argparse`, `dataclasses`, `datetime`, `hashlib`, `json`, `pathlib`, and
  `statistics`. `promotion-status` passes only with at least 10 eligible
  observations over 21 days, two hosted fallbacks, and all four negative
  receipt cases.

- [x] **Step 4: Encode and render the baseline**

  Record the six workflow IDs and verifier run `32330532453`; classify it
  `observed_baseline` and keep billing fields `null`. Then run:

  ```bash
  uv run python scripts/ccp_savings_report.py validate --root docs/quality/ccp-savings
  uv run python scripts/ccp_savings_report.py render --root docs/quality/ccp-savings --output docs/quality/CCP_GITHUB_ACTIONS_SAVINGS_CASE_STUDY.md
  uv run python scripts/ccp_savings_report.py check --root docs/quality/ccp-savings --output docs/quality/CCP_GITHUB_ACTIONS_SAVINGS_CASE_STUDY.md
  uv run pytest -q tests/test_ccp_savings_report.py
  ```

  Expected: PASS; promotion threshold remains unmet.

- [x] **Step 5: Commit when authorized**

  ```bash
  git add docs/quality/ccp-savings \
    docs/quality/CCP_GITHUB_ACTIONS_SAVINGS_CASE_STUDY.md \
    scripts/ccp_savings_report.py tests/test_ccp_savings_report.py \
    tests/fixtures/ccp-savings
  git commit --no-gpg-sign -m "feat(quality): measure hosted CI savings evidence"
  ```

### Task 4: Install the trusted receipt gate in observation mode

**Files:**

- Create: `.github/workflows/receipt-gate.yml`
- Modify: `tests/test_ccp_adoption_contract.py`

**Interfaces:**

- Consumes: trusted base policy, CCP source
  `3fccc197e5055a2759ee7afe51b91133938ec904`, and
  `ccp-evidence/<head-sha>/.ccp/receipt.json`.
- Produces: exact-head status `commit-ci-preflight/receipt`; it does not yet
  authorize a hosted skip.

- [x] **Step 1: Extend failing workflow-security tests**

  Assert `pull_request_target` only for opened, synchronize, reopened,
  ready-for-review, and labelled events; permissions exactly `contents: read`
  and `statuses: write`; require a non-draft, same-repository, non-Dependabot PR
  plus the trusted `ci:observe-local-receipt` label;
  full SHA pins; trusted base checkout; SHA-derived evidence branch; no PR code
  execution, cache, secret, Docker run, project test, `make`, `uv`, or `npm`;
  and final fail-closed status on the exact head.

- [x] **Step 2: Confirm RED**

  ```bash
  uv run pytest -q tests/test_ccp_adoption_contract.py
  ```

- [x] **Step 3: Adapt the upstream cross-repository template**

  Pin the exact CCP source and full `actions/checkout` commit. Retain the
  six-minute timeout, per-PR cancellation, bounded receipt path, one-MiB input
  limit, trusted verifier-only build, and final `always()` publication.

- [x] **Step 4: Verify observation-only behavior**

  ```bash
  uv run pytest -q tests/test_ccp_adoption_contract.py
  make agents-check
  git diff --check
  ```

  Expected: PASS; unlabelled pull requests publish no receipt status,
  labelled observations fail closed, `.github/workflows/ci.yml` is unchanged,
  and hosted CI still runs fully.

- [x] **Step 5: Commit when authorized**

  ```bash
  git add .github/workflows/receipt-gate.yml tests/test_ccp_adoption_contract.py
  git commit --no-gpg-sign -m "ci: verify exact-head local receipts"
  ```

### Task 5: Document the operator and evidence-publication path

**Files:**

- Create: `docs/quality/CCP_HYBRID_CI_RUNBOOK.md`
- Modify: `Makefile`
- Modify: `docs/knowledge/index.md`
- Modify: `docs/knowledge/log.md`
- Modify: `docs/quality/EVIDENCE_INDEX.md`
- Generate: `docs/knowledge/inventory.json`
- Generate: `docs/knowledge/inventory.md`

**Interfaces:**

- Consumes: config/policy, CCP coordination rules, local resource-admission
  policy, and evidence-branch contract.
- Produces: non-destructive Make targets and a fail-closed runbook; heavy run
  and push commands remain explicit authority-bearing operations.

- [x] **Step 1: Add non-destructive Make targets**

  ```make
  ccp-plan:
	commit-ci-preflight plan --config .commit-ci-preflight.toml --json

  ccp-verify:
	commit-ci-preflight verify --receipt .ccp/receipt.json --policy .commit-ci-policy.toml --expected-commit "$$(git rev-parse HEAD)" --json

  ccp-savings-check:
	uv run python scripts/ccp_savings_report.py check --root docs/quality/ccp-savings --output docs/quality/CCP_GITHUB_ACTIONS_SAVINGS_CASE_STUDY.md
  ```

- [x] **Step 2: Write the exact fail-closed operator sequence**

  The runbook includes the read-only bootstrap sequence:

  ```bash
  git status --short --branch
  git rev-parse HEAD
  commit-ci-preflight --version
  commit-ci-preflight resource status --json
  commit-ci-preflight admission status --json
  docker context show
  docker ps -q
  make ccp-plan
  ```

  Document the matrix `doctor`/`dry-run` gap as a hard stop. Explain the future
  run sequence, how generation advances from the attempt chain, interruption,
  restart, quarantine, post-run checks, and fallback without private paths.

- [x] **Step 3: Document append-only evidence publication**

  Use a temporary worktree at the exact source SHA, branch
  `ccp-evidence/<source-sha>`, forced add of only `.ccp/receipt.json`, and normal
  non-force push. Stop if the remote branch exists with different bytes.

- [x] **Step 4: Integrate documentation authority**

  Link the runbook from the knowledge index, add evidence claim
  `CCP-HYBRID-CONTRACT-001` as `proposed`, and add the knowledge-log entry.

- [x] **Step 5: Verify and commit when authorized**

  ```bash
  make docs-inventory-sync
  make docs-inventory-md
  make docs-check
  make docs-audit
  uv run pytest -q tests/test_ccp_adoption_contract.py tests/test_ccp_savings_report.py
  git diff --check
  git add Makefile docs/quality/CCP_HYBRID_CI_RUNBOOK.md \
    docs/knowledge/index.md docs/knowledge/log.md docs/quality/EVIDENCE_INDEX.md \
    docs/knowledge/inventory.json docs/knowledge/inventory.md
  git commit --no-gpg-sign -m "docs(quality): add hybrid local CI runbook"
  ```

### Task 6: Qualify the installed CCP runtime and first exact-head receipt

**Files:**

- Modify only if the reviewed plan changes: `.commit-ci-preflight.toml`
- Modify only if plan digests change: `.commit-ci-policy.toml`
- External evidence: installation/build receipt, admission snapshots, run
  journal, image records, and `.ccp/receipt.json`

**Interfaces:**

- Consumes: reviewed CCP source, safe coordinator, admitted host, cached OCI
  images, and clean bootstrap commit.
- Produces: independently verified exact-head receipt and cleanup evidence; no
  GitHub skip authority.

**Prerequisite:** Task 6 Step 0 must accept one reviewed CCP source with
matrix-aware runtime diagnosis and rendered mount inspection, or a separately
approved equivalent. Step 0 is accepted below; hosted CI remains authoritative
until the later task gates are terminal.

- [x] **Step 0: Accept one replacement CCP source boundary**

  Record the exact clean CCP source commit, complete source-test result, binary
  digest, version, and rollback pin. Prove matrix schema compatibility across
  `plan`, `run`, `doctor`, and `dry-run`, including `runtime_id` dispatch and
  rendered read-only/writable mount inspection. Recheck receipt-schema and
  verifier compatibility for required checks, freshness, exact-head binding,
  policy binding, and incomplete terminal state. Recompute the outer and every
  per-runtime configuration digest from the reviewed plan; verify immutable
  image references and Linux arm64 selection; then rerun workflow security,
  negative-fixture, documentation, and unchanged-hosted-CI tests. Accepted
  source: `3fccc197e5055a2759ee7afe51b91133938ec904`; installed executable:
  `sha256:b8d26013800c99ba806506a0539a9ddc781bfab52f95c8f1dbdff1b65c2fcd4c`;
  rollback executable:
  `sha256:3c8621b8e834356ada379f3ad9bd916a7a884b2c4f4da7ffb606744ab79b4fa8`.
  Qualified source tree: `9e478c1489a9926772e8ab8bea21bd57470494b6`; five
  required checks and independent verification PASS in source-test receipt:
  `sha256:2b6aec06b8b6cf6e07736c8e713dd05c03d439640c608cc52af124e93de290e7`.
  The plan-derived outer digest is
  `sha256:6f418ac6b90664e9ebbec4a5c7e28af946f0430250fcaf28b6a1f62196b4a635`.
  This closes only the replacement-source boundary: Steps 1–6 and M2 remain
  incomplete, hosted CI remains authoritative, and no official receipt exists.

- [ ] **Step 1: Diagnose coordinator state read-only**

  Preserve outputs from version, resource status, admission status, recover
  status, cache inventory, Docker context, and container inventory. Do not alter
  tickets or leases.

- [ ] **Step 2: Stop for narrow repair authority if required**

  If unsafe layout persists, identify exact affected objects and the documented
  recovery primitive. Request only that repair or rebuild authority.

- [ ] **Step 3: Build and test reviewed CCP source**

  In an isolated clean CCP worktree at the exact source commit, run the locked
  full test contract and preserve source SHA, binary digest, version, and test
  receipt before installation.

- [ ] **Step 4: Cache and verify OCI architecture**

  Confirm every configured digest resolves to Linux arm64. Pull only after
  resource/admission authorization; record image ID and repository digest.

- [ ] **Step 5: Run the official exact-head matrix**

  Require clean source, supported/enforced `admit`, inactive coordinator with
  queue zero, responsive runtime, and no unaccounted containers. Use a new
  generation and stop on any failure.

- [ ] **Step 6: Verify and close M2**

  Verify receipt against trusted policy and expected commit. Recheck admission,
  resources, containers, check/runtime bindings, receipt digest, and source
  cleanliness. This does not enable hosted skips.

### Task 7: Run parallel parity, negative, and fallback pilots

**Files:**

- Add per run: `docs/quality/ccp-savings/observations/<date>-pr-<number>-<sha12>.json`
- Generate: `docs/quality/CCP_GITHUB_ACTIONS_SAVINGS_CASE_STUDY.md`
- Modify the design evolution ledger only when milestone state changes

**Interfaces:**

- Consumes: representative exact PR heads, hosted CI metadata, local receipts,
  verifier runs, and negative/fallback scenarios.
- Produces: comparable evidence; no ruleset or skip authorization.

- [ ] **Step 1: Qualify five representative change classes**

  Run CCP and full hosted CI for one Python, frontend, documentation,
  locked-dependency, and mixed change. Compare required check IDs and terminal
  dispositions. A mismatch resets the parity count after correction.

- [ ] **Step 2: Prove seven negative receipt cases**

  Prove missing, malformed JSON, stale, corrupt-digest, wrong-SHA,
  wrong-policy, and incomplete or non-terminal receipts fail using disposable
  evidence or verifier fixtures. Generate mutations from the accepted receipt
  schema and verifier source rather than duplicating verifier logic in Matryca.
  Never alter valid historical evidence.

- [ ] **Step 3: Prove hosted fallback**

  Exercise one fork-shaped route and one maintainer-labelled fallback. Both run
  full hosted Ironclad and do not accept a receipt as a waiver.

- [ ] **Step 4: Validate observations**

  ```bash
  uv run python scripts/ccp_savings_report.py validate --root docs/quality/ccp-savings
  uv run python scripts/ccp_savings_report.py check --root docs/quality/ccp-savings --output docs/quality/CCP_GITHUB_ACTIONS_SAVINGS_CASE_STUDY.md
  ```

- [ ] **Step 5: Issue M3 GO or NO-GO**

  GO requires five comparable pairs, seven fail-closed negatives, and two hosted
  fallbacks. NO-GO preserves results and leaves hosted CI authoritative.

### Task 8: Observe and activate routing in a separate PR

**Files:**

- Modify: `.github/workflows/receipt-gate.yml`
- Modify: `.github/workflows/ci.yml`
- Modify: `tests/test_ccp_adoption_contract.py`
- Modify: `docs/quality/CCP_HYBRID_CI_RUNBOOK.md`
- Modify: `docs/quality/EVIDENCE_INDEX.md`

**Interfaces:**

- Consumes: terminal M3 GO and explicit ruleset authorization.
- Produces: exact-head `commit-ci-preflight/receipt-or-fallback` status and
  job-level routing that preserves required `Ironclad Gatekeeper` semantics.

- [ ] **Step 1: Write failing routing truth-table tests**

  Assert full Linux work on push to `main`; receipt-required internal route;
  fail-closed missing/invalid internal receipt; hosted fork, Dependabot, and
  trusted-label fallback; job-level rather than workflow-level skip; unchanged
  retained jobs; and current-head status binding.

- [ ] **Step 2: Publish the combined status in observation mode**

  Keep hosted-job conditions unchanged. Exercise opened, synchronize, reopened,
  ready-for-review, label add/remove, and head-update events. Prove that an old
  head status cannot satisfy the current head.

- [ ] **Step 3: Obtain separate ruleset authority**

  Present exact current ruleset JSON and the proposed addition. Add the combined
  context as required only after latest-head observation. Keep
  `Ironclad Gatekeeper` required and integration-bound.

- [ ] **Step 4: Activate job-level conditions**

  Change only duplicated Linux jobs. Retained jobs and `main` stay in their
  current event scope. The trusted fallback label selects hosted work; it never
  creates a synthetic PASS.

- [ ] **Step 5: Verify activation and rollback**

  Run one eligible receipt route and one forced fallback. Verify all required
  contexts, expected skips, no pending workflow, no unresolved threads, and a
  full hosted run after signed squash. Preserve a one-commit rollback restoring
  unconditional hosted Linux work without deleting evidence.

- [ ] **Step 6: Promote the evidence claim**

  Change `CCP-HYBRID-CONTRACT-001` from `proposed` to `verified` only after
  terminal activation evidence. Keep the baseline historical.

### Task 9: Complete the measurement epoch and Matryca case study

**Files:**

- Add: `docs/quality/ccp-savings/observations/*.json`
- Generate: `docs/quality/CCP_GITHUB_ACTIONS_SAVINGS_CASE_STUDY.md`
- Modify: `docs/quality/EVIDENCE_INDEX.md`
- Modify: `docs/knowledge/log.md`

**Interfaces:**

- Consumes: activated hybrid PRs, fallbacks, failures, exclusions, and optional
  provider billing export.
- Produces: publication-candidate summary and exact export digest.

- [ ] **Step 1: Accumulate the minimum window**

  Record at least 10 eligible comparable PRs over at least 21 days and at least
  two successful hosted fallbacks. Record failed, cancelled, excluded, and null
  results rather than sampling only successes.

- [ ] **Step 2: Generate the bounded statistics**

  Report count, median, interquartile range, candidate hosted seconds, verifier
  seconds, net estimated seconds, fallback/failure rates, and local elapsed
  time. Keep billing fields null unless independently sourced.

- [ ] **Step 3: Run the promotion gate**

  ```bash
  uv run python scripts/ccp_savings_report.py promotion-status --root docs/quality/ccp-savings --json
  ```

  Expected: PASS before any CCP repository case-study PR.

- [ ] **Step 4: Update authority without rewriting history**

  Add a new evidence claim for the bounded epoch and a knowledge-log entry. Do
  not modify the 2026-08-24 baseline facts.

### Task 10: Prepare the cross-repository CCP case study

**Files in `commit-ci-preflight`:**

- Create: `docs/case-studies/matryca-plumber.md`
- Modify: the current documentation index identified from live `origin/main`

**Interfaces:**

- Consumes: promotion PASS, generated Matryca report, observation digests, run
  URLs, and current CCP documentation policy.
- Produces: bounded public case study; no universal savings or identity claim.

- [ ] **Step 1: Reaudit current CCP main**

  Fetch `origin/main`, preserve its dirty primary checkout, create an isolated
  worktree, identify current case-study conventions, and revalidate every CCP
  source/policy version used during the epoch.

- [ ] **Step 2: Write the bounded case study**

  Include methodology, eligibility, workload split, window, statistics,
  fallback and negative results, local resource and maintenance costs, unsigned
  receipt boundary, exact source links, and reproducibility steps. Report
  positive, null, or negative savings honestly.

- [ ] **Step 3: Verify source bindings and documentation gates**

  Recompute export digests, test links, run the CCP documentation checks, and
  reject private paths, secrets, attribution, or unsupported billing claims.

- [ ] **Step 4: Stop at the external publication gate**

  Present exact branch/head/diff/check evidence and request separate push and PR
  authorization. Do not publish automatically.

### Task 11: Final programme audit

**Files:**

- Modify: `docs/superpowers/specs/2026-08-24-ccp-hybrid-ci-adoption-design.md`
- Modify: `docs/superpowers/plans/2026-08-24-ccp-hybrid-ci-adoption.md`
- Modify: `docs/quality/EVIDENCE_INDEX.md`
- Generate: `docs/knowledge/inventory.json`
- Generate: `docs/knowledge/inventory.md`

**Interfaces:**

- Consumes: every receipt, merged PR, active ruleset, observation, publication
  gate, and documentation check.
- Produces: requirement-by-requirement terminal disposition and restart-safe
  handoff for residual gates.

- [ ] **Step 1: Audit every design completion item**

  Mark complete only with exact current evidence. Preserve blocked, negative,
  historical, and external-gate states.

- [ ] **Step 2: Run final exact-head gates**

  ```bash
  make agents-check
  make docs-check
  make docs-audit
  make ccp-plan
  make ccp-savings-check
  make ci
  git diff --check
  ```

  An official CCP run is additional evidence and still requires fresh resource
  and admission PASS.

- [ ] **Step 3: Recheck external state**

  Verify exact PR heads, checks, expected skips, review threads, rulesets,
  merges, evidence branches, and any CCP case-study PR. Never transfer evidence
  across SHAs.

- [ ] **Step 4: Close with an evidence-bounded report**

  Report delivered behavior, observed savings, provider-confirmed savings or
  `none`, residual risks, rollback state, and next gate. Completion requires
  terminal evidence for every applicable design checkbox.

## Self-review checklist

- [ ] Every design scope item maps to a task.
- [ ] No task lets `pull_request_target` execute PR code.
- [ ] Hosted fallback is validation, not a waiver.
- [ ] Full hosted `main` qualification remains present.
- [ ] Receipt producer identity is not overclaimed.
- [ ] Billing and monetary fields cannot be inferred.
- [ ] Failed and excluded observations remain visible.
- [ ] Ruleset mutation and cross-repository publication retain separate gates.
- [ ] Documentation inventory and generated views are included.
- [ ] Runtime-derived digests and generations have deterministic acquisition
      rules rather than unresolved implementation decisions.
