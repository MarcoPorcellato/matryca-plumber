---
type: Document
---
## Problem Description

`BoundedPageParseWorker.parse_text` (`src/graph/bounded_page_parse.py`) bounds the wait for a worker response with `self._out_q.get(timeout=deadline)`. `multiprocessing.Queue.get(timeout=...)` only bounds the wait for the pipe to become *readable*; once readable it falls through to an unconditional `recv_bytes()`, which can still block past the configured deadline while a large or partial response is still being received.

Diagnosed during v2 beta candidate soak attempt **r7** ([`BETA_R7_BOUNDED_PARSE_HANDOFF_2026-07-23.md`](../BETA_R7_BOUNDED_PARSE_HANDOFF_2026-07-23.md)): a final diagnostic profile measured `166.923s` total against a configured `120s` page deadline, exceeding it by >45s with no bounded parse result returned. The r7 attempt was **STOPPED** — no tag, no release, no soak resumption — pending this fix, since the containment guarantee this method provides is the first gate in [`v2-beta-readiness.md`](v2-beta-readiness.md) ("Bounded parser containment").

## Proposed Architectural Solution

Enforce the configured deadline over the **entire** receive operation, not just queue-readiness:

1. Run the blocking `self._out_q.get()` on a daemon receiver thread.
2. Bound the wait with `threading.Event.wait(timeout=deadline)` on the calling thread.
3. On deadline overrun, treat it as a timeout exactly as before: terminate/reset the worker, discard queue state, and return content-free `timed_out=True` metadata. The killed worker's closed pipe unblocks the stalled receiver thread (daemon, so it cannot leak past process exit).
4. Preserve all existing contracts: stale results are never reused (a fresh worker/queue pair is created for the next request), concurrency/fork/shutdown safety unchanged, parser semantics/schema/routing/Shadow default-off behavior unchanged.

This is a surgical change scoped to the receive path inside `parse_text`; no signature, protocol, or public-behavior change.

## Estimated Impact

**LOW** — confirmed via `impact(target: "parse_text", direction: "upstream")`: 7 impacted symbols, 1 affected process (`scripts/measure_bounded_page_parse_overhead.py:main`), 2 affected modules (Graph, Tests).

## Validation

- New test `test_slow_receive_past_readiness_is_bounded_by_deadline` (`tests/test_bounded_page_parse.py`) reproduces the bug directly: stubs the queue's `get()` to become "ready" instantly but stall 5s, and asserts `parse_text` still times out near the configured 1s deadline instead of blocking for the stub's full duration.
- Full `tests/test_bounded_page_parse.py` suite: 18/18 passed.
- Full `make ci` (format, lint, typecheck, sandbox-read-check, version-check, agents-check, system-prompt-check, tests): green — 1446 passed, 2 skipped, 1 xfailed, 82.78% coverage.

## Files Involved

- `src/graph/bounded_page_parse.py` (`BoundedPageParseWorker.parse_text`)
- `tests/test_bounded_page_parse.py`

## Resume sequence (per r7 handoff)

This fix covers steps 1–4 of the handoff's resume sequence (issue + branch from `main`, reconfirm impact, surgical fix + tests, full `make ci`). Steps 5–9 (merge after review, rebuild candidate, rerun wheel/provenance gate, fresh ON probe, new soak attempt id, 24h+ soak, final audit) remain outstanding and out of scope for this PR.

---
**v2 Beta Readiness** · Blocks resumption of beta candidate soak · Depends on nothing
