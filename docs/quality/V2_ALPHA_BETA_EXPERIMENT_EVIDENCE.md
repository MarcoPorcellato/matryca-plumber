# V2 alpha/beta experiment evidence ledger

## Purpose and decision boundary

This is a sanitized supporting record for the v2 Shadow read-cache experiments. It is **not** a release note, an architecture specification, a service-level objective, or a beta release decision. [`docs/ARCHITECTURE.md`](../ARCHITECTURE.md) remains the authoritative architecture record. Quality material remains a legacy Phase 4 surface; this ledger does not create a `docs/knowledge/` concept, a new canonical source, or a change to the default-off opt-in contract.

The release decision is finalized in [`issue-bodies/v2-beta-readiness.md`](issue-bodies/v2-beta-readiness.md). All five beta publication gates are recorded `PASS`, with an explicit accepted boundary: the installed-wheel and soak evidence covers the design and read path, not the exact published bytes.

## Evidence classes

| Class | Meaning | Release-decision weight |
| --- | --- | --- |
| CI-reproducible | Focused repository tests that run in the normal test contract. | Contract evidence; not a field soak. |
| Opt-in slow | Explicitly selected local performance or pathological-parser tests. | Regression signal; host-dependent. |
| Single-machine exploratory | Sanitized measurements on one daily-use vault copy. | Observational only; not CLI or SLA evidence. |
| Installed-wheel historical | Upgrade/recovery probe run outside the checkout. | Historical only when superseded; must be rerun for the final candidate. |
| Installed-wheel candidate | Upgrade/recovery probe against the current candidate wheel, outside the checkout. | Candidate evidence; still requires soak and final code audit. |

## Published alpha hardening baseline

`v2.0.0-alpha.5` / `2.0.0a5` is the published hardening baseline. The campaign closed with no open P0/P1; one P2 (A1-BOOT-02) was explicitly accepted because rollback preserves the committed generation and forces non-ready health/fallback. Counts below are the recorded campaign probe totals, including parametrized cases where applicable; they are not a reconstructed historical full-suite total.

| Axis | Repository-supported evidence | Confirmed finding / fix status |
| --- | --- | --- |
| 1 — concurrency and recovery | 7 probes; campaign green. | Two P1 cross-process writer findings fixed in [#262](https://github.com/MarcoPorcellato/matryca-plumber/issues/262); P2 metadata coherence fixed in [#264](https://github.com/MarcoPorcellato/matryca-plumber/issues/264); A1-BOOT-02 accepted as above. |
| 2 — Shadow/Markdown correctness | 14 probes; campaign green. | P1 rename stale-owner parity fixed in [#272](https://github.com/MarcoPorcellato/matryca-plumber/issues/272). |
| 3 — routing and fallback | 19 probes; campaign green. | Flag-off, health-transition, zero-hit, error, and subtree fallback contracts passed; no confirmed residual finding recorded. |
| 4 — FTS5 | 52 pass, 0 xfail. | P1 hyphenated query handling fixed in [#277](https://github.com/MarcoPorcellato/matryca-plumber/issues/277); P2 query bound fixed in [#279](https://github.com/MarcoPorcellato/matryca-plumber/issues/279); the prior diacritic P2 was corrected as an invalid expectation. |
| 5 — CTE subtree | 43 pass, 0 xfail. | Depth-limit truncation status fixed in [#289](https://github.com/MarcoPorcellato/matryca-plumber/issues/289). |
| 6 — security and isolation | 24 pass, 0 xfail. | State/diagnostic path redaction fixed in [#293](https://github.com/MarcoPorcellato/matryca-plumber/issues/293); sandbox, flag-off, and no-Markdown-write contracts passed. |
| 7 — performance | 7 default-CI pass; 2 opt-in slow probes. | No unresolved finding recorded. The slow 10k/50k probes are host-dependent regression checks, not a portable performance baseline. |

The full historical finding table and probe names remain in [`issue-bodies/v2-alpha-hardening.md`](issue-bodies/v2-alpha-hardening.md). This ledger deliberately summarizes only release-relevant conclusions.

## Alpha.5 post-publish exploratory observations

The following Phase A/B observations used a daily-use vault copy and are sanitized single-machine evidence. They are not CLI timings, do not establish a service-level objective, and do not characterize other machines or vaults.

### Phase A — flag-off and controlled checks

| Check | Result | Sample basis |
| --- | --- | --- |
| Flag-off BM25 | p50 34.81 ms | n=20 |
| Subtree parser | p50 0.28 ms | n=20 |
| JSON schema | 6/6 success; warm p50 2584 ms | n=4 |
| Controlled LLM end-to-end | warm p50 2655 ms | n=4 |
| Shadow cache side effect | No `shadow.sqlite` created | flag-off observation |

### Phase B — copied-corpus bootstrap and read path

The copied corpus contained 1,009 pages and 56,597 blocks. Cold bootstrap took 189,355 ms (5.33 pages/s; 298.9 blocks/s) and produced a 28,033,024-byte database. Warm startup was p50 0.61 ms (n=20), FTS p50 was 0.03 ms (n=20), and CTE p50 was 3.59 ms (n=20). Single in-process create/edit/rename/delete samples were 2.82/3.00/5.30/2.45 ms respectively. Those four values are individual samples, not percentile claims.

## A-CLI-01 / #297 minimization and bounded containment

The parser concern was reduced to a deterministic synthetic page: pathological latency, not a demonstrated deadlock. The reproducer is privacy-clean and the opt-in slow test enforces a terminating child-process ceiling, so it cannot hold the suite indefinitely.

| Slice | Result | Evidence class |
| --- | --- | --- |
| Audit reproducer ([#298](https://github.com/MarcoPorcellato/matryca-plumber/pull/298)) | A deterministic synthetic reproducer and same-scale control page isolate the pathological shape without a daily-use vault. | Opt-in slow |
| PR2A ([#299](https://github.com/MarcoPorcellato/matryca-plumber/pull/299)) | CLI `search bm25` no longer eagerly bootstraps the AST, removing parser latency from a route that uses raw Markdown or Shadow FTS. | CI-reproducible |
| PR2B ([#300](https://github.com/MarcoPorcellato/matryca-plumber/pull/300)) | Terminable, persistent parse worker. Cold start: 91 ms; worker p50: 2.1 ms; median worker overhead: about 0.2 ms. On the same 1,009-page copied corpus at a 30-second deadline: 1,006 complete, 3 timeout, 0 error. | Single-machine exploratory |
| PR2C integration ([#305](https://github.com/MarcoPorcellato/matryca-plumber/pull/305)) | A timeout/failure cannot publish a partial AST cache or Shadow generation; the last complete incremental page remains usable; health becomes non-ready and reads route to existing fallback; diagnostics stay bounded and content-free. | CI-reproducible |

The product page-parse default is 15 seconds. The 30-second exploratory deadline above is not evidence that a 15-second product deadline has passed. Likewise, the evidence collector may use a bounded 60-second child probe for collection only; it is not a product readiness claim.

## Installed-wheel candidate evidence

### r3 — superseded historical run

The r3 installed-wheel run is retained only as historical evidence. Its baseline `2.0.0a5` readiness measurement was 185,195 ms; the candidate `2.0.0b1` measurement was 378,818 ms. The recorded upgrade, FTS, CTE, schema, duplicate, fallback, flag-off, unchanged-source, and wheel-import provenance checks were all true across 3,367 source Markdown files.

That run is **not final release evidence**: the candidate changed after [#317](https://github.com/MarcoPorcellato/matryca-plumber/pull/317) corrected virtual-environment interpreter provenance in the soak collector. A fresh r4 wheel run using the rebuilt final candidate is therefore required. Do not compare r3 durations as a performance claim or publish r3 raw evidence.

### r4 — historical installed-wheel observation

The post-#317 r4 run passed against the rebuilt `2.0.0b1` wheel (SHA-256 `04fd22584499917119d9fcef5ca52e2c56dc8f60adc46a8059ea605a735c0e74`). Baseline `2.0.0a5` readiness took 185,072 ms and the candidate probe took 380,540 ms across 3,367 source Markdown files. Upgrade-generation preservation, warm readiness, FTS, CTE, schema recovery, duplicate failure/recovery, fallback, flag-off no-op, installed-package provenance, working-copy Markdown integrity, and source immutability all passed.

The 60-second page-parse deadline was an evidence-collection setting, not the product's 15-second default and not an SLA. This observation does not close the candidate gate: the current root-cause investigation found non-hermetic artifact discovery and no wheel-to-soak identity binding. It must be rerun after the remediation described in [`BETA_EVIDENCE_REPRODUCIBILITY_RCA_2026-07-23.md`](BETA_EVIDENCE_REPRODUCIBILITY_RCA_2026-07-23.md). This gate does not by itself make the beta ready.

## Page-parse budget finding (2026-07-27)

> **Population note (added 2026-07-28).** "3,378 pages" counts every Markdown file under
> the vault root, including Logseq's own version history and backups. The cache indexes
> `pages/` and `journals/` only — 1,014 pages — of which **3** exceed the budget. The
> reconciliation, and a re-measurement that revises the range quoted below, are in
> [`SHADOW_DB_SOAK_24H_EVIDENCE_2026-07-28.md`](SHADOW_DB_SOAK_24H_EVIDENCE_2026-07-28.md).

A full-corpus parse-cost measurement on a sanitized daily-use vault copy (3,378 files,
candidate wheel `2.0.0b1`) established that **25 files (0.74%) exceed the 15-second
product default**, ranging 41.65–58.33 s, and account for **90.3% of total parse time**
(20.4 min of 22.6 min). Parse cost is strictly bimodal — no page falls between 5 s and
40 s — and is uncorrelated with size: the largest page in the corpus (650,106 B) parses
in 0.54 s.

Because `rebuild_shadow_from_graph` aborts the whole rebuild on the first over-budget
page, and health `READY` requires `indexed == source == actual`, the Shadow DB reaches
no accelerated state at all on this corpus under default settings. The failure is safe
(Markdown authoritative, daemon starts, nothing corrupted) but silent.

This is a **design defect, not a regression**, and it is not a `beta.1` blocker — the
flag is opt-in and default-off. It **is** a blocker for enabling Shadow DB by default and
for any acceleration claim on real-world graphs. Full measurement, TRIZ analysis, and the
per-page quarantine design:
[`SHADOW_DB_PARSE_BUDGET_TRIZ_2026-07-27.md`](SHADOW_DB_PARSE_BUDGET_TRIZ_2026-07-27.md);
implementation issue:
[`issue-bodies/shadow-page-parse-quarantine.md`](issue-bodies/shadow-page-parse-quarantine.md).

Consequence for evidence collection: soak and wheel runs configured with an enlarged
page-parse deadline (60 s or 90 s) exercise a configuration that **default operators do
not get** on a corpus containing such pages. Those runs remain valid as stability
evidence and must not be presented as evidence of default-configuration behaviour.

## Beta gate disposition

- **PASS** — the sanitized soak accumulated 24 hours across 144 cycles and 288 attempts.
- **PASS** — the installed-wheel and soak records were bound after the reproducibility remediation.
- **PASS** — full CI and the final code audit completed for the release scope.
- **Accepted boundary** — the released source includes later fail-safe fixes not exercised by the bound wheel and soak. This does not block the opt-in, default-off beta, but re-qualification against the released source is mandatory before default-on and the evidence must not be cited as byte-level proof.

## Reproduction and privacy rules

Public, privacy-clean reproduction paths are limited to repository tests and synthetic fixtures:

```bash
make ci
uv run pytest tests/test_ast_cache_bounded_parse.py tests/test_shadow_bounded_parse.py
make perf
uv run python scripts/gen_a_cli_01_pathological_page.py /tmp/a-cli-01-pathological.md
```

`make perf` is opt-in and may be host-sensitive. The final installed-wheel and long-running soak procedures require private operator inputs; their commands, raw JSON, page titles, vault paths, UUIDs, content hashes, source prompts, and raw evidence must not be copied into this repository. Refer to the corpus only as a **daily-use vault copy** and to implementation review only as a **code audit**.
