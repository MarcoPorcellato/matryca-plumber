---
okf_version: "0.2"
---

# Matryca Plumber knowledge bundle

This index provides progressive disclosure across maintained concepts and the classified legacy corpus. Matryca Plumber remains the authoritative editing origin; external projections are read-only, Git-provenanced consumer views.

## Documentation system

- [Documentation evolution and operating model](documentation-evolution.md) — Rationale, layers, authority boundaries, maintenance workflow, and migration history.
- [Matryca Plumber knowledge profile](profile.md) — OKF v0.2 compatibility and stricter Matryca producer rules.
- [Repository documentation inventory](inventory.md) — Generated view of every root and `docs/` Markdown surface.
- [Documentation update log](log.md) — Material documentation-system changes, newest first.

## Maintained architecture

- [Architecture index](architecture/) — Progressive-disclosure entry point for the maintained architecture concepts.

## Operator path

- [v2 Shadow DB runtime and operator contract](architecture/shadow-db.md) — Current activation, Read Only, external-cache, health, fallback, quarantine, and evidence links.
- [Release process](../RELEASE_PROCESS.md#v20-promotion-override) — Qualification, authorization, tag, and publication gates.

## Detailed established collections

- [Product identity and branding](../BRANDING.md) — Product naming and public identity.
- [Getting started](../FIRST_CONTRIBUTION.md) — First-contribution path and repository setup.
- [Contributor guide](../../CONTRIBUTING.md) — Development standards and verification gates.
- [OpenSpec index](../openspec/README.md) — Normative feature and agent contracts.
- [Roadmaps](../roadmaps/) — Active and historical delivery plans.
- [Quality evidence](../quality/) — Audits, qualification evidence, and issue-source records.
- [Release records](../releases/) — Version-specific public release documentation.

## Maintenance

```bash
make docs-inventory-sync  # reconcile added, moved, and removed repository documents
make docs-inventory-md    # regenerate the human-readable inventory
make docs-check           # blocking metadata, links, lifecycle, and drift checks
make docs-audit           # informational full-corpus classification report
```
