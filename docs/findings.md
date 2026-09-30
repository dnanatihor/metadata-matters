# Findings

This draft reads every number from the committed fixture runs under `results/`.
Those runs use the gold-SQL stub (`stub-gold`) and `HashEmbedder`.
`HashEmbedder` is a deterministic local hash, keyed by the model ids in `configs/models.yaml`.
It is not `sentence-transformers`. The stub returns the example's gold SQL, so execution accuracy
does not measure a language model.
SPEC.md Phase 6 also asks for a 500-question sample on the configured hosted models.
That run was not executed. `budget.max_usd` is 0 (see ADR 0002 and SPEC.md §12.1),
the BIRD dev set is not in the repository, and this checkout has no provider credentials.
On the 12-example fixture, `sample.n: 500` returns every example.

## rq1
Run `20260930T184730Z-128297c4` (`git_commit` `584cfb16ed9a6e370e56ed12dc53035e8f5f4b44`).
Models recorded in `run.json`: stub-gold.
Cost USD 0.0. Items 48.
Files: `results/rq1/20260930T184730Z-128297c4`.

```csv
label,condition,estimate,low,high,n
M0,M0,1.0,1.0,1.0,12
M1,M1,1.0,1.0,1.0,12
M2,M2,1.0,1.0,1.0,12
M3,M3,1.0,1.0,1.0,12
```

## rq2
Run `20260930T184732Z-40dda842` (`git_commit` `584cfb16ed9a6e370e56ed12dc53035e8f5f4b44`).
Models recorded in `run.json`: stub-gold.
Cost USD 0.0. Items 36.
Files: `results/rq2/20260930T184732Z-40dda842`.

```csv
label,condition,estimate,low,high,n,metric
D0,D0,1.0,1.0,1.0,12,ex
D1,D1,1.0,1.0,1.0,12,ex
D2,D2,1.0,1.0,1.0,12,ex
D0,D0,0.0,0.0,0.0,12,decoy_usage
D1,D1,0.0,0.0,0.0,12,decoy_usage
D2,D2,0.0,0.0,0.0,12,decoy_usage
```

## rq3
Run `20260930T184735Z-f664f7e2` (`git_commit` `584cfb16ed9a6e370e56ed12dc53035e8f5f4b44`).
Models recorded in `run.json`: sentence-transformers/all-MiniLM-L6-v2, sentence-transformers/all-mpnet-base-v2.
Cost USD 0.0. Items 480.
Files: `results/rq3/20260930T184735Z-f664f7e2`.

```csv
label,estimate,low,high,n
t0 sentence-transformers/all-MiniLM-L6-v2 global question,0.638888888888889,0.4305555555555556,0.8194444444444443,12
t0 sentence-transformers/all-MiniLM-L6-v2 global question_evidence,0.638888888888889,0.4305555555555555,0.8057291666666664,12
t0 sentence-transformers/all-MiniLM-L6-v2 in_database question,0.638888888888889,0.4305555555555556,0.8194444444444443,12
t0 sentence-transformers/all-MiniLM-L6-v2 in_database question_evidence,0.638888888888889,0.4305555555555555,0.8057291666666664,12
t0 sentence-transformers/all-mpnet-base-v2 global question,0.6736111111111112,0.5,0.8194444444444445,12
t0 sentence-transformers/all-mpnet-base-v2 global question_evidence,0.4861111111111111,0.3333333333333333,0.6458333333333334,12
t0 sentence-transformers/all-mpnet-base-v2 in_database question,0.6736111111111112,0.5,0.8194444444444445,12
t0 sentence-transformers/all-mpnet-base-v2 in_database question_evidence,0.4861111111111111,0.3333333333333333,0.6458333333333334,12
t1 sentence-transformers/all-MiniLM-L6-v2 global question,0.5972222222222222,0.3958333333333333,0.8055555555555555,12
t1 sentence-transformers/all-MiniLM-L6-v2 global question_evidence,0.6805555555555555,0.5,0.8333333333333334,12
t1 sentence-transformers/all-MiniLM-L6-v2 in_database question,0.5972222222222222,0.3958333333333333,0.8055555555555555,12
t1 sentence-transformers/all-MiniLM-L6-v2 in_database question_evidence,0.6805555555555555,0.5,0.8333333333333334,12
t1 sentence-transformers/all-mpnet-base-v2 global question,0.5694444444444444,0.4166666666666667,0.7222222222222223,12
t1 sentence-transformers/all-mpnet-base-v2 global question_evidence,0.5625,0.375,0.7296874999999995,12
t1 sentence-transformers/all-mpnet-base-v2 in_database question,0.5694444444444444,0.4166666666666667,0.7222222222222223,12
t1 sentence-transformers/all-mpnet-base-v2 in_database question_evidence,0.5625,0.375,0.7296874999999995,12
t2 sentence-transformers/all-MiniLM-L6-v2 global question,0.5833333333333334,0.375,0.7916666666666666,12
t2 sentence-transformers/all-MiniLM-L6-v2 global question_evidence,0.6319444444444444,0.4791666666666667,0.7708333333333334,12
t2 sentence-transformers/all-MiniLM-L6-v2 in_database question,0.5833333333333334,0.375,0.7916666666666666,12
t2 sentence-transformers/all-MiniLM-L6-v2 in_database question_evidence,0.6319444444444444,0.4791666666666667,0.7708333333333334,12
t2 sentence-transformers/all-mpnet-base-v2 global question,0.513888888888889,0.33315972222222223,0.7083333333333334,12
t2 sentence-transformers/all-mpnet-base-v2 global question_evidence,0.75,0.5625,0.9166666666666666,12
t2 sentence-transformers/all-mpnet-base-v2 in_database question,0.513888888888889,0.33315972222222223,0.7083333333333334,12
t2 sentence-transformers/all-mpnet-base-v2 in_database question_evidence,0.75,0.5625,0.9166666666666666,12
t3 sentence-transformers/all-MiniLM-L6-v2 global question,0.5,0.2916666666666667,0.7083333333333334,12
t3 sentence-transformers/all-MiniLM-L6-v2 global question_evidence,0.7013888888888888,0.46527777777777773,0.9029513888888886,12
t3 sentence-transformers/all-MiniLM-L6-v2 in_database question,0.5,0.2916666666666667,0.7083333333333334,12
t3 sentence-transformers/all-MiniLM-L6-v2 in_database question_evidence,0.7013888888888888,0.46527777777777773,0.9029513888888886,12
t3 sentence-transformers/all-mpnet-base-v2 global question,0.5069444444444444,0.3125,0.6875,12
t3 sentence-transformers/all-mpnet-base-v2 global question_evidence,0.6597222222222222,0.5,0.798611111111111,12
t3 sentence-transformers/all-mpnet-base-v2 in_database question,0.5069444444444444,0.3125,0.6875,12
t3 sentence-transformers/all-mpnet-base-v2 in_database question_evidence,0.6597222222222222,0.5,0.798611111111111,12
t4 sentence-transformers/all-MiniLM-L6-v2 global question,0.5972222222222222,0.40972222222222215,0.7638888888888888,12
t4 sentence-transformers/all-MiniLM-L6-v2 global question_evidence,0.8194444444444445,0.6458333333333334,0.937673611111111,12
t4 sentence-transformers/all-MiniLM-L6-v2 in_database question,0.5972222222222222,0.40972222222222215,0.7638888888888888,12
t4 sentence-transformers/all-MiniLM-L6-v2 in_database question_evidence,0.8194444444444445,0.6458333333333334,0.937673611111111,12
t4 sentence-transformers/all-mpnet-base-v2 global question,0.7013888888888888,0.5277777777777778,0.8404513888888886,12
t4 sentence-transformers/all-mpnet-base-v2 global question_evidence,0.6875,0.4583333333333333,0.875,12
t4 sentence-transformers/all-mpnet-base-v2 in_database question,0.7013888888888888,0.5277777777777778,0.8404513888888886,12
t4 sentence-transformers/all-mpnet-base-v2 in_database question_evidence,0.6875,0.4583333333333333,0.875,12
```

On this one-database fixture, each in-database row matches the global row with the same template, model id, and query mode.

## rq4
Run `20260930T184738Z-4b99c9f1` (`git_commit` `584cfb16ed9a6e370e56ed12dc53035e8f5f4b44`).
Models recorded in `run.json`: stub-gold, sentence-transformers/all-MiniLM-L6-v2, sentence-transformers/all-mpnet-base-v2.
Cost USD 0.0. Items 252.
Files: `results/rq4/20260930T184738Z-4b99c9f1`.

```csv
label,condition,estimate,low,high,n
full-m2,full-m2,1.0,1.0,1.0,12
t0-sentence-transformers/all-MiniLM-L6-v2-k10,t0-sentence-transformers/all-MiniLM-L6-v2-k10,1.0,1.0,1.0,12
t0-sentence-transformers/all-MiniLM-L6-v2-k20,t0-sentence-transformers/all-MiniLM-L6-v2-k20,1.0,1.0,1.0,12
t0-sentence-transformers/all-mpnet-base-v2-k10,t0-sentence-transformers/all-mpnet-base-v2-k10,1.0,1.0,1.0,12
t0-sentence-transformers/all-mpnet-base-v2-k20,t0-sentence-transformers/all-mpnet-base-v2-k20,1.0,1.0,1.0,12
t1-sentence-transformers/all-MiniLM-L6-v2-k10,t1-sentence-transformers/all-MiniLM-L6-v2-k10,1.0,1.0,1.0,12
t1-sentence-transformers/all-MiniLM-L6-v2-k20,t1-sentence-transformers/all-MiniLM-L6-v2-k20,1.0,1.0,1.0,12
t1-sentence-transformers/all-mpnet-base-v2-k10,t1-sentence-transformers/all-mpnet-base-v2-k10,1.0,1.0,1.0,12
t1-sentence-transformers/all-mpnet-base-v2-k20,t1-sentence-transformers/all-mpnet-base-v2-k20,1.0,1.0,1.0,12
t2-sentence-transformers/all-MiniLM-L6-v2-k10,t2-sentence-transformers/all-MiniLM-L6-v2-k10,1.0,1.0,1.0,12
t2-sentence-transformers/all-MiniLM-L6-v2-k20,t2-sentence-transformers/all-MiniLM-L6-v2-k20,1.0,1.0,1.0,12
t2-sentence-transformers/all-mpnet-base-v2-k10,t2-sentence-transformers/all-mpnet-base-v2-k10,1.0,1.0,1.0,12
t2-sentence-transformers/all-mpnet-base-v2-k20,t2-sentence-transformers/all-mpnet-base-v2-k20,1.0,1.0,1.0,12
t3-sentence-transformers/all-MiniLM-L6-v2-k10,t3-sentence-transformers/all-MiniLM-L6-v2-k10,1.0,1.0,1.0,12
t3-sentence-transformers/all-MiniLM-L6-v2-k20,t3-sentence-transformers/all-MiniLM-L6-v2-k20,1.0,1.0,1.0,12
t3-sentence-transformers/all-mpnet-base-v2-k10,t3-sentence-transformers/all-mpnet-base-v2-k10,1.0,1.0,1.0,12
t3-sentence-transformers/all-mpnet-base-v2-k20,t3-sentence-transformers/all-mpnet-base-v2-k20,1.0,1.0,1.0,12
t4-sentence-transformers/all-MiniLM-L6-v2-k10,t4-sentence-transformers/all-MiniLM-L6-v2-k10,1.0,1.0,1.0,12
t4-sentence-transformers/all-MiniLM-L6-v2-k20,t4-sentence-transformers/all-MiniLM-L6-v2-k20,1.0,1.0,1.0,12
t4-sentence-transformers/all-mpnet-base-v2-k10,t4-sentence-transformers/all-mpnet-base-v2-k10,1.0,1.0,1.0,12
t4-sentence-transformers/all-mpnet-base-v2-k20,t4-sentence-transformers/all-mpnet-base-v2-k20,1.0,1.0,1.0,12
```

## What these runs do not show

RQ1 execution accuracy is 1 for every metadata level because the stub emits the gold SQL, which does not depend on the context. RQ2 decoy usage is 0 for D0, D1, and D2 for the same reason: the gold SQL names the real tables. The decoy builder's effect on gold SQL is covered by `tests/test_phase3_decoys.py`, not by these stub scores. RQ4 execution accuracy is also 1 for full M2 and for every retrieved subset, again because the stub ignores the prompt.

RQ3 recall@10 is a real ranking of the hash vectors over the fixture column corpus. Treat differences across templates as properties of that hash, not of MiniLM or MPNet. The M3 caveat in each RQ1 report still applies: M3 appends the example's own evidence as a business-glossary hint.
