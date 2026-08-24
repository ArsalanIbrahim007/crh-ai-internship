# Baseline vs Fine-Tuned Benchmark

Both models were evaluated on the same held-out test set using deterministic generation settings.

## Quality Metrics

| Metric | Baseline | Fine-Tuned | Absolute Change | % Change |
|---|---:|---:|---:|---:|
| Semantic similarity | 0.7307 | 0.8167 | 0.0861 | +11.78% |
| Token F1 | 0.3970 | 0.4414 | 0.0444 | +11.19% |
| ROUGE-L F1 | 0.2424 | 0.3469 | 0.1044 | +43.08% |

## Generation Metrics

| Metric | Baseline | Fine-Tuned | Change |
|---|---:|---:|---:|
| Mean latency | 5.44s | 4.81s | +11.58% |
| Median latency | 5.70s | 4.70s | +17.50% |
| P95 latency | 6.07s | 6.63s | -9.32% |
| Mean generated tokens | 120.27 | 94.72 | -21.24% |
| Empty responses | 0 | 0 | +0 |

## Interpretation

The fine-tuned model improved on all measured quality metrics.

Semantic similarity, Token F1, and ROUGE-L are automatic reference-based quality metrics. They should not be reported as model accuracy.