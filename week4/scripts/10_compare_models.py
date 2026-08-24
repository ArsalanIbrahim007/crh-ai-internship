import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RESULTS_DIR = ROOT / "results"

BASELINE_FILE = RESULTS_DIR / "baseline_metrics.json"
FINETUNED_FILE = RESULTS_DIR / "finetuned_metrics.json"

OUTPUT_JSON = RESULTS_DIR / "baseline_vs_finetuned.json"
OUTPUT_MD = RESULTS_DIR / "baseline_vs_finetuned.md"


def load_json(path):
    if not path.exists():
        raise FileNotFoundError(f"Missing required file: {path}")

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def percentage_change(old, new):
    if old == 0:
        return None
    return ((new - old) / old) * 100


def lower_is_better_change(old, new):
    if old == 0:
        return None
    return ((old - new) / old) * 100


def fmt(value, decimals=4):
    if value is None:
        return "N/A"
    return f"{value:.{decimals}f}"


def fmt_pct(value):
    if value is None:
        return "N/A"

    sign = "+" if value >= 0 else ""
    return f"{sign}{value:.2f}%"


print("=" * 72)
print("WEEK 4 — BASELINE VS FINE-TUNED COMPARISON")
print("=" * 72)

baseline_raw = load_json(BASELINE_FILE)
finetuned_raw = load_json(FINETUNED_FILE)

print(f"Baseline file:   {BASELINE_FILE}")
print(f"Fine-tuned file: {FINETUNED_FILE}")


# ======================================================================
# NORMALIZE BOTH FILE FORMATS
# ======================================================================

baseline = {
    "semantic_similarity": float(
        baseline_raw["quality_metrics"]["mean_semantic_similarity"]
    ),
    "token_f1": float(
        baseline_raw["quality_metrics"]["mean_token_f1"]
    ),
    "rouge_l_f1": float(
        baseline_raw["quality_metrics"]["mean_rouge_l_f1"]
    ),
    "mean_generated_tokens": float(
        baseline_raw["generation_metrics"]["mean_generated_tokens"]
    ),
    "mean_latency_seconds": float(
        baseline_raw["generation_metrics"]["mean_latency_seconds"]
    ),
    "median_latency_seconds": float(
        baseline_raw["generation_metrics"]["median_latency_seconds"]
    ),
    "p95_latency_seconds": float(
        baseline_raw["generation_metrics"]["p95_latency_seconds"]
    ),
    "empty_responses": int(
        baseline_raw["generation_metrics"]["empty_responses"]
    ),
}

finetuned = {
    "semantic_similarity": float(
        finetuned_raw["semantic_similarity"]
    ),
    "token_f1": float(
        finetuned_raw["token_f1"]
    ),
    "rouge_l_f1": float(
        finetuned_raw["rouge_l_f1"]
    ),
    "mean_generated_tokens": float(
        finetuned_raw["mean_generated_tokens"]
    ),
    "mean_latency_seconds": float(
        finetuned_raw["mean_latency_seconds"]
    ),
    "median_latency_seconds": float(
        finetuned_raw["median_latency_seconds"]
    ),
    "p95_latency_seconds": float(
        finetuned_raw["p95_latency_seconds"]
    ),
    "empty_responses": int(
        finetuned_raw["empty_responses"]
    ),
}


# ======================================================================
# VALIDATION
# ======================================================================

baseline_test_examples = int(baseline_raw["test_examples"])
finetuned_test_examples = int(finetuned_raw["test_examples"])

if baseline_test_examples != finetuned_test_examples:
    raise RuntimeError(
        f"Test set mismatch: baseline={baseline_test_examples}, "
        f"finetuned={finetuned_test_examples}"
    )

print(f"Test examples:    {baseline_test_examples}")


comparison = {
    "test_examples": baseline_test_examples,
    "quality": {},
    "generation": {},
}


# ======================================================================
# QUALITY METRICS
# Higher is better
# ======================================================================

quality_metrics = {
    "semantic_similarity": "Semantic similarity",
    "token_f1": "Token F1",
    "rouge_l_f1": "ROUGE-L F1",
}

for key, label in quality_metrics.items():
    old = baseline[key]
    new = finetuned[key]

    comparison["quality"][key] = {
        "label": label,
        "baseline": old,
        "finetuned": new,
        "absolute_change": new - old,
        "percentage_change": percentage_change(old, new),
        "better_model": (
            "finetuned"
            if new > old
            else "baseline"
            if old > new
            else "tie"
        ),
    }


# ======================================================================
# LATENCY METRICS
# Lower is better
# ======================================================================

latency_metrics = {
    "mean_latency_seconds": "Mean latency",
    "median_latency_seconds": "Median latency",
    "p95_latency_seconds": "P95 latency",
}

for key, label in latency_metrics.items():
    old = baseline[key]
    new = finetuned[key]

    comparison["generation"][key] = {
        "label": label,
        "baseline": old,
        "finetuned": new,
        "absolute_change": new - old,
        "speed_change_percent": lower_is_better_change(old, new),
        "better_model": (
            "finetuned"
            if new < old
            else "baseline"
            if old < new
            else "tie"
        ),
    }


# ======================================================================
# OUTPUT LENGTH + EMPTY RESPONSES
# ======================================================================

baseline_tokens = baseline["mean_generated_tokens"]
finetuned_tokens = finetuned["mean_generated_tokens"]

comparison["generation"]["mean_generated_tokens"] = {
    "label": "Mean generated tokens",
    "baseline": baseline_tokens,
    "finetuned": finetuned_tokens,
    "absolute_change": finetuned_tokens - baseline_tokens,
    "percentage_change": percentage_change(
        baseline_tokens,
        finetuned_tokens,
    ),
}

baseline_empty = baseline["empty_responses"]
finetuned_empty = finetuned["empty_responses"]

comparison["generation"]["empty_responses"] = {
    "label": "Empty responses",
    "baseline": baseline_empty,
    "finetuned": finetuned_empty,
    "absolute_change": finetuned_empty - baseline_empty,
}


# ======================================================================
# SUMMARY
# ======================================================================

quality_wins = sum(
    1
    for item in comparison["quality"].values()
    if item["better_model"] == "finetuned"
)

quality_losses = sum(
    1
    for item in comparison["quality"].values()
    if item["better_model"] == "baseline"
)

quality_ties = sum(
    1
    for item in comparison["quality"].values()
    if item["better_model"] == "tie"
)

if quality_wins == len(quality_metrics):
    quality_summary = (
        "The fine-tuned model improved on all measured quality metrics."
    )
elif quality_wins > quality_losses:
    quality_summary = (
        "The fine-tuned model improved on the majority of measured "
        "quality metrics."
    )
elif quality_losses > quality_wins:
    quality_summary = (
        "The fine-tuned model performed worse on the majority of "
        "measured quality metrics."
    )
else:
    quality_summary = (
        "The measured quality metrics produced a mixed result."
    )


comparison["summary"] = {
    "quality_metrics_improved": quality_wins,
    "quality_metrics_worse": quality_losses,
    "quality_metrics_tied": quality_ties,
    "quality_metrics_total": len(quality_metrics),
    "statement": quality_summary,
    "important_note": (
        "Semantic similarity, Token F1, and ROUGE-L are automatic "
        "reference-based metrics and should not be described as "
        "classification accuracy."
    ),
}


# ======================================================================
# SAVE JSON
# ======================================================================

with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
    json.dump(
        comparison,
        f,
        indent=2,
        ensure_ascii=False,
    )


# ======================================================================
# SAVE MARKDOWN
# ======================================================================

lines = []

lines.append("# Baseline vs Fine-Tuned Benchmark")
lines.append("")
lines.append(
    "Both models were evaluated on the same held-out test set "
    "using deterministic generation settings."
)
lines.append("")

lines.append("## Quality Metrics")
lines.append("")
lines.append(
    "| Metric | Baseline | Fine-Tuned | Absolute Change | % Change |"
)
lines.append(
    "|---|---:|---:|---:|---:|"
)

for key in quality_metrics:
    item = comparison["quality"][key]

    lines.append(
        f"| {item['label']} "
        f"| {fmt(item['baseline'])} "
        f"| {fmt(item['finetuned'])} "
        f"| {fmt(item['absolute_change'])} "
        f"| {fmt_pct(item['percentage_change'])} |"
    )


lines.append("")
lines.append("## Generation Metrics")
lines.append("")
lines.append(
    "| Metric | Baseline | Fine-Tuned | Change |"
)
lines.append(
    "|---|---:|---:|---:|"
)

for key in latency_metrics:
    item = comparison["generation"][key]

    lines.append(
        f"| {item['label']} "
        f"| {fmt(item['baseline'], 2)}s "
        f"| {fmt(item['finetuned'], 2)}s "
        f"| {fmt_pct(item['speed_change_percent'])} |"
    )


tokens = comparison["generation"]["mean_generated_tokens"]

lines.append(
    f"| Mean generated tokens "
    f"| {fmt(tokens['baseline'], 2)} "
    f"| {fmt(tokens['finetuned'], 2)} "
    f"| {fmt_pct(tokens['percentage_change'])} |"
)


empty = comparison["generation"]["empty_responses"]

lines.append(
    f"| Empty responses "
    f"| {empty['baseline']} "
    f"| {empty['finetuned']} "
    f"| {empty['absolute_change']:+d} |"
)


lines.append("")
lines.append("## Interpretation")
lines.append("")
lines.append(quality_summary)
lines.append("")
lines.append(
    "Semantic similarity, Token F1, and ROUGE-L are automatic "
    "reference-based quality metrics. They should not be reported "
    "as model accuracy."
)


with open(OUTPUT_MD, "w", encoding="utf-8") as f:
    f.write("\n".join(lines))


# ======================================================================
# PRINT RESULTS
# ======================================================================

print("\n" + "=" * 72)
print("QUALITY COMPARISON")
print("=" * 72)

for key in quality_metrics:
    item = comparison["quality"][key]

    print(
        f"{item['label']:<22}"
        f" baseline={item['baseline']:.4f}"
        f" | finetuned={item['finetuned']:.4f}"
        f" | change={item['absolute_change']:+.4f}"
        f" ({fmt_pct(item['percentage_change'])})"
    )


print("\n" + "=" * 72)
print("GENERATION COMPARISON")
print("=" * 72)

for key in latency_metrics:
    item = comparison["generation"][key]

    print(
        f"{item['label']:<22}"
        f" baseline={item['baseline']:.2f}s"
        f" | finetuned={item['finetuned']:.2f}s"
        f" | speed change={fmt_pct(item['speed_change_percent'])}"
    )


print(
    f"{'Mean generated tokens':<22}"
    f" baseline={baseline_tokens:.2f}"
    f" | finetuned={finetuned_tokens:.2f}"
)

print(
    f"{'Empty responses':<22}"
    f" baseline={baseline_empty}"
    f" | finetuned={finetuned_empty}"
)


print("\nInterpretation:")
print(f"  {quality_summary}")

print("\nFiles:")
print(f"  {OUTPUT_JSON}")
print(f"  {OUTPUT_MD}")

print("\n" + "=" * 72)
print("RESULT: MODEL COMPARISON PASSED")
print("=" * 72)