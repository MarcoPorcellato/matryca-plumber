# Gate B public-RC soak runbook

This runbook starts the two independent, fail-closed soak profiles required by
the `v2.0.0` Gate B decision. Both profiles run against the installed public
`matryca-plumber==2.0.0rc1` wheel, never a source checkout.

## Profiles

| Profile | Shadow flag | Read Only | Graph activity | Required proof |
| --- | --- | --- | --- | --- |
| `default-on` | Unset | Unset | Synthetic fixture create/rename/delete on a copied vault | `READY`, FTS, subtree, watcher CRUD, recovery, and explicit-false opt-out |
| `read-only-external` | Unset | `true` | No graph mutation | `READY`, FTS, subtree, recovery, external-cache-only writes, explicit-false opt-out, and unchanged full graph manifest |

Each profile requires its own source copy, working copy, cache root, evidence
directory, candidate environment, and service label. Paths are private operator
inputs and must never be committed. The source copy is fingerprint-bound through
a private one-line realpath file. Evidence stores only hashes, counters, bounded
status categories, and timings.

## Required preparation

1. Download the public RC wheel and verify its SHA-256 against the GitHub
   prerelease and PyPI.
2. Create one Python 3.12 virtual environment per profile and install only that
   exact wheel.
3. Freeze the committed qualification runner outside the repository, vault,
   working copies, cache roots, and evidence roots; record its commit and digest.
4. Pass the verified wheel path and published SHA-256 to each profile. The
   collector verifies the installed package RECORD, records the exact wheel
   binding, and refuses to start the soak if either identity differs.
5. Copy the private source vault once per profile. Never point either collector
   at the live vault.

## Collector command

Use the profile-specific paths in this template:

```text
<candidate-python> <frozen-runner>/scripts/qualify_gate_b_soak.py \
  --profile <default-on|read-only-external> \
  --output <evidence-root> \
  --candidate-python <candidate-python> \
  --candidate-wheel <verified-public-wheel> \
  --expected-wheel-sha256 <published-wheel-sha256> \
  --source-vault <source-copy> \
  --expected-source-realpath-file <private-realpath-file> \
  --working-root <empty-working-copy-path> \
  --cache-root <external-cache-root> \
  --duration-seconds 259200 \
  --max-cycles 1000 \
  --interval-seconds 600 \
  --page-parse-timeout-seconds 15
```

`MATRYCA_SHADOW_DB_ENABLED` must not be present in the service environment. The
collector sets `MATRYCA_READ_ONLY=true` only inside the Read Only profile's
installed-wheel probe.

## Durable service contract

Run the collector through `scripts/run_gate_b_soak_supervisor.py` from a
user-scoped LaunchAgent on macOS. The service must:

- use stable Application Support paths rather than `/tmp` or a protected
  Documents location;
- set `RunAtLoad=true` and `KeepAlive` only for unsuccessful exits;
- use a bounded throttle interval;
- write stdout/stderr outside the graph and evidence directory;
- restart after process failure, logout/login, or host restart;
- stop after either terminal `PASS` or terminal `FAIL`;
- never award elapsed duration while the collector or host is stopped.

The supervisor returns a temporary-failure exit while no terminal result exists,
allowing the service manager to restart it. A valid `PASS` or `FAIL` result makes
the supervisor exit successfully and stop. A malformed terminal result also
stops automatically and requires maintainer intervention rather than entering a
restart loop.

## Acceptance

Starting a service does not close Gate B. Each profile closes only when its
machine-readable result is terminal `PASS`, the full source/working-copy
integrity checks pass, candidate and profile bindings match, and the sanitized
result is reviewed. A terminal `FAIL` is immutable evidence and requires defect
disposition plus a fresh attempt identifier.
