# 0001 — One BIRD-layout loader for the fixture and the dev set

- Status: accepted
- Date: 2026-09-30

## Context

Phase 0 requires a tiny fixture and a download script, and the fixture must load through the same loader interface as BIRD. SPEC.md §4 describes BIRD examples (`db_id`, question, evidence, gold SQL, difficulty) and per-database SQLite files plus `database_description` CSVs. It does not spell out the on-disk directory names.

## Options considered

1. A shared function that reads the public BIRD dev directory (`dev.json`, `dev_databases/<db_id>/<db_id>.sqlite`, `database_description/*.csv`), with the fixture committed in that same shape.
2. Separate fixture and BIRD loaders that only share a Python protocol.

## Decision

Use option 1. `load_bird_layout` is the only dataset loader. `load_fixture` calls it on `tests/fixtures/tiny_db`. The download script extracts the official `dev.zip` (nested `dev_databases.zip` included) into that same shape and checks the published SHA-256 of the 2024-06-27 bundle: `cdd6d19faeb45a23970b98d3ef6c40a87987c95459c2cf12076897a60cf5a630`. Description CSVs are decoded as UTF-8, then cp1252, and header names are stripped, because published BIRD files use both.

Unknown keys on an example are ignored so an extra annotation field does not fail the loader. `evidence: null` becomes an empty string.

## Consequences

Any future field the pipeline needs must be read by this loader or the fixture and the dev set will drift. The pinned checksum refuses a newer BIRD zip until the pin is updated on purpose. Publishing results still waits on the licence check in SPEC.md §12.4.
