---
type: qualification-gate-map
title: Release qualification gate map
description: Independent local, CI, package, operational, security, and publication gates.
last_verified: 2026-08-19
stale_after: 2026-11-17
status: maintained-proposal
authority: release-process-and-workflows
---

# Release qualification gate map

The gates below are independent. Green CI is evidence for the checks it ran;
it is not, by itself, release qualification. Every release decision requires
an exact source commit, artifact identity, runner/platform, terminal result,
and review of the applicable limitations.

| Gate | Authoritative command/workflow/evidence | State represented | Boundary |
| --- | --- | --- | --- |
| Fast/local | `make format-check`; `make lint`; `make typecheck`; targeted `uv run pytest ...`; `make docs-check` | Local development evidence | Does not substitute for protected CI, package, soak, security, or publication gates. |
| PR CI | `.github/workflows/ci.yml`; `make ci`; frontend lint/test/build; dependency review on pull requests | PR check result | Must be tied to the exact PR head and required checks; a local pass is not a PR result. |
| Full CI | `make ci` (`format-check`, lint, types, sandbox, version, agents, public-metrics, docs, prompt, tests) | Repository CI gate | Does not include package installation, durable soak, benchmark disposition, or release publication. |
| Python 3.13 evidence | CI job `python-313-evidence`; `uv run pytest -n auto -q -o addopts=` | Non-blocking Python 3.13 evidence | `continue-on-error: true`; evidence-only, not a blocking support or release gate. |
| Cross-platform Shadow | CI job `shadow-cross-platform` on `macos-latest` and `windows-latest`, Python 3.12, bounded named tests | Platform contract evidence | Covers the supported Shadow read contract only; it is not full Windows/macOS product qualification. |
| Package verification | `make release-build`; install and verify the produced sdist/wheel against the exact source and digest | Package/artifact evidence | Build success does not prove runtime soak, security review, or publication. |
| Benchmark | `V2_STABLE_PERFORMANCE_DISPOSITION_2026-08-18.md` and pinned benchmark result files | Bounded performance disposition | Results are workload/environment-specific and are not universal benchmarks or a substitute for correctness/fallback evidence. |
| Soak/recovery | `GATE_B_RC_SOAK_RUNBOOK.md`; `GATE_B_RC2_TERMINAL_EVIDENCE_2026-08-13.md`; exact installed artifact, profiles, checkpoints, restart/recovery | Durable operational evidence | Historical RC evidence is artifact-bound and cannot be reused for a changed source or artifact. Interruption, reboot, stale checkpoint, disk pressure, and service restart must preserve receipts and resume without deleting evidence. |
| Security | `.github/workflows/codeql.yml`; dependency review in CI; `SECURITY.md`; relevant security tests | Security evidence/review | A scan or test result is not a complete threat-model review, disclosure decision, or external security approval. |
| Release publication | `.github/workflows/release.yml` on a `v*` tag: verify job, `make release-build`, changelog extraction, GitHub Release, PyPI trusted publishing | External publication gate | Publication depends on GitHub/PyPI and maintainer authority; local or pre-publication success cannot claim publication. |
| Post-release observation | Release-specific observation window and fresh release/readiness record | External operational observation | Must be tied to the published version and exact artifacts; historical observations do not qualify a later release. |

## Resource admission and interruption boundary

Expensive benchmark, soak, and recovery work requires an explicit resource
admission decision before starting. `Unknown` or denied capacity is a hold,
not a pass. Use bounded parallelism, serialized memory-heavy work, durable
checkpoints, and an attempt chain that records source/artifact identity and
interruption reason. Setup, preflight, downtime, and an interrupted attempt do
not count as qualified runtime. Resume only from a validated checkpoint; never
delete or rewrite prior evidence to make an attempt appear continuous.

## Decision vocabulary

Use `verified` only for exact, reproduced evidence; `partial` when a required
dimension is missing; `historical` for preserved past evidence; `proposed` for
this map or future work; `blocked` for an unmet dependency; and `external gate`
when the decision belongs to GitHub, PyPI, a maintainer, or an independent
review body. No row may be promoted by inference from another row.
