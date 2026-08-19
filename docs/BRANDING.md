---
type: Document
---
# Branding and naming (Matryca Plumber)

Use this guide in README, UI copy, operator docs, and release notes.

## Product vs company

| Name | Meaning |
|------|---------|
| **Matryca Plumber** | This open-source application: local-first Logseq maintenance daemon, CLI, and Sovereign UI (`matryca-plumber` on PyPI). |
| **[Matryca.ai](https://matryca.ai)** | The studio behind the product. |
| **Marco Porcellato** | Author and maintainer of Matryca Plumber (Matryca.ai). |
| **Matryca Brain** | Separate commercial tier (not this repo). Do not call Matryca Plumber “Matryca Brain”. |

## Writing rules

1. **Do not shorten the app to “Matryca”** in user-facing text. Write **Matryca Plumber** on first mention in a section; later you may say “Plumber” only when the context is unmistakable (e.g. inside the Matryca Plumber control room).
2. **“Matryca” alone** is reserved for the company (**Matryca.ai**), graph page titles configured in wiki YAML (e.g. `Matryca Dashboard`), or block headings intentionally stamped in the vault (e.g. `### Matryca Backlink Context`).
3. **Attribution** — Where helpful (README intro, pre-flight modal, CONTRIBUTING), include: *Developed by Marco Porcellato · [Matryca.ai](https://matryca.ai)*.
4. **Technical identifiers** — Keep unchanged: `matryca-plumber`, `matryca plumber`, `MATRYCA_*`, `X-Matryca-Token`, `matryca-plumber::`, `MatrycaWikiConfig`, `MatrycaMCPServer`.
5. **AI agents** — Direct autonomous hosts to [`llms.txt`](../llms.txt) / PyPI `uvx matryca-plumber`; do not instruct them to `git clone` this repo unless they are contributing code.

## Examples

| Avoid | Prefer |
|-------|--------|
| “Matryca is headless…” | “Matryca Plumber is headless…” |
| “Point Matryca at your vault” | “Point Matryca Plumber at your vault” |
| “Install Matryca via uv” | “Install Matryca Plumber via `uv tool install matryca-plumber`” |
| “The Matryca app” | “Matryca Plumber” |
