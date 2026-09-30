# RQ2 decoys

## Method

Fixture run with stub models. Numbers below are read from metrics.csv.

## Results

| label | condition | estimate | low | high | n | metric |
| --- | --- | --- | --- | --- | --- | --- |
| D0 | D0 | 1.0 | 1.0 | 1.0 | 12 | ex |
| D1 | D1 | 1.0 | 1.0 | 1.0 | 12 | ex |
| D2 | D2 | 1.0 | 1.0 | 1.0 | 12 | ex |
| D0 | D0 | 0.0 | 0.0 | 0.0 | 12 | decoy_usage |
| D1 | D1 | 0.0 | 0.0 | 0.0 | 12 | decoy_usage |
| D2 | D2 | 0.0 | 0.0 | 0.0 | 12 | decoy_usage |

## Plots

![metrics](plots/metrics.png)

## Caveats

- Decoy tables exist only on copies. Checksums are in decoys.json.
