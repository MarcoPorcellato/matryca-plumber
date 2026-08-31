# Documentation update log

## 2026-08-31

- **v2.0.1-rc.2 failed publication and repository binding:** preserved the valid
  signed tag, exact release run, successful source/build/manifest/attestation stages,
  and empty GitHub Release and PyPI destinations. The checkout-free publish job failed
  before publication because GitHub CLI had no explicit repository binding. The
  corrected contract binds release creation to `GITHUB_REPOSITORY`; RC2 is not retried
  or reclassified as published, and recovery proceeds through a fresh candidate.

- **v2.0.1-rc.2 qualification preparation:** recorded the proposed Tier 3 RC2
  contract for operator `.env` parent-directory durability and maintenance-robot Git
  path isolation. Stable `v2.0.0` remains the default; RC1 remains historical. No RC2
  candidate source, tag, public release, package artifact, Gate B result, or stable
  decision is recorded. A future RC2 publication starts, but does not complete, the
  exact-artifact dual-profile 72-hour Gate B and later separate stable-decision path.

- **v2.0.1-rc.3 qualification preparation:** Reclassified RC2 as immutable terminal
  failed-publication history and linked its failed record. Recorded the active Tier 3
  RC3 preparation base, `.env` fsync and robot path-isolation controls, explicit
  checkout-free release repository binding, and workflow-contract coverage. RC3 source,
  tag, workflow run, artifacts, and qualification results remain unselected; Gate B and
  stable promotion remain separate and unauthorized.

- **Historical tag verification correction:** preserved the publication-time
  `unknown_key` observation for `v2.0.1-rc.1` and recorded GitHub's later `valid`
  verification after public-key registration. The annotated tag object, release
  commit, published artifacts, and incomplete Tier 2 qualification boundary remain
  unchanged.

## 2026-08-30

- **Exact-artifact release promotion:** documented the protected-main signed-tag
  boundary, isolated-keyring verification of the committed release key, and the
  fail-closed four-job release chain. Each run builds one wheel and one sdist,
  verifies the two-line SHA-256 manifest and downloaded file set, attests and
  verifies the downloaded subjects, and promotes only those bytes. Existing
  GitHub Release or PyPI destinations stop reruns; partial publication remains
  a separate recovery decision, while Gate B and post-release evidence stay
  independent.

- **Hosted qualification authority:** established standard GitHub-hosted runners
  as the public pull-request authority behind the protected `Ironclad Gatekeeper`
  context, with Python 3.12, Python 3.13, frontend, dependency-review, and
  macOS/Windows Shadow lanes. This supersedes the earlier hybrid local route as
  active routing without rewriting its 2026-08-24 through 2026-08-29 chronology.
  Local receipt routing is retired from the active tree. Package, Gate B,
  benchmark, and publication evidence remain independent; CodeQL ruleset
  enforcement remains a separate observed-context mutation.

## 2026-08-29

- **Official CCP guidance reconciliation:** bound the public operator guidance
  to upstream documentation commit
  `6ff736b1e2a1dfde8778330efdd4b82c845d45e7`, made the Matrix
  `current-v2` profile explicit across the safe `plan`, `doctor`, and `dry-run`
  targets, and recorded that dry-run output is a planning surface rather than a
  replay bundle. The separately measured `matrix-v2-legacy-v1` digest is not an
  accepted policy migration, and single-runtime receipt-v2 policy `1.1` is not
  projected onto the three-runtime Matrix contract.

- **Hybrid local CI authority split:** reverified the signed, durable public
  receipt-verifier pin at `3fccc197e5055a2759ee7afe51b91133938ec904`
  separately from the newer qualified local coordinator at source
  `27adf8d0820b3cd96f9c5e149de9b580ae41f639`, tree
  `d8e0364d1313fde0898a44517ae6d233d9e10763`, and executable
  `sha256:c8021e2322e172686c0a0c07d2b0260eafb5812d085d2306dbbde3fe4e964bd4`.
  The prior `sha256:7cde4c2888721d72fbb8c86b4fdcc75f992050979c5175a5bf10b0cecfa7c6f8`
  executable remains the immediate rollback. The local installation does not
  transfer verifier compatibility, change hosted-CI authority, or authorize a
  hosted skip; any public pin upgrade remains behind its compatibility gate.

## 2026-08-26

- **Hybrid local CI source boundary:** accepted the qualified CCP matrix source
  at `3fccc197e5055a2759ee7afe51b91133938ec904`, regenerated the three-runtime
  policy from its rendered plan, and added the existing Python 3.12 source
  security gate to local parity. This closes Task 6 Step 0 only: hosted CI
  remains authoritative; coordinator diagnosis, official receipt qualification,
  parity, fallback, routing, ruleset, and savings milestones remain separate.

## 2026-08-25

- **Source static-analysis baseline:** added a fast source-only security gate to
  the existing local and hosted aggregate checks, recorded every accepted
  finding with line-bound rationale, and preserved runtime-assertion hardening
  as a separate reviewed step. The gate adds no network access, container work,
  heavy local admission, or additional hosted workflow job.

## 2026-08-24

- **Hybrid local CI bootstrap:** added the pinned three-runtime CCP matrix,
  exact policy bindings, opt-in trusted receipt observer, immutable savings
  ledger and generated report, and the fail-closed operator runbook. A
  source-compatibility gate now requires matrix diagnostics, regenerated
  digests, and seven negative receipt cases before replacing the pin. Source
  verification found that matrix `doctor` and `dry-run` are not yet supported
  at the reviewed CCP pin, so official heavy local qualification and any hosted
  skip remain blocked while full hosted CI stays authoritative.

- **Hybrid local CI design:** approved a fail-closed, observation-first Commit
  CI Preflight adoption design and preserved its pre-activation GitHub Actions
  baseline. Both historical documents were later retired from the active tree;
  hosted CI remained authoritative until exact-head parity, negative cases,
  fallback qualification, routing observation, and separate ruleset approval
  were terminal.

- **Risk-based release qualification:** separated immutable exact-artifact evidence
  boundaries from gate applicability. Every release still needs fresh source, CI,
  package, and publication proof; a 72-hour Gate B campaign is reserved for durable,
  systemic, or otherwise high-risk changes and remains mandatory when that tier is
  selected.

- **v2.0.1 prerelease state:** recorded the historical public `v2.0.1-rc.1` tag, release commit,
  workflow, and wheel digest without promoting the prerelease to stable or claiming
  pending targeted qualification as complete. The record is artifact-bound and does
  not qualify later repository revisions.

- **v2.0.1 package and parser boundary:** recorded an independent public-wheel install
  with matching digest, zero installed-file mismatches, and parser 1.8.0 resolution.
  That exact artifact retained incomplete Tier 2 minimum/current dependency and
  bounded dual-profile gates; a later source requires fresh classification, and a
  72-hour campaign remains mandatory whenever its delta reaches Tier 3.

## 2026-08-23

- **v2.0.1 candidate qualification:** established a public, candidate-first plan
  for bounded journal-day retrieval. It separates preparation, tag publication,
  independent package binding, fresh dual-profile operational qualification, and any
  later stable-promotion decision; no `v2.0.0` evidence is transferred to the
  new artifact.

- **Read-surface documentation:** aligned the README, roadmap, release mechanics,
  agent onboarding, agent guide, and architecture maps with the canonical
  `journal_day` read contract: one ISO-dated journal, confined Markdown access,
  source-digest-reported stateless pagination, no Shadow calls from the handler, and
  no graph mutation. Ordinary runtime-profile bootstrap remains a separate startup
  concern.

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
