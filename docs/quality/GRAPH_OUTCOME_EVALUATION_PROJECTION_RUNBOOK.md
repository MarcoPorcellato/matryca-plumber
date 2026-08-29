---
type: Runbook
title: Graph-outcome evaluation projection runbook
description: Maintainer procedure for generating, verifying, retaining, reconstructing, and deleting deterministic content-free graph-outcome projection suites.
status: draft
classification: active
audience: [maintainer, contributor, operator, agent]
owner: quality
last_verified: 2026-08-26
stale_after: 2026-11-24
---

# Graph-outcome evaluation projection runbook

## Authority and scope

This runbook is the maintainer operating procedure for the deterministic
graph-outcome evaluation projection. The checked-in command implementation and
its focused tests define the executable contract; the approved PR A design and
implementation plan define the boundary and acceptance evidence. The
changelog records user-visible deltas. None of these surfaces authorizes a
release, publication, or product-runtime change.

The projection accepts only the fixed four synthetic graph-outcome scenarios.
It emits a closed JSON suite with canonical identities after binding it to one
exact clean named-branch source revision. It is an evidence projection, not a
benchmark, service, or general input processor.

## Preconditions

Before generating a suite, confirm all of the following:

- the intended checkout is at a named branch with no tracked or untracked
  changes;
- the asserted revision is the full lowercase commit identifier selected for
  the evidence record;
- the repository environment can run the checked-in command and its focused
  validation gates;
- the destination, if used, is an explicitly selected ordinary file location
  in an existing non-symlink directory; and
- the output will be handled as content-free evidence, not as a real-vault or
  product result.

The command independently rejects a source tree that is unavailable, detached,
dirty, malformed, or different from the asserted revision. Do not bypass that
source assertion by copying a previously generated file.

## Generate a suite

Generate the canonical suite to standard output:

```bash
uv run python scripts/project_graph_outcome_evidence.py \
  --source-revision <full-lowercase-commit>
```

Generate it as one explicit file instead:

```bash
uv run python scripts/project_graph_outcome_evidence.py \
  --source-revision <full-lowercase-commit> \
  --output projection.json
```

The file form refuses an existing destination by default. Use `--overwrite`
only after confirming that the selected destination is the intended ordinary
file and that replacement is authorized:

```bash
uv run python scripts/project_graph_outcome_evidence.py \
  --source-revision <full-lowercase-commit> \
  --output projection.json --overwrite
```

The installed file is written atomically. A failed pre-install operation leaves
the previous destination unchanged; a reported post-install directory-durability
failure may leave a complete replacement in place and must be investigated
before the result is retained.

## Stable exits and failure handling

| Exit | Meaning | Maintainer action |
| --- | --- | --- |
| 0 | Canonical suite emitted or installed. | Record the source revision and preserve only authorized content-free evidence. |
| 2 | Command syntax was invalid. | Correct the invocation without changing source or evidence. |
| 3 | Source binding failed. | Restore the selected clean named source state and reassert the intended revision. |
| 4 | Evidence, privacy, or schema validation rejected the suite. | Preserve the stable failure code and investigate the checked-in synthetic contract. |
| 5 | The explicit destination already exists. | Select a new destination or authorize deliberate overwrite. |
| 6 | Output installation, durability, cleanup, or standard-output handling failed. | Treat output state as uncertain until the destination is inspected safely. |

The command writes only a stable error code to standard error for its own
handled failures. Do not add exception text, source details, synthetic data, or
filesystem details to a public handoff.

## Privacy, retention, and reconstruction

The emitted suite is closed and content-free. It permits only the approved
synthetic scenario outcomes, normalized identifiers, bounded metrics,
fingerprints, and canonical identities. It excludes graph content, prompts,
answers, raw logs, paths, usernames, hostnames, credentials, timestamps, and
arbitrary metadata.

For reconstruction, return to the selected clean named branch, assert the
same full revision, regenerate through standard output, and compare the
canonical bytes with the retained evidence. A byte mismatch is an evidence
failure, not a reason to normalize or hand-edit the result.

Retain only the minimum authorized content-free suite and source-binding facts
needed by the relevant quality record. When retention expires, first confirm
the exact selected ordinary file and that it is not a symlink or source file;
then remove only that explicit generated output under the applicable evidence
retention policy. Never delete repository source, a directory tree, or an
ambiguous destination as part of projection cleanup.

## Limitations and future gate

PR A contains no MLflow integration, import, service, dependency, tracking
server, network activity, real-vault execution, or product path. It does not
qualify an agent, provider, benchmark, release, or external system.

PR B is not established by this runbook. A publisher design may enter review
only after a separately approved design and evidence gate defines its
dependency, privacy, security, network, retention, and product-boundary
requirements. Until then, the closed PR A suite remains the only documented
projection boundary.
