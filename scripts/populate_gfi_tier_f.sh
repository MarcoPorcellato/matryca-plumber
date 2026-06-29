#!/usr/bin/env bash
# Tier F — Clean Code / Clean Architecture good-first issues (env_parse DRY + boundary tests).
# Requires: gh auth with repo write scope.
# Usage: bash scripts/populate_gfi_tier_f.sh
#
# Idempotency: searches for exact issue titles before create. Re-running skips existing.
set -euo pipefail

REPO="MarcoPorcellato/matryca-plumber"
API_PAUSE=2
MILESTONE_V1912="v1.9.12 — Code Perfection & Tech Debt"

log() { printf '== %s ==\n' "$*"; }
pause() { sleep "$API_PAUSE"; }

preflight() {
  if ! gh auth status -h github.com &>/dev/null; then
    echo "ERROR: gh not authenticated. Run: gh auth login"
    exit 1
  fi
}

ensure_label() {
  local name="$1"
  local color="$2"
  local description="$3"
  if ! gh label list --repo "$REPO" --search "$name" --json name -q '.[].name' 2>/dev/null | grep -qxF "$name"; then
    gh label create "$name" --repo "$REPO" --color "$color" --description "$description" || true
    pause
  fi
}

issue_exists() {
  local title="$1"
  gh issue list --repo "$REPO" --state all --search "in:title \"${title}\"" --json title -q \
    ".[] | select(.title == \"${title}\") | .title" | grep -qxF "$title"
}

create_gfi_issue() {
  local title="$1"
  local body_file="$2"
  local labels="$3"
  local milestone="$4"
  if issue_exists "$title"; then
    local num
    num=$(gh issue list --repo "$REPO" --state open --search "in:title \"${title}\"" --json number,title -q \
      ".[] | select(.title == \"${title}\") | .number" | head -1)
    log "SKIP (exists): #$num $title"
    echo "$num"
    return 0
  fi
  gh issue create --repo "$REPO" \
    --title "$title" \
    --body-file "$body_file" \
    --label "$labels" \
    --milestone "$milestone"
  pause
}

comment_issue() {
  local issue="$1"
  local body="$2"
  if gh issue view "$issue" --repo "$REPO" --json comments -q '.comments | length' 2>/dev/null | grep -qv '^0$'; then
    log "SKIP welcome comment on #$issue (thread already has comments)"
    return 0
  fi
  gh issue comment "$issue" --repo "$REPO" --body "$body"
  pause
}

preflight
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BODY_DIR="$ROOT/docs/quality/issue-bodies"

log "Ensure clean-code label"
ensure_label "clean-code" "1d76db" "Uncle Bob / SOLID / env_parse DRY slice"

log "Tier F: F1 link_verification env_parse"
F1=$(create_gfi_issue \
  "[Tech Debt] link_verification: migrate strikes/batch/timeout to env_parse" \
  "$BODY_DIR/158-link-verification-env-parse.md" \
  "good first issue,help wanted,v1.9.x,tech-debt,clean-code" \
  "$MILESTONE_V1912")
echo "F1: $F1"

log "Tier F: F2 generational_cache env_parse"
F2=$(create_gfi_issue \
  "[Tech Debt] generational_cache: migrate MATRYCA_* env reads to env_parse" \
  "$BODY_DIR/159-generational-cache-env-parse.md" \
  "good first issue,help wanted,v1.9.x,tech-debt,clean-code" \
  "$MILESTONE_V1912")
echo "F2: $F2"

log "Tier F: F3 plumber_config _env_int delegate"
F3=$(create_gfi_issue \
  "[Tech Debt] plumber_config: delegate _env_int to utils.env_parse.env_int" \
  "$BODY_DIR/160-plumber-config-env-int-delegate.md" \
  "good first issue,help wanted,v1.9.x,tech-debt,clean-code" \
  "$MILESTONE_V1912")
echo "F3: $F3"

log "Tier F: F4 graph boundary forbid rag"
F4=$(create_gfi_issue \
  "[Tech Debt] Extend graph layer boundary test — forbid graph→rag imports" \
  "$BODY_DIR/161-graph-boundary-forbid-rag.md" \
  "good first issue,help wanted,v1.9.x,tech-debt,clean-code" \
  "$MILESTONE_V1912")
echo "F4: $F4"

log "Tier F: F5 concurrency_probe env_bool"
F5=$(create_gfi_issue \
  "[Tech Debt] concurrency_probe: use env_bool for flock degradation flag" \
  "$BODY_DIR/162-concurrency-probe-env-bool.md" \
  "good first issue,help wanted,v1.9.x,tech-debt,clean-code" \
  "$MILESTONE_V1912")
echo "F5: $F5"

log "Tier F: F6 env_parse clamp contract tests"
F6=$(create_gfi_issue \
  "[Tech Debt] Document link-verify and generational-cache clamp contract in tests" \
  "$BODY_DIR/163-env-parse-clamp-contract-tests.md" \
  "good first issue,help wanted,v1.9.x,tech-debt,clean-code" \
  "$MILESTONE_V1912")
echo "F6: $F6"

n1=$(echo "$F1" | grep -oE '[0-9]+$' || true)
n2=$(echo "$F2" | grep -oE '[0-9]+$' || true)
n3=$(echo "$F3" | grep -oE '[0-9]+$' || true)
n4=$(echo "$F4" | grep -oE '[0-9]+$' || true)
n5=$(echo "$F5" | grep -oE '[0-9]+$' || true)
n6=$(echo "$F6" | grep -oE '[0-9]+$' || true)

if [[ -n "$n1" ]]; then
log "Welcome comments"
comment_issue "$n1" "$(cat <<'EOF'
Hi! Thanks for contributing — Clean Code / config DI slice.

**What to fix:** `link_verify_strikes_threshold`, `link_verify_batch_size`, and `link_verify_timeout_seconds` in `src/graph/link_verification.py` use inline `os.environ` parsing. Migrate to `env_int` / `env_float` from `src/utils/env_parse.py`, then keep existing clamps.

**Read first:** [`docs/CLEAN_CODE_ARCHITECTURE.md`](docs/CLEAN_CODE_ARCHITECTURE.md)

**Verify:**
```bash
uv run pytest tests/test_link_verification.py tests/test_env_parse.py -q
make check
```

Keep the diff surgical — one module. Comment when you claim it!
EOF
)"
fi

if [[ -n "$n2" ]]; then
comment_issue "$n2" "$(cat <<'EOF'
Hi! DRY slice for generational cache config.

**What to fix:** `_generational_cache_max_graphs()` and `_bm25_mode()` in `src/graph/generational_cache.py` → use `env_parse` helpers.

**Verify:**
```bash
uv run pytest tests/test_generational_cache.py tests/test_env_parse.py -q
make check
```
EOF
)"
fi

if [[ -n "$n3" ]]; then
comment_issue "$n3" "$(cat <<'EOF'
Hi! Remove duplicate `_env_int` in `plumber_config.py` — delegate to `utils.env_parse.env_int`.

**Call sites:** `memory_budget.py`, `page_prompt_session.py`, `process_priority.py`.

**Verify:**
```bash
uv run pytest tests/test_plumber_config_env_serialization.py tests/test_env_parse.py -q
make check
```
EOF
)"
fi

if [[ -n "$n4" ]]; then
comment_issue "$n4" "$(cat <<'EOF'
Hi! Test-only architecture guard — extend `tests/test_graph_layer_boundary.py`.

Add `test_graph_modules_do_not_import_rag()` scanning `src/graph/**/*.py` for `rag` imports. If offenders exist, open a follow-up or fix in a separate PR.

**Verify:**
```bash
uv run pytest tests/test_graph_layer_boundary.py -q
make check
```
EOF
)"
fi

if [[ -n "$n5" ]]; then
comment_issue "$n5" "$(cat <<'EOF'
Hi! Trivial DRY — `src/graph/concurrency_probe.py` should use `env_bool` for `MATRYCA_ALLOW_FLOCK_DEGRADATION`.

**Verify:**
```bash
uv run pytest tests/test_env_parse.py -q
make check
```
EOF
)"
fi

if [[ -n "$n6" ]]; then
comment_issue "$n6" "$(cat <<'EOF'
Hi! Tests-as-spec slice — document clamp contracts after `env_parse` migration.

Pair with link_verification / generational_cache accessors; use `monkeypatch.setenv`. Prefer a **separate PR** from F1/F2 to avoid conflicts.

**Verify:**
```bash
uv run pytest tests/test_env_parse.py tests/test_link_verification.py tests/test_generational_cache.py -q
make check
```
EOF
)"
fi

log "Tier F complete. Update good_first_issues_blueprints.md with issue numbers: $n1 $n2 $n3 $n4 $n5 $n6"
