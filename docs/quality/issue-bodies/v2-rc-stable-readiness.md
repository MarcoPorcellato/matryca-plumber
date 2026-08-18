# v2.0.0 RC and stable readiness — decision record

## Problem Description

`v2.0.0-beta.1` published the opt-in Shadow DB read path while preserving
Markdown as the system of record and generational BM25 as the default discovery
path. The next release tracks must not conflate two separate programs:

1. stabilizing the Shadow DB read path for default-on MCP reads in `v2.0.0`;
2. adding biological memory and a Logseq DB write bridge in a later release.

The `v2.0.0` release scope is therefore the Shadow read path only. Biological
memory, Logseq DB Safe-Sync writes, content-aware Tana re-import, hardware
recommendations, and dynamic MCP tool filtering are explicitly deferred to
`v2.1.0` or later. Logseq OG writes remain protected by the existing OCC and
Markdown Safe-Sync contracts.

The beta decision accepted an evidence boundary because its bound soak artifact
predated several fail-safe fixes. That exception does not carry forward. A
default-on release candidate requires both re-qualification of the exact public
`matryca-plumber==2.0.0b1` predecessor and qualification of the exact new
candidate. Evidence from one artifact never transfers silently to the other.

As of 2026-08-05, the published `2.0.0rc1` candidate line contains the Strict Read Only
policy and guarded runtime, external per-user Shadow routing, default-on Shadow
with explicit opt-out, read-only observer daemon, deterministic graph
immutability gate, bounded 8,192-entry BM25 result cache, and Linux/macOS/Windows
Shadow contract CI merged through #376. Gate A is qualified on the exact merged
commit recorded below. This is not a stable release decision.

### Recorded exact-candidate Gate B context

The exact `2.0.0rc1` publication reached a split Gate B outcome. The
`read-only-external` profile is terminal `PASS`, while the `default-on` profile
was stopped and archived as non-terminal `RUNNING` after a bounded timeout
exposed a qualifier cleanup defect. Stable readiness remains blocked.

- Candidate: `matryca-plumber==2.0.0rc1`
- Public wheel SHA-256:
  `f9c60cc89049b9524ca9f9346a053bac3c7aba6f2186d9a31a3993bd7a9253cd`
- Runner source: `main@1e8805ec99c6471549ecf36e4a261a31013a0f6f`
- Qualifier SHA-256:
  `b4cee6a2b6c8a8fbd8bb890cf583b7d126f2e40bda8b55cb7a0c499c8490dbe6`
- Supervisor SHA-256:
  `bfcae04483a5003df8e83fb52ece42c0c933d7c708c9e73d55733309736e7445`
- Fresh attempt start: `2026-08-04T23:06:09Z`
- Profiles: `default-on` and `read-only-external`
- Read Only terminal status (`2026-08-08T15:31:08Z`): `PASS` after 412
  completed cycles, 824 recorded attempts, and 259,465.833 observed valid
  seconds.
- Default-on frozen status (`2026-08-09T08:46:18Z`): `RUNNING` after 239
  completed cycles, 149,454.297144625 valid seconds, 478 passing phase attempts,
  and 2,796 failed retries. The exact archive and root-cause disposition are
  recorded in
  [`GATE_B_RC1_DEFAULT_ON_FAILURE_2026-08-09.md`](../GATE_B_RC1_DEFAULT_ON_FAILURE_2026-08-09.md).
- Exclusion rule: 108 historical attempts are excluded from qualification per profile
  because they were `probe_invalid` on both profiles and lacked required `elapsed_ms`.

## Proposed Architectural Solution

Use two fail-closed promotion gates.

### Gate A — `v2.0.0-rc.1`

| Requirement | Evidence required | Status |
|-------------|-------------------|--------|
| Published-artifact identity | PyPI wheel and sdist digests match the GitHub prerelease assets; installed imports resolve from `site-packages` | [x] — verified after `v2.0.0-beta.1` publication |
| Exact-wheel functional smoke | Fresh PyPI install verifies flag-off, flag-on `READY`, FTS, bounded subtree reads, quarantine state, warm startup, and unchanged Markdown bytes | [x] — post-publication smoke passed |
| Exact-wheel real-vault qualification | Sanitized daily-use vault copy; product-default 15 s parse deadline; at least 72 hours and preferably 7 days; restart and watcher CRUD; controlled recovery; unchanged Markdown fingerprints | [x] — terminal `PASS` on 2026-08-03: 415 completed cycles, 831 recorded attempts, 259,225.349 observed seconds, 415 subtree and 415 synthetic CRUD checks with none skipped, and source Markdown unchanged during the source-to-working-copy check. This is exact `2.0.0b1` evidence only. See [`SHADOW_DB_EXACT_BETA_72H_SOAK_2026-07-30.md`](../SHADOW_DB_EXACT_BETA_72H_SOAK_2026-07-30.md) |
| Upgrade and rollback safety | Clean install plus `1.14.5`, `2.0.0a5`, and `2.0.0b1` upgrades to the exact RC candidate; schema mismatch and a forced rebuild failure each make the read port non-ready before a clean recovery, while opt-out, rollback, and Markdown integrity remain enforced | [x] — terminal `PASS` on 2026-08-03 against the exact `2.0.0rc1` wheel rebuilt from post-#373 `main@17899f09b82b8b982ff06472d3cfc2a249ebc79c` (SHA-256 `771040b47aac86972cb6da8f9d449a1c739f3ca2dce454739179cabf6de1aaa4`): all three baselines installed, upgraded, recovered, and rolled back; every candidate check was true; source and working Markdown were unchanged. |
| Defect threshold | No open P0/P1 in Shadow read-path scope; every P2 has an explicit maintainer disposition | [x] — live issue reconciliation found no open P0/P1 Shadow defect; delivered trackers #346 and #351 remain project-management follow-ups, while accepted P2 items A1-BOOT-02 and #333 have explicit fail-safe/deferred dispositions below |
| External-cache Read Only compatibility | Shadow DB, WAL/SHM, and writer lock resolve outside `LOGSEQ_GRAPH_PATH`; `MATRYCA_READ_ONLY=true` permits only validated external-cache writes; graph fingerprint and graph-local file inventory remain unchanged | [x] — implementation merged through #363; deterministic source-tree E2E gate passes across CLI, MCP, UI, daemon, Shadow, hidden files, Git metadata, and symlink cases. The exact post-#373 RC wheel also reached `READY` under Read Only with an external cache while the graph file inventory and Markdown remained unchanged. See [`READ_ONLY_IMMUTABILITY_E2E.md`](../READ_ONLY_IMMUTABILITY_E2E.md) and [`v2-external-shadow-cache-read-only.md`](v2-external-shadow-cache-read-only.md) |
| Default-on contract | Unset `MATRYCA_SHADOW_DB_ENABLED` prefers Shadow reads, including under Read Only with a valid external cache; explicit `false` restores the legacy path; every non-ready state falls back to Markdown/BM25 | [x] — implemented and source-tested in #362; the exact post-#373 RC wheel reached `READY` with the flag unset, honored explicit `false`, and excluded Shadow reads during schema-mismatch and forced-rebuild-failure states before clean recovery |
| Operator contract | `.env.example`, Sovereign UI settings/help, `llms.txt`, `.well-known/llms.txt`, OpenSpec fragments, generated prompt, roadmap, tests, and changelog agree | [x] — exact-candidate review on `ced0c94722d2c7943824ebcd55e9fa437d65746d` confirmed current defaults, Read Only/external-cache semantics, opt-out/fallback wording, byte-identical `llms.txt` surfaces, generated-prompt hash, and UI/config coverage; historical alpha/beta sections retain their historical defaults deliberately |
| Release-candidate proof | Full CI, code audit, clean release build, installed-wheel smoke, and supported-platform checks pass on the exact RC commit | [x] — exact `main@ced0c94722d2c7943824ebcd55e9fa437d65746d`; Ubuntu full gate plus macOS/Windows Shadow contract jobs and CodeQL passed; clean wheel/sdist build and exact-wheel installed smoke passed with the digests recorded below |

#### Gate A closeout — 2026-08-03

The frozen candidate source is
`main@ced0c94722d2c7943824ebcd55e9fa437d65746d`, the merge commit for #376.
GitHub Actions run `30813967874` passed the Ubuntu Ironclad Gatekeeper and the
supported Shadow read contract on both `macos-latest` and `windows-latest`.
CodeQL run `30813968213` also passed on the same commit. The full CI gate covers
formatting, Ruff, mypy, sandbox-read policy, version consistency, agent-router
coherence, public-metrics policy, generated-prompt hash, and pytest.

A clean tracked-source `make release-build` produced:

- wheel SHA-256
  `424be4ae6a80f0925b609752a40ebd7b33b8fe0adb15e18244c22fb6eadaaf81`;
- sdist SHA-256
  `6ad351cf24ddbd8c4a96f010db555e78b54baadc88288cff371ac870afb12c62`.

This closeout record is documentation-only and is excluded from both release
archives. A rebuild from the closeout commit confirmed byte-identical extracted
wheel and sdist member contents. The archive digests themselves are not
reproducible because the current build records build-time ZIP/tar timestamps;
the second build therefore had different container digests despite identical
members. The digests above identify the exact installed artifact used for this
Gate A smoke, not a reproducible-build guarantee. The resulting `main` merge
must retain green CI, and release publication must build, record, and smoke the
final artifacts produced for upload. This explicitly bounds the otherwise
self-referential act of recording evidence after freezing the runtime
candidate.

The wheel was installed into a fresh disposable environment outside the
checkout. Import/version provenance resolved to `site-packages` at
`2.0.0rc1`. The candidate probe passed default-on readiness, explicit opt-out,
external-cache-only routing, schema-mismatch fallback and recovery, injected
rebuild-failure fallback and recovery, Strict Read Only readiness, and unchanged
Markdown bytes and graph file inventory.

The live v2.0 milestone inventory contains project trackers rather than open
P0/P1 Shadow defects. #351 was delivered by #360; #346's implementation slices
#347–#350 and #352–#353 are closed. #17 retains only the later Logseq DB adapter
scope already assigned outside this release, while #20 and #343 remain release
trackers. Accepted P2 A1-BOOT-02 remains safe because rollback preserves the
committed generation and error health forces Markdown/BM25 fallback. Security
hardening #333 remains explicitly deferred: bounded-parser payloads originate
from the owned worker and are correlation-checked before deserialization, but
replacing or restricting pickle remains a tracked defense-in-depth follow-up.
No raw graph content or private operator path is recorded in this closeout.

#### Upgrade/rollback collector diagnosis — 2026-08-03

The first exact-candidate run failed as `candidate_probe_failed` after the
collector placed four full real-vault rebuild/recovery phases under one
600-second subprocess deadline. Historical real-vault evidence already
recorded individual probe durations up to 516 seconds, so this was a harness
budget defect rather than a Shadow corruption signal. The collector now keeps
installation commands capped at 600 seconds and gives only the multi-rebuild
candidate probe an independent, bounded 3,600-second ceiling.

The corrected-timeout run completed all candidate checks but exposed a second
provenance defect: subprocesses inherited the repository working directory, so
`import src` could resolve the checkout instead of the installed wheel. Both
the installed-package and candidate probes now execute from the virtual
environment directory. After #373 merged, the candidate artifact was rebuilt
from the exact merged `main` commit and a fresh privacy-bounded run recorded the
terminal `PASS` summarized above. No private path, graph content, or
child-process diagnostic is retained in the committed record.

`v2.0.0-rc.1` may be published only when every Gate A row is complete.

### Gate B — `v2.0.0`

| Requirement | Evidence required | Status |
|-------------|-------------------|--------|
| RC observation | At least 7 days of RC availability and maintainer operation, with no unresolved P0/P1 regression | [x] — RC2 was published at `2026-08-09T16:45:18Z`; the seven-day cutoff passed at `2026-08-16T16:45:18Z`. The v2.0 milestone has no unresolved P0/P1 regression; open P0/P1 work is explicitly assigned to later v2.1+ programmes. |
| Default-on soak | At least 72 hours and preferably 7 days with the flag unset, plus an explicit opt-out control run | [x] — exact public `2.0.0rc2` wheel terminal `PASS` on 2026-08-13 after 417 cycles, 834 passing attempts, and 259,548.995 valid seconds; source/working Markdown fingerprints matched and the artifact, installed RECORD, runner, and attempt chain were verified. See [`GATE_B_RC2_TERMINAL_EVIDENCE_2026-08-13.md`](../GATE_B_RC2_TERMINAL_EVIDENCE_2026-08-13.md). |
| Read Only external-cache soak | Default-on Shadow reaches and retains `READY` with `MATRYCA_READ_ONLY=true`; all writes remain outside the graph and Markdown fingerprints remain unchanged | [x] — exact public `2.0.0rc2` wheel terminal `PASS` on 2026-08-13 after 417 cycles, 834 passing attempts, and 259,421.167 valid seconds; source/working Markdown fingerprints matched and the artifact, installed RECORD, runner, and attempt chain were verified. See [`GATE_B_RC2_TERMINAL_EVIDENCE_2026-08-13.md`](../GATE_B_RC2_TERMINAL_EVIDENCE_2026-08-13.md). |
| Upgrade matrix | Stable `1.14.5`, alpha `2.0.0a5`, beta `2.0.0b1`, and RC upgrade paths pass from published artifacts | [x] — the persistent exact-public-`2.0.0rc2` receipt reached terminal `PASS`: all four published baselines installed, upgraded to candidate, completed every candidate check, rolled back, and preserved working Markdown. The receipt binds candidate wheel SHA-256 `0b0c8a94377b9c1805b7304a10fe728c6d5c1f4ba120519b6e25c374c0a42318`; it is maintainer-held qualification evidence and does not replace final exact-stable-artifact verification. |
| Cross-platform gate | Linux, macOS, and Windows CI or installed-runtime evidence passes for the supported Shadow read contract | [x] — PR #513 candidate `2150e290` reached terminal success for Ironclad Gatekeeper, macOS Shadow-contract, Windows Shadow-contract, and Python 3.13 evidence; CodeQL and dependency review also passed, with only the expected lockfile auto-fixer skip. |
| Performance disposition | FTS and subtree measurements have explicit pass thresholds or a documented non-blocking disposition; fallback remains usable | [x] — deterministic capacity, large-corpus, and retrieval-scorecard evidence meets the parity and bounded-resource thresholds in [`V2_STABLE_PERFORMANCE_DISPOSITION_2026-08-18.md`](../V2_STABLE_PERFORMANCE_DISPOSITION_2026-08-18.md); host-dependent latency and RSS remain diagnostic, not release claims. |
| Stable documentation | In-memory BM25 is deprecated as the default discovery path but remains a supported fallback; no beta/RC wording survives on stable surfaces | [x] — the candidate synchronizes the stable version across `llms.txt`, `.well-known/llms.txt`, the Shadow operator contract, OpenSpec onboarding, generated `SYSTEM_PROMPT.md`, roadmap surfaces, and the release changelog; checks pass and historical RC references remain explicitly labelled. |
| Final release proof | Full CI, code audit, clean build, release-note extraction, installed-wheel smoke, and artifact digest verification pass on the exact stable commit | [ ] — explicitly pending on the frozen-RC2-derived exact stable candidate |

`v2.0.0` may be published only when every Gate B row is complete.

### Promotion sequence

1. A terminal exact-beta soak `PASS` closes only the Gate A exact-beta real-vault row; a
   `FAIL` blocks promotion and requires disposition.
2. Complete the other Gate A rows on one frozen candidate commit, then build and
   verify the candidate artifacts.
3. Publish `v2.0.0-rc.1` only after Gate A is fully checked.
4. Preserve the split rc.1 outcome without repairing its live SQLite state.
5. Publish and bind the corrected `2.0.0rc2` artifact after the parser 1.7.1
   integration and qualifier fix merge.
6. Run fresh dual-profile Gate B attempts against the installed public rc.2
   wheel, not a source checkout or prior artifact.
7. Publish stable `v2.0.0` only after Gate B is fully checked.

The rc.1 default-on checkpoint remains non-terminal and archived. Both fresh
rc.2 profiles reached terminal `PASS` after integrity and exact artifact-binding
review; the complete receipt is
[`GATE_B_RC2_TERMINAL_EVIDENCE_2026-08-13.md`](../GATE_B_RC2_TERMINAL_EVIDENCE_2026-08-13.md).
All other Gate B rows remain independently blocking for stable readiness.

### Non-negotiable runtime invariants

- Logseq Markdown remains the system of record.
- Shadow DB remains a daemon-owned read cache and never writes vault Markdown.
- `MATRYCA_READ_ONLY=true` forbids every graph-local write but permits validated
  external derived-cache writes.
- Shadow SQLite, WAL/SHM, and lock files live outside `LOGSEQ_GRAPH_PATH` for the RC
  architecture; `MATRYCA_CACHE_PATH` remains an external-root override.
- Shadow reads are permitted only while health is `READY`.
- Disabled, bootstrapping, stale, schema-mismatched, or error states route to
  Markdown/BM25.
- `MATRYCA_SHADOW_DB_ENABLED=false` remains a supported emergency opt-out.
- Logseq DB writes use an official CLI/API bridge only; that bridge is outside
  the `v2.0.0` release scope.

## Estimated Impact

This scope keeps the v2 major release focused on the already shipped and
qualified Shadow read architecture. It avoids coupling default-on read routing
to unfinished memory, import, hardware-DX, or Logseq DB write programs while
preserving those programs as explicit v2.1 follow-ups.

The principal release risks are the physical cache relocation and the default
change. Operators who leave the Shadow flag unset will move from generational
BM25 to health-gated Shadow reads, while beta graph-local databases become
legacy disposable state. External path validation, deterministic rebuild,
Read Only isolation, opt-out, and fallback are release blockers, not
best-effort behavior.

## Files Involved

- `src/shadow/` — bootstrap, health, query, sync, and state contracts
- `src/graph/safety/write_policy.py` — graph boundary and external cache policy
- `src/graph/ports/` and `src/agent/shadow_graph_repository.py` — read routing
- `src/agent/plumber_config.py` and `.env.example` — default and operator contract
- `src/cli/ui_server.py` and `frontend/` — operator state and configuration
- `llms.txt`, `.well-known/llms.txt`, and `SYSTEM_PROMPT.md` — agent contract
- `scripts/smoke_postpublish_beta1_pypi.py` and private sanitized qualification
  harnesses — artifact evidence
- `scripts/qualify_rc_upgrade_rollback.py` — fail-closed installed-wheel RC
  upgrade, recovery fallback, default-on/read-only, and rollback qualification
- `docs/roadmaps/ROADMAP_V2_PREPARATION.md` and
  `docs/roadmaps/ROADMAP_V2_SHADOW_DB.md` — rollout scope
- `docs/quality/issue-bodies/v2-external-shadow-cache-read-only.md` — approved
  external-cache and Read Only architecture

---

**Tracking issue:** [#343](https://github.com/MarcoPorcellato/matryca-plumber/issues/343)

**Parent epic:** [#20](https://github.com/MarcoPorcellato/matryca-plumber/issues/20)

_The RC and stable release decisions remain separate maintainer authority gates._
