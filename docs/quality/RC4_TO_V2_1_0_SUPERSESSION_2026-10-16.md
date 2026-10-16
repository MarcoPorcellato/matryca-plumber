---
type: Decision
---
# RC4 to 2.1.0 qualification-track supersession

Date: 2026-10-16. Status: **accepted release-line decision; no qualification,
tag or publication result**.

## Decision

Prioritize an experimental offline OG identity/topology producer on the 2.1.0
alpha line, followed by Trama's independent admission gate. The
[2.1.0a1 plan](V2_1_0A1_RELEASE_QUALIFICATION_PLAN_2026-10-16.md)
is now the active limited-release plan; the
[release process](../RELEASE_PROCESS.md) owns release mechanics.
This implements the approved producer-first and single-successor-line decisions,
not a reduction of the full programme's acceptance criteria.

The 2.0.1 line ends with the published
[RC3 prerelease](../releases/v2.0.1-rc.3-GITHUB.md); RC4 preparation was not
published. There is **no current final candidate**. Earlier RC4 source selections,
including the `74884c38…` and `e350125f…` records, did exist and remain historical.
Do not rewrite that history as “no candidate was ever selected.”

## What is preserved

The prior [RC4 preparation](V2_0_1_RC4_RELEASE_PREPARATION_2026-09-06.md) and
[qualification plan](V2_0_1_RC4_RELEASE_QUALIFICATION_PLAN_2026-09-06.md)
remain byte-preserved historical authorities for their own attempts. Candidates,
failed and consumed attempts, provenance, reviews, receipts and private
checkpoints remain unchanged. Neither historical local success nor a static
contract/TCK qualifies a later public artifact or operational consumer.

No historical evidence is transferred as a 2.1.0 PASS. Useful implementation
and procedures may be reused only with fresh exact-source/artifact verification.
Stable v2.0.0 remains the default; this decision does not retrospectively qualify
or publish RC4, close its tracking issue or promise stable 2.1.0 support.

## Transferred unfinished obligations

| Obligation | Successor disposition |
| --- | --- |
| Installed Windows launcher/receipt boundary (slice L) | Retain the accepted implementation and security criteria; finish independently before a Windows package qualification claim. Upstream byte-only provenance is not installed execution evidence. |
| Native Windows x64 installed-package and process-lifecycle row | Remains NO-GO until exact native evidence passes. POSIX runtime results and a Windows gateway refusal do not satisfy it. |
| Aggregate full Stage A workflow | Land its separately reviewed implementation before selecting the full candidate; do not dispatch the withheld prototype. |
| Full three-platform Stage A | Select a new clean source after all required implementation/workflow merges; qualify Linux x64, macOS arm64 and Windows x64 against the one exact canonical pair before the corresponding full-platform claim. |
| Tier 3 dual-profile Gate B | Retain both exact-public-artifact profiles, each with at least 259,200 valid seconds and all digest, restart, checkpoint and lifecycle criteria. No earlier campaign transfers. |
| Notes, manifests, inventory and issue evidence | Reconcile current pointers without altering old records; record exact candidate/publication results only when they exist. |

These obligations continue on the full 2.1.0 qualification track under
[Plumber #582](https://github.com/MarcoPorcellato/matryca-plumber/issues/582).
This record does not assert that the remote issue or any local tracker has
already been updated or completed.

## Separate experimental gates

The first alpha targets Linux x86_64 and macOS arm64 on CPython 3.12/3.13,
with wheel and sdist installs: eight required rows. The source is offline OG,
content-free and synthetic-only. Windows is refused by the gateway; that narrow
capability restriction does not remove Windows obligations from full package
qualification.

Pre-publication experimental qualification, the maintainer's signed tag and
publication, actual-public-artifact verification and Trama's #2 admission are
distinct gates. Experimental publication never required completion of the
separately governed full Gate B campaign. The later full qualification and
stable decisions still require every applicable obligation above.

The release workflow rebuilds its own canonical wheel/sdist pair; diagnostic
pre-publication hashes are not public artifact hashes. Handoff must bind and
retest the actual public bytes, including full installed-package verification
and operational TCKs. A static schema release alone cannot unblock Trama.

## Explicit non-goals

No DB support, page/block payload, writes, events, sync, Shadow ingestion, public
UI, user-graph access or active-desktop coexistence is included. No dependency
range, Parser release beyond the exact selected profile, Windows support,
Trama compatibility or stable support is admitted by this decision.
