# Metadata Matters — Quantify how catalog metadata changes text-to-SQL accuracy

[![CI](https://img.shields.io/badge/CI-workflow-blue)](.github/workflows/ci.yml)
[![Licence](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)

> Under construction. The design and build plan are in [SPEC.md](SPEC.md).

## Why

Text-to-SQL benchmarks score models on bare schemas, while people working from a data catalog choose tables using descriptions, sample values, business hints, and labels such as certified or deprecated. This repository measures whether that metadata changes execution accuracy and schema retrieval, including whether governance labels keep a model off plausible but wrong decoy tables. It is for catalog teams and researchers who need that comparison to be reproducible and testable offline.

## Quickstart

Planned: one command that runs on a fresh machine.

## Licence

Apache-2.0. The BIRD dev set is not included. `scripts/download_bird.py` fetches it into `data/bird/`, which is gitignored. Confirm BIRD's licence at <https://bird-bench.github.io/> before publishing results that use it. Token prices in `configs/prices.yaml` are maintained by hand and must be checked before a paid run.

## Results

<!-- results:start -->
<!-- results:end -->

