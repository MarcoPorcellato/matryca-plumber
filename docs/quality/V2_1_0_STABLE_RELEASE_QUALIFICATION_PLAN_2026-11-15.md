---
type: Roadmap
---

# 2.1.0 stable release qualification plan

S0 planning baseline: 2026-11-15. **Tier 3; no RC or stable candidate selected.**
This plan records targets, not admitted support. The [release process](../RELEASE_PROCESS.md),
[risk-based decision](RISK_BASED_RELEASE_QUALIFICATION_DECISION_2026-08-24.md),
[RC4 supersession record](RC4_TO_V2_1_0_SUPERSESSION_2026-10-16.md) and
[issue #582](https://github.com/MarcoPorcellato/matryca-plumber/issues/582)
carry the applicable rules. Historical RC4 and experimental alpha evidence do
not substitute for successor qualification.

## Scope and starting evidence

Qualify the existing Logseq OG/Markdown CLI, MCP and Shadow product, including
existing protected writes, Strict Read Only and fallback, bootstrap status,
and bounded dashboard cancellation. Freeze new capabilities: no native Logseq
DB, Obsidian, payload, new memory features, new writes or sync, or Trama
admission. Keep the existing experimental OG identity/topology gateway separate
and synthetic-only; a stable package version does not make that profile stable.

Use [v2.0.0](../releases/v2.0.0-GITHUB.md) as the last qualified stable
baseline. The [alpha.4 public-byte handoff](OG_OPERATIONAL_V1_ALPHA4_PUBLIC_HANDOFF.md)
is bounded experimental evidence on distinct original public packages. The
[#676 Windows verifier increment](https://github.com/MarcoPorcellato/matryca-plumber/pull/676)
does not qualify native installed packages: runtime provenance, protected launch
and native lifecycle/package evidence remain outstanding.

## Qualification targets

The original S0 all-platform target remains **24 installed rows**: Parser **1.9.0** and
**1.11.3** × Linux x86_64, macOS arm64 and Windows x64 × two exact CPython
runtimes per platform × original wheel and original sdist. The 2026-11-17
ordinary-runtime amendment selects CPython **3.12.16** and **3.13.18** in place
of the original S0 patches. Linux/macOS binary source selection and provenance
remain pending; the selected Windows binaries still need provenance closure
and native qualification. A later Parser release does not change either
profile without a scoped decision and fresh evidence.

The separately named **first-stable Linux/macOS scope** targets 16 ordinary
installed rows: two explicitly selected Parser profiles × Linux x86_64 and
macOS arm64 × CPython 3.12.16 and 3.13.18 × original wheel and original sdist.
The eight Windows rows are deferred to the all-platform track, not skipped or
passed in a 24-row campaign. Native Windows evidence remains a prerequisite for
that all-platform track, not for this separately qualified first-stable scope.
No other OS, architecture, runtime or Parser version is qualified by implication.
The universal `py3-none-any` wheel may be selected by an installer on an
unsupported platform; installation does not establish support.

Parser 1.11.3 remains the prior upper-profile target. Parser 1.11.4 is a current
metadata-only upper-profile candidate, pending an explicit choice and exact
compatibility and provenance evidence. Neither is selected by this amendment;
no dependency change follows. A current unpinned installation is not qualified
by an exact-profile result.

Each ordinary profile needs an exact, hash-locked dependency closure and
installed-origin checks. The declared Parser interval is not an empirical
compatibility claim. Do not change the root lock or dependencies under S0.
The sdist build closure stays separate and uses the locked CPython 3.12 builder;
a CPython 3.13 runtime row does not qualify a 3.13 build environment.

Preserve the distinct experimental gateway profile: Parser 1.9.0, exact locked
closure and synthetic fixture, Linux x86_64/macOS arm64, CPython 3.12.14/3.13.15,
original wheel and sdist. Packaged proposed, planned and unqualified labels
remain unchanged. Windows refusal is a negative control, not Windows support.

## Remaining gates

| Phase | Required outcome |
| --- | --- |
| S1 | For the all-platform track, verify native Windows installation authority, protected entry-point launch and process-tree cleanup for both distributions. Do not substitute generated-launcher tests or gateway refusal. Admit exact Linux/macOS runtime providers, binaries and build/runtime closures before the first-stable lane executes. |
| S2 | Land and verify a separately named, fail-closed ordinary first-stable lane and RC metadata before selecting one exact clean source. Reuse one canonical frontend → original sdist → original wheel pair; independently compute and require the exact 16-row set, authenticated source, profile, artifacts, jobs, runners and terminal cleanup. A missing, skipped, duplicate, unexpected, stale or mismatched row is not a pass. Preserve ordinary installed-package verification independently of the experimental OG aggregate. Explicitly amend workflow-admission checks for this lane; a different workflow filename must not bypass the Windows readiness guard. Obtain an independent pre-publication decision; exact signed RC tag and publication are separate maintainer gates. |
| S3 | Verify the actual public RC packages and provenance. Qualify clean install, upgrade and rollback from v2.0.0 and the relevant alpha.4 transition; reconcile older required paths explicitly. Verify Shadow readiness/fallback, Strict Read Only immutability, representative performance and durability on the exact public artifact. |
| S4 | Classify the RC-to-stable finalization delta, select the exact stable source, run fresh applicable gates and verify actual stable public artifacts after separately authorized publication. Do not attribute RC soak to stable bytes. |

[#656](https://github.com/MarcoPorcellato/matryca-plumber/issues/656) still
requires exact-profile dashboard performance acceptance or an explicit reviewed
disposition; bounded cancellation alone does not establish throughput. Keep
[Parser coupling #63](https://github.com/MarcoPorcellato/matryca-plumber/issues/63)
in the ordinary-profile checks. No broader issue is closed by this plan.

## RC observation and durability

Require **at least seven days** of availability and documented maintainer
operation on the exact eligible public RC, starting no earlier than actual
artifact admission and maintainer operation. No unresolved in-scope P0/P1
defects may remain at promotion; in-scope P2 findings require reviewed disposition.

Independently require **259,200 valid execution seconds (72 hours) per profile**
for `default-on` and `read-only-external`, following the
[Gate B runbook](GATE_B_RC_SOAK_RUNBOOK.md). Observation may overlap valid soak.
Concurrent profiles require approved capacity and independent roots, caches,
services and evidence. Do not backdate from alpha.4, count downtime or transfer
evidence to a different candidate. Synthetic testing does not replace any
required representative-vault evidence; actual data intake needs separate consent.

## Version and publication boundary

The successor version policy must be closed and source-bound: signed RC tags
`v2.1.0-rc.N` correspond to package versions `2.1.0rcN`, for positive decimal
`N` without leading zeroes; the final signed tag `v2.1.0` corresponds to
`2.1.0`. Preserve existing RC4 and experimental defaults. RC tag creation and
push, final promotion, final tag creation and push, and publication require
their separate explicit authorizations and applicable evidence. Verify the
actual public original wheel and original sdist after each publication.

This document does not authorize any build, dispatch, pilot, data intake, tag,
publication or support claim.
