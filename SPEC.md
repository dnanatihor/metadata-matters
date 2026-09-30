# Metadata Matters — Does Catalog Metadata Make AI Better?

| | |
|---|---|
| Repo name | `metadata-matters` |
| Version | 0.1.0 |
| Size | Medium–large (compute and API budget) |
| Depends on | nothing; findings inform `governed-rag-reference` |

---

## 0. Using this spec with Cursor

Save as `SPEC.md` at the repo root. Implement one phase at a time from §10 with the prompts in Appendix A. All development runs against a tiny fixture database and stub models; real models are only called by explicit `run` commands with a budget cap.

If this repository was created with the portfolio bootstrap, the prompts below are already filled in per phase in `CURSOR_PROMPTS.md`, and `.cursor/rules/project.mdc` already contains the project rules from Appendix A.

---

## 1. Purpose and research questions

A reproducible benchmark that quantifies how data-catalog metadata affects AI systems working over databases.

| ID | Question |
|---|---|
| RQ1 | How does metadata richness (none → descriptions → value descriptions and samples → business hints) change text-to-SQL execution accuracy? |
| RQ2 | Do governance labels (certified / deprecated) help models avoid plausible but wrong "decoy" tables? |
| RQ3 | Which text template for embedding catalog assets gives the best schema retrieval? |
| RQ4 | End to end: with schema context limited to retrieved columns, which template yields the best text-to-SQL accuracy? |

RQ2 is the novel contribution: most text-to-SQL benchmarks ignore governance signals, while real catalogs are full of deprecated and duplicate tables.

### 1.1 Non-goals

Building a new text-to-SQL system, fine-tuning models, or declaring any model "best" beyond the tested configuration and date.

### 1.2 Data and IP

Uses the public **BIRD** dev set only. The download script fetches it; the dataset is never committed. Confirm and follow BIRD's licence terms in the README. Templates and prompts are written from scratch for this repo and must not reuse any employer's internal templates or data.

---

## 2. Technology stack

| Concern | Choice |
|---|---|
| Language | Python 3.11+, `uv` |
| SQL | `sqlite3` (BIRD databases), `sqlglot` (table/column extraction) |
| LLMs | `langchain` `init_chat_model` (multiple providers) |
| Embeddings | `sentence-transformers` (local) + optional API embeddings |
| Numerics | `numpy`, `pandas`, `scipy` |
| Plots | `matplotlib` |
| Config | YAML → `pydantic` v2 |
| Cache | sqlite (`cache.db`) keyed by request hash |
| Quality | `pytest`, `ruff`, `mypy --strict` |

---

## 3. Repository layout

```
metadata-matters/
├── configs/{rq1.yaml, rq2.yaml, rq3.yaml, rq4.yaml, models.yaml, prices.yaml}
├── prompts/text_to_sql.v1.md
├── templates/embedding/{t0.j2 … t4.j2}
├── scripts/download_bird.py
├── src/mm/
│   ├── data/{bird.py, fixture.py}
│   ├── context/{ddl.py, levels.py}         # M0–M3
│   ├── decoys.py                           # RQ2
│   ├── llm/{runner.py, cache.py, budget.py, extract_sql.py}
│   ├── evaluate/{execution.py, relevance.py, retrieval_metrics.py, stats.py}
│   ├── retrieval/{corpus.py, embed.py, index.py}
│   ├── report/{tables.py, plots.py, readme.py}
│   └── cli.py
├── results/<rq>/<run_id>/                  # committed: metrics.csv, report.md, plots/
└── tests/fixtures/tiny_db/                 # hand-made SQLite + descriptions + 12 questions
```

---

## 4. Data

- **BIRD dev**: for each example, `db_id`, `question`, `evidence`, gold `SQL`, and `difficulty` (simple / moderate / challenging). Each database has a SQLite file and `database_description/*.csv` with column descriptions and value descriptions.
- **Sampling**: `sample.n` (default 500) stratified by difficulty and database with a fixed seed; `n: all` uses the full dev set. The sampled IDs are written to `results/<rq>/<run_id>/sample.json`.
- **Fixture**: `tests/fixtures/tiny_db` mimics BIRD's structure (3 tables, description CSVs, 12 questions with gold SQL) so every code path is testable offline.

---

## 5. RQ1 — Metadata levels

Context builders produce the schema section of the prompt:

| Level | Content |
|---|---|
| M0 | `CREATE TABLE` statements read from the SQLite schema |
| M1 | M0 + column descriptions as SQL comments |
| M2 | M1 + value descriptions + up to 3 distinct sample values per column (from the database, truncated to 40 characters each) |
| M3 | M2 + the example's BIRD `evidence`, labelled "Business glossary hint" |

M3's evidence is question-specific; the report must state this caveat.

**Prompt** (`prompts/text_to_sql.v1.md`, Jinja2): system message with dialect (SQLite), instructions to return a single SQL query in a fenced `sql` block, and the schema context; user message with the question. Temperature 0. `extract_sql` takes the last fenced `sql` block, or the whole response if none; failure to extract counts as incorrect.

**Evaluation — execution accuracy (EX):** run predicted and gold SQL against the database (read-only connection, `mode=ro` URI), each with a timeout (default 30 s via `sqlite3` progress handler). Correct when the result sets are equal as sets of rows (order-insensitive), matching BIRD's convention. Errors and timeouts are incorrect and recorded with their cause.

---

## 6. RQ2 — Decoys and governance labels

For each sampled example, build a decoy variant of its database (a copy; originals are never modified):

1. Identify tables referenced by the gold SQL (`sqlglot`).
2. For one or two of them, create a decoy table with a plausible name from a fixed pattern list (`<name>_legacy`, `<name>_v1`, `<name>_backup`, `old_<name>`), the same columns, and perturbed data: 30% of rows dropped and one numeric column scaled by a random factor between 0.8 and 1.2 (seeded). Queries against the decoy therefore return wrong answers.

Conditions (all built on M1):

| Condition | Context |
|---|---|
| D0 | Real and decoy tables, no labels |
| D1 | + `-- status: certified` on real tables, `-- status: deprecated` on decoys |
| D2 | D1 + a one-line note on each decoy: "Deprecated; use `<real table>` instead." |

Metrics: EX, and **decoy usage rate** (fraction of predictions that reference any decoy table, via `sqlglot`). The decoy copies and their seed are recorded so results are reproducible.

---

## 7. RQ3 — Embedding templates for schema retrieval

- **Corpus:** one document per column and one per table across all dev databases (optionally including RQ2 decoys).
- **Templates** (Jinja2, versioned):

| Template | Column document content |
|---|---|
| T0 | `table.column` |
| T1 | T0 + data type |
| T2 | T1 + column description |
| T3 | T2 + value description + sample values |
| T4 | T3 + table description + names of sibling columns |

- **Queries:** the question (and a second setting with the evidence appended).
- **Relevance:** columns and tables referenced by the gold SQL, extracted with `sqlglot` after qualification against the database schema. Examples where extraction fails are excluded and counted.
- **Settings:** in-database (corpus limited to the example's database) and global (all databases, closer to catalog search).
- **Models:** list in `configs/models.yaml`; at least two local `sentence-transformers` models; API models optional.
- **Index:** normalised embeddings, brute-force cosine with `numpy` (the corpus is small). Embeddings cached on disk per (model, template, corpus hash).
- **Metrics:** Recall@5, Recall@10 (fraction of gold columns retrieved), full-coverage@10 (all gold columns in the top 10), MRR of the first gold table, nDCG@10.

---

## 8. RQ4 — End to end

For each (embedding model, template), retrieve the top-k columns (k ∈ {10, 20}), build an M2-style context containing only the tables of retrieved columns and only the retrieved columns within them, and run the RQ1 pipeline. Compare against full-schema M2 as the upper reference.

---

## 9. Runner, statistics, and reporting

### 9.1 Runner

- Every LLM and embedding call goes through a cache keyed by `sha256(model_id | prompt_version | full_prompt)`. Runs are resumable: rerunning skips cached items.
- **Budget:** `prices.yaml` holds per-model token prices (maintained by hand; the README says prices must be checked). The runner estimates cost before starting, refuses to start if the estimate exceeds `budget.max_usd`, and stops cleanly if actual spend reaches it.
- Concurrency limit per provider; exponential backoff on rate-limit errors.
- Every run writes `run.json`: run ID, git commit, package versions, model IDs, prompt and template versions, dataset checksum, sample IDs file, seed, start/end time, token usage, and cost.

### 9.2 Statistics

- EX per condition with 95% bootstrap confidence intervals (1,000 resamples, fixed seed).
- Paired comparisons between conditions for the same model with McNemar's test (exact binomial when discordant pairs < 25); report p-values and the difference in EX with CI.
- Retrieval metrics with bootstrap CIs.
- Breakdowns by difficulty.

### 9.3 Reports

`results/<rq>/<run_id>/`: `predictions.jsonl` (not committed if over 5 MB), `metrics.csv`, `report.md` (method, conditions, results tables, plots, caveats), `plots/*.png`. `mm readme` regenerates a results section in `README.md` between `<!-- results:start -->` and `<!-- results:end -->` markers from the latest committed runs.

CLI:

```
mm download                     # BIRD dev
mm run rq1|rq2|rq3|rq4 -c configs/rqX.yaml [--dry-run] [--fixture]
mm report RUN_DIR
mm readme
```

`--dry-run` prints the item count and cost estimate only. `--fixture` runs against the tiny fixture with stub models.

---

## 10. Phases and acceptance criteria

**Phase 0 — Scaffold and fixture.** Layout, config models, tiny fixture DB, download script. *Accept:* tooling passes; the fixture loads through the same loader interface as BIRD. *Baseline:* the repository baseline in Appendix B.1 is in place, including a README stub with the project name, one-line value proposition, Why, and a planned Quickstart; the CI workflow's commands pass locally.

**Phase 1 — RQ1 pipeline.** Context levels, prompt, SQL extraction, EX evaluator. *Accept:* on the fixture, a stub model that returns gold SQL scores 100%, one that returns invalid SQL scores 0%, and a query returning the same rows in a different order counts as correct; a runaway query times out and counts as incorrect.

**Phase 2 — Runner and statistics.** Cache, budget, resume, concurrency, `run.json`, bootstrap and McNemar. *Accept:* rerunning a completed fixture run makes zero model calls; the budget guard refuses a run whose estimate exceeds the cap; statistics functions match hand-computed values on small arrays.

**Phase 3 — RQ2 decoys.** §6. *Accept:* decoy databases are created as copies (originals' checksums unchanged); the gold SQL rewritten to use the decoy table returns a different result on at least 95% of fixture examples; decoy usage detection is unit-tested.

**Phase 4 — RQ3 retrieval.** §7. *Accept:* relevance extraction is unit-tested on fixture gold SQL; metric functions match hand-computed rankings; the embedding cache prevents recomputation.

**Phase 5 — RQ4 and reporting.** §8, §9.3, `mm readme`. *Accept:* the fixture runs of all four RQs produce reports and plots; `mm readme` updates only the marked section.

**Phase 6 — Real runs.** Execute RQ1–RQ4 on a 500-question sample with the configured models, commit results, and write the findings article draft in `docs/findings.md`. *Accept:* every committed result has a `run.json`; the README results table is generated, not hand-written. *README:* README.md satisfies Appendix B.2 and B.3; a CI job runs the Quickstart on a fresh checkout and passes; all example output comes from real runs.

---

## 11. Conventions

Python 3.11+, `mypy --strict`, `ruff`. Everything seeded and versioned; no result without a `run.json`. Databases opened read-only. No network in tests. Results are described as specific to the models, prompts, and date tested.

---

## 12. Open decisions

1. **Budget and models** — which providers and models, and the maximum spend per RQ.
2. **Sample size** — 500 stratified questions versus the full dev set.
3. **Additional datasets** — whether to add an enterprise-style benchmark (e.g. Spider 2.0) later.
4. **BIRD licence compliance** — confirm terms before publishing results.

---

## Appendix A — Cursor prompts

<!-- bootstrap:phase-prompt -->
```
Read SPEC.md. Implement Phase N from §10 only. Satisfy every acceptance criterion for Phase N, write tests first where the spec gives expected outputs, and do not start later phases. Use only the fixture database and stub models. If anything is ambiguous, list the ambiguity and stop.
```

<!-- bootstrap:review-prompt -->
```
Review the Phase N implementation against SPEC.md. For each acceptance criterion in §10, state whether it is met and which test proves it. List every divergence from the spec. Do not fix anything yet.
```

Project rules:

<!-- bootstrap:rules -->
```
- Never call a real model or embedding API in tests; only `mm run` without --fixture does that, behind the budget guard.
- Never modify original databases; decoys are built on copies.
- Every run writes run.json; results without one are invalid.
- Report numbers only from generated metrics files, never typed by hand.
```

---

## Appendix B — Repository baseline and README

### B.1 Repository baseline (Phase 0)

- `README.md` stub (items 1, 4, and a planned Quickstart from B.2), `CHANGELOG.md` (Keep a Changelog format with an `[Unreleased]` section), `LICENSE` (Apache-2.0), `.gitignore`, and `docs/adr/` with a template. The portfolio bootstrap creates these; if the repository was created by hand, create them in Phase 0.
- `pyproject.toml` managed by `uv`, with `ruff` (lint and format) and `mypy --strict` configured there.
- `.pre-commit-config.yaml` running ruff, ruff-format, and basic hygiene hooks (trailing whitespace, end of file, YAML and JSON checks). Pin hook versions to the latest releases at Phase 0.
- `.github/workflows/ci.yml` running lint, type-check, and tests with `uv` on every push and pull request, plus the `web/` build and tests where the project has a UI. Add the CI badge to the README.
- Conventional commit messages, semantic versioning, and a CHANGELOG entry for every release.

### B.2 README requirements (Phase 6)

The README is a deliverable of Phase 6. Sections, in order:

1. `# <Name> — <one-line value proposition>`
2. Badges: CI, licence, PyPI (libraries only)
3. Demo: `![demo](docs/demo.gif)` (placeholder until recorded; see B.3)
4. Why: 2–3 sentences on the problem and who has it
5. Quickstart: one command that works on a fresh machine
6. How it works: Mermaid architecture diagram and a short walkthrough
7. Results / example output: real output from the tool (see B.3)
8. Design decisions: links to `docs/adr/`
9. Roadmap: only things not yet built
10. Licence

Rules:

- Every command in the README must run. A CI job executes the Quickstart on a fresh checkout.
- All example output comes from a real run on the repository's fixtures, never written by hand.
- Keep it under about 150 lines; longer material goes in `docs/`.

### B.3 Demo and results for this project

- **Demo:** Use the headline chart image instead of a GIF: execution accuracy by metadata level, and decoy usage by condition.
- **Results / example output:** The section generated by `mm readme` between the results markers.

The demo is recorded by a person, not generated. For terminal demos, Cursor may write a `docs/demo.tape` script for `vhs`, which records terminal sessions as GIFs; re-record whenever the output changes.

README prompt for Phase 6:

<!-- bootstrap:readme-prompt -->
```
Read SPEC.md, including Appendix B. Write README.md following Appendix B.2 exactly, with the demo and results content from B.3. Take the Quickstart commands from what actually works in this repository, and add a CI job that runs them on a fresh checkout. For "Results / example output", run the tool on the included fixtures and paste the real output; do not invent any output. Leave docs/demo.gif as a placeholder with a TODO. Keep it under 150 lines and move anything longer into docs/.
```
