# Governance

Matryca Plumber is maintained as an open-source project by Marco Porcellato. This
document describes the current operating model; it does not claim a larger
maintainer team, a review quorum, or response-time commitments.

## Authority and roles

The maintainer is the final decision authority for repository scope, protected
branches, releases, security handling, and changes to public contracts. The
maintainer may delegate a specific review or area only when that delegation is
explicitly recorded in the relevant issue or pull request.

Contributors may propose changes, review code, improve documentation and tests,
provide interoperability fixtures, help with triage, and conduct research. A
contribution does not become an accepted project decision until it is reviewed
and merged by the maintainer or an explicitly delegated reviewer.

Areas needing specialist review—security, privacy, release qualification,
runtime behavior, interoperability, or documentation contracts—should be
identified in the issue or pull request. No backup owner is implied where none
is named. The project currently has a single maintainer, so availability and
review capacity are real constraints rather than hidden commitments.

## Decisions and contribution path

Use [GitHub Discussions](https://github.com/MarcoPorcellato/matryca-plumber/discussions)
for questions, proposals, and architecture debate. Use a
[GitHub issue](https://github.com/MarcoPorcellato/matryca-plumber/issues) for a
specific bug, feature, documentation change, research task, or governance
decision with a clear outcome. Use a pull request for an implemented,
reviewable change and include its acceptance criteria, scope, non-goals,
evidence, and relevant documentation decisions.

The maintainer evaluates scope, safety, compatibility, evidence, and project
fit. A proposal may be accepted, revised, deferred, or rejected. Discussion and
review should remain in the linked public issue or pull request so the reason
for a decision is discoverable. Disagreements should be stated respectfully in
the relevant thread; unresolved conflicts may be escalated by requesting a
maintainer decision. The [Code of Conduct](CODE_OF_CONDUCT.md) applies to all
project spaces.

## Security and releases

Report suspected vulnerabilities privately through [SECURITY.md](SECURITY.md),
not through a public issue or discussion. Security concerns may supersede normal
triage and are handled with the minimum necessary disclosure until a safe public
resolution is possible.

Only the maintainer authorizes a release, publication, version claim, or release
qualification decision. Release decisions require the repository's documented
source, artifact, platform, and terminal evidence; a local success or an
unverified historical result is not release authorization.

## Transparency and limitations

The project is intentionally transparent about its current single-maintainer
limitation. No standing review quorum, backup maintainer, triage rota, service
level, or delivery date exists unless separately named and recorded. Contributions
remain welcome, but acceptance depends on available maintainer capacity and the
quality and evidence required for the proposed change.
