# Shadow read profile — OpenSpec

## Purpose

`ShadowDbStateResponse.read_profile` is a versioned, content-free companion to the
existing `shadow_db` state payload. It lets a read-side consumer decide whether a
cache snapshot is usable without inspecting SQLite tables, filesystem paths, or
producer-private configuration.

This is an additive v1 contract. Logseq Markdown remains authoritative; an absent,
disabled, stale, or incompatible profile never authorizes a consumer to write,
bootstrap, migrate, or recover the cache.

## Contract

The profile has the following stable fields:

| Field | Meaning |
| --- | --- |
| `profile` / `version` | Closed identity: `shadow-read-profile`, version `1`. |
| `producer_version` | Installed package version, or `unknown` when metadata is unavailable. |
| `graph_id` | Versioned, hashed graph binding identifier; never a filesystem path. |
| `generation` | Non-negative committed cache generation when metadata is readable. |
| `state` / `ready` | Snapshot state and whether it is currently `ready`. |
| `schema_compatible` | `true`, `false`, or `null` when metadata cannot be read. |
| `capabilities` | Closed v1 capability set: `state`. |

Consumers must require all values they need. In particular, `ready == true`,
`schema_compatible == true`, a non-empty `graph_id`, and a known supported profile
version are separate checks. Missing or unknown fields are a no-serve condition.

## Safety boundary

The resolver uses the query-only connection already used by the state API. It does
not create a cache, change metadata, migrate schema, or expose graph roots, cache
paths, page content, titles, or identifiers. Cache failure retains the existing
content-free `shadow_db` reason and may omit binding/generation information.

The profile is diagnostic and admission data only. It does not replace established
health routing or Markdown/BM25 fallback.
