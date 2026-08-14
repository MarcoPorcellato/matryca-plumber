# Gate B RC2 terminal qualification evidence — 2026-08-13

## Purpose and decision boundary

This record captures the terminal dual-profile Gate B qualification of the
published `matryca-plumber==2.0.0rc2` artifact. It is evidence for that exact
installed public wheel only. It does not qualify a later source commit, a new
wheel, or the stable `2.0.0` artifact by implication.

The campaign exercised the default-on Shadow profile and the Strict Read Only
profile with an external derived-cache root. Logseq Markdown remained the
system of record throughout.

## Frozen artifact and runner binding

| Field | Value |
| --- | --- |
| Public release | [`v2.0.0-rc.2`](https://github.com/MarcoPorcellato/matryca-plumber/releases/tag/v2.0.0-rc.2) |
| Release commit | `c4cb76dd1c65edc2f55dd0f16384da196144bd9c` (verified) |
| Wheel | `matryca_plumber-2.0.0rc2-py3-none-any.whl` |
| Wheel SHA-256 | `0b0c8a94377b9c1805b7304a10fe728c6d5c1f4ba120519b6e25c374c0a42318` |
| Frozen deployment manifest SHA-256 | `23a5ef39b8e33dcf00b8d2e8d3cb8c260b523c203fe0d991365fce5cf3666c00` |
| Runner commit | `013267d168a66947fb581a95ed20b98194b29edb` (verified) |
| Qualifier SHA-256 | `95f2e329834897ad3177c9ce2b2da6b6049b446754e61daf6e328b876a8d7962` |
| Supervisor SHA-256 | `bfcae04483a5003df8e83fb52ece42c0c933d7c708c9e73d55733309736e7445` |
| Parser runtime | `logseq-matryca-parser==1.7.1` |

The campaign verified the installed wheel `RECORD` and provenance before
crediting time. The default-on and Read Only LaunchAgent manifests matched the
frozen deployment manifest. No checkout-local package was used as candidate
provenance.

## Terminal results

| Profile | Terminal status | Valid elapsed time | Target | Completed cycles | Recorded attempts |
| --- | --- | ---: | ---: | ---: | ---: |
| Default-on | `PASS` | 259,548.995 s | 259,200 s | 417 | 834 |
| Read Only + external Shadow | `PASS` | 259,421.167 s | 259,200 s | 417 | 834 |

For both profiles:

- every recorded attempt passed;
- attempt sequences were contiguous from `0` through `833`;
- each attempt's predecessor digest matched the prior attempt digest and the
  final cursor matched the final attempt;
- the source-to-working-copy Markdown fingerprint stayed equal and the
  source was unchanged during copy;
- standard error remained empty;
- the terminal supervisor exited successfully after the terminal result.

The qualification includes the profile-specific default-on/explicit-opt-out
and Strict Read Only/external-cache controls defined by the frozen runner. It
does not credit downtime, setup, preflight, RC1 evidence, or prior invalid
attempts.

## Result and remaining stable gates

This closes the **Default-on soak** and **Read Only external-cache soak** rows
for the exact RC2 artifact in the v2 stable-readiness decision. RC1's split
outcome remains preserved as historical evidence and is not rewritten.

Stable `v2.0.0` remains a separate maintainer decision. The persistent
exact-public-`2.0.0rc2` upgrade/rollback receipt has since reached terminal
`PASS` across `1.14.5`, `2.0.0a5`, `2.0.0b1`, and `2.0.0rc1`; it binds the wheel
SHA-256 recorded above and preserves working Markdown after each rollback. It
closes the RC2 upgrade-matrix row only, not final stable-artifact verification.
The following gates are intentionally still open: the minimum RC observation
window, supported-platform evidence, performance disposition, stable operator
wording, and full release proof on the exact stable commit.

The published RC2 wheel is therefore a qualified public prerelease for users
who want to test the v2 Shadow DB contract now. It must not be represented as
the stable `2.0.0` release until the remaining gates are complete.

## Related records

- [RC and stable readiness decision](issue-bodies/v2-rc-stable-readiness.md)
- [Gate B public-RC soak runbook](GATE_B_RC_SOAK_RUNBOOK.md)
- [RC1 failure disposition and RC2 remediation](GATE_B_RC1_DEFAULT_ON_FAILURE_2026-08-09.md)
- [v2.0.0 stable readiness issue #343](https://github.com/MarcoPorcellato/matryca-plumber/issues/343)
