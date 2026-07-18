# Matryca knowledge bundle

**OKF-inspired pilot — partial conformance.** Existing canonical paths under `docs/` remain authoritative during Phase 1.

This directory introduces structured, metadata-rich documentation for progressive disclosure. See [`profile.md`](profile.md) for the local profile and conformance scope.

## Sections

| Area | Status | Entry |
| --- | --- | --- |
| Architecture | pilot | [`architecture/index.md`](architecture/index.md) |
| Product | planned Phase 2 | legacy: [`../BRANDING.md`](../BRANDING.md) |
| Getting started | planned Phase 2 | legacy: [`../FIRST_CONTRIBUTION.md`](../FIRST_CONTRIBUTION.md), [`../../CONTRIBUTING.md`](../../CONTRIBUTING.md) |
| Guides | planned Phase 2 | legacy: [`../integrations/`](../integrations/) |
| Reference | planned Phase 2 | legacy: [`../../llms.txt`](../../llms.txt), [`../../.env.example`](../../.env.example) |
| Specifications | planned Phase 3 | legacy: [`../openspec/README.md`](../openspec/README.md) |
| Decisions | planned Phase 4 | legacy: [`../PROJECT_DIARY.md`](../PROJECT_DIARY.md) |
| Roadmaps | planned Phase 4 | legacy: [`../roadmaps/`](../roadmaps/), [`../../ROADMAP.md`](../../ROADMAP.md) |
| Quality | planned Phase 4 | legacy: [`../quality/`](../quality/) |
| Releases | planned Phase 4 | legacy: [`../releases/`](../releases/) |

## Inventory

- Curated SSOT: [`inventory.json`](inventory.json)
- Generated view: [`inventory.md`](inventory.md) (do not edit by hand)

Regenerate with `make docs-inventory-md`. Reconcile new or missing paths with `make docs-inventory-sync`.

## Verification

```bash
make docs-check    # blocking: bundle + inventory drift
make docs-audit    # informational: legacy coverage
```
