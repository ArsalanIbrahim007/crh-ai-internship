import json
import sys
from collections import Counter
from pathlib import Path

import pandas as pd
from datasets import load_dataset


# ============================================================
# PROJECT IMPORTS
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from config import (
    DATASET_NAME,
    PROCESSED_DATA_DIR,
    RESULTS_DIR,
    SEED,
    SAMPLES_PER_INTENT,
    TRAIN_PER_INTENT,
    VAL_PER_INTENT,
    TEST_PER_INTENT,
)


# ============================================================
# HELPERS
# ============================================================

REQUIRED_COLUMNS = {
    "instruction",
    "response",
    "category",
    "intent",
}


def save_jsonl(df: pd.DataFrame, path: Path) -> None:
    with path.open("w", encoding="utf-8") as f:
        for record in df.to_dict(orient="records"):
            f.write(
                json.dumps(
                    record,
                    ensure_ascii=False,
                )
                + "\n"
            )


def clean_text(value) -> str:
    if value is None:
        return ""

    return " ".join(str(value).strip().split())


def distribution(df: pd.DataFrame, column: str) -> dict:
    counts = Counter(df[column].tolist())

    return {
        str(key): int(value)
        for key, value in sorted(counts.items())
    }


def split_balanced_dataset(
    df: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    train_parts = []
    val_parts = []
    test_parts = []

    intents = sorted(df["intent"].unique())

    for index, intent in enumerate(intents):
        intent_df = df[df["intent"] == intent].copy()

        if len(intent_df) < SAMPLES_PER_INTENT:
            raise RuntimeError(
                f"Intent '{intent}' contains only "
                f"{len(intent_df)} usable examples after cleaning, "
                f"but {SAMPLES_PER_INTENT} are required."
            )

        # Deterministic but different shuffle for every intent.
        intent_seed = SEED + index

        intent_df = intent_df.sample(
            n=SAMPLES_PER_INTENT,
            random_state=intent_seed,
            replace=False,
        ).reset_index(drop=True)

        train_end = TRAIN_PER_INTENT
        val_end = train_end + VAL_PER_INTENT
        test_end = val_end + TEST_PER_INTENT

        if test_end != SAMPLES_PER_INTENT:
            raise RuntimeError(
                "Split configuration does not sum to "
                "SAMPLES_PER_INTENT."
            )

        train_parts.append(
            intent_df.iloc[:train_end].copy()
        )

        val_parts.append(
            intent_df.iloc[train_end:val_end].copy()
        )

        test_parts.append(
            intent_df.iloc[val_end:test_end].copy()
        )

    train_df = pd.concat(
        train_parts,
        ignore_index=True,
    )

    val_df = pd.concat(
        val_parts,
        ignore_index=True,
    )

    test_df = pd.concat(
        test_parts,
        ignore_index=True,
    )

    # Shuffle the final datasets so examples are not grouped
    # by intent during training/evaluation.
    train_df = train_df.sample(
        frac=1,
        random_state=SEED,
    ).reset_index(drop=True)

    val_df = val_df.sample(
        frac=1,
        random_state=SEED + 1,
    ).reset_index(drop=True)

    test_df = test_df.sample(
        frac=1,
        random_state=SEED + 2,
    ).reset_index(drop=True)

    return train_df, val_df, test_df


# ============================================================
# MAIN
# ============================================================

def main() -> None:
    print("=" * 70)
    print("WEEK 4 — CUSTOMER SUPPORT DATASET CURATION")
    print("=" * 70)

    print(f"\nSource dataset:")
    print(f"  {DATASET_NAME}")

    # --------------------------------------------------------
    # 1. LOAD
    # --------------------------------------------------------

    print("\n[1/7] Loading source dataset...")

    dataset = load_dataset(
        DATASET_NAME,
        split="train",
    )

    original_rows = len(dataset)
    original_columns = dataset.column_names

    print(f"Rows loaded: {original_rows:,}")
    print(f"Columns:     {original_columns}")

    # --------------------------------------------------------
    # 2. VALIDATE SCHEMA
    # --------------------------------------------------------

    print("\n[2/7] Validating schema...")

    missing_columns = REQUIRED_COLUMNS.difference(
        original_columns
    )

    if missing_columns:
        raise RuntimeError(
            "Dataset schema has changed. "
            f"Missing required columns: {sorted(missing_columns)}"
        )

    print("Schema validation passed.")

    # --------------------------------------------------------
    # 3. CONVERT + CLEAN
    # --------------------------------------------------------

    print("\n[3/7] Cleaning rows...")

    df = dataset.to_pandas()

    # Retain the source fields that actually exist.
    keep_columns = [
        column
        for column in [
            "flags",
            "instruction",
            "category",
            "intent",
            "response",
        ]
        if column in df.columns
    ]

    df = df[keep_columns].copy()

    text_columns = [
        column
        for column in [
            "flags",
            "instruction",
            "category",
            "intent",
            "response",
        ]
        if column in df.columns
    ]

    for column in text_columns:
        df[column] = df[column].map(clean_text)

    rows_before_empty_filter = len(df)

    df = df[
        (df["instruction"] != "")
        & (df["response"] != "")
        & (df["intent"] != "")
        & (df["category"] != "")
    ].copy()

    empty_rows_removed = (
        rows_before_empty_filter - len(df)
    )

    # --------------------------------------------------------
    # 4. REMOVE EXACT DUPLICATES
    # --------------------------------------------------------

    print("[4/7] Removing exact instruction/response duplicates...")

    rows_before_dedup = len(df)

    df = df.drop_duplicates(
        subset=[
            "instruction",
            "response",
        ],
        keep="first",
    ).reset_index(drop=True)

    duplicate_rows_removed = (
        rows_before_dedup - len(df)
    )

    print(
        f"Empty/invalid rows removed: {empty_rows_removed:,}"
    )

    print(
        f"Exact duplicates removed:   {duplicate_rows_removed:,}"
    )

    print(
        f"Usable rows remaining:      {len(df):,}"
    )

    # --------------------------------------------------------
    # 5. INSPECT REAL DISTRIBUTIONS
    # --------------------------------------------------------

    print("\n[5/7] Inspecting source distribution...")

    intents = sorted(df["intent"].unique())
    categories = sorted(df["category"].unique())

    intent_counts = (
        df["intent"]
        .value_counts()
        .sort_index()
    )

    print(f"Detected intents:    {len(intents)}")
    print(f"Detected categories: {len(categories)}")

    print("\nExamples per intent after cleaning:")

    for intent, count in intent_counts.items():
        print(f"  {intent:<32} {count:>5}")

    insufficient = intent_counts[
        intent_counts < SAMPLES_PER_INTENT
    ]

    if not insufficient.empty:
        print("\nERROR: Some intents do not have enough examples:")

        for intent, count in insufficient.items():
            print(
                f"  {intent}: {count} "
                f"(need {SAMPLES_PER_INTENT})"
            )

        raise RuntimeError(
            "Cannot create the requested balanced dataset."
        )

    # --------------------------------------------------------
    # 6. BALANCED SPLIT
    # --------------------------------------------------------

    print("\n[6/7] Creating deterministic balanced splits...")

    train_df, val_df, test_df = split_balanced_dataset(df)

    # Add provenance after split.
    for split_name, split_df in [
        ("train", train_df),
        ("validation", val_df),
        ("test", test_df),
    ]:
        split_df["split"] = split_name
        split_df["source"] = DATASET_NAME

    print(f"Train:      {len(train_df):,}")
    print(f"Validation: {len(val_df):,}")
    print(f"Test:       {len(test_df):,}")

    # --------------------------------------------------------
    # 7. VALIDATE + SAVE
    # --------------------------------------------------------

    print("\n[7/7] Validating and saving outputs...")

    expected_intents = len(intents)

    expected_train = expected_intents * TRAIN_PER_INTENT
    expected_val = expected_intents * VAL_PER_INTENT
    expected_test = expected_intents * TEST_PER_INTENT

    if len(train_df) != expected_train:
        raise RuntimeError(
            f"Train size mismatch: "
            f"{len(train_df)} != {expected_train}"
        )

    if len(val_df) != expected_val:
        raise RuntimeError(
            f"Validation size mismatch: "
            f"{len(val_df)} != {expected_val}"
        )

    if len(test_df) != expected_test:
        raise RuntimeError(
            f"Test size mismatch: "
            f"{len(test_df)} != {expected_test}"
        )

    # Guarantee no instruction/response pair appears across splits.
    def pair_set(frame: pd.DataFrame) -> set:
        return set(
            zip(
                frame["instruction"],
                frame["response"],
            )
        )

    train_pairs = pair_set(train_df)
    val_pairs = pair_set(val_df)
    test_pairs = pair_set(test_df)

    if train_pairs & val_pairs:
        raise RuntimeError(
            "Data leakage detected between train and validation."
        )

    if train_pairs & test_pairs:
        raise RuntimeError(
            "Data leakage detected between train and test."
        )

    if val_pairs & test_pairs:
        raise RuntimeError(
            "Data leakage detected between validation and test."
        )

    train_path = (
        PROCESSED_DATA_DIR / "train.jsonl"
    )

    val_path = (
        PROCESSED_DATA_DIR / "validation.jsonl"
    )

    test_path = (
        PROCESSED_DATA_DIR / "test.jsonl"
    )

    save_jsonl(train_df, train_path)
    save_jsonl(val_df, val_path)
    save_jsonl(test_df, test_path)

    stats = {
        "source_dataset": DATASET_NAME,
        "original_rows": int(original_rows),
        "original_columns": list(original_columns),
        "rows_after_cleaning": int(len(df)),
        "empty_invalid_rows_removed": int(
            empty_rows_removed
        ),
        "exact_duplicates_removed": int(
            duplicate_rows_removed
        ),
        "detected_category_count": int(
            len(categories)
        ),
        "detected_categories": categories,
        "detected_intent_count": int(
            len(intents)
        ),
        "detected_intents": intents,
        "source_intent_distribution": distribution(
            df,
            "intent",
        ),
        "source_category_distribution": distribution(
            df,
            "category",
        ),
        "sampling": {
            "samples_per_intent": SAMPLES_PER_INTENT,
            "train_per_intent": TRAIN_PER_INTENT,
            "validation_per_intent": VAL_PER_INTENT,
            "test_per_intent": TEST_PER_INTENT,
            "seed": SEED,
        },
        "final_sizes": {
            "train": int(len(train_df)),
            "validation": int(len(val_df)),
            "test": int(len(test_df)),
            "total": int(
                len(train_df)
                + len(val_df)
                + len(test_df)
            ),
        },
        "train_intent_distribution": distribution(
            train_df,
            "intent",
        ),
        "validation_intent_distribution": distribution(
            val_df,
            "intent",
        ),
        "test_intent_distribution": distribution(
            test_df,
            "intent",
        ),
        "leakage_check": "passed",
    }

    stats_path = RESULTS_DIR / "dataset_stats.json"

    with stats_path.open(
        "w",
        encoding="utf-8",
    ) as f:
        json.dump(
            stats,
            f,
            indent=2,
            ensure_ascii=False,
        )

    print()
    print("=" * 70)
    print("RESULT: DATASET CURATION PASSED")
    print("=" * 70)

    print(f"Source rows:     {original_rows:,}")
    print(f"Usable rows:     {len(df):,}")
    print(f"Intents:         {len(intents)}")
    print(f"Categories:      {len(categories)}")

    print()
    print("Balanced output:")
    print(f"  Train:         {len(train_df):,}")
    print(f"  Validation:    {len(val_df):,}")
    print(f"  Test:          {len(test_df):,}")

    print()
    print("Leakage:")
    print("  Train vs validation: PASS")
    print("  Train vs test:       PASS")
    print("  Validation vs test:  PASS")

    print()
    print("Files:")
    print(f"  {train_path}")
    print(f"  {val_path}")
    print(f"  {test_path}")
    print(f"  {stats_path}")


if __name__ == "__main__":
    main()