---
description: Python coding standards, libraries, and concurrency safety
globs: "*.py"
---

## Dependency management and developer experience
- **Dependency Management & DX:** Strictly use **`uv`** (never `pip`). 
- Always instruct the user to run **`make check`** to validate code (formatting, linting, mypy strict, pytest). Code is not ready until all tests pass with zero warnings.

## Runtime and quality
- **Python:** target **3.12+**.
- **Types:** annotate public APIs; `mypy` must type-check the package on `--strict` mode.
- **Validation:** use **Pydantic** models for config, JSON payloads, and boundaries.
- **Architecture:** layer boundaries and Clean Code checklist — see [`12-clean-code-architecture.mdc`](12-clean-code-architecture.mdc) and [`docs/CLEAN_CODE_ARCHITECTURE.md`](../../docs/CLEAN_CODE_ARCHITECTURE.md).

## Concurrency and I/O (File System Safety)
- **Optimistic Concurrency:** Matryca runs in the background. Before overwriting any `.md` file, you MUST check if the file's `mtime` has changed since it was read. Use `atomic_write_bytes_if_unchanged` to prevent data loss if the user is typing in Logseq.
- **Zero-Byte / Ghost Files:** Always implement early-exit guards for empty or whitespace-only files to prevent crashes.

## Observability
- Use structured logging via **`loguru`**.
- Do not log full note bodies to stdout.