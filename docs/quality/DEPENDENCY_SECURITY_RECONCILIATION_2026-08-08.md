# Dependency security reconciliation — 2026-08-08

## Purpose and evidence boundary

This record reconciles the eight open Dependabot alerts observed on the default branch with the smallest reviewable dependency updates. It distinguishes three forms of evidence that must not be conflated:

1. a resolved lockfile proves that the dependency graph can select non-vulnerable versions;
2. local and pull-request checks prove compatibility with the repository test contract;
3. only a post-merge GitHub rescan can close or dismiss an alert.

No alert was dismissed or claimed closed during this work. No repository setting, release artifact, Gate B record, tag, publication, or protected-branch rule was changed.

Source snapshot: `MarcoPorcellato/matryca-plumber`, branch `ci/stacked-pr-gate-401`, commit `d5ad6224fbb9d9785989ec8c00d9954ea3f8a11a`, reviewed on 2026-08-08.

## Alert inventory and remediation map

| Alert | Package | Severity | Scope | Locked before | Affected range | First fixed | Planned resolution |
| ---: | --- | --- | --- | --- | --- | --- | --- |
| #46 | `postcss` (npm) | moderate | transitive development dependency in `frontend/package-lock.json` | `8.5.20` | `<=8.5.22` | `8.5.23` | Separate frontend lock-only slice at `>=8.5.23`; do not couple it to Python runtime changes. [GHSA-fxqj-rqcc-2cmp](https://github.com/advisories/GHSA-fxqj-rqcc-2cmp) |
| #45 | `cryptography` (PyPI) | high | transitive runtime dependency through `PyJWT[crypto]` and MCP | `49.0.0` | `>=44,<50` | `50.0.0` | This Python slice locks `50.0.0`. [GHSA-g6cj-pr64-35w5](https://github.com/advisories/GHSA-g6cj-pr64-35w5) |
| #44 | `aiohttp` (PyPI) | high | transitive runtime dependency through Instructor | `3.14.1` | `<=3.14.2` | `3.14.3` | This Python slice locks `3.14.3`. [GHSA-cq5v-8q36-5273](https://github.com/advisories/GHSA-cq5v-8q36-5273) |
| #43 | `aiohttp` (PyPI) | moderate | transitive runtime dependency through Instructor | `3.14.1` | `<=3.14.1` | `3.14.2` | This Python slice locks `3.14.3`, superseding the minimum fix. [GHSA-mfx4-hv73-q22v](https://github.com/advisories/GHSA-mfx4-hv73-q22v) |
| #42 | `aiohttp` (PyPI) | moderate | transitive runtime dependency through Instructor | `3.14.1` | `<=3.14.1` | `3.14.2` | This Python slice locks `3.14.3`, superseding the minimum fix. [GHSA-mq44-7p77-q5h7](https://github.com/advisories/GHSA-mq44-7p77-q5h7) |
| #40 | `GitPython` (PyPI) | moderate | direct runtime dependency in `pyproject.toml` | minimum `3.1.52`, locked `3.1.54` | through `3.1.55` | `3.1.56` | This Python slice requires `>=3.1.57` and locks `3.1.58`, also satisfying the later follow-up fixes. [GHSA-p538-c434-8v24](https://github.com/advisories/GHSA-p538-c434-8v24) |
| #39 | `GitPython` (PyPI) | moderate | direct runtime dependency in `pyproject.toml` | minimum `3.1.52`, locked `3.1.54` | `<=3.1.56` | `3.1.57` | This Python slice requires `>=3.1.57` and locks `3.1.58`. [GHSA-539m-9xh6-q6rr](https://github.com/advisories/GHSA-539m-9xh6-q6rr) |
| #38 | `GitPython` (PyPI) | high | direct runtime dependency in `pyproject.toml` | minimum `3.1.52`, locked `3.1.54` | `<=3.1.56` | `3.1.57` | This Python slice requires `>=3.1.57` and locks `3.1.58`. [GHSA-3f7w-8rr8-f37f](https://github.com/advisories/GHSA-3f7w-8rr8-f37f) |

The Python resolver selected only these package-version changes:

- `aiohttp`: `3.14.1` to `3.14.3`;
- `cryptography`: `49.0.0` to `50.0.0`;
- `GitPython`: `3.1.54` to `3.1.58`;
- project metadata: `GitPython>=3.1.52` to `GitPython>=3.1.57`.

Wheel URLs, hashes, sizes, and upload timestamps necessarily changed for the three refreshed package records. No unrelated package version changed.

## Existing automated-update pull requests

| Pull request | Scope | Alert coverage | Decision |
| --- | --- | --- | --- |
| #368 | Expands the MCP requirement from major version 1 to major version 2 | None of the eight alerts | **NO-GO as an alert fix.** It is a separate runtime compatibility change and requires its own API and behavior qualification. |
| #369 | Groups eleven frontend dependency updates, including PostCSS `8.5.25` | Would address #46 after merge and rescan | **NO-GO as the preferred security slice.** The relevant fix is bundled with ten unrelated updates; use a targeted PostCSS lock-only change first. The grouped maintenance update can be reviewed independently afterward. |
| #377 | Groups GitHub Actions reference updates | None of the eight alerts | **NO-GO as an alert fix.** Review it independently, especially after CI workflow changes are reconciled. |

These decisions do not reject the unrelated maintenance objectives of the three pull requests. They prevent broad or major-version updates from being presented as necessary remediation for alerts they do not resolve.

## Smallest safe implementation order

1. Update the three Python runtime packages in one resolver-consistent slice and raise the direct GitPython floor.
2. Verify the locked environment, exact installed versions, focused integration tests, and the complete repository CI contract.
3. Submit that slice independently; after merge, wait for the default-branch Dependabot rescan before claiming alerts #38–#45 closed.
4. Stack a separate PostCSS lock-only slice, prove that no unrelated npm package changed, and run frontend install, lint, tests, and build.
5. After that merge, wait for the default-branch rescan before claiming alert #46 closed.
6. Reassess #368, #369, and #377 only against their own maintenance objectives and current base conflicts.

## Release and Gate B boundary

The Python slice changes runtime dependency metadata and the exact installed bytes. If it is included in v2.0.0, the release must be built as a new exact artifact and the maintainer must make an explicit requalification decision; existing `v2.0.0-rc.1` Gate B evidence cannot be rebound or reused as proof for that new wheel. Keeping this slice on the post-stable stack avoids invalidating the current RC qualification, but also means the affected default-branch alerts remain open until the change is merged and rescanned.

The PostCSS slice is development-tooling-only, but it still requires its normal frontend and CI evidence. Neither slice authorizes a tag, release, package publication, alert dismissal, or Gate B mutation.

## Validation receipt

The Python slice produced the following local evidence on macOS arm64 with CPython 3.12.13:

- a fresh `uv sync --locked --extra dev` resolved 101 packages and installed the changed lock without mutation;
- installed metadata reported aiohttp `3.14.3`, cryptography `50.0.0`, and GitPython `3.1.58`;
- 38 focused Git audit, MCP handshake/server, URL-policy, prompt-injection, and adaptive LLM client tests passed;
- a fresh CPython 3.13.2 locked environment selected the same three versions and passed the same 38 focused tests;
- `make ci` passed with 1,685 tests passed, 5 skipped, and 83.48% coverage;
- format, lint, typing, graph-read sandbox, version consistency, agent coherence, public-metrics, documentation, inventory, and system-prompt checks all passed;
- the lock diff contains version changes only for aiohttp, cryptography, and GitPython, plus the corresponding project GitPython requirement.

One first sandboxed full-suite run denied the existing daemon-lock test permission to execute macOS `ps`. The exact test passed with normal process permissions, and the complete `make ci` rerun then passed. This was an execution-environment restriction, not a dependency or source regression.

An independent read-only review remains required on the final staged diff before commit.

The later PostCSS slice must separately record `npm ci`, frontend lint, tests, and production build, plus a package-lock diff proving the update is isolated.
