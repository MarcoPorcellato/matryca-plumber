---
type: Decision
---
# Experimental alpha acquisition and release recovery

Date: 2026-10-18. Status: acquisition correction; proposed later candidate migration. No publication or Trama admission is established.

## Decision and scope

Preserve the [failed alpha.1 tag and publication evidence](../releases/v2.1.0-alpha.1-FAILED-PUBLICATION.md). Replace the invalid reserved-variable bootstrap in both affected workflow families with one repository-owned, standard-library-only exact-archive acquisition helper. Use a separate non-publishing Linux x86_64/macOS arm64/Windows x64 lane to test real bootstrap acquisition without invoking a publisher.

The helper runs under isolated CPython >=3.12, authenticates the exact archive before opening it, bounds redirects/bytes/expanded metadata, rejects links/special/traversing/colliding members and extracts only the expected executable into a fresh owned root. It spawns no child and provisions no interpreter, dependency or application. Verification recomputes archive/executable identities; an editable record is not a trust anchor. Partial/failed evidence stays retained.

The three fixed official archives are bound to source bea138450f0e620a4ce5765b0e38cff7b9f0799f and release 0.12.19. The upstream source declaration is MIT OR Apache-2.0, verified against [Cargo.toml](https://github.com/astral-sh/uv/blob/bea138450f0e620a4ce5765b0e38cff7b9f0799f/Cargo.toml), [LICENSE-MIT](https://github.com/astral-sh/uv/blob/bea138450f0e620a4ce5765b0e38cff7b9f0799f/LICENSE-MIT) and [LICENSE-APACHE](https://github.com/astral-sh/uv/blob/bea138450f0e620a4ce5765b0e38cff7b9f0799f/LICENSE-APACHE) on 2026-10-18. This is a source declaration, not a separate binary-license or source-to-binary attestation conclusion, endorsement or support claim.

| Platform | Archive | Bytes | SHA-256 |
| --- | --- | ---: | --- |
| Linux x86_64 | uv-x86_64-unknown-linux-gnu.tar.gz | 19831732 | 23bf5552d220e0842b65c862097b2ebaeba0064b74eda5e565e77fd25969d8c8 |
| macOS arm64 | uv-aarch64-apple-darwin.tar.gz | 16988553 | a9a8df1eedeb192f2e47e40e2faabfb387db4b850209118786d42f89dde3e0ba |
| Windows x64 | uv-x86_64-pc-windows-msvc.zip | 17955780 | 6dbb02d79e419522f1c500f0adb1cddcff0cda7d59b0d66ea7f5e3b4a1b2f5f0 |

## Preserved setup behavior

Workflow-owned bindings retain UV_PYTHON=3.12 for tooling/build environments, with assertions on the actual interpreters. The bootstrap Python may be newer without choosing the tooling minor. Installed runtime rows independently select and check 3.12 or 3.13. Managed-Python storage and generated command links remain inside the job-owned root, not a home/shared installation. Later consumption remains no-download.

The removed action's consumed uv-path and uv-version outputs are replaced by a verified absolute executable path and an observed version. The helper bin and owned Python-command directories are the only new PATH entries. Optional tool-bin injection, action cache restore/save, uvx output, automatic environment activation, Python-version/runtime-id outputs and problem matchers have no consumer in the affected exact-alpha blocks and are not re-created. Legacy release setup and required CI remain unchanged.

The new native lane does not install managed Python, dependencies or the application and establishes no Windows package support. It uploads only sanitized bootstrap identity, hash and refusal evidence, not signed download URLs, environment dumps or private paths. Operator artifact downloads require separate authority.

## Native Windows diagnostic boundary

The first native acquisition run passed Linux and macOS but rejected Windows with `file_changed`. Its failure report then attempted to consume success-only bindings and failed secondarily. The exact differing identity field and bootstrap runtime are not yet established; no platform or timestamp explanation is accepted from the error code alone.

The diagnostic candidate preserves rejection and adds only captured before/opened and before/after equality flags for device, inode, size, modification time and change time, the read-length equality and the full running Python implementation/version. It emits no paths or raw metadata. Failure reporting records failed/not-run observations without success-only verification or version probes. A native diagnostic failure remains non-mergeable until its cause is independently reviewed and a separate cause-bound corrective candidate passes all three rows.

The canonical editorial policy now permits only the exact pinned source and three archives listed above for factual qualification references. Source-license naming eligibility does not authenticate binary bytes or establish support. The original alpha.1 failure and all separate candidate, publication, public-byte and Trama gates remain unchanged.

## Later candidate: recommendation, not activation

Recommend v2.1.0-alpha.2 / 2.1.0a2 rather than reuse alpha.1. A later separately approved migration must first inventory and classify active references versus immutable history, including:

1. Package version, root-lock project metadata, the identical llms pair, changelog/release notes and a candidate-specific qualification plan.
2. The closed alpha constants, filenames and version guards in alpha1_matrix.py, alpha1_public.py, bundle.py, publisher/public-input/diagnostic dispatch logic and corresponding tests. Do not broadly enable unsupported future versions or replace historical alpha.1 references.
3. Packaged dependency-profile.json project.version and lock_sha256; its changed digest in the packaged manifest and every transitive validator/manifest/hash binding. Revalidate the native export/requirements closure rather than assuming regenerated bytes.
4. Generated documentation inventory and the exact later source/compatibility provenance.

Current acquisition work changes none of those version, lock or resource bindings. Later metadata changes must preserve exact dependency selections, Parser 1.9.0, semantic contracts, fixture/golden/TCK semantics and the producer root/lifecycle policy. Any additional necessity is an explicit scope decision, not a silent update.

Only after the migration is merged may one clean final source/tree undergo a new exact-source campaign. Earlier successful diagnostics bind only their source and are not transferred. Publication then requires explicit maintainer activation of that full commit/tree and signed tag, acknowledging GitHub Releases and PyPI effects. There is no old-tag rerun, manual alternate uploader, force-push, dependency refresh, gate waiver or publication in this correction.

## Remaining Trama boundary

After successful publication, independently acquire and verify the actual public wheel/sdist, six release assets and their provenance; repeat the declared eight installed rows and controls against those bytes, then publish the immutable producer handoff. Trama #2 must separately evaluate the exact handoff before its adapter/test admission. Bootstrap CI, static resources, a source checkout or this recovery document is not that admission.

This remains experimental OG identity plus complete content-free topology. Payload/text/properties, DB, user graphs, writes/events/sync/UI, stable compatibility and installed-Windows claims remain excluded. The separately governed full Tier 3 campaign is not launched here.
