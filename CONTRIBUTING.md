# Contributing to Matryca Plumber

Thank you for investing your time in **Matryca Plumber** (`matryca-plumber`), developed by **Marco Porcellato** at **[Matryca.ai](https://matryca.ai)**. Use the full product name in user-facing copy — not “Matryca” alone. See [`docs/BRANDING.md`](docs/BRANDING.md).

This project exists so humans and **autonomous local systems** can collaborate on **Logseq OG** graphs the right way: **blocks**, **`id::`**, and **local Markdown** — not flattened blobs in someone else's database. Whether you fix a typo, tighten a test, extend a **`MaintenanceDaemon`** cognitive module, or harden the **`graph_dispatch`** + **`logseq-matryca-parser`** headless CRUD plane, you are helping keep the **Ironclad** bar high.

**Surfaces, one contract:** the **Sovereign UI** (FastAPI + React on `:8500`), the **`matryca` / `matryca plumber` CLI**, and the **optional FastMCP stdio sidecar** are different doors into the **same** sandboxed graph semantics. New work should default **daemon-first** — autonomous duty cycles and direct file I/O — not “stdio MCP as the product.”

---

## Architecture context (where your patch lands)

| Layer | Primary paths | Contributor focus |
|--------|----------------|-------------------|
| **Autonomous runtime** | `src/agent/maintenance_daemon.py`, `src/agent/plumber_modules/`, `src/agent/plumber_config.py` | Duty-cycle scans, cognitive lints, thermal pacing, ledger / telemetry sync |
| **Headless CRUD & graph plane** | `src/agent/graph_dispatch.py`, `src/graph/**`, **`logseq-matryca-parser`** | OCC, `page_rmw_lock`, atomic writes, fence dead zones, namespace / property parity |
| **Operator control plane** | `src/cli/**` (incl. `ui_server.py`, `ui_auth.py`), `frontend/` | **Zero-Trust** local API (`X-Matryca-Token`), cockpit UX |
| **Optional MCP ingress** | `src/agent/mcp_server.py` (`register_mcp_tools`, `@mcp.tool()`) | Thin registration over the same dispatch graph — not a second datastore or write path. Standalone tools: **`store_fact`** (identity), **`ingest_document`** (atomic external Markdown — see [`docs/openspec/ingest.md`](docs/openspec/ingest.md)). |

Deep reference: [`SYSTEM_PROMPT.md`](SYSTEM_PROMPT.md), [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md), [`docs/openspec/README.md`](docs/openspec/README.md) (index), [`docs/openspec/llm-performance.md`](docs/openspec/llm-performance.md) (v1.8 edge), [`docs/openspec/link-verification.md`](docs/openspec/link-verification.md) / [`agent-dx.md`](docs/openspec/agent-dx.md) (v1.9), [`docs/openspec/security-sandbox.md`](docs/openspec/security-sandbox.md) (v1.9.9), [`docs/openspec/agent-onboarding.md`](docs/openspec/agent-onboarding.md) (v1.9.2 `llms.txt`), [`docs/openspec/live-telemetry-ui.md`](docs/openspec/live-telemetry-ui.md) (v1.9.3 Sovereign UI), [`llms.txt`](llms.txt) (agent execution guide).

**Configuration:** [`.env.example`](.env.example) is the operator reference, split into **Operator essentials** (day-one / Settings drawer) and **Advanced / high impact** (mutating lint, MCP, security). Each key documents **Default (code)** and **Template** when they differ. Agents must keep `.env.example` in sync when changing env vars — see [`.cursor/rules/07-env-example.mdc`](.cursor/rules/07-env-example.mdc). `MATRYCA_LM_INSTRUCTOR_*` and `MATRYCA_LLM_PROMPT_CACHE_MODE` are legacy or reserved (not read by runtime). CI: `tests/test_env_example_coverage.py`.

---

## Philosophy (non-negotiable)

Matryca Plumber is built on three pillars. Every contribution must respect them:

| Pillar | Meaning |
|--------|---------|
| **Local-first** | The Logseq graph on disk (`LOGSEQ_GRAPH_PATH`) is the system of record. Reads and writes go through UTF-8 Markdown I/O, `fcntl.flock` RMW locks, and atomic swaps — not a hosted sync service. |
| **Zero external databases** | No SQLite, Postgres, Redis, or cloud DB as a dependency for core behavior. Ephemeral in-memory indexes and JSON ledgers at the graph root are allowed; the vault itself stays pure Markdown. |
| **Absolute Logseq AST parity** | Spatial structure comes from **`logseq_matryca_parser`** and bounded helpers in `src/graph/`. Mutations must preserve outliner semantics: nested bullets, property planes, multiline continuations, and fence-protected dead zones. |

---

## Phase 0–4 Hardening Rules

These rules are enforced in code and in CI. **Violating them in a PR will be rejected**, even if tests pass by accident.

### Phase 0 — Paradigm lock

- Operate only on files inside the designated graph root (`path_sandbox.assert_path_within_graph`).
- Read graph Markdown and sidecars with **`read_graph_file_text()`** (or bounded JSON helpers) — not raw `Path.read_text()` under `src/graph`, `src/agent`, or `src/rag`. CI **`make sandbox-read-check`** enforces this (v1.9.9). The only daemon exception is pid/lock sidecar reads in `maintenance_daemon.py` tagged `# sandbox-read-ok` on the same line — see [`docs/openspec/security-sandbox.md`](docs/openspec/security-sandbox.md).
- Never introduce a central database, ORM, or external state store for graph content.
- Prefer direct file I/O over the Logseq HTTP API for background linting, indexing, and analysis.

### Phase 1 — OCC snapshot (Optimistic Concurrency Control)

Humans and the Plumber daemon edit the **same** `.md` files concurrently. Local LLM inference is slow; a naive read-modify-write would overwrite live edits.

**Rule:** Before reading page content for any mutation path, capture a **Phase-1 snapshot**:

1. Record `st_mtime` via `read_file_mtime()` / `OCCSnapshot.capture()` in `src/graph/markdown_blocks.py`.
2. Hold that `baseline_mtime` for the entire inference or edit assembly window.

**No contributor may write to the filesystem on a mutation path without first establishing this baseline.**

### Phase 2 — OCC verification

**Rule:** Immediately before committing bytes to disk, run **Phase-2 verification**:

1. Call `occ_verify_before_write()` or commit through `atomic_write_bytes_if_unchanged()`.
2. If `file_mtime_drifted()` is true (the user edited in Logseq during inference), **abort the write** — return `False`, log the skip, and preserve the human's changes.
3. Only when mtime still matches, commit via temp file → `fsync` → `os.replace` under `page_rmw_lock`.

**Do not** hold `page_rmw_lock` across LLM inference. Phase 2 daemon flow (`_process_llm_cycle_file`): snapshot → read → cognitive lint / `index_page` (no page lock) → drift check → `apply_semantic_page_result` (lock only for the atomic write). See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md#optimistic-concurrency-control-occ).

OCC complements `fcntl.flock` (no torn writes) with **lost-update prevention** (no silent overwrites).

### Phase 3 — AST parity

Logseq OG's on-disk contract is strict. Violations cause silent index corruption.

| Topic | Rule |
|-------|------|
| **Line-0 frontmatter** | Page properties (`tags::`, `alias::`, `title::`, …) live at the **absolute top** of the file as raw `key:: value` lines **without** bullet dashes (`- `). A blank line separates frontmatter from the first bullet. |
| **Block properties** | Block-scoped properties (`id::`, `matryca-plumber::`, …) sit **immediately under the parent bullet**, indented **+2 spaces**, **before** child bullets or multiline continuations. Never orphan or delete existing `id::` lines. **`id::` is identity, not metadata** — `parse_logseq_property_line` excludes key `id` so hygiene tools never regex-edit UUID lines. |
| **Multiline blocks** | Shift+Enter continuations use `indent + 2 spaces` (`bullet_indent_unit()`). Property insertion must respect continuation lines before child bullets (`block_property_insert_index()`). |
| **Windows `\r\n` stripping** | All scanners normalize with `strip_line_endings()` / `rstrip("\r\n")` before regex matching. Writes emit `\n` via `canonical_line_suffix()` — never reintroduce `\r\n` on output. Mixed line endings must not break fence detection or block-span math. |
| **Dead zones** | Never mutate lines inside fenced code blocks, HTML comments, or `#+BEGIN_QUERY` … `#+END_QUERY` regions (`global_fence_scanner.py`). |

When in doubt: exercise mutators with **`dry_run=true`** first (from **pytest** fixtures, the **CLI**, or the **optional MCP** path); ground truth lives in **`read_logseq_page`** / the parser adapter — not in guessed line offsets.

### Phase 4 — No central DB (JSON ledger only)

Matryca Plumber tracks daemon progress in a **local JSON ledger** at the graph root — not in a database server.

| File | Role |
|------|------|
| **`.matryca_daemon_state.json`** | AI ledger + checkpoint plane (processed files, bootstrap phase, token telemetry, quarantine flags). Written atomically (tmp → fsync → `os.replace`). |
| **`.matryca_xray_state.json`** | Session alias map (`[n]` → block UUID) for X-Ray mode. |

**Forbidden:** SQLite, Postgres, Redis, or any hosted DB as system-of-record for graph content or daemon state.

Optional git snapshots on the graph repo are fine; they remain files on disk.

---

## Local development with `uv`

1. **Python 3.12+** (see `.python-version`).
2. Install **[uv](https://docs.astral.sh/uv/)**.
3. From the repository root:

   ```bash
   make install
   ```

   This runs `uv sync --extra dev` and creates `.venv/`.

   For CPU sandbox / `psutil` tests (`tests/test_process_priority.py`), also install the edge extra:

   ```bash
   uv sync --extra dev --extra edge
   ```

4. Optional: activate the venv or use `uv run` / Makefile targets.

   ```bash
   source .venv/bin/activate
   ```

5. For integration work, copy env defaults:

   ```bash
   cp .env.example .env
   ```

   Set **`LOGSEQ_GRAPH_PATH`** to your Logseq graph root (folder containing `pages/`). Matryca Plumber is headless — no Logseq desktop app required for most tests.

   On the first daemon/CLI/UI/MCP start, **`prepare_matryca_runtime()`** provisions log dirs, sibling **`matryca-l1/`**, **`.matryca_semantic_cache/`**, **`templates/`**, and an optional **`matryca-wiki.yml`** (see [`docs/openspec/runtime-bootstrap.md`](docs/openspec/runtime-bootstrap.md)).

### Plumber commands — UI vs daemon

| Command | Role |
|---------|------|
| **`matryca plumber status`** / **`ui`** | Starts the Sovereign UI + FastAPI on **`http://127.0.0.1:8500`**. Does **not** start the maintenance daemon. |
| **`matryca plumber start`** | Starts the maintenance daemon only. Does **not** open a browser or bind `:8500`. |
| **`matryca plumber stop`** | Stops the daemon. |

Shorthand (`matryca-plumber status`, `matryca-plumber start`, …) routes to the same `plumber` subcommands.

### Daemon-first dev loop (recommended)

After `make install`, validate changes the way operators run the **Agentic OS** (use the `.env` from step **5** — same `LOGSEQ_GRAPH_PATH` and LM settings you use for tests):

- **Build the Sovereign UI** (once, or when `frontend/` changes; `status`/`ui` auto-runs `npm run build` when `node_modules/` exists):

   ```bash
   cd frontend && npm ci && npm run build && cd ..
   ```

- **Open the cockpit** (typical first step):

   ```bash
   uv run matryca plumber status
   ```

   Browse to **`http://127.0.0.1:8500`**, complete the **Zero-Trust** token bootstrap (`GET /api/auth/session`, loopback-only), then click **Start Engine** — or start the daemon from a terminal first (below).

- **Optional — run the daemon from the terminal** (foreground is best while iterating):

   ```bash
   uv run matryca plumber start --foreground
   ```

   Or detach with `uv run matryca plumber start` and tail **`logs/matryca_plumber_ops.log`**. In another terminal, `uv run matryca plumber status` attaches the UI; live telemetry (~**5s** refresh) works when `/api/state` reports a live **`daemon_pid`**.

**Do not expect a dashboard from `plumber start` alone** — that command is headless graph maintenance only.

Ensure your repo **`.env`** includes the Ironclad security block from **`.env.example`** (at minimum `MATRYCA_MCP_ENABLED=true` if you use MCP hosts). See [`SECURITY.md`](SECURITY.md) for the full matrix.

**Optional MCP stdio** — set `MATRYCA_MCP_ENABLED=true` before invoking bare `matryca-plumber` (stdio MCP is off by default). Supported MCP hosts include **Claude Desktop**, **Cursor**, and **[Hermes Agent](docs/integrations/hermes-agent.md)** (`~/.hermes/config.yaml`). Reach for a live MCP host only when you touch `mcp_server.py`, tool schemas, or host-specific serialization. Most graph and daemon behavior is proven faster with **`make test-fast`** (local iteration) or **`make check`** (full CI gate) plus the loop above — without wiring an external MCP host.

6. List Make targets:

   ```bash
   make help
   ```

### Makefile targets

| Target | What it does |
|--------|----------------|
| `make install` | `uv sync --extra dev` |
| `make format` | Ruff auto-fix + format |
| `make lint` | Ruff lint only |
| `make typecheck` | `mypy src/ tests/` (strict) |
| `make test` / `make test-full` | Full suite: coverage ≥ 70%, `-n auto` |
| `make test-fast` | Fast local gate: `NUM_WORKERS` (default `4`), no coverage, skips `tests/slow/`, `integration`, and `test_security_remediation.py` |
| `make test-integration` | Subprocess CLI + cross-process lock + bootstrap routing tests (`-m integration`) |
| `make sandbox-read-check` | Ensures graph/agent/rag reads use `read_graph_file_text()` (v1.9.9) |
| `make perf` | `pytest -m slow` — memory / harvest soak (optional, not in default CI) |
| **`make check`** | **`lint` → `typecheck` → `sandbox-read-check` → `test`** (full local gate) |
| **`make ci`** | **`format-check` → `lint` → `typecheck` → `sandbox-read-check` → `test`** (GitHub Actions) |

**Focused loops (UI / daemon telemetry):** while iterating on Sovereign UI or checkpoint code, run a subset instead of the full suite:

```bash
uv run pytest tests/test_ui_server.py tests/test_maintenance_daemon.py tests/test_control_room_progress.py -q --no-cov
```
| `make clean` | Remove `.venv`, caches |

### Frontend (Sovereign UI)

Same build as in **Daemon-first dev loop**; CI runs `npm ci` + `npm run build` before `make check`.

```bash
cd frontend
npm ci
npm run build
```

---

## Merge bar: green `make check`

**No pull request is merged unless `make check` is 100% green.**

That means, in order:

1. **Ruff** — lint clean (`make ci` also runs `format-check` without mutating the tree)
2. **Mypy** — strict type-check on `src/` and `tests/` (**zero `# type: ignore` in `src/`** — see [Strict typing](#strict-typing-zero-mypy-suppressions-in-src))
3. **Sandbox read gate** — `make sandbox-read-check` (no new `Path.read_text()` bypasses in graph/agent/rag; daemon pid/lock reads need `# sandbox-read-ok`)
4. **Pytest** — full suite via `make test-full` / `make test` (**720+** targets on `main`; slow tests excluded unless you run `make perf`). Use **`make test-fast`** during iteration (`NUM_WORKERS` default `4`, no coverage).

GitHub Actions on pushes and pull requests to **`main`** runs **`make ci`** (see [`.github/workflows/ci.yml`](.github/workflows/ci.yml)): `uv sync`, frontend `npm ci` + `npm run build`, then `make ci`. **Any failing test blocks merge.**

Never commit secrets (no `.env`, tokens, or private graph paths in git).

### Agent-facing documentation (`llms.txt`)

When you add, rename, or remove **CLI subcommands or flags** that external agents rely on:

1. Verify commands with `LOGSEQ_GRAPH_PATH` set and `uvx matryca-plumber …`.
2. Update **[`llms.txt`](llms.txt)** and **[`.well-known/llms.txt`](.well-known/llms.txt)** in the **same PR** (byte-identical).
3. Cross-check [`docs/openspec/agent-dx.md`](docs/openspec/agent-dx.md), [`docs/openspec/agent-onboarding.md`](docs/openspec/agent-onboarding.md), and [`docs/openspec/security-sandbox.md`](docs/openspec/security-sandbox.md) when graph read paths or JSON sidecars change.

Patch releases should ship after agent-surface changes so PyPI `uvx` consumers receive accurate instructions.

**Background OS service:** `matryca service install` must target a **stable** binary (for example after `uv tool install matryca-plumber`). Do not install the daemon from ephemeral `uvx` — see [README.md](README.md) (section **Background OS service (`matryca service`)**).

---

## Writing tests (daemon-first, graph plane, optional MCP)

Most regressions are caught by exercising **`MaintenanceDaemon`**, **`plumber_modules/`**, **`src/graph/`**, and **`graph_dispatch`** — not by spawning a stdio MCP host.

### Where logic should live

- **Fat modules, thin edges** — implement behavior in `src/graph/`, `src/agent/plumber_modules/`, or `src/agent/graph_dispatch.py`; keep **`@mcp.tool()`** handlers and CLI entrypoints as thin delegates.
- **Parser is spatial truth** — hierarchy and `id::` contracts come from **`logseq-matryca-parser`**; do not hand-roll a second full-page AST for vault-wide work (see [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) § bounded-work paradigm).

### Stack conventions

- **pytest + `tmp_path`** — graph fixtures under a fake `pages/` tree; set `LOGSEQ_GRAPH_PATH` with `monkeypatch.setenv` for integration-style tests.
- **pytest-asyncio** — `asyncio_mode = auto` in `pyproject.toml`. Use `@pytest.mark.asyncio` when awaiting async dispatch or daemon helpers.
- **Pydantic** — cover models with `model_validate` / `ValidationError` where schema rules apply.
- **FastMCP (`@mcp.tool()`)** — registered in `register_mcp_tools` (`src/agent/mcp_server.py`). Test the **underlying** function or dispatch path; you almost never need a real stdio MCP session in CI.

### Recommended patterns

1. **Pure unit tests** — Fast, no disk I/O: schema and guardrails (see `tests/test_mcp_server.py` for outline validation patterns — the file name is legacy; the style applies across surfaces).
2. **Filesystem fixtures** — `tmp_path` graphs for mutators, OCC, and fence scanners (`src/graph/` tests are the template).
3. **Async dispatch tests** — Await `graph_dispatch` / `MatrycaMCPServer` methods directly against a temp graph when you need end-to-end headless writes without MCP framing.
4. **Daemon cycle tests** — Prefer targeted tests on `maintenance_daemon.py` helpers (or small integration tests) over long-running full-graph loops in CI.

### Tool design checklist (CLI, MCP, and shared mutators)

- Prefer explicit typed parameters; use `dict[str, Any]` only where JSON interchange must stay flexible.
- For mutators, default **`dry_run=true`** when behavior could touch many files.
- **`src/`** must satisfy **strict mypy**; tests may relax annotations per Ruff `per-file-ignores` for `tests/**`.

When you add or change behavior on the **Agentic OS** path, **extend or add tests under [`tests/`](tests/)** so Ironclad invariants stay pinned before review.

### Strict typing: zero mypy suppressions in `src/`

Matryca Plumber enforces **`[tool.mypy] strict = true`** on `src/` and `tests/` ([#60](https://github.com/MarcoPorcellato/matryca-plumber/issues/60)). Production code must **not** use `# type: ignore` to silence the checker.

| Situation | Preferred fix |
|-----------|----------------|
| JSON / disk literals deserialized into `Literal` unions | `typing.cast()` **after** a runtime membership check |
| Third-party types without stubs (e.g. `watchdog.Observer`) | Define a minimal `typing.Protocol` for the methods you call |
| `dict.get` / `max()` key callbacks | Lambda or explicit loop — avoid passing partially-typed bound methods |
| `PathLike` vs `Path` at API boundaries | `Path(graph_root)` at the call site when the callee expects `Path` |
| `int()` on `object` from JSON | `isinstance()` branches for `bool`, `int`, `float`, `str`; default for unknown types |

**Forbidden in `src/`:** new `# type: ignore`, `# mypy: ignore-errors`, or `@no_type_check` on modules. If mypy reports an error you cannot resolve without a suppression, refactor the types or open an issue — do not merge a ignore comment.

Verification: `uv run mypy src tests` (also run via `make typecheck` / `make check`).

---

## Releases

User-facing changes belong in [`CHANGELOG.md`](CHANGELOG.md) under `[Unreleased]`. To ship a version, follow [`docs/RELEASE_PROCESS.md`](docs/RELEASE_PROCESS.md) (local bump + tag; CI publishes PyPI and GitHub notes from the changelog).

---

## Pull request workflow

1. **Fork** the repository and use a **focused** branch per change.
2. **Open or reference an issue** for larger features so design stays aligned with the Phase 0–4 rules.
3. Describe **why** the change exists and any trade-offs in the PR body.
4. Confirm **`make check`** passes locally.
5. Use the PR template checklist (OCC, CRLF, `make check`) in [`.github/pull_request_template.md`](.github/pull_request_template.md).

If an overarching audit issue is closed by a maintainer while your PR is open, please **rebase against `main`** and update your tests/docs accordingly to match the new architecture.

---

## GitHub Issues workflow

| Use | When |
|-----|------|
| **[Discussion](https://github.com/MarcoPorcellato/matryca-plumber/discussions)** | RFCs, architecture debate, open-ended community Q&A |
| **Issue** | Trackable work with a clear done state |
| **`[EPIC]` parent issue** | Multi-PR initiatives (e.g. v2.0 Shadow DB) with **sub-issues** |
| **`question` label** | Community questions that may convert to features |

**Conventions:**

- Apply **labels as GitHub metadata** — do not write `Labels: foo, bar` in the issue body.
- Link PRs with `Fixes #N` / `Closes #N`.
- v2.0 work uses milestone **`v2.0.0 — Shadow DB & Safe-Sync Architecture`** and labels `v2.0`, `epic`, `core`, `database`, `safety`, `mcp`, `dx` as appropriate.
- Agent UX contract work (Soft Gate, `bootstrap_status`) shipped in **v1.9.5**; tracked under **`v1.9.6 - Agent UX`** for issue closure.

**Templates:** [`.github/ISSUE_TEMPLATE/`](.github/ISSUE_TEMPLATE/) — `feature_request.yml`, `bug_report.yml`, `epic.yml`, `question.yml`.

**Good first issues:** [open issues labeled `good first issue`](https://github.com/MarcoPorcellato/matryca-plumber/issues?q=is%3Aopen+label%3A%22good+first+issue%22) — includes #38, #43, #52, #53, #56, #69, #71, [#85](https://github.com/MarcoPorcellato/matryca-plumber/issues/85), [#90](https://github.com/MarcoPorcellato/matryca-plumber/issues/90)–[#92](https://github.com/MarcoPorcellato/matryca-plumber/issues/92), [#101](https://github.com/MarcoPorcellato/matryca-plumber/issues/101)–[#105](https://github.com/MarcoPorcellato/matryca-plumber/issues/105). Shipped: #44 ([#100](https://github.com/MarcoPorcellato/matryca-plumber/pull/100)), #45, #89, #93. Maintainer context and verify commands: [`good_first_issues_blueprints.md`](good_first_issues_blueprints.md). Welcome comments are on each GitHub thread.

| Label | When |
|-------|------|
| `good first issue` | Scoped fix, existing tests, no OCC/flock expertise required |
| `help wanted` | Maintainer welcomes external PRs on this issue |

---

## Reporting bugs

Include OS, Logseq version, LM Studio model, Matryca Plumber version, and **zipped** Loguru / ops logs from **`logs/matryca_plumber_ops.log`** (and rotated archives beside that path, if present). See the [bug report issue template](.github/ISSUE_TEMPLATE/bug_report.yml).

---

## Code of conduct

Be respectful, assume good intent, and keep feedback actionable. We want contributors of all backgrounds to feel welcome.
