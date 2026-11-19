---
type: qualification-gate-map
title: Release qualification gate map
description: Risk-selected local, CI, package, operational, security, and publication gates with independent evidence boundaries.
last_verified: 2026-11-15
stale_after: 2027-05-14
status: draft
classification: active
owner: release
authority: release-process-and-workflows
---

# Release qualification gate map

The gates below are independent. Green CI is evidence for the checks it ran;
it is not, by itself, release qualification. Every release decision requires
an exact source commit, artifact identity, runner/platform, terminal result,
and review of the applicable limitations.

Review scope (2026-11-15): the active-candidate registry and Python 3.13 CI row
below were reconciled against the selected alpha.4 source and current workflow.
Other gate rows and external branch-protection settings were not revalidated;
their existing review dates and qualification limits remain controlling.

| Gate | Authoritative command/workflow/evidence | State represented | Boundary |
| --- | --- | --- | --- |
| Fast/local | `make format-check`; `make lint`; `make typecheck`; targeted `uv run pytest ...`; `make docs-check` | Local development evidence | Does not substitute for protected CI, package, soak, security, or publication gates. |
| PR CI | `.github/workflows/ci.yml`; `make ci`; frontend lint/test/build; dependency review on pull requests | PR check result | Must be tied to the exact PR head and required checks; a local pass is not a PR result. |
| Full CI | `make ci` (`format-check`, lint, types, sandbox, version, agents, public-metrics, docs, prompt, tests) | Repository CI gate | Does not include package installation, durable soak, benchmark disposition, or release publication. |
| Python 3.13 compatibility | CI job `python-313-compatibility`; `uv run pytest -n auto -q -o addopts=` | Workflow job result; `continue-on-error` is not set | Runs the full test suite on Python 3.13. Whether branch protection requires this job was not checked; this is not full product or platform qualification. |
| Cross-platform Shadow | CI job `shadow-cross-platform` on `macos-latest` and `windows-latest`, Python 3.12, bounded named tests | Platform contract evidence | Covers the supported Shadow read contract only; it is not full Windows/macOS product qualification. |
| Package verification | `make release-build`; install and verify the produced sdist/wheel against the exact source and digest | Package/artifact evidence | Build success does not prove runtime soak, security review, or publication. |
| Benchmark | `V2_STABLE_PERFORMANCE_DISPOSITION_2026-08-18.md` and pinned benchmark result files | Bounded performance disposition | Results are workload/environment-specific and are not universal benchmarks or a substitute for correctness/fallback evidence. |
| Soak/recovery | `GATE_B_RC_SOAK_RUNBOOK.md`; `GATE_B_RC2_TERMINAL_EVIDENCE_2026-08-13.md`; exact installed artifact, profiles, checkpoints, restart/recovery | Durable operational evidence | Historical RC evidence is artifact-bound and cannot be reused for a changed source or artifact. Interruption, reboot, stale checkpoint, disk pressure, and service restart must preserve receipts and resume without deleting evidence. |
| Security | `.github/workflows/codeql.yml`; dependency review in CI; `SECURITY.md`; relevant security tests | Security evidence/review | A scan or test result is not a complete threat-model review, disclosure decision, or external security approval. |
| Release publication | `.github/workflows/release.yml` on a `v*` tag: `verify`, `destination-preflight`, `build-release`, and `publish-release`; a two-line SHA-256 manifest and provenance attestations for the downloaded wheel and sdist | Exact-artifact external publication gate | Publication depends on GitHub/PyPI and maintainer authority; existing destinations fail closed, partial publication needs a separate recovery decision, and local or pre-publication success cannot claim publication. |
| Post-release observation | Release-specific observation window and fresh release/readiness record | External operational observation | Must be tied to the published version and exact artifacts; historical observations do not qualify a later release. |

## Risk-selected applicability

Every release starts with a written classification of the delta from the last
qualified public artifact. The classification selects gates; it never weakens the
binding of a result to exact source, artifacts, commands, platforms, and terminal
receipts.

Classify behavior introduced or materially affected by the delta. Merely traversing
an unchanged subsystem does not by itself raise the tier, but that subsystem belongs in
the bounded control smoke; any new side effect, changed state, or unexplained
interaction triggers escalation.

| Tier | Typical delta | Minimum qualification | 72-hour Gate B |
| --- | --- | --- | --- |
| 0 — documentation | Documentation, governance, metadata, or generated navigation only; no shipped behavior or dependency change | Documentation gates, exact-head PR CI, and publication checks if a release is produced | Not applicable |
| 1 — isolated read-only | Additive bounded read/API behavior that does not change Shadow, parser semantics, graph I/O, writes, defaults, service lifecycle, persistence, recovery, or concurrency | Exact source and required CI; public-package digest, install, metadata, and `RECORD` binding; targeted tests on supported CI platforms; bounded smoke in each affected runtime profile | Not required unless evidence reveals scope drift or a high-risk interaction |
| 2 — runtime or dependency | Common-path runtime, dependency, performance, or platform change without durable-state or data-integrity semantics | Tier 1 plus affected-platform, fallback, recovery, security, and bounded canary evidence selected in the release plan | Decision required and documented; escalate when durable behavior may be affected |
| 3 — durable or systemic | Shadow persistence, watcher, recovery, concurrency, external Read Only cache, graph I/O, parser semantics, write plane, service lifecycle, migrations, defaults, security/data-integrity boundary, or a major release | Full applicable gate map, including fresh exact-artifact dual-profile Gate B and terminal integrity review | Required; 259,200 valid seconds per required profile unless a stricter plan applies |

An emergency security fix may use a smaller fail-closed pre-publication envelope only
when delay creates greater risk. The maintainer must record the exception, limitations,
and follow-up observation; urgency never converts partial evidence into a pass.

The canonical rationale and escalation rules are in the
[risk-based release qualification decision](RISK_BASED_RELEASE_QUALIFICATION_DECISION_2026-08-24.md).

## Active candidate-plan registry

The registry adds the S0 stable plan and the separate alpha.4 public-byte
receipt. Unrelated gate-map rows and historical candidate evidence are unchanged.

| Candidate plan | Risk tier | Coordination | State | Boundary |
| --- | --- | --- | --- | --- |
| [Full 2.1.0 stable qualification plan](V2_1_0_STABLE_RELEASE_QUALIFICATION_PLAN_2026-11-15.md) | Tier 3 | S0 planning baseline; S1 native Windows; S2 full Stage A; S3 exact public RC and Gate B; S4 stable finalization | `planning; no RC selected` | Qualification targets are not support claims. Native Windows and full-package gates remain open; alpha.4 does not satisfy them or start the seven-day RC observation. |
| [Experimental 2.1.0a4 qualification plan](V2_1_0A4_RELEASE_QUALIFICATION_PLAN_2026-11-14.md) | Tier 3; bounded experimental release, not stable qualification | [Separate public-byte handoff](OG_OPERATIONAL_V1_ALPHA4_PUBLIC_HANDOFF.md) | `accepted exact public bytes; experimental only` | [Pre-tag source run 43678299031](https://github.com/MarcoPorcellato/matryca-plumber/actions/runs/43678299031) remains source-specific. [Public-byte run 43716337039](https://github.com/MarcoPorcellato/matryca-plumber/actions/runs/43716337039) verified the original public packages for the exact synthetic POSIX tuple. Windows refusal is not installed qualification; no stable, DB, user-graph or new Trama claim follows. |
| [Historical v2.0.1-rc.4 qualification plan](V2_0_1_RC4_RELEASE_QUALIFICATION_PLAN_2026-09-06.md) | Tier 3: Parser/graph I/O, lifecycle and topology boundaries | Historical selected candidate `74884c38edb9cae445fa465969aa2c9cee5ecd1c`; #579/#582; [supersession record](RC4_TO_V2_1_0_SUPERSESSION_2026-10-16.md) | `historical; superseded` | Preserve exact-source hosted CI, build, installed-resource and TCK history without transferring it to a new candidate. RC4 was not published. L, native Windows, three-platform Stage A and 259,200 valid seconds per required dual-profile Gate B remain unfinished obligations, not waived or passed gates. No RC4 tag, public bundle, stable decision or DB support exists. |

Historical RC1 and RC3 records remain bound to their own artifacts. This registry does not
represent publication, qualification, or stable-promotion results.

## Resource admission and interruption boundary

Expensive benchmark, soak, and recovery work requires an explicit resource
admission decision before starting. Follow the [local resource-admission
coordinator runbook](CI_RESOURCE_ADMISSION_RUNBOOK.md). `Unknown` or denied
capacity is a hold, not a pass. Use bounded parallelism, serialized
memory-heavy work, durable checkpoints, and an attempt chain that records
source/artifact identity and interruption reason. Setup, preflight, downtime,
and an interrupted attempt do not count as qualified runtime. Resume only from
a validated checkpoint; never delete or rewrite prior evidence to make an
attempt appear continuous. The coordinator is operational support only; it is
not Matryca release, artifact, CI, identity, external, or platform
qualification.

## Decision vocabulary

Use `verified` only for exact, reproduced evidence; `partial` when a required
dimension is missing; `historical` for preserved past evidence; `proposed` for
this map or future work; `blocked` for an unmet dependency; and `external gate`
when the decision belongs to GitHub, PyPI, a maintainer, or an independent
review body. No row may be promoted by inference from another row.
