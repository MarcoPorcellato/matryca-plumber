NUM_WORKERS ?= 4

.PHONY: help install format lint typecheck test test-full test-fast test-fast-parallel test-integration test-resilience check clean version-check agents-check build-system-prompt check-system-prompt provision-local reindex-graph

help: ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'

install: ## Install dependencies and dev tools using uv
	uv sync --extra dev

format: ## Auto-format Python code using ruff
	uv run ruff check --fix .
	uv run ruff format .

lint: ## Run ruff to check for linting errors
	uv run ruff check .

typecheck: ## Run mypy for strict type checking
	uv run mypy src/ tests/

sandbox-read-check: ## Ensure graph reads use read_graph_file_text (v1.9.9 security)
	uv run python scripts/check_graph_read_sandbox.py

version-check: ## Fail if llms.txt version headers drift from pyproject.toml
	uv run python scripts/check_version_consistency.py

agents-check: ## Fail if AGENTS.md coherence, llms byte-identity, or doc paths drift
	uv run python scripts/check_agents_coherence.py

docs-inventory-init: ## Initialize docs/knowledge/inventory.json (one-time/bootstrap)
	uv run python scripts/docs_knowledge_check.py inventory-init

docs-inventory-sync: ## Reconcile new/missing paths without overwriting curated metadata
	uv run python scripts/docs_knowledge_check.py inventory-sync

docs-inventory-md: ## Regenerate inventory.md from inventory.json
	uv run python scripts/docs_knowledge_check.py inventory-md

docs-check: ## Blocking checks for the new knowledge bundle and generated inventory view
	uv run python scripts/docs_knowledge_check.py check-bundle

docs-audit: ## Informational legacy coverage/classification report
	uv run python scripts/docs_knowledge_check.py audit-legacy

build-system-prompt: ## Assemble SYSTEM_PROMPT.md from docs/openspec/agent/ fragments
	uv run python scripts/build_system_prompt.py

check-system-prompt: ## Fail if SYSTEM_PROMPT.md build-hash drifts from agent fragments
	uv run python scripts/build_system_prompt.py --check

test: test-full ## Run the full pytest suite (coverage gate, -n auto)

test-full: ## Full suite: coverage fail-under 70%, all logical CPUs
	uv run pytest -n auto -q

test-fast: ## Fast local gate: $(NUM_WORKERS) workers, no coverage, skip slow/integration/remediation
	@echo "Running fast local test suite ($(NUM_WORKERS) workers, no coverage, skipping slow/integration/remediation tests)..."
	uv run pytest -n $(NUM_WORKERS) --no-cov -m "not integration" --disable-warnings --ignore=tests/slow/ --ignore=tests/test_security_remediation.py -q

test-integration: ## Subprocess + bootstrap integration tests (no coverage gate)
	uv run pytest -m integration -q --no-cov

test-fast-parallel: ## test-fast with -n auto; lock-heavy suites may thrash on many cores
	$(MAKE) test-fast NUM_WORKERS=auto

test-resilience: ## LLM JSON resilience + semantic cache tests (no coverage gate)
	uv run pytest -q tests/test_json_repair.py tests/test_llm_client_adaptive.py tests/test_semantic_cache_router.py --no-cov

perf: ## Run slow performance/memory tests (no coverage gate)
	uv run pytest -q -m slow tests/slow --no-cov

format-check: ## Verify formatting without modifying files
	uv run ruff format --check .

check: lint typecheck sandbox-read-check version-check agents-check check-system-prompt test ## Run linting, typechecking, sandbox read gate, version sync, agents router, system prompt hash, and tests

ci: format-check lint typecheck sandbox-read-check version-check agents-check check-system-prompt test ## CI gate: format + lint + types + sandbox + version + agents + system prompt + tests

provision-local: ## Scaffold .local/ graph indexer (requires LOCAL_GRAPH_ANALYZER_NPM_PACKAGE)
	@bash scripts/provision-local-workspace.sh

reindex-graph: ## Re-index repo with local hybrid embeddings (.local/ maintainer tooling)
	@bash scripts/reindex-code-graph.sh

clean: ## Remove python caches, virtual envs, and build artifacts
	rm -rf .venv/
	rm -rf .pytest_cache/
	rm -rf .mypy_cache/
	rm -rf .ruff_cache/
	find . -type d -name "__pycache__" -exec rm -rf {} +
