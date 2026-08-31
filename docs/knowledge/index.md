# Matryca Plumber knowledge bundle

This index provides progressive disclosure across maintained concepts and the classified legacy corpus. Matryca Plumber remains the authoritative editing origin; external projections are read-only, Git-provenanced consumer views.

## Documentation system

- [Documentation evolution and operating model](documentation-evolution.md) — Rationale, layers, authority boundaries, maintenance workflow, and migration history.
- [Matryca Plumber knowledge profile](profile.md) — OKF v0.2 compatibility and stricter Matryca producer rules.
- [Repository documentation inventory](inventory.md) — Generated view of every root and `docs/` Markdown surface.
- [Documentation update log](log.md) — Material documentation-system changes, newest first.
- [Repository governance and AAIF readiness programme](../quality/REPOSITORY_GOVERNANCE_AND_AAIF_READINESS_PROGRAMME_2026-08-19.md) — Current cross-cutting sequence for governance, evidence, interoperability, and external-readiness work.

## Maintained architecture

- [Architecture index](architecture/) — Progressive-disclosure entry point for the maintained architecture concepts.

## Operator path

- [v2 Shadow DB runtime and operator contract](architecture/shadow-db.md) — Current activation, Read Only, external-cache, health, fallback, quarantine, and evidence links.
- [Release process](../RELEASE_PROCESS.md#v2-release-qualification-rule) — Qualification, authorization, tag, and publication gates.

## Detailed established collections

- [Product identity and branding](../BRANDING.md) — Product naming and public identity.
- [Getting started](../FIRST_CONTRIBUTION.md) — First-contribution path and repository setup.
- [Contributor guide](../../CONTRIBUTING.md) — Development standards and verification gates.
- [OpenSpec index](../openspec/README.md) — Normative feature and agent contracts.
- [Interoperability contract](../openspec/interoperability-contract.md) — Read-first capability levels, source authority, and boundaries for future external qualification.
- [Roadmaps](../roadmaps/) — Active and historical delivery plans.
- [Governance](../../GOVERNANCE.md) — Maintainer authority, contribution decisions, security escalation, and current limits.
- [Quality evidence](../quality/) — Audits, qualification evidence, and issue-source records.
- [Public quality evidence index](../quality/EVIDENCE_INDEX.md) — Bounded public claims with owning sources, limitations, and review dates.
- [Release qualification gate map](../quality/RELEASE_QUALIFICATION_GATE_MAP.md) — Independent local, CI, package, operational, security, and publication gates.
- [Risk-based release qualification decision](../quality/RISK_BASED_RELEASE_QUALIFICATION_DECISION_2026-08-24.md) — Selects fresh exact-artifact gates by change risk without transferring historical evidence.
- [Public release and soak evidence policy](../quality/PUBLIC_RELEASE_AND_SOAK_EVIDENCE_POLICY.md) — Retention, redaction, review, and artifact-bound claim rules for public qualification evidence.
- [Proposed v2.0.1-rc.2 qualification plan](../quality/V2_0_1_RC2_RELEASE_QUALIFICATION_PLAN_2026-08-31.md) — Active Tier 3 preparation contract; no RC2 source, publication, artifact, Gate B result, or stable decision is selected or passed.
- [v2.0.1-rc.1 prerelease record](../releases/v2.0.1-rc.1-GITHUB.md) — Historical, artifact-bound publication facts and incomplete gates that do not qualify current `main`.
- [Local resource-admission coordinator runbook](../quality/CI_RESOURCE_ADMISSION_RUNBOOK.md) — macOS `macos-v4` admission, interruption, recovery, and evidence boundaries.
- [Source static-analysis adoption baseline](../quality/STATIC_ANALYSIS_ADOPTION_BASELINE_2026-08-25.md) — Fast source security gate, reviewed suppression boundary, staged assertion hardening, and hosted-compute limits.
- [Legacy milestone reconciliation](../quality/LEGACY_MILESTONE_RECONCILIATION_2026-08-19.md) — Source review and completed migration of the remaining pre-v2 audit issues into v2.1 and v2.2.
- [Release records](../releases/) — Version-specific public release documentation.

## Maintenance

```bash
make docs-inventory-sync  # reconcile added, moved, and removed repository documents
make docs-inventory-md    # regenerate the human-readable inventory
make docs-check           # blocking metadata, links, lifecycle, and drift checks
make docs-audit           # informational full-corpus classification report
```
