# AGENTS.md — Matryca Plumber instruction router

This file routes coding assistants to the correct instruction layer. **Do not load every doc at once.**

## Audience map

| You are… | Read first | Do not load |
|----------|------------|-------------|
| **Cursor agent patching this repo** | [`.cursor/rules/00-karpathy-agent-behavior.mdc`](.cursor/rules/00-karpathy-agent-behavior.mdc), this file, [`CONTRIBUTING.md`](CONTRIBUTING.md), [`docs/CLEAN_CODE_ARCHITECTURE.md`](docs/CLEAN_CODE_ARCHITECTURE.md) | Full [`SYSTEM_PROMPT.md`](SYSTEM_PROMPT.md) (runtime vault law) |
| **External agent on a user Logseq vault** | [`llms.txt`](llms.txt) → [`SYSTEM_PROMPT.md`](SYSTEM_PROMPT.md) | [`.cursor/rules/`](.cursor/rules/) |
| **Maintainer changing MCP/CLI/prompt contracts** | [`docs/PROMPT_ARCHITECTURE.md`](docs/PROMPT_ARCHITECTURE.md), [`docs/openspec/agent-onboarding.md`](docs/openspec/agent-onboarding.md), [`docs/openspec/agent/`](docs/openspec/agent/), [`docs/openspec/llm-performance.md`](docs/openspec/llm-performance.md), rule `11-prompt-maintainer` | — |
| **Maintainer planning v2.0 Shadow DB** | [`docs/roadmaps/ROADMAP_V2_PREPARATION.md`](docs/roadmaps/ROADMAP_V2_PREPARATION.md), [`v2_preparation_blueprints.md`](v2_preparation_blueprints.md), [Epic #20](https://github.com/MarcoPorcellato/matryca-plumber/issues/20) | Full v1.9.x audit triage docs |

## Cursor rule routing

| Rule | When it applies |
|------|-----------------|
| [`00-karpathy-agent-behavior.mdc`](.cursor/rules/00-karpathy-agent-behavior.mdc) | Always — investigate, minimal diff, run checks |
| [`01-core-paradigm.mdc`](.cursor/rules/01-core-paradigm.mdc) | Logseq OG blocks, properties, namespaces → SSOT [`docs/openspec/agent/paradigm.md`](docs/openspec/agent/paradigm.md) |
| [`02-python-standards.mdc`](.cursor/rules/02-python-standards.mdc) | Any `*.py` edit |
| [`03-logseq-api.mdc`](.cursor/rules/03-logseq-api.mdc) | `src/**/*.py` — headless file I/O default |
| [`04-spatial-parser.mdc`](.cursor/rules/04-spatial-parser.mdc) | `src/**/*.py` graph parsing |
| [`05-release-preparation.mdc`](.cursor/rules/05-release-preparation.mdc) | Semver release (on request) |
| [`06-auto-changelog.mdc`](.cursor/rules/06-auto-changelog.mdc) | User-visible changes — update `CHANGELOG.md` |
| [`07-env-example.mdc`](.cursor/rules/07-env-example.mdc) | New/changed `MATRYCA_*` env vars |
| [`08-github-workflow-standards.mdc`](.cursor/rules/08-github-workflow-standards.mdc) | GitHub issues/PRs (on request) |
| [`09-github-identity-marco-porcellato.mdc`](.cursor/rules/09-github-identity-marco-porcellato.mdc) | GitHub actions as maintainer |
| [`10-tooling-static-analysis-policy.mdc`](.cursor/rules/10-tooling-static-analysis-policy.mdc) | Public docs / CI — vendor-agnostic tooling |
| [`11-prompt-maintainer.mdc`](.cursor/rules/11-prompt-maintainer.mdc) | Prompt fragments, Tier-1 builders, MCP docstrings (on request) |
| [`12-clean-code-architecture.mdc`](.cursor/rules/12-clean-code-architecture.mdc) | Clean Code & Clean Architecture — repo-wide boundaries, `env_parse`, layer tests |

## Runtime agent surfaces

- **Distribution quickstart:** [`llms.txt`](llms.txt) and [`.well-known/llms.txt`](.well-known/llms.txt) (byte-identical)
- **Cognitive law (Tier-2 vault agents):** [`SYSTEM_PROMPT.md`](SYSTEM_PROMPT.md) — LLM OS, MCP tools, Safe-Sync
- **OpenSpec maintainer specs:** [`docs/openspec/agent-onboarding.md`](docs/openspec/agent-onboarding.md)

## Verification before merge

```bash
make agents-check          # AGENTS.md paths, llms byte-identity, rule index
make build-system-prompt   # after editing docs/openspec/agent/ fragments
make check-system-prompt   # fragment build-hash vs SYSTEM_PROMPT.md
make ci                  # full CI gate (format-check + lint + types + tests)
```
