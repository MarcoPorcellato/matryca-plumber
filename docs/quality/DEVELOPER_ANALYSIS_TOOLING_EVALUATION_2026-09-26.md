---
type: Roadmap
title: Developer analysis tooling evaluation
description: Evidence-bounded comparison of interactive analysis tools for synthetic Matryca Plumber diagnostics.
status: draft
classification: active
audience: [maintainer, contributor, agent]
owner: quality
last_verified: 2026-09-26
stale_after: 2027-03-25
---

# Developer analysis tooling evaluation

## Purpose and decision boundary

Evaluate whether an interactive notebook or report tool adds a useful named
role to Matryca Plumber's existing command-line and test workflow. The exact
project release `marimo 0.25.0` is the only candidate named in this document because its exact source
revision has verified, immutable upstream license evidence recorded below.
This is a maintainer-tool fit assessment, not a product feature, dependency
proposal, security certification, or performance claim.

The evidence collected so far does **not** support adopting a tool or claiming
that one is superior. This plan's achievable terminal outcome is a documented
`DEFER` unless new, separately authorized evidence changes that result. The
existing CLI, deterministic tests, hosted CI, and original evidence remain the
authorities.

## Verified repository and environment snapshot

- **Historical pilot anchor:** the evaluation began from local
  `main@3208bedfaeef0708034089057702cd21fa5dec52`, tree
  `8d649b8154791b41cd48b30eaf515b7b563ad3a5`. That checkout was 33 commits
  behind the then-cached `origin/main`; direct Git network access failed.
- **Reconciliation anchor:** on 2026-09-26, a read-only GitHub repository lookup confirmed public
  `MarcoPorcellato/matryca-plumber` `main@2579702736cb3f63d3cc58aba48a29aa6aed6878`.
  The locally available `origin/main` resolved to the same commit and tree
  `9d72fcf0c3407854d8744d90f3996c269d8bfa44`; local HEAD was its ancestor.
  An isolated checkout was created at that exact commit. Git transport still
  could not resolve `github.com`, so no fetch occurred; the remote tip was
  independently verified through that read-only repository lookup immediately before worktree
  creation. This anchor is verified as of that check, not guaranteed current
  after it.
- The 33 intervening upstream commits changed 118 paths, including both
  inventory files. The older local inventory diff was preserved separately and
  is **not** an input to the current inventory. Only the evaluation document
  was carried into this clean checkout.
- The local command-path inventory found `marimo 0.25.0`. Other notebook,
  headless-export, narrative-report, and interactive-viewer candidates were
  not available on that command path; they remain unnamed and unqualified.
  On 2026-09-26, a local command-path lookup resolved
  `installed-marimo-entrypoint`, and a CLI version query returned `0.25.0`.
  This launched only the CLI version command; it did not execute a
  notebook. No package resolution, install, or download occurred. Do not launch
  `marimo 0.25.0` again in this documentary pass; any new runtime action needs a
  separate authorization.

## Evidence ledger

Evidence strength is deliberately limited to what is preserved. Digests bind
local artifacts; they do not retroactively prove the exact command, environment,
or provenance of an earlier execution.

| Evidence | Exact artifact identity | Result | Class and limitation |
| --- | --- | --- | --- |
| Synthetic input | `pilot-root/fixtures/synthetic_runs.json`, SHA-256 `4d50178e0124d607f26e3694ca8f8d45868b62a1f90b381353f22d54de3f7002` | 8 fixture rows | Synthetic, local. `pilot-root` is the isolated scratch experiment, not the Plumber checkout. No user graph or live DB used. |
| Analysis implementation | `pilot-root/analysis.py`, SHA-256 `95460e54b191b8e14bea55afd849cc5610d6cfd09e416ada792dcc322ef1316c` | Existing deterministic summarizer | Source identity preserved; earlier invocation's complete argv/runtime receipt was not preserved. |
| Synthetic summary | Captured output: 8 rows; default-on 1/4 failures (0.25), p50 46.5 ms, p95 90 ms; read-only-external 3/4 failures (0.75), p50 84 ms, p95 140 ms; most-failed scenario `read_subtree` (2). Malformed input was rejected with `record fields do not match schema`. | Observed once | Exploratory result only. The exact runner command and captured-output digest are unavailable; do not call it a reproducible benchmark or qualification. |
| `marimo 0.25.0` notebook source | `pilot-root/notebooks/diagnostic.py`, SHA-256 `f1f9727164011ae59e2f4ab2a6c1f8ad1171d1d66ab9e10f4cd435ba3ef112e7` | Recorded `marimo check notebooks/diagnostic.py` passed; version reported as `0.25.0` | Static validation only; does not execute notebook cells or demonstrate productivity, isolation, or correctness against the fixture. Exact runtime receipt is not retained. |
| Earlier `marimo 0.25.0` smoke exports | `pilot-root/results/diagnostic-1.html`, SHA-256 `f7515435f9c5caa21b2952cacb05539a1c29c20ed912f6d962bd45f846f9f5ab`; `pilot-root/results/diagnostic-2.html`, SHA-256 `9fc3f3a1897da75e3880bd729087681db7a2d3cb924e51766e767795b958e8ea` | Earlier report said synthetic smoke tests and exports passed | Historical carry-forward. Command, exact `marimo 0.25.0` runtime artifact identity, fixture binding, and provenance chain are not preserved here; zero qualification credit. |
| Dependency files | `pilot-root/pyproject.toml`, SHA-256 `735e609305d7d834de77854bb796e548874b4f11b124250b5328f509d8e0e3ff`; `pilot-root/uv.lock`, SHA-256 `d3b8edf15a2c51bae3f960487c6be2e32f347cde0ba3076c7dc781c22feef089` | Snapshot identities recorded | These are pilot-root files, not Plumber dependency changes. No dependency changes or installs made under this plan. |
| Admission profile | SHA-256 `d5e52458a149283cf26a4c14a0d1a562aeb273fe25b396ada3ca2dd1fd78c329` | Deny-default profile reviewed | Hash-bound review only; not a security certification. |
| Admission child probe | `pilot-root/scripts/admission_probe.py`, SHA-256 `dcd8dcc01f0f07ae2cb333ec13565a292a3603ac81e4de6a5be4cbfa440312cf` | One authorized invocation did not reach the child | Invocation count consumed. No retry, alternate interpreter, equivalent launcher, or widened profile under that authorization. |
| Admission launcher | `pilot-root/scripts/launch_admission_probe.py`, SHA-256 `c379dece2f8eed845a41f76ef1e35e2fd4547e82ffe6ca6f1096a75ff9292170` | Outer runner failed while binding its owned loopback control listener with `Operation not permitted`, before `sandbox-exec` or child launch | Environment admission blocker, not a `marimo 0.25.0` failure or sandbox pass. No probe attempt directory, socket, or outside-probe files remained. |
| Official project documentation | Immutable release README linked in [Official references](#official-references) | Project capabilities reviewed against the exact source commit | Documentation evidence only; not local execution or comparative measurement. |

## Exact-version naming evidence

The following evidence permits this document to name only the exact project
release `marimo 0.25.0`; it does not qualify the installed command's artifact
identity or any other component in its dependency set.

| Subject | Verified evidence | Scope and limit |
| --- | --- | --- |
| Upstream source license | The official immutable [`LICENSE` at upstream commit `d9a60e77c286a4c63fb93eda2cdac186e77a1025`](https://github.com/marimo-team/marimo/blob/d9a60e77c286a4c63fb93eda2cdac186e77a1025/LICENSE) contains Apache License 2.0. SPDX identifier: `Apache-2.0`. Verified 2026-09-26. | Covers the source repository at this exact commit; it is not a legal review of the full project or its dependencies. |
| Release-to-source provenance | The official [PyPI release page for `marimo 0.25.0`](https://pypi.org/project/marimo/0.25.0/) reports `Apache-2.0` and PyPI-verified Trusted Publishing provenance binding its sdist and wheel to the same upstream commit. Sdist SHA-256: `0005827578027cf9ea2cce039e099c029a9323a3467cb15100228918c1608ad1`; wheel SHA-256: `43bb4d82d713f44fc064e77668e59a9fbb6172a6cf7c3abe25c15ef2cb1cce31`. | Identifies the public release artifacts and their source commit. The locally observed command version was not bound to either artifact digest, so this is not proof that the local installation is byte-identical. |
| Classification boundary | The [SPDX specification](https://spdx.github.io/spdx-spec/v3.0.1/model/ExpandedLicensing/Properties/isOsiApproved/) defines `isOsiApproved` as whether OSI lists a license as approved; that field alone does not classify a license as non-copyleft. | This repository's allowlist is a narrow editorial eligibility rule, not a universal legal taxonomy. |

No other candidate project is named or eligible on the current evidence. A
future named candidate needs its own exact-version, immutable official license
record before publication.

Private raw diagnostics and local paths stay outside this public-repository
document. The hashes above identify reviewed artifacts, not a complete signed
experiment manifest.

## Candidate roles — hypotheses, not adoption

| Candidate | Current evidence | Hypothesized role | Main limitation |
| --- | --- | --- | --- |
| Command-line workflow, deterministic tests, static reports | One synthetic summary observed; exact execution provenance incomplete | Default debugging and all authoritative checks | Less interactive; remains the baseline and authority. |
| `marimo 0.25.0` | Command reported version `0.25.0`; notebook static check passed; earlier smoke is unbound historical evidence; the single admission invocation was blocked before child launch | Interactive exploration of sanitized evidence | Package sandbox is not filesystem/network isolation. The installed artifact digest is unknown. No execution retry is authorized. |
| Exploratory notebook environment | Category-level hypothesis only; no exact candidate release or docs snapshot pinned; unavailable locally | General exploratory analysis | Stateful kernels and stored outputs can complicate review and reproducibility. |
| Narrative report and headless-rendering workflow | Category-level hypothesis only; no exact candidate release or docs snapshot pinned; unavailable locally | Narrative reports with controlled execution | A report workflow is not necessarily a reactive diagnostic notebook. |
| Interactive evidence viewer | Category-level hypothesis only; no exact candidate release or docs snapshot pinned; unavailable locally | Persistent interactive evidence view if a concrete need appears | Adds an app/server surface; not a notebook replacement. |

These are role hypotheses. Documentation-based fit is not measured superiority;
unavailable tools must not receive comparative numeric scores.

## Comparison rubric

If a future separately authorized qualification becomes possible, use one
identical, versioned synthetic fixture and rubric for each admitted candidate:

- identify the highest-failure-rate profile;
- identify the most-failed scenario;
- report the declared control case;
- reject malformed or incomplete input;
- reproduce the independent CLI oracle's canonical numeric output.

Record correctness, malformed-input handling, output reproducibility,
reviewability, interaction value, setup effort, execution time, resource use,
and maintenance surface. Separate setup, preparation, execution, and diagnosis
time. A single maintainer's friction observations are exploratory, not an
unbiased productivity estimate or percentage improvement.

Adoption would require all correctness checks, reproducible canonical output,
a concrete benefit over CLI, recorded maintenance cost, and no elevation of a
tool into evidence authority, production dependency, or CI gate merely because
one pilot passed. Otherwise, `DEFER` or `REJECT` is valid.

## Remaining permitted work and stop boundary

The current plan permits only these bounded documentary steps:

1. Read-only inspection of already collected tool paths, installed metadata,
   and file hashes only. Do not launch `marimo 0.25.0` or another candidate executable,
   import packages, resolve dependencies, download, or install.
2. Compare official documentation for the candidate roles; distinguish claims
   from measured behavior.
3. Reconcile the preserved result summaries and hashes into this evidence
   ledger, retaining every provenance limitation.
4. Update this document and its generated documentation inventory, then run
   documentation validation and whitespace/diff checks.
5. Record the fields required for a future runtime-test proposal. Preparing a
   concrete executable envelope is deferred to a separately scoped proposal;
   neither its preparation nor execution is required to complete this
   documentary evaluation.

No `marimo 0.25.0` execution, headless export, notebook-cell execution, interpreter
substitution, or equivalent relaunch is allowed in this plan. The consumed
one-shot admission probe cannot be bypassed. Any new runtime comparison,
installation, or broader execution requires a separate reviewed and authorized
attempt bound to exact inputs and commands. Do not touch user graphs, live
Logseq DBs, credentials, production data, or external services.

## Completion checklist

- [x] Repository and tool snapshot recorded with stale-upstream caveat.
- [x] Candidate roles and evidence classes distinguished.
- [x] Preserved fixture, source, dependency, notebook, and failed-admission
      artifact identities recorded.
- [x] Existing results reconciled without promoting unbound historical smoke
      or incomplete admission into qualification evidence.
- [x] Official-documentation-only alternatives explicitly labeled unmeasured.
- [x] No unsupported comparative scores or adoption claims.
- [x] Exact consumed-probe stop boundary recorded; no retry proposed within
      this authorization.
- [x] Future execution is explicitly deferred: the generic envelope below is
      not an executable, reviewed authorization packet. Exact versions, paths,
      commands, resources, and outputs must be proposed separately before a
      new attempt.
- [x] Documentation inventory and docs checks pass on the final document.
- [x] Final disposition (`DEFER`) and the next authorization boundary are
      recorded.

## Current disposition

**DEFER tool adoption and comparative runtime qualification.** Retain the
command-line workflow, deterministic tests, static reports, and hosted CI as the development and evidence
authorities. `marimo 0.25.0` remains an unqualified candidate for a possible
maintainer role. Other candidate projects stay unnamed pending exact-version
license evidence. No candidate has been selected or rejected on measured
comparative evidence. Completing this documentary
evaluation with a `DEFER` is a valid terminal outcome; it does not authorize or
trigger another probe.

## Proposed future runtime envelope (not authorized or executed)

Before a future attempt, record and review one exact envelope per candidate:

- target tool and pinned version/digest;
- exact clean source anchor and fixture/script digests;
- one explicit argv and working directory;
- deny-default filesystem/network policy and owned writable output root;
- timeout, CPU/memory/resource bounds, and maximum attempt count of one;
- expected outputs, cleanup/evidence-preservation rules, and stop conditions.

Start only after a separate authorization. A failed or blocked attempt is
terminal for that envelope; do not retry or switch tools inside it.

## Persistent execution goal

```text
In `MarcoPorcellato/matryca-plumber`, continue the documentary-only evaluation
from freshly reverified public `main` (last verified
`2579702736cb3f63d3cc58aba48a29aa6aed6878`) governed by
`docs/quality/DEVELOPER_ANALYSIS_TOOLING_EVALUATION_2026-09-26.md`. Reverify the
worktree and repository anchor; inspect only already-collected tool paths,
  installed metadata, and file hashes; do not launch `marimo 0.25.0` or another candidate
executable, import candidate-tool packages, resolve dependencies, download,
install, or run notebooks, exports, apps, or runtime qualification. Compare
official tool documentation, reconcile only preserved evidence with its exact
provenance limits, update this document and its generated inventory, and pass
the repository documentation checks. Complete the documentary evaluation with
terminal DEFER for tool adoption and comparative runtime qualification.
Preserved evidence may refine candidate hypotheses but cannot authorize
adoption or reopen runtime testing. Do not publish externally or change product
code, dependencies, or CI. Do not retry the consumed `marimo 0.25.0` admission probe or
autonomously create another runtime attempt; any such work requires a separate
exact authorization. Preserve the evidence boundary and leave a restart-safe
final status.
```

## Official references

- [Immutable project README at the provenance-bound source commit](https://github.com/marimo-team/marimo/blob/d9a60e77c286a4c63fb93eda2cdac186e77a1025/README.md)
- [Exact `marimo 0.25.0` release metadata and artifact provenance](https://pypi.org/project/marimo/0.25.0/)
- [Immutable upstream license at the provenance-bound source commit](https://github.com/marimo-team/marimo/blob/d9a60e77c286a4c63fb93eda2cdac186e77a1025/LICENSE)
- [SPDX `isOsiApproved` definition](https://spdx.github.io/spdx-spec/v3.0.1/model/ExpandedLicensing/Properties/isOsiApproved/)
