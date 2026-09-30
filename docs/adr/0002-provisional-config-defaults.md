# 0002 — Provisional config defaults while the model budget is open

- Status: accepted
- Date: 2026-09-30

## Context

Phase 0 needs config models for `configs/rq*.yaml`, `models.yaml`, and `prices.yaml`. SPEC.md §7 requires at least two local sentence-transformers models. SPEC.md §12.1 leaves the chat providers and the maximum spend per RQ undecided. SPEC.md §4 already sets `sample.n` default 500 and allows `n: all`.

## Options considered

1. Refuse to write YAML until §12.1 is decided.
2. Load the schema the spec already names, set `budget.max_usd` to 0, list two local embedding models, and leave chat model lists empty.

## Decision

Option 2. The checked-in retrieval models are `sentence-transformers/all-MiniLM-L6-v2` and `sentence-transformers/all-mpnet-base-v2`. Their token prices are 0. `budget.max_usd: 0` means a paid run is not authorised. Chat model ids stay empty in `rq1.yaml` and `rq2.yaml`.

## Consequences

A later phase can refuse a run whose estimate exceeds `max_usd` without inventing a dollar cap here. Real runs need an explicit decision for §12.1 before `max_usd` or the chat model list is raised. Prices remain hand-maintained and must be checked before any paid call.
