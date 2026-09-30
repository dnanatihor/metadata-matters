# 0003 — Token estimate and the McNemar statistic

- Status: accepted
- Date: 2026-09-30

## Context

SPEC.md §9.1 requires a cost estimate before a run starts and a stop when actual spend reaches the cap. It does not define how tokens are estimated. SPEC.md §9.2 requires McNemar's exact binomial test when discordant pairs are under 25, and a p-value otherwise, without naming the large-sample statistic.

## Options considered

1. Count tokens with a provider tokenizer, and use a continuity-corrected McNemar chi-square.
2. Estimate input tokens as `ceil(characters / 4)` with a 256-token output allowance, and use `(b - c)^2 / (b + c)` without a continuity correction when discordant pairs are 25 or more.

## Decision

Option 2. The estimate is deterministic and needs no network. Actual spend uses the token counts on the completion. An estimate strictly above `budget.max_usd` refuses the run before any model call. After a call with positive cost, further calls are not started once spend is at least the cap. In-flight calls already inside the concurrency window finish.

The exact test is `binomtest(b, b + c, 0.5)` two-sided. Zero discordant pairs have p = 1. Bootstrap intervals use 1,000 resamples, NumPy Generator seed, and the 2.5 and 97.5 percentiles of the resampled mean.

## Consequences

The estimate will not match a vendor tokenizer. Prices in `configs/prices.yaml` still have to be checked before a paid run. The chi-square p-value will not match a continuity-corrected implementation.
