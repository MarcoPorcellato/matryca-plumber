---
type: Runbook
title: OG operational package boundary
description: Records the prepared OG operational resource package and its unqualified evidence boundary.
resource: docs/quality/
tags: [graph, operational-profile, qualification]
audience: [maintainer, contributor, operator, agent]
last_verified: 2026-10-13
stale_after: 2027-04-13
status: draft
classification: active
owner: quality
---

# OG operational package boundary

This document records the prepared source package for the experimental OG process gateway. It describes package contents and the evidence still required; it does not establish runtime support or compatibility with an external consumer.

## Profile state

The packaged descriptor identifies `plumber.og.operational/v1` and remains `unqualified`. Its four declared rows—Linux x86_64 with Python 3.12 and 3.13, and macOS arm64 with Python 3.12 and 3.13—remain `planned`. The profile advertises only graph identification and a complete topology snapshot from an OG Markdown source.

The dependency profile records a no-header UV export of the frozen lock: its 83-entry native export has a pinned SHA-256, and the packaged requirements prepend the recorded `--require-hashes` policy line without changing those native bytes. The lock-derived closure includes `virtualenv` 21.7.13 and `python-discovery` 1.6.0 alongside the exact `logseq-matryca-parser` 1.9.0 requirement, and introduces no dependency. This remains preparation metadata, not proof that an installed package has been qualified.

## Package contents and bounds

The package carries a finite manifest, descriptor, schemas, dependency profile, hash-locked requirements, TCK cases, topology golden, and five synthetic Markdown fixtures. The descriptor binds the schema and resource digest values plus the original bytes of the TCK and process-consumer modules at fixed package-relative paths. The manifest binds the exact static resource inventory. Synthetic privacy canaries occupy both an outliner block and a page-property value; Parser 1.9.0 diagnostics retain the declared 5-page, 9-block, 2-edge complete topology. Fixtures contain no user graph data.

The process consumer uses a 180-second execution limit, 4 MiB stdout and 512-byte stderr limits, and a 5-second total owned-process cleanup budget. Fixture roots are private to each invocation; directories use mode `0700` and files use mode `0600`. On cleanup uncertainty, the harness stops subsequent invocations and retains its synthetic root rather than treating uncertain cleanup as success.

The TCK's installed-package interface is:

```text
python -I -B -m matryca_plumber.graph_gateway.tck --report FILE
```

It accepts only an explicit report destination and uses the packaged synthetic inputs. It records installed-origin and bounded environment-artifact fingerprints over all regular-file bytes and directory names beneath the resolved `purelib` and `platlib` roots inside the active prefix: at most 100,000 entries, 64 MiB per file, and 512 MiB total. Unknown, unreadable, or over-budget inventory fails closed; the fingerprint is checked before and after every child invocation. The TCK schedules native synthetic timeout, stdout/stderr overflow, same-group SIGKILL escalation, and an injected cleanup-interruption fallback control through the same process reader; their outcomes remain separately labeled. It does not accept a user graph. Source-checkout or editable execution is rejected as installed evidence. Source-level unit tests map capture bounds and integrity, addition/removal, audit, startup, inventory mutation, and process controls, but those tests are not black-box proof of the installed TCK's behavior.

## Evidence boundary and remaining gates

The present deliverable is source preparation only. No package build or install, public wheel or sdist admission, installed TCK execution, runtime-matrix result, or external-consumer update is included. No Trama compatibility, stable support, or qualification claim is made.

Future qualification must bind the exact wheel and sdist bytes, verify package namespace and installed-file integrity and import origins, then run the installed TCK against both artifact paths in every declared runtime row. It must also verify the bounded environment inventory remains unchanged. These are separate gates; passing source tests or ordinary hosted source CI cannot substitute for them.
