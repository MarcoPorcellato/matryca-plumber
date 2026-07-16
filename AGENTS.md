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

<!-- gitnexus:start -->
# GitNexus — Code Intelligence

This project is indexed by GitNexus as **matryca-plumber** (7859 symbols, 17081 relationships, 300 execution flows). Use the GitNexus MCP tools to understand code, assess impact, and navigate safely.

> Index stale? Run `node .gitnexus/run.cjs analyze` from the project root — it auto-selects an available runner. No `.gitnexus/run.cjs` yet? `npx gitnexus analyze` (npm 11 crash → `npm i -g gitnexus`; #1939).

## Always Do

- **MUST run impact analysis before editing any symbol.** Before modifying a function, class, or method, run `impact({target: "symbolName", direction: "upstream"})` and report the blast radius (direct callers, affected processes, risk level) to the user.
- **MUST run `detect_changes()` before committing** to verify your changes only affect expected symbols and execution flows. For regression review, compare against the default branch: `detect_changes({scope: "compare", base_ref: "main"})`.
- **MUST warn the user** if impact analysis returns HIGH or CRITICAL risk before proceeding with edits.
- When exploring unfamiliar code, use `query({search_query: "concept"})` to find execution flows instead of grepping. It returns process-grouped results ranked by relevance.
- When you need full context on a specific symbol — callers, callees, which execution flows it participates in — use `context({name: "symbolName"})`.
- For security review, `explain({target: "fileOrSymbol"})` lists taint findings (source→sink flows; needs `analyze --pdg`).

## Never Do

- NEVER edit a function, class, or method without first running `impact` on it.
- NEVER ignore HIGH or CRITICAL risk warnings from impact analysis.
- NEVER rename symbols with find-and-replace — use `rename` which understands the call graph.
- NEVER commit changes without running `detect_changes()` to check affected scope.

## Resources

| Resource | Use for |
|----------|---------|
| `gitnexus://repo/matryca-plumber/context` | Codebase overview, check index freshness |
| `gitnexus://repo/matryca-plumber/clusters` | All functional areas |
| `gitnexus://repo/matryca-plumber/processes` | All execution flows |
| `gitnexus://repo/matryca-plumber/process/{name}` | Step-by-step execution trace |

## CLI

| Task | Read this skill file |
|------|---------------------|
| Understand architecture / "How does X work?" | `.claude/skills/gitnexus/gitnexus-exploring/SKILL.md` |
| Blast radius / "What breaks if I change X?" | `.claude/skills/gitnexus/gitnexus-impact-analysis/SKILL.md` |
| Trace bugs / "Why is X failing?" | `.claude/skills/gitnexus/gitnexus-debugging/SKILL.md` |
| Rename / extract / split / refactor | `.claude/skills/gitnexus/gitnexus-refactoring/SKILL.md` |
| Tools, resources, schema reference | `.claude/skills/gitnexus/gitnexus-guide/SKILL.md` |
| Index, status, clean, wiki CLI commands | `.claude/skills/gitnexus/gitnexus-cli/SKILL.md` |

<!-- gitnexus:end -->
