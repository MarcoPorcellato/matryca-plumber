## Summary

<!-- Why does this change exist? What trade-offs did you consider? -->

-

## Acceptance criteria

<!-- What observable outcome makes this PR complete? Link the issue or decision record. -->

-

## Scope and non-goals

<!-- State the files/behavior intentionally changed and what is explicitly out of scope. -->

- Scope:
- Non-goals:

## Security, privacy, and compatibility

<!-- Describe impact, or state "None" with a brief reason. Include migration or rollback concerns. -->

- Security/privacy impact:
- Compatibility impact:

## Test plan

- [ ] `make check` passes locally (or `make ci` for format-check too)
- [ ] OCC / CRLF: graph writes preserve `id::` lines and page frontmatter at line 0
- [ ] User-visible behavior change documented in [`CHANGELOG.md`](../CHANGELOG.md) under `[Unreleased]`
- [ ] If CLI/MCP/env changed: [`llms.txt`](../llms.txt) and [`.well-known/llms.txt`](../.well-known/llms.txt) stay in sync

## Documentation and changelog

<!-- Explain the documentation and CHANGELOG decision, including why no update is needed. -->

- Documentation impact:
- Changelog decision:

## Rollback or rejection conditions

<!-- State what evidence, regression, security concern, or scope change should block or revert this PR. -->

-

## Issue linking

<!-- Use Closes #N / Fixes #N for auto-close on merge; Refs #N for partial work -->

Closes #
