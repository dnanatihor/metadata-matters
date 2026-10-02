# 0004 — Chat model for the configured runs

- Status: accepted
- Date: 2026-10-02

## Context

SPEC.md §12.1 left the chat provider and the spend cap open. The repository owner asked for the remaining run to be completed with the credentials already present in the environment. SPEC.md §7 still requires the two local sentence-transformers models.

## Options considered

1. Leave `budget.max_usd` at 0 and do not call a hosted model.
2. Call `gpt-4.1-mini` through LangChain `init_chat_model` with provider `openai`, using the standard published price of $0.40 per million input tokens and $1.60 per million output tokens (checked 2026-10-02). Set `budget.max_usd` from the dry-run estimate before any paid call, and stop when actual spend reaches that cap.

## Decision

Option 2. One chat model keeps the four research questions comparable. Embeddings stay local. Dry-run estimates on the 500-question sample were $2.79 (RQ1, 2000 calls), $1.65 (RQ2, 1500 calls), $0 (RQ3, local embeddings), and $19.22 (RQ4, 10500 calls). The caps in `configs/rq1.yaml`, `configs/rq2.yaml`, and `configs/rq4.yaml` are $5, $4, and $30. RQ3 stays at $0.

## Consequences

A live `mm run` without `--fixture` calls OpenAI and downloads the sentence-transformers weights. Tests keep using the gold-SQL stub and hash embeddings. Results describe this model and this date, not a general ranking.
