# On-Demand Release Package Qualification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce fail-closed, exact-commit pre-publication package and platform evidence for the RC4 Stage A decision without adding work to routine pull-request CI.

**Architecture:** Keep the existing release builder and canonical wheel/sdist pair unchanged. A repository-owned verifier binds those exact bytes to independent build-job outputs, checks archive and installed-package integrity, and emits sanitized receipts. The wheel is installed directly. Because an sdist must be built to install it, each platform uses a separate private PEP 517 build environment to build a temporary wheel from the authenticated original sdist, then installs that wheel into the clean sdist runtime environment. A manually dispatched workflow runs the verifier and frozen focused tests on Linux, macOS arm64, and Windows; an aggregator accepts only complete all-green evidence. The current Windows launcher boundary is NO-GO, so this workflow is not yet dispatchable as a qualification and cannot yield Stage A PASS.

**Tech Stack:** Python 3.12, pytest, uv, GitHub Actions YAML, SHA-256, Python `zipfile`/`tarfile`/`importlib.metadata`, existing static TCKs and release builder.

**Spec:** `docs/superpowers/specs/2026-09-27-on-demand-release-package-qualification-design.md`

## Global Constraints

### Implementation status — 2026-09-27

Local implementation is **in progress**, not qualification evidence. The sdist
helper, workflow lane, and receipt binding are now present in the isolated
worktree. The earlier integrated focused run with 142 passes and 2 receipt
assertion failures on error ordering is historical. After repairing raw PEP 517
dynamic-expression and extras handling, the latest integrated package suite is
**225 passed, 1 expected skip** before final typing additions. The subsequent
exact clone-local, locked/offline full `make ci` passed: **2443 passed, 6
skipped, 4 warnings, and 84.73% coverage**, using four pytest workers; all
static, documentation, and type gates were green. Earlier sandbox `ps` and
shared-primary-venv coverage failures were diagnostic history only, not the
final run. Sol's final quality and security reviews are **PASS_WITH_NOTES**. The
process-containment review separately
passed with notes after 21 focused tests; none of these scoped reviews is a
public qualification result. The aggregate uv
0.12.19 archive/hash/active-binary check is locally implemented before its
`uv sync` and passed 14 focused workflow tests. These remain local implementation
and review evidence, not hosted qualification. The required Windows row still
exits NO-GO. The workflow now pins official uv
`0.12.19`; the official
[GHSA-2cv4-cqwr-gwf7 advisory](https://github.com/astral-sh/uv/security/advisories/GHSA-2cv4-cqwr-gwf7)
marks `>=0.12.7,<0.12.18` affected by Windows wheel-extraction path traversal,
with `>=0.12.18` patched. The [0.12.19 release page](https://github.com/astral-sh/uv/releases/tag/0.12.19)
links verified commit `bea138450f0e620a4ce5765b0e38cff7b9f0799f`; its official
[Windows x64 archive checksum](https://releases.astral.sh/github/uv/releases/download/0.12.19/uv-x86_64-pc-windows-msvc.zip.sha256)
is `6dbb02d79e419522f1c500f0adb1cddcff0cda7d59b0d66ea7f5e3b4a1b2f5f0`.
The superseded `0.12.16` pin was in the affected range and remains historical
only; never use it for Windows wheel installation. The Windows row exits before
installation and remains NO-GO pending launcher provenance and native platform
evidence. The SHA-pinned `astral-sh/setup-uv` action is a trusted bootstrap
boundary: action-internal code runs before workflow-owned verification. The
workflow must independently verify the official uv `0.12.19` archive and active
binary before any workflow-owned uv invocation, including `uv sync`; the
aggregate job must repeat that check before its own `uv sync`. The guarantee is
“verified before workflow-owned uv use,” not “verified before any action-internal
code." Review notes retain three scope limits: the PEP 518 environment record
observes package names and versions, not package artifact hashes; two official
uv archive downloads are not byte-count capped before digest verification; and
tested process containment is not a hostile-code sandbox. Windows launcher
provenance and native platform evidence remain unresolved, so the workflow is
not dispatchable as a Stage A qualification. No hosted dispatch, Stage A PASS,
or stable-release claim is implied. Update this checkpoint only after the
Windows launcher/native evidence gates are complete.

- Reverify protected `main`, tree, version, `uv.lock`, action pins, and existing CI before editing or selecting a candidate. The planning anchor `b56254854b28701bd7f8b2e83a8ede58915f309d` is historical, not a release candidate.
- Keep `.github/workflows/ci.yml`, its required `Ironclad Gatekeeper`, and `.github/workflows/release.yml` unchanged. An optional out-of-band content-ledger output may be added to `scripts/build_release_artifacts.py`; default distribution bytes and tag-driven invocation must remain unchanged.
- New workflow: `workflow_dispatch` from `refs/heads/main` only, one full lowercase 40-character input SHA equal to `github.sha`, clean exact checkout, `contents: read` only, full-SHA-pinned Actions, no publication or write path.
- One wheel and one source distribution from one selected commit. Independently export verified filenames, sizes, SHA-256 values, artifact ID/digest and run ID; each platform checks these before installation. A manifest inside the artifact alone is insufficient.
- Check complete archive member safety and ownership; compare all 26 static contract/TCK resources across source, archives, and two isolated installs per platform. Require installed `RECORD` completeness and verified distribution-owned payload; allow only explicit, tested installer-generated exceptions. Stage A qualification installs must be fresh and cache-free: any package-owned `.pyc` or `.pyo` is a failure, not an exception to repair in place.
- Python 3.12 jobs: `ubuntu-24.04` x64, `macos-15` arm64, `windows-2022` x64; verify actual architecture at runtime. Locked runtime dependencies; neither install may import Plumber from the checkout.
- Required platform or receipt failure, cancellation, timeout, unexpected skip, or missing dependency means NO-GO. Stage A is separate from tag/publication authority and post-publication Gate B.
- Generator metadata is not complete PEP 517 build-environment provenance. Sdist qualification must record the exact observed backend package-name/version manifest before and after a no-isolation build from the authenticated original sdist, verify declared and backend-returned dynamic requirements against that manifest without installing anything opportunistically, and bind the temporary wheel name, size, and SHA-256. The temporary wheel is only an installation vehicle; it is never added to or substituted for the canonical release `dist` pair. These checks establish which exact sdist and observed build environment produced the tested install; they do not claim reproducible builds.
- Windows launcher provenance and native Windows package evidence remain NO-GO. Do not dispatch the workflow, claim Stage A PASS, or make stable-release claims while any required platform is deliberately rejected or not qualified.
- Historical Windows launcher research remains bounded: the [official uv 0.12.16 release](https://github.com/astral-sh/uv/releases/tag/0.12.16) linked signed release commit `761ff1379b3b79f61fc8d421dfe4fe064834e084`, and GitHub marked that commit signature verified. This old tool pin was vulnerable under GHSA-2cv4-cqwr-gwf7 and must not be used for Windows wheel installation. The current workflow instead pins patched uv `0.12.19`, with the exact official [Windows x64 archive checksum](https://releases.astral.sh/github/uv/releases/download/0.12.19/uv-x86_64-pc-windows-msvc.zip.sha256) recorded above. The tag-pinned launcher source/content path and exact executable-template provenance used for launcher generation have not yet been verified. `RECORD` and the `MZ` header alone are insufficient. Admission still requires exact tag/source resolution, an independent template-and-payload verifier, process-tree containment review, and native Windows x64 tests.
- Security advisory gate: [GHSA-2cv4-cqwr-gwf7](https://github.com/astral-sh/uv/security/advisories/GHSA-2cv4-cqwr-gwf7) identifies uv `>=0.12.7,<0.12.18` as affected by Windows wheel-install path traversal; uv `>=0.12.18` is patched. The workflow now pins `0.12.19` and verifies official per-platform archive checksums. The superseded `0.12.16` pin was affected and remains historical only; the current Windows row still fails before any wheel install. The patched tool pin does not qualify the Windows launcher or platform: retain NO-GO until source/template provenance and native tests pass.
- All synthetic tests use disposable roots. Do not mount a user graph or claim Logseq DB support. Standard hosted CI is the full public-repository gate; no CCP heavy run.
- Run local code-graph impact analysis before editing an existing symbol and changed-flow analysis before any later commit. The index was stale during planning; refresh it before code execution or use current-source analysis if it remains unavailable.
- Commit, push, PR, workflow dispatch, issue mutation, merge, branch deletion, tag and release are separate authorization boundaries. This plan itself grants none.

## Review Focus

1. A renamed wheel plus matching edited manifest must fail against independent build outputs before installation (Task 1).
2. An archive with a duplicate path, symlink, traversal, extra unowned file, or missing ordinary Python module/frontend asset must fail even when all 26 required resources exist (Task 1).
3. An installed `RECORD` with an empty hash for a distribution-owned frontend file must fail, while an explicitly allowed `RECORD`-self exception passes (Task 2).
4. A Windows timeout followed by a healthy parse must be tested through the real worker lifecycle, without assuming Unix `SIGKILL` semantics (Task 3).
5. A skipped matrix child or missing platform receipt must make the final workflow gate fail, not pass because another platform succeeded (Task 4).

---

## File Structure

- `scripts/release_qualification/__init__.py`: typed, CI-only package boundary.
- `scripts/build_release_artifacts.py`: optional out-of-band content ledger captured inside the disposable source/frontend build before staging is removed; no default-output change.
- `scripts/release_qualification/bundle.py`: immutable source/archive binding, exact expected-versus-actual member sets, resource parity, two-line manifest, and independent handoff checks.
- `scripts/release_qualification/installed.py`: isolated interpreter provenance, `RECORD` accounting, exact installed resources, and the three installed TCKs; sdist verification is bound to the original sdist even though its tested install is built through a temporary wheel.
- `scripts/release_qualification/sdist_build.py`: qualification-only PEP 517 build-environment inspection, dynamic-requirement verification, no-build-isolation temporary-wheel build from the bound original sdist, and before/after manifest and output binding.
- `scripts/release_qualification/focused.py`: frozen platform-specific pytest node selections and sanitized result counts.
- `scripts/qualify_release_package.py`: small CLI exposing `build-handoff`, `verify-handoff`, `prepare-sdist-build`, `verify-installed`, `run-focused`, and `verify-receipts`; no release or network operation.
- `tests/test_release_package_bundle.py`, `tests/test_release_package_installed.py`, `tests/test_release_package_focused.py`: synthetic positive/negative tests for the corresponding modules.
- `.github/workflows/release-package-qualification.yml` and `tests/test_release_package_workflow_contract.py`: manual source/build/platform/aggregate workflow and semantic mutation-resistant contract tests.
- `tests/test_release_package_sdist_build.py`: synthetic positive/negative coverage for PEP 517 source-distribution build provenance.
- `docs/RELEASE_PROCESS.md`, `docs/quality/V2_0_1_RC4_RELEASE_QUALIFICATION_PLAN_2026-09-06.md`, `docs/knowledge/log.md`, `docs/knowledge/inventory.json`, `docs/knowledge/inventory.md`, and `CHANGELOG.md`: narrowly reconcile operator instructions, Stage A evidence location, documentation inventory, and changelog decision. Do not rewrite historical receipts.

### Task 1: Verify the single build and bind its handoff

**Files:** Modify `scripts/build_release_artifacts.py` and `tests/test_build_release_artifacts.py`; create `scripts/release_qualification/__init__.py`, `scripts/release_qualification/bundle.py`, `tests/test_release_package_bundle.py`; start `scripts/qualify_release_package.py` with only the two handoff commands.

**Interfaces:** `build_release_artifacts(repo_root: Path, output_dir: Path, *, content_ledger_path: Path | None = None) -> tuple[Path, Path]` preserves its old two-argument behavior and optionally writes a JSON ledger outside `output_dir` after a successful build. Ledger lists selected tracked source files, exact generated frontend file names/hashes, and known generated metadata classes. `BundleBinding` records `source_commit`, `source_tree`, `version`, `wheel_name`, `wheel_size`, `wheel_sha256`, `sdist_name`, `sdist_size`, `sdist_sha256`, `wheel_inventory_sha256`, and `sdist_inventory_sha256`. `build_binding(repository: Path, dist: Path, ledger: Path, expected_commit: str) -> BundleBinding` verifies then emits values. `verify_handoff(dist: Path, manifest: Path, expected: BundleBinding) -> None` checks downloaded bytes against independent expected values and the manifest. `build-handoff` writes one validated, compact `binding_json` output to `GITHUB_OUTPUT` only after verification; `verify-handoff` parses that value from the `EXPECTED_BINDING_JSON` environment variable populated from `needs.build-bundle.outputs.binding_json`, never from the downloaded artifact. Artifact ID/digest come from the pinned upload step, not from files inside the artifact.

- [ ] Write failing synthetic tests: exactly one wheel/sdist with the current normalized version passes; missing/extra distribution, duplicate archive path, traversal, link/special member, compiled cache, metadata drift, unowned extra file, and missing or byte-changed public resource each fail. Remove an ordinary tracked `src` module or one generated frontend asset from both archives while retaining the ledger: each case must fail.
- [ ] Test a pair and manifest changed together while the expected `BundleBinding` stays fixed; `verify_handoff` must reject before any install. Test malformed/missing output values and a mismatched source commit/tree.
- [ ] Run `rtk uv run pytest -q -o addopts= tests/test_release_package_bundle.py`; confirm the new tests fail for missing interfaces.
- [ ] Add an optional builder ledger path and test that default invocation still creates only the same two distribution files. Capture tracked module/resource names and bytes from the selected source snapshot and generated frontend names/hashes before staging cleanup; write ledger only after successful archive build to a path outside `dist`.
- [ ] Implement safe archive-member canonicalization and derive exact mandatory member sets for wheel and sdist from the ledger: every tracked importable `src` module, copied public contract/TCK resource, and every generated frontend asset must appear with matching bytes. Categorize remaining tracked sdist inputs and backend-generated metadata under explicit rules; compare expected and observed sets rather than only an allowed subset. Reuse `verify_release_archives` without weakening it.
- [ ] Implement canonical two-line `SHA256SUMS` and `BundleBinding` serialization with strict names, sizes, SHA-256 syntax, source ID, and stable member-inventory digests. Reject symlinks/special members, duplicate normalized names, case-colliding names, and any unexpected category.
- [ ] Implement `build-handoff` and `verify-handoff` CLI subcommands; require the out-of-band ledger, validate output path types, and never write a partial success output. Run the focused tests and `tests/test_build_release_artifacts.py`; expect PASS.
- [ ] Review archive rules against a real diagnostic pair but do not use that pair as future candidate evidence. Check `rtk uv run ruff check scripts/release_qualification scripts/qualify_release_package.py tests/test_release_package_bundle.py` and `rtk uv run mypy scripts/release_qualification scripts/qualify_release_package.py`; expect PASS.
- [ ] Preserve a task checkpoint. Commit only under a separate explicit authorization.

### Task 2: Qualify both isolated installed distributions

**Files:** Create `scripts/release_qualification/installed.py`, `scripts/release_qualification/sdist_build.py`, `tests/test_release_package_installed.py`, and `tests/test_release_package_sdist_build.py`; extend `scripts/qualify_release_package.py` with `verify-installed`, `prepare-sdist-build`, and the required exact artifact/binding arguments.

**Interfaces:** `verify_installed(python: Path, binding: BundleBinding, source_root: Path, kind: Literal["wheel", "sdist"], *, artifact: Path) -> InstalledReceipt`. The required keyword-only `artifact` is the exact bound release wheel or original sdist associated with the selected environment. Before deriving installed expectations, authenticate its exact bound name, size, SHA-256, and member-inventory digest against independent `BundleBinding`; parse only within the limits in `bundle.py`. For the sdist runtime, installation uses a separately recorded temporary wheel built from the exact authenticated sdist; `verify_installed(..., kind="sdist", artifact=<original-sdist>)` must still authenticate and derive expected payload from the original archive. Do not add fields to `BundleBinding`. Derive generated frontend and install expectations from the authenticated archive, not Git-only frontend state. `InstalledReceipt` contains interpreter/platform identity, installed version and location class, `RECORD` inventory digest, 26-resource digest, three TCK outcomes, and dependency-version digest; it contains no local paths or graph content. Verify installed files and `RECORD` before any Plumber import or TCK execution. `-I` alone does not prevent environment `.pth` startup code: use a site-disabled (`-I -S`) pre-integrity bootstrap, then import only after integrity passes.

The qualification-only CLI is `prepare-sdist-build --artifact BOUND_SDIST --source-root CLEAN_BOUND_CHECKOUT --python PY312 --uv UV_BINARY --uv-sha256 FULL_SHA --wheel-output EMPTY_PRIVATE_DIRECTORY`, with independent `EXPECTED_BINDING_JSON`. It verifies the sdist and clean checkout bind to the same source/tree; safely extracts only validated members; creates a private build venv from static PEP 518 requirements; records the complete observed package name/version set; queries `get_requires_for_build_wheel`; verifies each dynamic requirement against already observed package versions without installing it; runs `uv build --wheel --no-build-isolation` against the authenticated extraction; and rejects package-manifest or source/archive drift. It emits a sanitized receipt binding source/tree, original sdist, uv identity, backend, static/dynamic requirements and satisfiers, complete build package set, and temporary-wheel name/size/SHA-256. Exactly one expected temporary wheel may appear in its empty private output directory. It remains outside canonical `dist` and is never canonical. This proves exact inputs and the observed environment for one attempt, not reproducibility.

- [ ] Write failing tests using synthetic site-packages and a tiny real disposable venv: installed import resolving to checkout, missing/malformed `RECORD`, unlisted installed file, traversal, empty hash/size for distribution payload, missing frontend file, one tampered contract byte, and missing TCK fail. Also reject artifact name, size, SHA-256, or inventory mismatch before deriving installed expectations. Reject package-owned `.pyc`/`.pyo` before import whether listed, unlisted, hashed, or hash-empty; do not delete caches to obtain a pass. Account for `RECORD` self and narrow installer-generated metadata without demanding fields that the installed-project format makes optional.
- [ ] Add failing synthetic tests for the separate sdist-build lane: bind only the original sdist; reject unsafe or extra tar members and altered sdist/source tree; accept static and backend-dynamic requirements already satisfied by the observed package manifest; reject malformed, unsupported, absent, incompatible, URL/direct-reference, or duplicate requirements; reject manifest drift, wrong temporary-wheel identity, extra wheel, or a non-empty output directory. Verify the temporary wheel stays outside canonical `dist` and is not passed as the sdist verifier's `artifact`.
- [ ] Run `rtk uv run pytest -q -o addopts= tests/test_release_package_installed.py`; confirm failure for missing interfaces.
- [ ] Implement strict `RECORD` parsing: normalized unique paths, confinement to the selected venv, complete installed-file accounting, SHA-256 or stronger hash/size verification for archive-owned payload and metadata, and a closed exception allowlist for installer-generated metadata. Fresh Stage A environments must contain no package-owned bytecode before or after verifier probes; use an external fresh bytecode-cache prefix for those probes. This is stricter than general installed-package validity. Do not assume PyPA requires hashes for every row.
- [ ] Add required keyword-only `artifact: Path` to `verify_installed`. First authenticate its exact name, size, SHA-256, and inventory digest using the corresponding independent `BundleBinding` fields; bounded-parse that authenticated archive before deriving expected installed bytes. For a wheel, map package payload members directly from the wheel and allow only explicit installer metadata transformations. For an sdist, strip exactly its canonical versioned top-level directory, map source payload into the installed package, and allow only explicit backend/build/install metadata transformations. Keep generated frontend bytes archive-derived; never treat Git-only frontend state as authority. Keep `BundleBinding` schema unchanged.
- [ ] Verify complete installed-file and `RECORD` integrity before importing Plumber or running TCKs. Use a site-disabled `-I -S` bootstrap for pre-integrity checks: `-I` alone does not suppress `.pth` processing from the target environment. Only after integrity passes, run a separate isolated probe and the three installed TCKs; capture bounded sanitized outcomes and reject checkout imports.
- [ ] For workflow invocation, create separate wheel and sdist runtime environments plus the private sdist-build environment. Install runtime dependencies from selected `uv.lock` without installing the project. Install the canonical wheel directly in the wheel environment; build a temporary wheel from the exact bound sdist, then install only that temporary wheel in the sdist runtime environment. Use no dependency re-resolution. Fail if either installed runtime set differs from the lock-selected set.
- [ ] Add a distinct disposable PEP 517 build environment for the sdist lane. Create it from the authenticated original sdist's `[build-system]` static requirements; record the complete exact observed build-environment package-name/version manifest. Inspect and explicitly verify both declared PEP 518 requirements and requirements returned by the backend's PEP 517 dynamic-requirement hook against that manifest. If a requirement is malformed, unsupported, absent, or version-incompatible, fail closed; never resolve or install a missing dynamic requirement during verification.
- [ ] Run `uv build --wheel --no-build-isolation` against the extracted, authenticated original sdist in that private build environment. Snapshot the complete observed package manifest before and after; any drift fails. Validate the temporary wheel's expected project/version/name, size, and SHA-256, and place it outside canonical `dist`. Record its identity and the build-environment manifest in the sanitized sdist receipt. Do not call this a reproducible-build result and do not substitute the temporary wheel for either the canonical release wheel or original bound sdist.
- [ ] Install the temporary wheel with `--no-deps` into the separate clean sdist runtime environment after installing only the selected lock-bound runtime dependencies. Invoke `verify-installed` with `--kind sdist` and the exact original sdist path so source identity, archive payload, and receipt remain bound to `BundleBinding`; verify that the installed payload corresponds to the authenticated sdist through the separately recorded temporary-wheel build chain. Keep the canonical wheel lane unchanged.
- [ ] Keep Windows qualification NO-GO until each installer-generated launcher executable is authenticated in full against an independently pinned, reviewed installer artifact and architecture-specific template, including interpreter binding, entry-point payload, and trailing bytes. `MZ`, PE structure, or a self-consistent `RECORD` alone is insufficient. Require native Windows x64 evidence for both installation kinds; never convert this blocker into a skipped or partial platform pass.
- [ ] Run installed-verifier tests plus `tests/test_plumber_consumer_package_v1_tck.py`, `tests/test_plumber_graph_read_v1_tck.py`, and `tests/test_plumber_graph_topology_v1_tck.py`; expect PASS. Run Ruff and mypy on new files; expect PASS.
- [ ] Preserve a task checkpoint. Commit only under a separate explicit authorization.

### Task 3: Freeze candidate-bound focused controls

**Files:** Create `scripts/release_qualification/focused.py`, `tests/test_release_package_focused.py`; extend `scripts/qualify_release_package.py` with `run-focused`.

**Interfaces:** `focused_nodes(platform: Literal["linux", "macos", "windows"]) -> tuple[str, ...]` returns immutable explicit pytest node IDs. `run-focused` runs only that list from the selected checkout, fails on collection errors/skips, and emits counts bound to source SHA and platform.

- [ ] Write failing tests asserting the exact node lists and rejection of unknown platform, missing node, collection failure, or unexpected skip. Assert Windows selection contains a deterministic timeout followed by healthy parse and no Unix-only crash test.
- [ ] Freeze these 17 Linux/macOS node IDs exactly; do not replace them with file-level globs:

  ```text
  tests/test_og_parser_identity_adapter.py::test_parser_receives_exact_admitted_snapshot_from_one_source_read
  tests/test_og_parser_identity_adapter.py::test_adapter_rejects_oversize_snapshot_before_parser_invocation
  tests/test_og_parser_identity_adapter.py::test_adapter_rejects_same_size_replacement_inode_after_descriptor_read
  tests/test_og_topology_session_read.py::test_og_topology_uses_one_complete_parser_snapshot_without_content_leakage
  tests/test_og_topology_session_read.py::test_og_topology_rejects_unresolved_block_reference
  tests/test_og_topology_session_read.py::test_og_topology_rejects_title_collision
  tests/test_og_topology_session_read.py::test_og_topology_excludes_aggregate_page_property_refs
  tests/test_og_identity_session_read.py::test_consumer_receives_only_plumber_owned_identity_response
  tests/test_og_identity_session_read.py::test_close_is_idempotent_and_rejects_every_later_identity_read
  tests/test_og_identity_session_read.py::test_identity_rejects_foreign_graph_binding
  tests/test_logseq_db_official_host_capability_protocol.py::test_no_supported_fixture_is_committed_before_runtime_evidence
  tests/test_bounded_page_parse.py::test_controlled_hanging_child_times_out_and_kills_worker
  tests/test_bounded_page_parse.py::test_timeout_then_healthy_parse_gets_new_pid
  tests/test_bounded_page_parse.py::test_no_stale_result_after_timeout
  tests/test_bounded_page_parse.py::test_worker_crash_recovers_bounded
  tests/test_ast_cache_bounded_parse.py::test_bounded_timeout_does_not_publish_partial_graph
  tests/test_ast_cache_bounded_parse.py::test_incremental_timeout_preserves_exact_last_complete_graph
  ```
- [ ] Freeze Windows nodes to `tests/test_bounded_page_parse.py::test_controlled_hanging_child_times_out_and_kills_worker`, `::test_timeout_then_healthy_parse_gets_new_pid`, `::test_no_stale_result_after_timeout`, and `::test_worker_survives_success_and_shuts_clean`; do not include `::test_worker_crash_recovers_bounded` because it uses Unix `SIGKILL`. Keep the Windows package/TCK lane separate and required.
- [ ] Run `rtk uv run pytest -q -o addopts= tests/test_release_package_focused.py` and the Linux/macOS node selection locally. The Windows selection needs terminal hosted Windows evidence; a local collection or macOS pass does not disposition it.
- [ ] Preserve the full node list and counts in sanitized output. Any later node-list change requires a new source commit and new candidate qualification. Commit only under a separate explicit authorization.

### Task 4: Wire the manual workflow and terminal gate

**Files:** Create `.github/workflows/release-package-qualification.yml`, `tests/test_release_package_workflow_contract.py`; extend `scripts/qualify_release_package.py` with `verify-receipts` and test its synthetic three-platform inputs.

**Interfaces:** Workflow jobs `verify-source`, `build-bundle`, `platform-qualification` (three explicit matrix rows), and `qualification-gate`. Build outputs carry the verified Task 1 binding; upload outputs carry artifact ID/digest. Each platform writes one sanitized receipt bound to run ID, source/tree, artifact ID/digest, OS/architecture, both install results, and focused test counts. `verify-receipts` accepts exactly three expected rows and matching bindings; the gate also requires every `needs.*.result == success`.

- [ ] Write failing semantic workflow tests for dispatch-only trigger, exact `main`/full-SHA equality, immutable checkout, `contents: read`, pinned Actions, no secrets/write/publish path, one build, three required runner rows, independent build outputs, artifact-ID handoff, receipt upload, `fail-fast: false`, `if: always()` aggregate, and `continue-on-error` absence. Mutation-test removal of each dependency, a skipped platform, and a missing receipt.
- [ ] Run `rtk uv run pytest -q -o addopts= tests/test_release_package_workflow_contract.py`; confirm absence of workflow fails.
- [ ] Implement `verify-source` with exact commit/tree/version/clean-checkout checks. Add `build-bundle` invoking the existing release-builder script once with the optional content-ledger path outside `dist`, then Task 1's verifier; emit output values only after verification, upload one short-lived bundle, and reject empty artifact ID/digest.
- [ ] Implement each platform row with actual OS/architecture assertion, exact checkout, download by the build's artifact ID from the same run, independent Task 1 handoff check **before** either installation, then the direct bound-wheel install and the isolated PEP 517 sdist-to-temporary-wheel chain described in Task 2, followed by both Task 2 TCK runs and Task 3 focused tests. Put canonical archive identities, exact sdist build-environment manifest, temporary-wheel identity, and per-row outcomes in a bounded sanitized receipt; upload it with a unique row name.
- [ ] Keep the Windows row fail-closed while its launcher bytes lack independent template/installer provenance. Do not make the manual workflow dispatchable or report Stage A qualification success until the required Windows launcher and native Windows x64 evidence gate is actually admitted; a deliberate failing Windows job is not a usable qualification run.
- [ ] Implement `qualification-gate` to run after any upstream outcome, require all three platform jobs plus source/build success, download exactly three receipt artifacts, and validate exact bindings, including each sdist build-environment manifest, dynamic-requirement satisfiers, and temporary-wheel identity. Failure, cancellation, timeout, skip, unexpected artifact or missing receipt is terminal NO-GO.
- [ ] Contract-test that every eligible sdist row executes `prepare-sdist-build`, never installs the original sdist directly, passes the original bound sdist to `verify-installed`, and keeps its temporary wheel outside canonical `dist`. Keep Windows terminal NO-GO until separately admitted; do not represent an unconditional Windows failure as a Stage A qualification.
- [ ] Run `rtk uv run pytest -q -o addopts= tests/test_release_package_workflow_contract.py tests/test_release_package_bundle.py tests/test_release_package_installed.py tests/test_release_package_sdist_build.py tests/test_release_package_focused.py tests/test_ci_workflow_contract.py tests/test_release_workflow_contract.py`. Run `rtk make ci` and `rtk make docs-check`; expect PASS. Do not dispatch the new workflow while Windows remains NO-GO.
- [ ] Preserve a task checkpoint. Commit, push and PR only under separate explicit authorizations; do not dispatch until the workflow lands on protected `main` and a new exact candidate is selected.

### Task 5: Reconcile public operator evidence and activate only after review

**Files:** Modify `docs/RELEASE_PROCESS.md`, `docs/quality/V2_0_1_RC4_RELEASE_QUALIFICATION_PLAN_2026-09-06.md`, `docs/knowledge/log.md`, `docs/knowledge/inventory.json`, `docs/knowledge/inventory.md`, and `CHANGELOG.md` only if the changelog gate says the operator change belongs there.

**Interfaces:** The release process points to workflow name, exact dispatch input, evidence fields, Stage A human GO/NO-GO, historical attempt retention, separate tag/publication authorization, and independent public-artifact Stage B Gate B. Issue #582 remains the tracker; no issue mutation is part of implementation.

- [ ] Add a concise operator procedure for selecting exact protected `main` after workflow merge, checking ordinary exact-head CI, dispatching once under separate authorization, verifying run/receipt identities, and documenting NO-GO or requesting independent Stage A review. State that the workflow's own merge changes source identity and invalidates earlier diagnostic candidate evidence.
- [ ] Link the procedure from the RC4 plan without rewriting its historical source/result statements. Record documentation evolution in `docs/knowledge/log.md`; curate the spec and plan inventory entries and regenerate `inventory.md`.
- [ ] Run `rtk make docs-check`, `rtk make docs-audit`, `rtk git diff --check`, and relevant release-document contract tests. Confirm no stale status claim, local path, tool attribution, or private raw evidence enters public text.
- [ ] Request a read-only Sol review of exact diff, workflow authority, verifier threat model, Windows lifecycle selection, and tests. Repair any `BLOCKED` finding and rerun affected gates. For changed archive/file trust boundaries, request the security reviewer as well.
- [ ] After separate authorization and exact-head CI, create short PRs in dependency order; do not let an intermediate verifier-only PR activate an incomplete workflow. Reverify each base/head/diff/required checks before any separately authorized merge.
- [ ] Only after an authorized merge, reselect the new exact `main` commit and request a distinct workflow-dispatch authorization. A green run is evidence for independent Stage A review, not tag, GitHub Release, PyPI, Gate B, or stable support authority.

## Completion Check

Plan implementation is complete only when verifier (including sdist build-environment) and workflow contract tests, full required hosted PR CI, and documentation gates are terminal green at the exact implementation head, with independent review and no unresolved scope concerns. The workflow must be a usable qualification path, not a deliberately failing Windows scaffold. RC4 Stage A remains incomplete until the admitted workflow runs on a newly selected `main` candidate and its three platform receipts—including exact original-sdist and temporary-wheel provenance—receive a separate GO decision. Neither condition authorizes publication, and no reproducible-build claim follows from matching hashes in a single qualification run.
