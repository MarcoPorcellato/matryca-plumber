# RC4 independently locked build environment: design proposal

Status: approved by the maintainer on 2026-09-30; architecture and security
reviews passed with recorded limitations. The implementation plan requires
review before execution.
Date: 2026-09-30.
Source: main `4842d2cb577477678b17aff07696acbdc7a38f0e`, tree
`eea7e15190be8ed537e4a2bd87ff30cfa7ea562f`.

## Purpose and authority

Remove the remaining opportunistic PEP 517 environment provisioning from
`prepare_sdist_build` so RC4 qualification consumes independently selected build
inputs. GitHub issue #582 and
`docs/quality/V2_0_1_RC4_RELEASE_QUALIFICATION_PLAN_2026-09-06.md` remain canonical.
This proposal does not establish package qualification or release authority.

The existing helper authenticates the original sdist and checks package-manifest
stability, but creates its build environment and installs unpinned static build
requirements internally. The current runtime/development lock has no separately
selected build-toolchain closure. Recording the resulting manifest does not
establish independent provisioning provenance.

## Architecture decision

Use a dedicated repository-tracked qualification build lock, separate from the
application runtime/development `uv.lock`. A shared build dependency group is
technically possible but couples application resolution and qualification inputs
without a requirement for that coupling.

The explicit caller owns provisioning and environment lifetime. The build helper
only consumes an already provisioned private environment. It must not create,
resolve, install, sync or repair that environment. Moving today's unconstrained
install to another helper does not satisfy this boundary.

No build-toolchain versions or artifacts are selected by this decision. Exact
versions, the complete dependency closure, official identity/licensing/advisory
evidence and accepted artifact hashes must be reviewed before provisioning.

## Trusted descriptor

The provisioning descriptor binds:

- Exact source commit and tree.
- Original sdist and bundle-binding identity.
- Dedicated lock digest and reviewed provisioning recipe identity.
- Tool version and executable SHA-256.
- Target operating system and architecture.
- Python implementation, full version and executable identity.
- Complete canonical provisioned package-name/version manifest and its digest.

The expected descriptor digest must arrive independently from the caller or
aggregator. Self-hashing a helper-generated observation is not independent trust.
Private environment paths remain outside public evidence.

The trusted provisioner must retain admitted evidence that it used the exact
reviewed lock and recipe, verified the selected artifact hashes, and performed
no re-resolution or repair. Its identity and evidence binding are selected by
the independent caller/aggregator, not certified by the consumer helper. A
descriptor supplied without that trusted provisioning chain is rejected.

The helper validates actual environment/interpreter identity and independently
observes package contents. Its existing process-containment and bounds remain in
force. These checks do not establish a hostile-code sandbox.

## Observations and acceptance

Keep separate, genuinely collected complete manifests for:

1. Provisioning completion.
2. Before backend hooks.
3. After backend hooks.
4. After the wheel build.

Require equality, not subset membership or copied aliases. Record static and
dynamic requirement expressions, applicable marker decisions and exact package
satisfiers. Fail closed on missing/incompatible packages, extra unapproved
packages, unsupported markers or requirements, and descriptor/lock/source/tool
or target mismatch. Dynamic requirements must not trigger automatic lock refresh
or package installation.

Name/version equality detects package-set drift, not arbitrary same-version byte
mutation. Do not claim tamper-proof environments or reproducible builds.

Security review accepts this explicitly limited provenance/package-set claim:
lock artifact hashes, trusted provisioning evidence and complete observed
manifests are required. Installed RECORD rehash or arbitrary byte-immutability
proof is not silently added; it would require a separate stronger policy and
test boundary if requested later.

## Artifact and receipt boundaries

Keep the original independently authenticated sdist as the installed verifier's
artifact input. Build its diagnostic wheel with no build isolation in the
provisioned environment. Preserve that wheel's name, size and digest outside
canonical `dist`; install it into a separate runtime environment with `--no-deps`.

Version the changed receipt contract explicitly. Bind lock, descriptor and recipe
identities plus all observed manifests and requirement satisfiers in the build
receipt; validate these fields in aggregation. Legacy receipts remain historical
and cannot satisfy the new acceptance gate.

Windows remains NO-GO until separate native installed-package and lifecycle
evidence is qualified. Do not deploy the aggregate Stage A workflow, weaken its
admission test, or dispatch qualification as part of this implementation slice.

## Dependency-ordered implementation outline

1. Freeze the narrow written specification and implementation plan.
2. Establish reviewed build-lock ownership and provisioning format without
   altering runtime/development dependency resolution.
3. Characterize current helper/CLI/receipt behavior and inspect symbol impact.
4. Add failing deterministic descriptor and environment-binding tests.
5. Implement the typed descriptor and consumer-only helper boundary.
6. Extend receipt/aggregation tests and implement the versioned evidence contract.
7. Update CLI/operator documentation and canonical plan together; keep existing
   platform prohibitions explicit.
8. Obtain functional and security review, signed commits and exact-head hosted CI
   on a short isolated branch before conditional merge.
9. Rebind the source after merge. Provisioning, artifact builds, workflow dispatch,
   Stage A disposition and publication retain their separate gates.

## Required negative controls

- Missing or mismatched lock, descriptor or independently expected digest.
- Wrong source/tree, target, Python or tool identity.
- Missing or extra packages; incompatible static/dynamic requirement satisfiers.
- Package-manifest drift during hooks or build.
- Attempted environment creation, installation, resolution or repair by helper.
- Original-sdist substitution or mutation.
- Canonical-output contamination and additional wheel outputs.
- Receipt-field/version mismatch and legacy evidence reuse.

## Review and scope

Routine implementation and deterministic tests remain delegated; functional
review and changed trust-boundary security review are independent. The bounded
architecture review selected lock ownership but did not grant installation,
build, publication or merge authority.

No product runtime migration, environment-management service, UI, DB adapter,
write path, signing infrastructure or general-purpose environment framework is
part of this proposal.

## Official standard reference

[PEP 517 build-environment requirements](https://peps.python.org/pep-0517/#build-environment)
require static and applicable dynamic dependencies to be available. They do not
require opportunistic installation inside this qualification verifier.

[PEP 518](https://peps.python.org/pep-0518/) identifies static bootstrap
requirements. The official [lock/sync documentation](https://docs.astral.sh/uv/concepts/projects/sync/)
and [build-dependency documentation](https://docs.astral.sh/uv/concepts/projects/dependencies/)
distinguish project resolution from build requirements; the
[CLI reference](https://docs.astral.sh/uv/reference/cli/) documents that
`--no-build-isolation` assumes the build dependencies are already installed.

The existing platform receipt's runtime `lock_sha256` must remain separate from
the new build-lock identity; do not relabel its historical meaning. The focused
test runner retains its independently selected runtime/test environment.
