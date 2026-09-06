---
type: audit
title: Logseq DB bundled CLI artifact qualification evidence — 2026-09-06
description: Exact-artifact evidence for the first bundled-CLI qualification attempt, which stopped before execution because the selected official macOS arm64 application failed code-signature verification.
resource: docs/quality/LOGSEQ_DB_CLI_ARTIFACT_EVIDENCE_2026-09-06.md
tags: [logseq, database, compatibility, qualification, provenance, safety]
last_verified: 2026-09-06
stale_after: 2026-12-05
status: blocked
classification: active
audience: [maintainer, contributor, operator]
owner: integration
authority: logseq-db-host-capability-attempt
related:
  - ../decisions/2026-09-05-plumber-logseq-gateway-authority.md
  - LOGSEQ_DB_CAPABILITY_BASELINE_2026-09-05.md
  - EVIDENCE_INDEX.md
---

# Logseq DB bundled CLI artifact qualification evidence — 2026-09-06

## Verdict

**Terminal outcome: `upstream_blocked`.**

The first exact-artifact attempt stopped before running Logseq. The selected
official macOS arm64 ZIP matched both GitHub's asset digest and the separately
published checksum list, but the extracted application failed Apple's strict
code-signature verification. The failure reproduced after both conventional
ZIP extraction and Apple's metadata-preserving archive extraction.

No Logseq executable was invoked. No graph, fixture, worker, lock, server,
configuration, or user data was created, opened, queried, switched, or changed.
This result does not qualify or reject the bundled CLI's read semantics. It
only proves that this exact application archive cannot cross Matryca's
executable-admission boundary.

## Exact public artifact binding

| Field | Value |
| --- | --- |
| Repository | `logseq/logseq` |
| GitHub release ID | `248188362` |
| Release name | `Desktop app Nightly Release 20260826` |
| Published | `2026-08-26T15:08:02Z` |
| Release tag | `nightly` |
| Release target field | `dde0aba2d441c962d28989b0af894cc261da3898` |
| Target tree | `5ef6f5dd74a2e9970285d99f24d8149ce4c29aca` |
| Target commit verification | unsigned |
| Current mutable `nightly` ref observed on 2026-09-06 | `f7362f07b0cecd1c3ef6e0983c1446868658fb00` |
| Asset ID | `530968220` |
| Asset | `Logseq-darwin-arm64-2.0.1-alpha+nightly.20260826.zip` |
| Asset size | `168418244` bytes |
| GitHub asset digest | `sha256:f3cbaff017f2063a68583d9ca885aa1e52f1e324df98ea4fcb24c75fee2c244d` |
| Downloaded ZIP digest | `sha256:f3cbaff017f2063a68583d9ca885aa1e52f1e324df98ea4fcb24c75fee2c244d` |
| Official checksum-list asset ID | `530968241` |
| Official checksum-list digest | `sha256:a05a3d55fe9f6137e1b590245a630bf9b09895c1b66f1350df57861cfc125707` |
| Checksum-list ZIP entry | `f3cbaff017f2063a68583d9ca885aa1e52f1e324df98ea4fcb24c75fee2c244d` |
| Platform | macOS `15.7.3` (`24G419`), arm64 |

The release target field and mutable nightly ref are recorded separately. They
are not treated as the embedded CLI revision because the executable did not
pass admission and `--version` was therefore not run.

## Static application observations

The extracted bundle identified itself as `com.logseq.logseq`, version
`2.0.1`, arm64, with Team Identifier `K378MFWK59`, hardened-runtime metadata,
and a stapled notarization ticket. Those metadata do not override failed
signature verification.

Selected content digests, retained only to make the failed application image
identifiable, were:

| Bundle object | SHA-256 |
| --- | --- |
| Main executable | `1439b505b36e41b24e1bbe514725da0b0d0c438f9efcb8419a2877c38fce5773` |
| CodeResources | `9f22d2782c8ed6aaa12da4dfc9db9b54d5eee86a5ea2f505b2620e5d964376fd` |
| Info.plist | `9450af57c73d35607319b631cebb998c90382b412e48e3c07b4b37714b48575e` |
| app.asar | `9f5036361c52bccdabe1ecb9abd84d2b551b8b5828cc77a816fe7774ccf41c29` |

Apple's verifier returned `invalid signature (code or signature have been
modified)` for the application, its main executable, Electron Framework, and
each packaged helper application. Gatekeeper assessment did not produce a
successful admission. The same application-level failure remained after an
independent metadata-preserving extraction.

## Official documentation and example policy

Current official Logseq source documentation was inspected at source commit
`d2ab7726ab74402c14fdbc33041a89ac55c899ae`, tree
`b2aad1319bf1fe21f7c7d4e713685ae4cc504b6c`. The CLI guide blob was
`9ee9aadf75073622c9d90fa51ca03304752d244c`; the DB query guide blob was
`29044c08ba599f4da0edd9ebb239fa13d838c455`.

Those current documents are orientation, not proof of behavior in the older
selected artifact. They describe:

- isolated roots through `--root-dir`;
- explicit graph selection through `--graph`;
- structured output through `--output json`;
- graph metadata through `graph info`;
- page and block-tree reads through `show`;
- runnable examples through the bundled `example` surface;
- automatic worker lifecycle that may create lock state or replace a
  revision-mismatched worker.

Official sources do not publish a reusable DB fixture with stable page and
block identifiers. The accepted future fixture approach is therefore to use
the admitted artifact's own help and examples to provision one fresh synthetic
graph in a disposable isolated root, record its runtime-generated identifiers,
then freeze it before a separately bounded read-only qualification. Fixture
provisioning is graph mutation and must never be counted as read-only evidence.

That provisioning did not occur in this attempt because executable admission
failed first.

## Transport and safety boundary

This attempt exercised no transport. The future selection order remains:

1. exact bundled CLI;
2. official Plugin SDK;
3. MCP stdio.

MCP HTTP remains blocked while
[Logseq db-test #1101](https://github.com/logseq/db-test/issues/1101) is open.
The previously reported MCP page-read defect in
[Logseq db-test #833](https://github.com/logseq/db-test/issues/833) was closed
as completed on 2026-08-31, but issue closure is not exact-artifact evidence.

No fallback transport was attempted after the artifact admission failure. No
internal SQLite access, Parser DB path, Markdown fallback, Shadow use, sync,
import, export, graph switching, server command, event subscription, write,
or UI automation occurred.

## Re-entry gate

Issue [#491](https://github.com/MarcoPorcellato/matryca-plumber/issues/491)
may start a new bundled-CLI attempt only with a newly selected official
macOS arm64 artifact that has:

1. immutable GitHub asset identity, size, and publisher-provided digest;
2. a locally matching downloaded digest;
3. successful Apple code-signature and Gatekeeper verification after
   metadata-preserving extraction or from an independently admitted disk image;
4. an inspectable bundled CLI whose `--version` and relevant help output can be
   bound before any fixture is provisioned;
5. a fresh disposable root and an explicit separation between fixture writes
   and read-only qualification.

A later artifact receives a new evidence record. This terminal failed attempt
must not be overwritten, reclassified as a capability result, or used to claim
Logseq DB support.

## Product boundary

Matryca Plumber source and runtime behavior are unchanged. `GraphReadPort`
remains filesystem/Shadow-only. No DB adapter, public endpoint, Parser DB path,
consumer wiring, event path, Shadow ingestion, or write capability is enabled.
Trama and Brain remain downstream consumers of future Plumber-owned contracts.

