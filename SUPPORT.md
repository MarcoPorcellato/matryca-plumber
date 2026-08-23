# Support

**Matryca Plumber** is maintained by [Marco Porcellato](https://github.com/MarcoPorcellato) · [Matryca.ai](https://matryca.ai).

## Where to get help

| Channel | Use for |
|---------|---------|
| [GitHub Discussions](https://github.com/MarcoPorcellato/matryca-plumber/discussions) | RFCs, architecture debate, open-ended Q&A |
| [GitHub Issues](https://github.com/MarcoPorcellato/matryca-plumber/issues) | Bugs, features, and trackable work with a clear done state |
| [`CONTRIBUTING.md`](CONTRIBUTING.md) | How to run tests, open PRs, and follow Phase 0–4 rules |
| [`SECURITY.md`](SECURITY.md) | **Private** vulnerability reports — do not open public issues |

## Operator docs

- Quick start: [`README.md`](README.md)
- Environment variables: [`.env.example`](.env.example)
- Agent / MCP contract: [`llms.txt`](llms.txt)

## Response expectations

This is a maintainer-led OSS project. Issues and discussions are triaged as
capacity allows; there are no response-time or resolution guarantees.

## Triage and disposition

The maintainer first checks whether a report has enough information to
reproduce or evaluate it, whether it belongs in this repository, and whether it
contains sensitive security information. A report may then be:

- kept open for investigation or implementation;
- converted to a discussion when it is primarily a question or proposal;
- linked to an existing issue or epic when it duplicates tracked work;
- deferred or closed as out of scope, unsupported, unreproducible, or already
  resolved, with the reason recorded where practical.

Priority is based on impact and safety, not arrival order. Active security or
privacy risk is handled ahead of ordinary work. P0/P1 issues affect safety,
data integrity, security, release qualification, or a broad blocking failure;
P2 issues affect important supported behavior without an immediate broad risk;
P3 issues are limited, cosmetic, exploratory, or convenience improvements.
Priority may change as evidence changes. Do not include secrets, private graph
content, credentials, or exploit details in public reports; use
[`SECURITY.md`](SECURITY.md) for vulnerabilities.
