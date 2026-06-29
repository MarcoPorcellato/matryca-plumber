#!/usr/bin/env bash
# v2.0 preparation — phase tracking issues, slice backlog, label/milestone hygiene.
# Requires: gh auth with repo write scope.
# Usage: bash scripts/populate_v2_preparation.sh
set -euo pipefail

REPO="MarcoPorcellato/matryca-plumber"
API_PAUSE=2
MILESTONE_V20="v2.0.0 — Shadow DB & Safe-Sync Architecture"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BODY_DIR="$ROOT/docs/quality/issue-bodies"

log() { printf '== %s ==\n' "$*"; }
pause() { sleep "$API_PAUSE"; }

preflight() {
  if ! gh auth status -h github.com &>/dev/null; then
    echo "ERROR: gh not authenticated. Run: gh auth login"
    exit 1
  fi
}

ensure_label() {
  local name="$1" color="$2" description="$3"
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

create_issue() {
  local title="$1" body_file="$2" labels="$3" milestone="$4"
  if issue_exists "$title"; then
    local num
    num=$(gh issue list --repo "$REPO" --state open --search "in:title \"${title}\"" --json number,title -q \
      ".[] | select(.title == \"${title}\") | .number" | head -1)
    log "SKIP (exists): #$num $title"
    echo "$num"
    return 0
  fi
  gh issue create --repo "$REPO" --title "$title" --body-file "$body_file" \
    --label "$labels" --milestone "$milestone"
  pause
}

comment_issue() {
  local issue="$1" body="$2"
  if gh issue view "$issue" --repo "$REPO" --json comments -q '.comments | length' 2>/dev/null | grep -qv '^0$'; then
    log "SKIP welcome comment on #$issue (thread has comments)"
    return 0
  fi
  gh issue comment "$issue" --repo "$REPO" --body "$body"
  pause
}

patch_issue_body() {
  local num="$1" body_file="$2"
  gh issue edit "$num" --repo "$REPO" --body-file "$body_file"
  pause
}

preflight

log "Ensure v2 labels"
ensure_label "v2-prep" "ededed" "v2 Phase 0-1: prerequisites and GraphRepository ports"
ensure_label "v2-alpha" "bfd4f2" "v2 Phase 2-3: shadow sync and read routing"
ensure_label "v2-memory" "d4c5f9" "v2 Phase 4: biological memory layer"
ensure_label "v2-safesync" "fef2c0" "v2 Safe-Sync Logseq DB write bridge"

log "Patch milestone description"
gh api -X PATCH "repos/$REPO/milestones/3" \
  -f description="Epic #20: Shadow DB read cache (shadow.sqlite, FTS5, CTEs), GraphRepository (#17), Safe-Sync (#25). Visitor guide: docs/roadmaps/ROADMAP_V2_PREPARATION.md · v2_preparation_blueprints.md" \
  >/dev/null || log "WARN: milestone PATCH failed (check milestone number)"
pause

log "Refresh Epic #20 and core sub-issue bodies"
patch_issue_body 20 "$ROOT/scripts/github-reorg/bodies/issue-20.md"
patch_issue_body 17 "$ROOT/scripts/github-reorg/bodies/issue-17.md"
patch_issue_body 24 "$ROOT/scripts/github-reorg/bodies/issue-24.md"
patch_issue_body 25 "$ROOT/scripts/github-reorg/bodies/issue-25.md"

log "Phase 0 tracking issue"
P0=$(create_issue \
  "[v2 Phase 0] v1.9.12 prerequisites for Shadow DB" \
  "$BODY_DIR/v2-phase0-prerequisites.md" \
  "epic,v2.0,v2-prep" \
  "$MILESTONE_V20")
echo "P0: $P0"

log "Phase 1 tracking issue"
P1=$(create_issue \
  "[v2 Phase 1] GraphRepository — Markdown adapter (no behavior change)" \
  "$BODY_DIR/v2-phase1-graph-repository.md" \
  "epic,v2.0,v2-prep,core" \
  "$MILESTONE_V20")
echo "P1: $P1"

log "Phase 2 tracking issue"
P2=$(create_issue \
  "[v2 Phase 2] Shadow DB — incremental Markdown sync" \
  "$BODY_DIR/v2-phase2-shadow-sync.md" \
  "epic,v2.0,v2-alpha,database" \
  "$MILESTONE_V20")
echo "P2: $P2"

log "Phase 3 tracking issue"
P3=$(create_issue \
  "[v2 Phase 3] Shadow DB — read routing behind opt-in flag" \
  "$BODY_DIR/v2-phase3-read-routing.md" \
  "epic,v2.0,v2-alpha,mcp" \
  "$MILESTONE_V20")
echo "P3: $P3"

log "Phase 4 tracking issue"
P4=$(create_issue \
  "[v2 Phase 4] Biological memory + Logseq DB Safe-Sync" \
  "$BODY_DIR/v2-phase4-memory-safesync.md" \
  "epic,v2.0,v2-memory,v2-safesync" \
  "$MILESTONE_V20")
echo "P4: $P4"

log "Phase 1 slices"
S1A=$(create_issue \
  "[v2] GraphReadPort + MarkdownGraphRepository parity tests" \
  "$BODY_DIR/v2-phase1-graph-read-port.md" \
  "v2.0,v2-prep,core,tech-debt" \
  "$MILESTONE_V20")
S1B=$(create_issue \
  "[v2] graph_dispatch: delegate one read path to GraphReadPort" \
  "$BODY_DIR/v2-phase1-dispatch-read-delegate.md" \
  "v2.0,v2-prep,core,tech-debt" \
  "$MILESTONE_V20")

log "Phase 2 slices"
S2A=$(create_issue \
  "[v2] shadow: open_shadow_db connection helper" \
  "$BODY_DIR/v2-phase2-shadow-open-connection.md" \
  "v2.0,v2-alpha,database" \
  "$MILESTONE_V20")
S2B=$(create_issue \
  "[v2] shadow: post_write incremental sync handler" \
  "$BODY_DIR/v2-phase2-post-write-sync.md" \
  "v2.0,v2-alpha,database,core" \
  "$MILESTONE_V20")
S2C=$(create_issue \
  "[v2] shadow: FTS5 search query module" \
  "$BODY_DIR/v2-phase2-fts5-search.md" \
  "v2.0,v2-alpha,database" \
  "$MILESTONE_V20")

log "Phase 3 slices"
S3A=$(create_issue \
  "[v2] MATRYCA_SHADOW_DB_ENABLED env flag + .env.example" \
  "$BODY_DIR/v2-phase3-shadow-env-flag.md" \
  "v2.0,v2-alpha,dx" \
  "$MILESTONE_V20")
S3B=$(create_issue \
  "[v2] Sovereign UI shadow sync health surface" \
  "$BODY_DIR/v2-phase3-ui-shadow-health.md" \
  "v2.0,v2-alpha,dx" \
  "$MILESTONE_V20")

log "Phase 4 slice"
S4A=$(create_issue \
  "[v2] search_graph(method=recall) stub + biological-memory openspec" \
  "$BODY_DIR/v2-phase4-recall-search-method.md" \
  "v2.0,v2-memory,mcp" \
  "$MILESTONE_V20")

n0=$(echo "$P0" | grep -oE '[0-9]+$' || true)
n1=$(echo "$P1" | grep -oE '[0-9]+$' || true)
n2=$(echo "$P2" | grep -oE '[0-9]+$' || true)
n3=$(echo "$P3" | grep -oE '[0-9]+$' || true)
n4=$(echo "$P4" | grep -oE '[0-9]+$' || true)

if [[ -n "$n0" ]]; then
  comment_issue "$n0" "$(cat <<EOF
Phase 0 tracks v1 blockers before GraphRepository work. **Start here for v2 prep contributors:**

- SSOT: [ROADMAP_V2_PREPARATION.md](https://github.com/MarcoPorcellato/matryca-plumber/blob/main/docs/roadmaps/ROADMAP_V2_PREPARATION.md)
- Link PRs to #58 / #59 / Tier F env_parse — do not duplicate those issues.
- \`make check\` before review.
EOF
)"
fi

if [[ -n "$n1" ]]; then
  comment_issue "$n1" "$(cat <<EOF
Phase 1 — ports without behavior change. Slices: graph-read-port, dispatch-read-delegate.

Parent: #17 · Epic: #20

\`\`\`bash
uv run pytest tests/test_graph_repository.py -q
make check
\`\`\`
EOF
)"
fi

log "Epic #20 index comment"
gh issue comment 20 --repo "$REPO" --body "$(cat <<EOF
**v2 preparation index updated** — visitor SSOT: [\`docs/roadmaps/ROADMAP_V2_PREPARATION.md\`](docs/roadmaps/ROADMAP_V2_PREPARATION.md) · [\`v2_preparation_blueprints.md\`](v2_preparation_blueprints.md)

| Phase | Tracking issue |
|-------|----------------|
| 0 | #${n0:-TBD} |
| 1 | #${n1:-TBD} |
| 2 | #${n2:-TBD} |
| 3 | #${n3:-TBD} |
| 4 | #${n4:-TBD} |

Core: #17 GraphRepository · #24 Shadow read · #25 Safe-Sync write.
EOF
)" || true
pause

log "Done. Update v2_preparation_blueprints.md phase table with: $n0 $n1 $n2 $n3 $n4"
