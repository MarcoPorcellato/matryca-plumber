# First contribution

One-page path from fork to a green PR. Full rules live in [`CONTRIBUTING.md`](../CONTRIBUTING.md).

## Before you code

1. Read the hook in [`README.md`](../README.md) — Matryca Plumber is **Logseq OG** (Markdown on disk), not a hosted notes API.
2. Pick work:
   - [Good first issues](https://github.com/MarcoPorcellato/matryca-plumber/issues?q=is%3Aopen+label%3A%22good+first+issue%22) (label `good first issue`)
   - Tier F Clean Code slices — [`good_first_issues_blueprints.md`](../good_first_issues_blueprints.md)
3. For architecture debate (v2 Shadow DB), use [Discussion #19](https://github.com/MarcoPorcellato/matryca-plumber/discussions/19); for trackable bugs/features, open an **issue**.

## Local setup

```bash
git clone https://github.com/MarcoPorcellato/matryca-plumber.git
cd matryca-plumber
make install
cd frontend && npm install && npm run build && cd ..
```

Requires **Python ≥3.12** and **Node.js 22** (see [`pyproject.toml`](../pyproject.toml)).

## Dev loop

```bash
make test-fast    # fast pytest loop (~seconds)
make ci           # full gate before PR (format-check + lint + mypy + tests)
```

Graph changes: never delete `id::` lines; respect OCC — see **Phase 0–4** in [`CONTRIBUTING.md`](../CONTRIBUTING.md).

## Open a PR

1. Branch from `main`.
2. Run `make ci` locally.
3. User-visible changes: bullet under `## [Unreleased]` in [`CHANGELOG.md`](../CHANGELOG.md).
4. Use the [PR template](https://github.com/MarcoPorcellato/matryca-plumber/blob/main/.github/pull_request_template.md) — link `Fixes #N` or `Refs #N`.

**Merge bar:** `make check` / `make ci` green on GitHub Actions.

## Where to ask

| Question | Channel |
|----------|---------|
| Bug or feature | [GitHub Issue](https://github.com/MarcoPorcellato/matryca-plumber/issues/new/choose) |
| RFC / design | [Discussions](https://github.com/MarcoPorcellato/matryca-plumber/discussions) |
| Security | [Private advisory](https://github.com/MarcoPorcellato/matryca-plumber/security/advisories/new) — not a public issue |
| Conduct | marco@matryca.ai — [`CODE_OF_CONDUCT.md`](../CODE_OF_CONDUCT.md) |
