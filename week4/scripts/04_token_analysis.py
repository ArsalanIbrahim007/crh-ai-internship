import json
import sys
from pathlib import Path

import numpy as np
from transformers import AutoTokenizer


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from config import (
    MODEL_NAME,
    PROCESSED_DATA_DIR,
    RESULTS_DIR,
    SYSTEM_PROMPT,
)


def load_jsonl(path: Path) -> list[dict]:
    records = []

    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()

            if line:
                records.append(json.loads(line))

    return records


def build_training_text(
    tokenizer,
    instruction: str,
    response: str,
) -> str:
    messages = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT,
        },
        {
            "role": "user",
            "content": instruction,
        },
        {
            "role": "assistant",
            "content": response,
        },
    ]

    return tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=False,
    )


def truncation_stats(
    lengths: list[int],
    threshold: int,
) -> dict:
    count = sum(length > threshold for length in lengths)

    percentage = (
        100 * count / len(lengths)
        if lengths
        else 0
    )

    return {
        "threshold": threshold,
        "truncated_examples": count,
        "truncated_percentage": round(percentage, 2),
    }


def main() -> None:
    print("=" * 70)
    print("WEEK 4 — TOKEN LENGTH ANALYSIS")
    print("=" * 70)

    train_path = PROCESSED_DATA_DIR / "train.jsonl"
    val_path = PROCESSED_DATA_DIR / "validation.jsonl"
    test_path = PROCESSED_DATA_DIR / "test.jsonl"

    for path in (train_path, val_path, test_path):
        if not path.exists():
            raise FileNotFoundError(
                f"Missing dataset file: {path}"
            )

    print("\n[1/5] Loading tokenizer...")

    tokenizer = AutoTokenizer.from_pretrained(
        MODEL_NAME,
        use_fast=True,
    )

    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    print("[2/5] Loading curated datasets...")

    train_records = load_jsonl(train_path)
    val_records = load_jsonl(val_path)
    test_records = load_jsonl(test_path)

    all_records = (
        train_records
        + val_records
        + test_records
    )

    print(f"Train examples:      {len(train_records):,}")
    print(f"Validation examples: {len(val_records):,}")
    print(f"Test examples:       {len(test_records):,}")
    print(f"Total examples:      {len(all_records):,}")

    if len(all_records) == 0:
        raise RuntimeError("No dataset records found.")

    print("\n[3/5] Formatting examples with Mistral chat template...")

    texts = []

    for record in all_records:
        text = build_training_text(
            tokenizer,
            record["instruction"],
            record["response"],
        )

        texts.append(text)

    print("[4/5] Tokenizing all examples...")

    lengths = []

    for index, text in enumerate(texts, start=1):
        tokens = tokenizer(
            text,
            add_special_tokens=False,
            truncation=False,
        )

        lengths.append(
            len(tokens["input_ids"])
        )

        if index % 500 == 0:
            print(
                f"  Processed {index:,}/{len(texts):,}"
            )

    lengths_array = np.array(lengths)

    stats = {
        "model": MODEL_NAME,
        "total_examples": len(lengths),
        "minimum": int(np.min(lengths_array)),
        "mean": round(float(np.mean(lengths_array)), 2),
        "median": round(float(np.median(lengths_array)), 2),
        "p90": round(
            float(np.percentile(lengths_array, 90)),
            2,
        ),
        "p95": round(
            float(np.percentile(lengths_array, 95)),
            2,
        ),
        "p99": round(
            float(np.percentile(lengths_array, 99)),
            2,
        ),
        "maximum": int(np.max(lengths_array)),
        "thresholds": {
            "128": truncation_stats(
                lengths,
                128,
            ),
            "256": truncation_stats(
                lengths,
                256,
            ),
            "512": truncation_stats(
                lengths,
                512,
            ),
        },
    }

    print("\n[5/5] Saving analysis...")

    output_path = (
        RESULTS_DIR / "token_analysis.json"
    )

    with output_path.open(
        "w",
        encoding="utf-8",
    ) as f:
        json.dump(
            stats,
            f,
            indent=2,
        )

    print()
    print("=" * 70)
    print("TOKEN LENGTH RESULTS")
    print("=" * 70)

    print(f"Examples: {stats['total_examples']:,}")
    print(f"Minimum:  {stats['minimum']}")
    print(f"Mean:     {stats['mean']}")
    print(f"Median:   {stats['median']}")
    print(f"P90:      {stats['p90']}")
    print(f"P95:      {stats['p95']}")
    print(f"P99:      {stats['p99']}")
    print(f"Maximum:  {stats['maximum']}")

    print()
    print("TRUNCATION RISK")
    print("-" * 70)

    for threshold in (128, 256, 512):
        data = stats["thresholds"][str(threshold)]

        print(
            f"{threshold:>3} tokens: "
            f"{data['truncated_examples']:>4} examples "
            f"({data['truncated_percentage']:.2f}%)"
        )

    print()
    print(f"Saved to:")
    print(f"  {output_path}")

    print()
    print("=" * 70)
    print("RESULT: TOKEN ANALYSIS PASSED")
    print("=" * 70)


if __name__ == "__main__":
    main()