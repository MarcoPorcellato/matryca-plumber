# Contributor-ready shipped-evidence closure audit — 2026-08-08

## Purpose and authority

This document revalidates eight still-open contributor-ready issues whose requested
refactors are already present on the default branch. It separates issue-specific
completion from unrelated file-level debt and prepares an allowlisted closure proposal.

This audit is evidence only. It does not authorize issue comments, issue closure,
milestone changes, pull-request changes, release actions, or Gate B mutations. Live
GitHub state and the repository remain authoritative.

## Exact snapshot

- Repository: `MarcoPorcellato/matryca-plumber`
- Audited stacked source: `security/frontend-advisories-2026-08@986575070f45c6ed61be11d2d1e5ba8cf44a7503`
- Refreshed default branch: `origin/main@8754c1dd744dfdda64d3df89f1d20d8d64c7d440`
- GitHub capture: `2026-08-08T03:10:05Z`
- Issue allowlist: #220, #221, #222, #225, #226, #228, #232, and #234
- Issue state at capture: all eight open

The audited source is the dependency-hardening stack used by this programme. Every
implementing commit named below is an ancestor of both that source and the refreshed
`origin/main`; the refactors are therefore shipped default-branch history rather than
stack-only changes.

## Evidence method

For each issue, the audit:

1. read the current issue title, body, labels, state, and requested verification;
2. resolved the implementing commit and confirmed it is an ancestor of `origin/main`;
3. inspected the current target symbol and its extracted helpers;
4. ran the issue's file-wide `C901`, `PLR0912`, and `PLR0915` command;
5. ran the eight named focused suites together with coverage disabled to isolate test
   behavior from the repository-wide coverage threshold;
6. ran the complete `make ci` result as the final current-tree gate.

The focused command completed with **173 passed**. Running the same focused subset
without `--no-cov` also executes all 173 tests successfully, but exits nonzero because
the repository applies a 70% whole-suite coverage threshold to the intentionally narrow
selection. That exit is a coverage-scope artifact, not a test assertion failure.

## Issue-by-issue disposition

| Issue | Target and shipped commit | Target result | Exact file-wide complexity command | Proposed disposition |
| ---: | --- | --- | --- | --- |
| #220 | `load_agent_context` — `a6b8ef872bc29c8201aca54c8b095fe279035689` | Requested extraction is present; target is not reported by the selected rules. | PASS | Ready for separately authorized closure with shipped evidence. |
| #221 | `InstructorLLMClient.index_page` — `7f4bdae9902e7952004c7e35aab0ef9cba43fd71` | Requested extraction is present; target is not reported by the selected rules. | PASS | Ready for separately authorized closure with shipped evidence. |
| #222 | `_format_index_section` — `d2cbfd7d0db4a291ac006735e612976bfb6c8f92` | Requested extraction is present; target is not reported by the selected rules. | Nonzero only for `apply_semantic_corrections_to_lines` and `apply_semantic_page_result`. | Ready for separately authorized closure with the unrelated findings stated explicitly. |
| #225 | `run_cognitive_lint_pipeline` — `62f112580f95c5645ef7e9df4a04c2969f397dce` | Requested extraction is present; target is not reported by the selected rules. | PASS | Ready for separately authorized closure with shipped evidence. |
| #226 | `_upsert_backlink_in_content` — `7d7bb4d5a4c14927eb18d7478ed4643e9ca0b414` | Requested extraction is present; target is not reported by the selected rules. | Nonzero only for `run_backlink_backpropagator`. | Ready for separately authorized closure with the unrelated finding stated explicitly. |
| #228 | `robot_git_commit` — `1d92de15aef129286b48aead9ab7d1c2b73fef6b` | Requested extraction is present through `_open_robot_commit_repo` and `_relative_committable_paths`; target is not reported. | PASS | Ready for separately authorized closure with shipped evidence. |
| #232 | `mapreduce_harvest_page_summary` — `cc37a524fdcb60d269ca7fc27c77e54a108bc7c5` | Requested extraction is present; target is not reported by the selected rules. | PASS | Ready for separately authorized closure with shipped evidence. |
| #234 | `_mutate_block_hygiene_property` — `2c3fee5a14b3ac3a06efc02bda1bd8f246aa63bb` | Requested extraction is present; target is not reported by the selected rules. | Nonzero only for `extract_links_from_page` and `verify_registry_batch`. | Ready for separately authorized closure with the unrelated findings stated explicitly. |

The three nonzero file-wide commands do not report the symbols named by #222, #226, or
#234. They expose separate residual complexity in the same modules. Closing these three
issues must not be represented as clearing the entire file, and the residual functions
must not be silently absorbed into this closure batch.

## Focused and full-gate receipt

| Gate | Result |
| --- | --- |
| Implementing commit ancestry against `origin/main@8754c1d` | PASS — all eight commits are ancestors |
| Target-symbol selected complexity rules | PASS — none of the eight targets is reported |
| Exact file-wide complexity command | PASS for #220, #221, #225, #228, and #232; scoped caveat for #222, #226, and #234 |
| Eight named focused suites with `--no-cov` | PASS — 173 passed |
| Complete `make ci` on the documentation audit branch | PASS — exit 0; format, lint, mypy, repository guards, documentation, prompt integrity, and the full parallel test suite passed |

## Proposed remote closure batch

The batch remains proposal-only until the maintainer explicitly authorizes the remote
mutation. Before execution:

1. fetch the current issue state and stop if any allowlisted issue has changed;
2. confirm all eight implementing commits remain ancestors of the current default branch;
3. confirm the full-CI receipt below is green on the accepted audit commit;
4. comment on and close exactly the eight allowlisted issues as completed;
5. cite the implementing commit, source path, focused-test receipt, and full-CI receipt;
6. for #222, #226, and #234, name the unrelated residual functions and avoid any
   file-wide-clean claim;
7. re-read all eight issues and produce a final mutation receipt.

No issue outside the allowlist may be changed. Do not create or apply milestones or
priority labels in the same batch. If live issue state, default-branch ancestry, or CI
evidence differs, stop and refresh this document instead of widening the allowlist.

## Suggested closure evidence

Use one concise maintainer comment per issue:

> Closing as delivered on `main` in `<implementing-commit>`. The requested target
> extraction is present in `<source-path>`; the target no longer triggers the named
> complexity rules, the focused regression suites pass, and the current repository
> full-CI gate is green at `<audit-commit>`.

For #222, #226, and #234, append:

> The issue's file-wide command still reports different functions in the same module;
> those residual findings are outside this target-specific closure and are not claimed
> as resolved here.

## Boundaries and rollback

This documentation slice changes no Python source, test, dependency, lockfile, workflow,
runtime contract, Gate B evidence, tag, release, or publication state. If the audit is
rejected, revert only this evidence document and its inventory/ledger links. Remote issue
closures, once separately authorized, are recoverable by reopening the exact allowlist
and preserving the evidence comments.
