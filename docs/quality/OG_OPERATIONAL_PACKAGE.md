---
type: Runbook
title: OG operational package boundary
description: Records the prepared OG operational resource package and its unqualified evidence boundary.
resource: docs/quality/
tags: [graph, operational-profile, qualification]
audience: [maintainer, contributor, operator, agent]
last_verified: 2026-10-17
stale_after: 2027-04-13
status: draft
classification: active
owner: quality
---

# OG operational package boundary

This document records the prepared source package for the experimental OG process gateway. It describes package contents and the evidence still required; it does not establish runtime support or compatibility with an external consumer.

## Profile state

The packaged descriptor identifies `plumber.og.operational/v1` and remains `unqualified`. Its four declared rows—Linux x86_64 with Python 3.12 and 3.13, and macOS arm64 with Python 3.12 and 3.13—remain `planned`. The profile advertises only graph identification and a complete topology snapshot from an OG Markdown source.

The dependency profile records an offline no-header UV export of the approved alpha lock with its MCP-only security amendment: the 73-entry native export has a pinned SHA-256, and the packaged requirements prepend the recorded `--require-hashes` policy line without changing those native bytes. The exact closure includes `mcp` 1.30.0 for [GHSA-84m7-p3x7-pcfv](https://github.com/advisories/GHSA-84m7-p3x7-pcfv), `GitPython` 3.2.1, `multidict` 6.9.1 and `logseq-matryca-parser` 1.9.0. Only MCP and its root requirement changed; all unrelated lock records remain byte-identical. The older branch's virtualenv and python-discovery closure remains excluded. The profile binds project version `2.1.0a1`, root-lock bytes, native export, packaged requirements and the complete resource digest chain. The export does not install dependencies. This remains preparation metadata, not proof that an installed package has been qualified or that future dependency versions are compatible.

## Package contents and bounds

The package carries a finite manifest, descriptor, schemas, dependency profile, hash-locked requirements, TCK cases, topology golden, and five synthetic Markdown fixtures. The descriptor binds the schema and resource digest values plus the original bytes of the TCK and process-consumer modules at fixed package-relative paths. The manifest binds the exact static resource inventory. Synthetic privacy canaries occupy both an outliner block and a page-property value; Parser 1.9.0 diagnostics retain the declared 5-page, 9-block, 2-edge complete topology. Fixtures contain no user graph data.

Physical namespace-file qualification is deferred. The existing nested-directory fixture `pages/sub/x.md` is not evidence for decoding the physical file `pages/sub___x.md` as semantic page `sub/x`. This package does not change the fixture or golden bytes and makes no namespace-file compatibility claim from them.

The process consumer uses a 180-second execution limit, 4 MiB stdout and 512-byte stderr limits, and a 5-second total owned-process cleanup budget. Fixture roots are private to each invocation; directories use mode `0700` and files use mode `0600`. On cleanup uncertainty, the harness stops subsequent invocations and retains its synthetic root rather than treating uncertain cleanup as success.

The TCK's installed-package interface is:

```text
python -I -B -m matryca_plumber.graph_gateway.tck --report FILE
```

It accepts only an explicit report destination and uses the packaged synthetic inputs. Resource authentication precedes origin admission. Source-checkout, editable or outside-prefix execution stops before environment enumeration, fingerprinting or controls with exit 2, `not_run` / `not_installed` / `unqualified`; its path-free report retains authenticated resource evidence, identity booleans and `sha256: null` with an explicit uncollected fingerprint scope. For an admitted installed origin, the TCK records bounded environment-artifact fingerprints over all regular-file bytes and directory names beneath the resolved `purelib` and `platlib` roots inside the active prefix: at most 100,000 entries, 64 MiB per file, and 512 MiB total. Unknown, unreadable, or over-budget inventory still fails closed as a qualification failure, not as an uninstalled-origin refusal; the fingerprint is checked before and after every child invocation. The TCK schedules native synthetic timeout, stdout/stderr overflow, same-group SIGKILL escalation, and an injected cleanup-interruption fallback control through the same process reader; their outcomes remain separately labeled. It does not accept a user graph. Source-level unit tests map capture bounds and integrity, addition/removal, audit, startup, inventory mutation, and process controls, but those tests are not black-box proof of the installed TCK's behavior.

## Evidence boundary and remaining gates

The present deliverable is source preparation only. No package build or install, public wheel or sdist admission, installed TCK execution, runtime-matrix result, or external-consumer update is included. No Trama compatibility, stable support, or qualification claim is made.

Future qualification must bind the exact wheel and sdist bytes, verify package namespace and installed-file integrity and import origins, then run the installed TCK against both artifact paths in every declared runtime row. It must also verify the bounded environment inventory remains unchanged. These are separate gates; passing source tests or ordinary hosted source CI cannot substitute for them.
