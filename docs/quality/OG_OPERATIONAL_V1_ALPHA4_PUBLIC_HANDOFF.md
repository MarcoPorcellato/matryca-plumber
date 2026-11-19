---
type: Audit
title: Alpha.4 public OG producer handoff
description: Exact alpha.4 public package identities and bounded experimental OG qualification evidence.
resource: docs/quality/
tags: [graph, operational-profile, qualification, provenance]
audience: [maintainer, contributor, operator, agent]
last_verified: 2026-11-15
stale_after: 2027-05-14
status: stable
classification: active
owner: quality
---

# Alpha.4 public OG producer handoff

**Accepted experimental evidence, not stable qualification or Trama admission.**
The original public Plumber `2.1.0a4` wheel and sdist passed the exact
synthetic, content-free OG identity and topology checks described below.

## Original producer and independent verifier

| Role | Exact binding |
| --- | --- |
| Original producer | `1d884ddcbdb37ecdd0d4ad3ccb3e9a6d406e1bdd`, tree `22bced0e8eef57595acdfed12933e53905f22a95` |
| Signed tag | `v2.1.0-alpha.4`, annotated object `ddbd21acdf1bccd0c861b7027e2dff4bd0c05dfe` |
| Original publisher | [43700694911, attempt 1](https://github.com/MarcoPorcellato/matryca-plumber/actions/runs/43700694911) |
| Public-byte verification | [43716337039, attempt 1](https://github.com/MarcoPorcellato/matryca-plumber/actions/runs/43716337039) |
| Separate recovery verifier | `b505d8e88279c04a531886a221c1b22f2f005740`, tree `022b6c87b7d1357cdc58e880eea68fd82709b34f` |

| Original distribution | Bytes | SHA-256 |
| --- | ---: | --- |
| `matryca_plumber-2.1.0a4-py3-none-any.whl` | 768,418 | `6d611de748d267bf377dd8f3266259ede71268fd39f30ac7136238cc99cdad56` |
| `matryca_plumber-2.1.0a4.tar.gz` | 1,092,752 | `829ab1ca7c5e3427f9c35686a7c0589209c840b1e7b2ccf421f47272e7665dec` |

The [GitHub prerelease](https://github.com/MarcoPorcellato/matryca-plumber/releases/tag/v2.1.0-alpha.4)
and [PyPI release](https://pypi.org/project/matryca-plumber/2.1.0a4/)
provide the original public artifacts. The campaign verified publication
attestations against the original source, signed tag, release workflow and
publisher invocation. The verifier ran from a distinct checkout and was not
the package producer. Do not substitute rebuilt packages or pre-tag hashes.

## Observed result and limits

All eight required jobs succeeded. The original wheel and install from the
original sdist each passed on Linux x86_64 and macOS arm64 with CPython 3.12.14
and 3.13.15: eight installed rows with verified cleanup. Checks covered
installed metadata, `RECORD`, resources, import origins and static and
operational TCKs under the exact hash-locked Parser 1.9.0 closure. Four
independent sdist build environments were used. Same-run reports and the
aggregate were independently verified. The earlier unsuccessful campaign
[43701397202, attempt 1](https://github.com/MarcoPorcellato/matryca-plumber/actions/runs/43701397202)
remains separate; no evidence was transferred from it.

The packaged proposed, planned and unqualified labels remain unchanged.
Windows refusal is not installed Windows qualification. Scope is limited to the
authenticated disposable synthetic fixture and exact evaluated tuples. No user
graphs, native DB, payload, writes, sync, OS network-isolation claim, broad
Logseq application compatibility or stable support follows. Trama's restricted
alpha.3 admission remains separate; this handoff does not admit or re-pin
alpha.4. See the [stable qualification plan](V2_1_0_STABLE_RELEASE_QUALIFICATION_PLAN_2026-11-15.md)
for the carried gates.
