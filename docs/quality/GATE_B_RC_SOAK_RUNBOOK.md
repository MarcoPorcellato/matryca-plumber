# Gate B public-RC soak runbook

This runbook starts the two independent, fail-closed soak profiles required by
the `v2.0.0` Gate B decision. Both profiles run against the installed public
`matryca-plumber==2.0.0rc1` wheel, never a source checkout.

## Recorded checkpoint snapshot (public candidate `2.0.0rc1`)

The recorded checkpoint for stable-promotion evidence is `RUNNING`
(no terminal PASS/FAIL yet):

- `checkpoint_recorded_at`: `2026-08-04T23:16:10Z`
- `attempt_started_at`: `2026-08-04T23:06:09Z` (`2026-08-05 01:06:09`
  Europe/Rome)
- `status`: `RUNNING`

| Field | Value |
| --- | --- |
| Candidate artifact | `matryca-plumber==2.0.0rc1` |
| Public wheel SHA-256 | `f9c60cc89049b9524ca9f9346a053bac3c7aba6f2186d9a31a3993bd7a9253cd` |
| Runner source | `main@1e8805ec99c6471549ecf36e4a261a31013a0f6f` |
| Qualifier SHA-256 | `b4cee6a2b6c8a8fbd8bb890cf583b7d126f2e40bda8b55cb7a0c499c8490dbe6` |
| Supervisor SHA-256 | `bfcae04483a5003df8e83fb52ece42c0c933d7c708c9e73d55733309736e7445` |
| Profiles | `default-on`, `read-only-external` |
| target_duration_seconds | `259200` |
| max_cycles | `1000` |
| interval_seconds | `600` |
| page_parse_timeout_seconds | `15` |
| exact installed-wheel/RECORD gate | `PASS` |
| earliest uninterrupted completion estimate | 2026-08-08 01:06 (Europe/Rome) |

### Recorded checkpoint history and recovery proof

- An earlier attempt sequence accumulated `108` attempts **per profile** and produced
  zero completed cycles, zero valid elapsed seconds, and `probe_invalid` outcomes.
  The profile adapter omitted required `elapsed_ms` from otherwise successful probe
  payloads, so the generic collector rejected each as `probe_invalid`; this evidence
  is explicitly excluded from qualification and not reused.
- PR #382 corrected that probe path by adding measured `elapsed_ms` to profile probe
  payloads and adding adapter-to-collector regression coverage.
- A corrected preflight launch then failed closed as `working_copy_exists` because
  previous working/cache roots remained after creating fresh evidence directories.
  The failed preflight bundle, old roots, and logs were archived and excluded from
  the active checkpoint.
- A fully fresh attempt began at `2026-08-04T23:06:09Z` with clean working/cache/
  evidence roots and the same public wheel.
- At the first valid checkpoint both profiles reached cycle 1 with:
  - `cycle 1` completed
  - two PASS phase attempts each (ON/OFF)
  - non-empty chained attempt cursor
  - no stderr errors
  - elapsed: `440.1835287499998s` (`default-on`), `440.2918676670015s`
    (`read-only-external`)
- A controlled service stop/reload proof was then executed. While stopped, state
  files were byte-identical and no elapsed seconds were credited. Both LaunchAgents
  reloaded and resumed, advanced to cycle 2, and retained `two completed cycles`
  with `four PASS phase attempts` per profile at recorded checkpoint
  `2026-08-04T23:16:10Z`.
  Post-resume elapsed values became: `448.1676894170014s` (`default-on`) and
  `447.76504575099534s` (`read-only-external`).
- At the recorded checkpoint, the corrected fresh attempt had controlled service stop/reload proof;
  it has not yet been host-reboot-tested. Prior deployment behavior supports
  LaunchAgent restart resilience, but host-restart behavior has not yet been
  demonstrated for this attempt.
- A separate six-hour supervisory health check observes evidence and service health,
  reporting material changes, interventions, failures, and terminal completion.

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
