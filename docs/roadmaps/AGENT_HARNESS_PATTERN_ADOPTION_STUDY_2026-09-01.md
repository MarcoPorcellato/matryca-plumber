---
type: Roadmap
title: Evidence-led agent harness pattern adoption study
description: A bounded study of DeepSeek Harness patterns that can strengthen Matryca Plumber without changing its Logseq-first authority, safety, or privacy boundaries.
resource: docs/roadmaps/AGENT_HARNESS_PATTERN_ADOPTION_STUDY_2026-09-01.md
tags: [agentic-memory, architecture, evidence, governance, replay, safety]
status: draft
classification: active
last_verified: 2026-09-01
stale_after: 2027-02-28
audience: [maintainer, contributor, operator, agent]
owner: quality
authority: pattern-adoption-study
source_repository: MarcoPorcellato/matryca-plumber
source_ref: main
source_commit: 0506d975fe697646e5165db1505ee93a67041801
related:
  - ../quality/GRAPH_OUTCOME_SYNTHETIC_HARNESS.md
  - ../quality/HUMAN_GOVERNED_ADAPTIVE_RETRIEVAL_PROGRAMME_2026-08-16.md
  - ../quality/AGENTIC_MEMORY_GRAPH_OUTCOME_EVALUATION_PLAN_2026-08-11.md
  - ROADMAP_V2_BIOLOGICAL_MEMORY.md
---

# Evidence-led agent harness pattern adoption study

**Date:** 2026-09-01

**Decision status:** approved design direction; implementation remains separately gated

**Scope:** selected engineering patterns from DeepSeek Harness, not adoption of its
runtime, dependency graph, or product model

## Executive decision

Matryca Plumber should adopt a small set of agent-harness patterns where they make
existing local-first memory behaviour easier to inspect, replay, test, and operate.
It should do so through narrow, Python-native contracts that preserve four existing
boundaries:

1. Logseq Markdown stays the canonical user-owned source of truth.
2. Shadow DB and every new harness artifact remain rebuildable derived state.
3. Strict Read Only, Safe-Sync, and explicit human authorization remain hard safety
   boundaries, not optional hooks.
4. Public evidence stays content-free by default and never becomes raw prompt or vault
   telemetry.

The first implementation target is **provider-free, keyless replay of a bounded
agent-memory episode**. It must prove deterministic reconstruction from declared
inputs and content-free evidence before any runtime provider integration, multi-agent
scheduler, default-on behaviour, or canonical write authority is considered.

## How to read this study

Statements are deliberately separated:

| Label | Meaning |
| --- | --- |
| Verified source fact | Behaviour inspected at the named immutable upstream revision. |
| Matryca fact | Behaviour or contract already present at the named Matryca source revision. |
| Decision | Approved direction for later, separately authorized implementation. |
| Proposal | Candidate design that requires an issue, implementation, and evidence gate. |
| Unknown | A question that must be resolved by a focused spike; it is not a product claim. |

Neither a source review nor a passing synthetic check proves a release, a production
runtime, a model-quality gain, compatibility with a third party, or safe canonical
writes.

## Evidence baseline and submitted-study provenance

| Surface | Immutable anchor | Role in this study |
| --- | --- | --- |
| Matryca Plumber | [`0506d975fe697646e5165db1505ee93a67041801`](https://github.com/MarcoPorcellato/matryca-plumber/commit/0506d975fe697646e5165db1505ee93a67041801) | Exact local source baseline for Matryca findings and mappings. |
| DeepSeek Harness | [`50a2bfc64f892a740ed6424e07f370d0a1970bce`](https://github.com/deepseek-ai/DeepSeek-Harness/tree/50a2bfc64f892a740ed6424e07f370d0a1970bce) | Immutable upstream review anchor for the seven patterns. |
| Submitted study | See provenance below | Input for hypotheses and terminology; never sufficient evidence by itself. |

The submitted study was produced by **QWEN3.8-27B**, using **4-bit MLX
quantization**, locally on the maintainer's **MacBook Pro M4 Max with 36 GB RAM**.
This is provenance metadata for the submitted analysis. It is not verification of its
claims, a hardware benchmark, a quality comparison, or evidence that Matryca requires
that model, quantization, or hardware.

The exact upstream review anchors are the [architecture overview](https://github.com/deepseek-ai/DeepSeek-Harness/blob/50a2bfc64f892a740ed6424e07f370d0a1970bce/docs/architecture.md),
[agent lifecycle](https://github.com/deepseek-ai/DeepSeek-Harness/blob/50a2bfc64f892a740ed6424e07f370d0a1970bce/docs/agent-lifecycle.md),
[capability seams](https://github.com/deepseek-ai/DeepSeek-Harness/blob/50a2bfc64f892a740ed6424e07f370d0a1970bce/docs/capability-seams.md),
[configuration reference](https://github.com/deepseek-ai/DeepSeek-Harness/tree/50a2bfc64f892a740ed6424e07f370d0a1970bce/apps/cli),
[Agent Teams documentation](https://github.com/deepseek-ai/DeepSeek-Harness/blob/50a2bfc64f892a740ed6424e07f370d0a1970bce/docs/subsystems/agent-team.md),
and [keyless evidence paths](https://github.com/deepseek-ai/DeepSeek-Harness/tree/50a2bfc64f892a740ed6424e07f370d0a1970bce/packages/test-support).
They must be re-read at an exact revision before implementation. Upstream source and
product state are drift-prone; this study makes no claim about a later upstream head.

## Seven patterns: evidence and disposition

| Pattern | Verified upstream fact | Matryca disposition | Why |
| --- | --- | --- | --- |
| 1. Append-only event log and model-visible trace | Durable session events are replayed into model context. | **Adapt** as a content-free, reconstructible episode trace. | Matryca needs evidence of decisions and boundaries, not raw transcripts. |
| 2. Cascading pre/execute/post guards | Waterfall hooks can wrap or short-circuit lifecycle decisions. | **Adapt narrowly.** | Hard guards stay mandatory; optional telemetry and budgets must remain reversible. |
| 3. Definition/provider/consumer seams | Services distinguish definitions, providers, and consumers. | **Adopt selectively.** | A seam is useful only where a real alternative provider or consumer exists. |
| 4. Profiles, bundles, patches, and effective-config inspection | Layered configuration can be composed and inspected. | **Adapt first as a redacted effective-config report.** | Operators need inspectability without introducing a universal plugin system. |
| 5. Commands versus next-request context injection | Commands and durable session context have different lifecycle roles. | **Adapt through existing proposal and operator authority.** | A command must not silently grant future write authority. |
| 6. Subagent seam and Agent Teams | Team coordination exists but is explicitly experimental and opt-in. | **Defer.** | Matryca Plumber is an executor, not a general scheduler; cross-agent authority belongs in Matryca Brain. |
| 7. Keyless snapshot replay and golden tests | Deterministic replay paths can validate assembled behaviour without provider credentials. | **Adopt first.** | It produces the strongest early evidence with least privacy, cost, and provider coupling. |

### Pattern 1: model-visible means reconstructibly traceable

**Decision:** a Matryca trace must record only stable identifiers, declared action
class, policy result, source/artifact fingerprints, and outcome code. It must be
possible to reconstruct the evaluated state from declared fixtures and manifest
fingerprints. It must not log raw prompts, retrieved block content, user vault paths,
credentials, provider output, or a stable user identity.

This extends the existing content-free approach in the
[synthetic graph-outcome harness](../quality/GRAPH_OUTCOME_SYNTHETIC_HARNESS.md).
It does not turn an execution trace into a canonical memory, behavioural profile, or
telemetry stream.

### Pattern 2: guard phases without a bypass path

**Decision:** retain current hard safety checks as direct, non-removable control flow.
Where a new projection needs optional observation, use a separate registration that
can be enabled, disabled, and removed without changing safety semantics. A failed or
unknown guard must fail closed. No generic waterfall framework is justified.

The initial phases are conceptual only:

1. pre-action policy and source-state validation;
2. authorized, bounded action or explicit abstention;
3. post-action integrity check and content-free receipt.

The design must prove that optional observers cannot weaken Strict Read Only,
Safe-Sync, OCC, or human approval requirements.

### Pattern 3: seams only at real variability boundaries

**Decision:** use a Definition/Provider/Consumer split only for a capability that has
at least two credible implementations or must be substituted in deterministic tests.
Likely first candidates are an episode-trace writer and a replay provider. Existing
graph ports, Shadow projections, and operator surfaces remain authoritative in their
present layers until a specific dependency-direction review admits a change.

This rejects a repository-wide rewrite into an abstract agent framework. A seam must
have a named consumer, narrow data contract, ownership, test fixture, and deletion
path before it is introduced.

### Pattern 4: inspect effective configuration, redact defaults

**Proposal:** introduce an offline command or library report that renders the resolved
evaluation/replay configuration: profile name, public schema version, enabled feature
classes, policy mode, and non-secret fingerprints. It must exclude secrets, local
paths, raw vault identifiers, prompt content, and environment values. The report is
an operator aid and fixture input; it is not a configuration registry, remote control
plane, or promise of plugin compatibility.

### Pattern 5: separate requests from persistent authority

**Decision:** an operator command may request a bounded evaluation or proposal. Only
a separately accepted, revision-bound record may affect a later request, and it may
affect retrieval only until Safe-Sync’s write gates permit more. Matryca Brain owns
cross-session coordination and approval decisions; Plumber receives a narrow,
validated execution request and reports evidence back.

This aligns with the durable proposal-queue direction and prevents a command from
becoming an invisible permanent policy change.

### Pattern 6: defer general teams and scheduling

**Decision:** do not add Agent Teams, a Plumber task scheduler, or autonomous
delegation as part of this programme. These introduce lifetime, concurrency, privacy,
and authority questions that are not needed to make a replayable memory episode
useful. A future Matryca Brain integration may provide a versioned request/response
seam after its own governance contract and end-to-end evidence exist.

### Pattern 7: keyless replay before provider realism

**Decision:** first delivery is a provider-free replay fixture and golden result. It
must validate exact manifest schema, canonical/derived-state isolation, guard result,
and content-free outcome. Provider-backed, model-based, live-vault, or multi-process
testing is later work and cannot retroactively strengthen the first result.

## Existing ownership and issue reconciliation

This study deliberately does not create seven new issues. Live GitHub reconciliation
identifies [#477](https://github.com/MarcoPorcellato/matryca-plumber/issues/477) as
the primary tracker for DeepSeek Harness pattern adoption. Issue state, labels,
milestones, and bodies must be re-read immediately before any GitHub mutation.

| Existing issue | Current role retained by this study | Boundary |
| --- | --- | --- |
| [#477](https://github.com/MarcoPorcellato/matryca-plumber/issues/477) | Primary tracker for pattern adoption, implementation order, and decision reconciliation | Owns this study's delivery coordination; it does not grant runtime or write authority. |
| [#446](https://github.com/MarcoPorcellato/matryca-plumber/issues/446) | Parent governed-memory programme | Retains its broader programme scope. |
| [#452](https://github.com/MarcoPorcellato/matryca-plumber/issues/452) | Durable proposal queue and curation | Commands do not bypass curation. |
| [#483](https://github.com/MarcoPorcellato/matryca-plumber/issues/483) | Graph-outcome harness | First keyless replay extends its evidence boundary. |
| [#526](https://github.com/MarcoPorcellato/matryca-plumber/issues/526) | Evidence receipts | Owns public evidence indexing and retention constraints. |
| [#519](https://github.com/MarcoPorcellato/matryca-plumber/issues/519) and [#520](https://github.com/MarcoPorcellato/matryca-plumber/issues/520) | Repository standards and quality alignment | Retain their own acceptance and governance boundaries. |

**Issue decision:** use #477 for adoption reconciliation. Open a child issue only if
its exact scope cannot remain reviewable in #477; any child must link #477, #483, and
#526 without duplicating their acceptance evidence. Interoperability, GraphRepository,
and Safe-Sync issues are orthogonal to this delivery and remain unchanged.

## Narrow implementation sequence

### P0 — freeze a replayable evidence contract

1. Define a versioned episode manifest with public, content-free fields.
2. Define the smallest trace event schema and permitted outcome codes.
3. Define golden fixtures with isolated canonical and derived roots.
4. Add deterministic validators that reject schema drift, missing fingerprints,
   forbidden content fields, wrong root isolation, and stale source binding.

**Exit gate:** fixture replay produces the expected content-free result from a clean
checkout, and tampered fixture or trace inputs fail closed.

### P1 — attach the contract to existing graph-outcome evidence

1. Adapt a single existing read-only and vetoed episode to the P0 manifest.
2. Prove Strict Read Only abstention, derived-state isolation, and corrupt-state
   no-serve behaviour remain intact.
3. Index only redacted receipt facts according to #526’s ownership.

**Exit gate:** current graph-outcome tests and new replay tests pass without a
provider, network call, real vault, or change to canonical Markdown.

### P2 — add a narrow operator inspection surface

1. Render the effective redacted configuration for a declared replay profile.
2. Bind a requested execution to a profile schema and exact source revision.
3. Preserve a reversible disable path and verify that disabled optional hooks do not
   alter hard-guard outcomes.

**Exit gate:** configuration output is deterministic, secret-free, and independently
validated; all safety outcomes are identical with optional observation disabled.

### P3 — consider provider or Brain integration only after P0–P2

1. Re-read #477, #452, #483, #519, #520, and #526 at their current state.
2. Decide whether a versioned Brain-to-Plumber request boundary is justified.
3. Run a separate design and threat review before any provider, team, or cross-process
   capability is introduced.

**Exit gate:** an explicit maintainer authorization, a source-bound specification, and
new exact evidence. This study alone authorizes none of these changes.

## Explicit non-goals

- No DeepSeek Harness or Cordis runtime dependency.
- No raw prompts, provider output, vault content, credentials, local paths, or stable
  user identifiers in public traces or receipts.
- No Plumber scheduler, general Agent Teams implementation, or autonomous delegation.
- No seven-issue duplication of the seven patterns.
- No claim that 100% coverage proves behavioural, operational, security, or release
  quality.
- No new canonical write path, Shadow DB authority, or bypass around Strict Read Only,
  Safe-Sync, OCC, or human authorization.
- No cloud service, required model, network dependency, telemetry provider, or hardware
  requirement.
- No performance, benchmark, compatibility, or product-superiority claim from this
  study or its initial keyless fixture.

## Risk register

| Risk | Consequence | Mitigation |
| --- | --- | --- |
| Trace becomes hidden telemetry | Privacy and governance breach | Content-free schema, validators, local-only default, public redaction review. |
| Optional hook weakens a hard guard | Unsafe action | Keep hard guards direct and test hook-disabled/hook-enabled parity. |
| Abstraction outruns product need | More code, less clarity | Require a named consumer, substitute, owner, and deletion path for every seam. |
| Replay mistakes fixture for reality | False product claim | Label it provider-free synthetic evidence and retain exact limits in receipts. |
| Teams blur authority | Unreviewed mutation or conflicting action | Defer scheduling to an explicitly governed Brain boundary. |
| Existing issues diverge | Duplicate or contradictory delivery | Read exact live issue state before every issue or project mutation. |

## Definition of done for first delivery

- #477 records the reconciled owner decision, or a linked child records a narrower
  contract that #477 cannot own without becoming unreviewable.
- Versioned manifest, content-free event schema, golden fixture, validator, and tests.
- Clean-checkout keyless replay evidence bound to an exact source revision.
- Negative tests for malformed, stale, tampered, content-bearing, and isolation-breaking
  inputs.
- Proof that hard guard results are unchanged when optional observation is disabled.
- Evidence-index and documentation updates that describe both result and limitations.
- No provider, network, real-vault, scheduler, canonical-write, or release claim.

## Source index

- [DeepSeek Harness reviewed repository revision](https://github.com/deepseek-ai/DeepSeek-Harness/tree/50a2bfc64f892a740ed6424e07f370d0a1970bce)
- [DeepSeek Harness architecture](https://github.com/deepseek-ai/DeepSeek-Harness/blob/50a2bfc64f892a740ed6424e07f370d0a1970bce/docs/architecture.md)
- [DeepSeek Harness lifecycle](https://github.com/deepseek-ai/DeepSeek-Harness/blob/50a2bfc64f892a740ed6424e07f370d0a1970bce/docs/agent-lifecycle.md)
- [DeepSeek Harness capability seams](https://github.com/deepseek-ai/DeepSeek-Harness/blob/50a2bfc64f892a740ed6424e07f370d0a1970bce/docs/capability-seams.md)
- [Matryca synthetic graph-outcome harness](../quality/GRAPH_OUTCOME_SYNTHETIC_HARNESS.md)
- [Matryca human-governed adaptive retrieval programme](../quality/HUMAN_GOVERNED_ADAPTIVE_RETRIEVAL_PROGRAMME_2026-08-16.md)
- [Matryca graph-outcome evaluation plan](../quality/AGENTIC_MEMORY_GRAPH_OUTCOME_EVALUATION_PLAN_2026-08-11.md)
