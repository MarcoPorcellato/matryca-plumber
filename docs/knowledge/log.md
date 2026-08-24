# Documentation update log

## 2026-08-24

- **Hybrid local CI bootstrap:** added the pinned three-runtime CCP matrix,
  exact policy bindings, opt-in trusted receipt observer, immutable savings
  ledger and generated report, and the fail-closed operator runbook. A
  source-compatibility gate now requires matrix diagnostics, regenerated
  digests, and seven negative receipt cases before replacing the pin. Source
  verification found that matrix `doctor` and `dry-run` are not yet supported
  at the reviewed CCP pin, so official heavy local qualification and any hosted
  skip remain blocked while full hosted CI stays authoritative.

- **Hybrid local CI design:** approved a fail-closed, observation-first
  [Commit CI Preflight adoption design](../superpowers/specs/2026-08-24-ccp-hybrid-ci-adoption-design.md)
  and preserved its [pre-activation GitHub Actions baseline](../quality/CCP_GITHUB_ACTIONS_SAVINGS_BASELINE_2026-08-24.md).
  Hosted CI remains authoritative until exact-head parity, negative cases,
  fallback qualification, routing observation, and separate ruleset approval
  are terminal.

## 2026-08-23

- **v2.0.1 candidate qualification:** established a public, candidate-first plan
  for bounded journal-day retrieval. It separates preparation, tag publication,
  independent package binding, fresh dual-profile Gate B qualification, and any
  later stable-promotion decision; no `v2.0.0` evidence is transferred to the
  new artifact.

- **Read-surface documentation:** aligned the README, roadmap, release mechanics,
  agent onboarding, agent guide, and architecture maps with the canonical
  `journal_day` read contract: one ISO-dated journal, confined Markdown access,
  digest-bound bounded pagination, and no Shadow initialization or graph mutation.

## 2026-08-19

- **Legacy milestone reconciliation:** recorded the initial source review and
  applied the seven documented issue moves after fresh authenticated
  revalidation; the empty historical v1.9.11 and v1.9.12 milestones are closed
  while all unresolved work remains open in v2.1 or v2.2.

- **Interoperability consumer paths:** added an evidence-bounded matrix for
  parser, CLI, MCP, external-cache, and Matryca Knowledge consumers. Each path
  now states its safe starting point, required hold, and non-claims.

- **Contributor architecture guidance:** corrected the active contributor
  philosophy and Phase 4 guidance to distinguish the v2 external, disposable
  SQLite Shadow cache from an authoritative database or remote memory store.

- **Public release and soak evidence:** added the canonical retention, redaction,
  review, correction, and exact-artifact boundary policy for source checks, CI,
  package artifacts, soak campaigns, release publication, and post-release
  observations.

- **Resource admission:** added the local resource-admission coordinator runbook
  with the macOS `macos-v4` thresholds, fail-closed interruption policy,
  ticket/workspace-lock rules, schema boundaries, and explicit non-qualification
  limits.

- **Interoperability contract:** added a read-first, vendor-neutral proposal and
  content-free fixture catalog. It records capability boundaries and negative
  cases without claiming external-provider, concurrent-writer, or semantic
  interoperability qualification.

- **Repository governance and AAIF readiness:** established the canonical
  cross-cutting programme and its evidence-bound execution ledger; retained
  existing specialist and historical dossiers in their original roles, corrected
  the current security-support line, and linked the programme from maintained
  documentation entry points.

- **Governance and evidence entry points:** added the maintainer governance
  model, contribution-triage guidance, public quality evidence index, and
  independent release-qualification gate map without broadening any release or
  external-readiness claim.

## 2026-08-18

- **Stable v2.0.0 publication:** recorded the signed tag, exact stable commit,
  matching GitHub Release/PyPI artifact digests, completed Gate B and publication
  proof, README release guidance, and the public release record. Historical RC1/RC2
  evidence remains immutable and explicitly bound to its original artifacts.

- **Stable-readiness preparation:** recorded the completed RC2 observation window, four-baseline upgrade matrix, current cross-platform CI baseline, and non-blocking performance disposition; stable-candidate proof remains a separate exact-head gate.

## 2026-08-14

- **Stable-readiness state:** Reconciled RC2 terminal soak and persistent upgrade/rollback evidence, corrected the roadmap's historical RC1 framing, and recorded the RC observation cutoff while retaining the remaining stable-promotion blockers.

## 2026-08-13

- **RC2 qualification evidence:** Recorded the terminal dual-profile Gate B result for the exact public `2.0.0rc2` wheel, including frozen artifact and runner bindings, 72-hour valid-time proof, attempt-chain integrity, Read Only external-cache isolation, and explicit remaining stable-release gates.

## 2026-08-11

- **Graph-outcome evaluation:** Accepted a P0.5 plan for resettable Logseq graph environments, stale-memory and concurrent-human scenarios, final-world-state grading, safety vetoes, paired reliability evidence, release integration, and public Commit CI Preflight receipt gates for reducing duplicated GitHub Actions workload; publicly acknowledged @hardness1020's contribution to the programme correction.

## 2026-08-10

- **Agentic-memory governance:** Replaced decay-first planning with governed evidence, deterministic recall, reproducible benchmarks, proposal-first curation, and late opt-in proactivity while preserving Markdown authority and derived Shadow semantics.
- **Execution trace:** Added the [Agentic Memory Leadership Programme](../quality/AGENTIC_MEMORY_LEADERSHIP_PROGRAMME_2026-08-10.md) with delegated audit receipts, GitHub control-plane changes, claim policy, correction rounds, and completion gates.

## 2026-08-08

- **Machine-readable validation:** Added deterministic, schema-versioned JSON findings with stable fingerprints, bounded messages, independent layer summaries, and normalized Git provenance while preserving the existing blocking text gate.

## 2026-08-07

- **Dual-layer validation:** Separated OKF v0.2 format compatibility from Matryca quality reporting while retaining one deterministic blocking documentation gate.
- **Biological-memory scope authority:** Aligned OpenSpec, roadmaps, and issue templates on v2.1+ delivery while preserving v2.0 as the Shadow DB read-path release.
- **Distribution authority:** Preserved the versioned RC agent contract while routing mutable qualification and stable-promotion status to the readiness record.
- **OpenSpec authority:** Retired the pre-ship Shadow migration trigger, corrected generated-prompt ownership, and routed current operator behavior to its canonical contract.
- **Roadmap authority:** Replaced duplicated current Shadow defaults and live Gate B state with canonical operator and readiness links while preserving milestone history.
- **Architecture authority:** Removed mutable Shadow defaults, release status, and exact test-count ownership from the system architecture document while preserving its internal design role.
- **Operator authority:** Established one canonical v2 runtime/operator path and explicit roles for README, architecture, release, roadmap, quality, changelog, and release-note surfaces.
- **Performance evidence:** Added the reproducible BM25 query-cache capacity decision, raw benchmark bindings, memory envelope, and synthetic-evidence boundary.

## 2026-08-06

- **Upgrade:** Aligned the maintained bundle with the pinned Open Knowledge Format v0.2 contract.
- **Governance:** Separated official OKF `status` from Matryca `classification` and added unique canonical roles.
- **Trust:** Added native `verified` events, absolute `stale_after` dates, and transitional `last_verified` compatibility fields.
- **Guidance:** Added [Documentation evolution and operating model](documentation-evolution.md).
- **Validation:** Expanded deterministic checks for metadata, local links, anchors, reserved indexes, chronology, and inventory schema v2.

## 2026-07-18

- **Initialization:** Created the OKF-inspired `docs/knowledge/` pilot, architecture index, local profile, and generated repository inventory.
