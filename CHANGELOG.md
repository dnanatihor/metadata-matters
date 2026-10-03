# Changelog

All notable changes to this project are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project uses [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- Repository created from SPEC.md.
- Phase 0 scaffold: BIRD-layout loader, tiny fixture, config models, BIRD download script, and CI.
- Phase 1 text-to-SQL context levels, prompt, SQL extraction, and execution accuracy.
- Phase 2 runner: response cache, budget guard, resume, and bootstrap and McNemar statistics.
- Phase 3 decoy databases built on copies, with usage detection.
- Phase 4 schema retrieval: relevance, ranking metrics, and an embedding cache.
- Phase 5 reports and plots for fixture runs of RQ1-RQ4, and `mm readme`.
- Phase 6 fixture runs of RQ1-RQ4, generated README results, and `docs/findings.md`.
- Live BIRD-dev runs (500 questions) for RQ1-RQ4 with `gpt-4.1-mini` and local sentence-transformers.
- Recorded `docs/demo.gif` from the live RQ1 and RQ2 headline charts.
- Live runs call `gpt-4.1-mini` and local sentence-transformers when `--fixture` is omitted.
