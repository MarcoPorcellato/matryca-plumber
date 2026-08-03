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

As of 2026-08-03, the unreleased RC-target source contains the Strict Read Only
policy and guarded runtime, external per-user Shadow routing, default-on Shadow
with explicit opt-out, read-only observer daemon, deterministic graph
immutability gate, and bounded 8,192-entry BM25 result cache merged through
#366. This describes implementation state, not an RC release or Gate A closure.

## Proposed Architectural Solution

Use two fail-closed promotion gates.

### Gate A — `v2.0.0-rc.1`

| Requirement | Evidence required | Status |
|-------------|-------------------|--------|
| Published-artifact identity | PyPI wheel and sdist digests match the GitHub prerelease assets; installed imports resolve from `site-packages` | [x] — verified after `v2.0.0-beta.1` publication |
| Exact-wheel functional smoke | Fresh PyPI install verifies flag-off, flag-on `READY`, FTS, bounded subtree reads, quarantine state, warm startup, and unchanged Markdown bytes | [x] — post-publication smoke passed |
| Exact-wheel real-vault qualification | Sanitized daily-use vault copy; product-default 15 s parse deadline; at least 72 hours and preferably 7 days; restart and watcher CRUD; controlled recovery; unchanged Markdown fingerprints | [x] — terminal `PASS` on 2026-08-03: 415 completed cycles, 831 recorded attempts, 259,225.349 observed seconds, 415 subtree and 415 synthetic CRUD checks with none skipped, and unchanged source Markdown. This is exact `2.0.0b1` evidence only. See [`SHADOW_DB_EXACT_BETA_72H_SOAK_2026-07-30.md`](../SHADOW_DB_EXACT_BETA_72H_SOAK_2026-07-30.md) |
| Upgrade and rollback safety | Clean install plus `1.14.5`, `2.0.0a5`, and `2.0.0b1` upgrades to the exact RC candidate; schema mismatch, failed rebuild, opt-out, and rollback/recovery fall back without partial reads or Markdown writes | [ ] |
| Defect threshold | No open P0/P1 in Shadow read-path scope; every P2 has an explicit maintainer disposition | [ ] |
| External-cache Read Only compatibility | Shadow DB, WAL/SHM, and writer lock resolve outside `LOGSEQ_GRAPH_PATH`; `MATRYCA_READ_ONLY=true` permits only validated external-cache writes; graph fingerprint and graph-local file inventory remain unchanged | [x] — implementation merged through #363; deterministic source-tree E2E gate passes across CLI, MCP, UI, daemon, Shadow, hidden files, Git metadata, and symlink cases. See [`READ_ONLY_IMMUTABILITY_E2E.md`](../READ_ONLY_IMMUTABILITY_E2E.md) and [`v2-external-shadow-cache-read-only.md`](v2-external-shadow-cache-read-only.md) |
| Default-on contract | Unset `MATRYCA_SHADOW_DB_ENABLED` prefers Shadow reads, including under Read Only with a valid external cache; explicit `false` restores the legacy path; every non-ready state falls back to Markdown/BM25 | [ ] — implemented and source-tested in #362; exact-candidate installed-wheel qualification remains pending |
| Operator contract | `.env.example`, Sovereign UI settings/help, `llms.txt`, `.well-known/llms.txt`, OpenSpec fragments, generated prompt, roadmap, tests, and changelog agree | [ ] — source surfaces synchronized; final exact-candidate review remains pending |
| Release-candidate proof | Full CI, code audit, clean release build, installed-wheel smoke, and supported-platform checks pass on the exact RC commit | [ ] |

`v2.0.0-rc.1` may be published only when every Gate A row is complete.

### Gate B — `v2.0.0`

| Requirement | Evidence required | Status |
|-------------|-------------------|--------|
| RC observation | At least 7 days of RC availability and maintainer operation, with no unresolved P0/P1 regression | [ ] |
| Default-on soak | At least 72 hours and preferably 7 days with the flag unset, plus an explicit opt-out control run | [ ] |
| Read Only external-cache soak | Default-on Shadow reaches and retains `READY` with `MATRYCA_READ_ONLY=true`; all writes remain outside the graph and Markdown fingerprints remain unchanged | [ ] |
| Upgrade matrix | Stable `1.14.5`, alpha `2.0.0a5`, beta `2.0.0b1`, and RC upgrade paths pass from published artifacts | [ ] |
| Cross-platform gate | Linux, macOS, and Windows CI or installed-runtime evidence passes for the supported Shadow read contract | [ ] |
| Performance disposition | FTS and subtree measurements have explicit pass thresholds or a documented non-blocking disposition; fallback remains usable | [ ] |
| Stable documentation | In-memory BM25 is deprecated as the default discovery path but remains a supported fallback; no beta/RC wording survives on stable surfaces | [ ] |
| Final release proof | Full CI, code audit, clean build, release-note extraction, installed-wheel smoke, and artifact digest verification pass on the exact stable commit | [ ] |

`v2.0.0` may be published only when every Gate B row is complete.

### Promotion sequence

1. A terminal exact-beta soak `PASS` closes only the Gate A real-vault row; a
   `FAIL` blocks promotion and requires disposition.
2. Complete the other Gate A rows on one frozen candidate commit, then build and
   verify the candidate artifacts.
3. Publish `v2.0.0-rc.1` only after Gate A is fully checked.
4. Run Gate B against the installed public RC, not a source checkout or beta
   artifact.
5. Publish stable `v2.0.0` only after Gate B is fully checked.

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
- `docs/roadmaps/ROADMAP_V2_PREPARATION.md` and
  `docs/roadmaps/ROADMAP_V2_SHADOW_DB.md` — rollout scope
- `docs/quality/issue-bodies/v2-external-shadow-cache-read-only.md` — approved
  external-cache and Read Only architecture

---

**Tracking issue:** [#343](https://github.com/MarcoPorcellato/matryca-plumber/issues/343)

**Parent epic:** [#20](https://github.com/MarcoPorcellato/matryca-plumber/issues/20)

_The RC and stable release decisions remain separate maintainer authority gates._
