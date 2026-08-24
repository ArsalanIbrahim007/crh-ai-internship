import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

RESULTS_DIR = ROOT / "results"
DATA_DIR = ROOT / "data" / "processed"

MAIN_ADAPTER = (
    ROOT
    / "outputs"
    / "mistral7b-customer-support-r8"
    / "final_adapter"
)

FINAL_ADAPTER = (
    ROOT
    / "outputs"
    / "mistral7b-customer-support-r16"
    / "final_adapter"
)


def load_json(path: Path):
    with path.open(
        "r",
        encoding="utf-8",
    ) as f:
        return json.load(f)


def count_jsonl(path: Path):
    count = 0

    with path.open(
        "r",
        encoding="utf-8",
    ) as f:
        for line in f:
            if line.strip():
                count += 1

    return count


def test_dataset_files_exist():
    assert (
        DATA_DIR / "train.jsonl"
    ).exists()

    assert (
        DATA_DIR / "validation.jsonl"
    ).exists()

    assert (
        DATA_DIR / "test.jsonl"
    ).exists()

    assert (
        DATA_DIR / "synthetic_train.jsonl"
    ).exists()


def test_dataset_sizes():
    assert count_jsonl(
        DATA_DIR / "train.jsonl"
    ) == 2160

    assert count_jsonl(
        DATA_DIR / "validation.jsonl"
    ) == 270

    assert count_jsonl(
        DATA_DIR / "test.jsonl"
    ) == 270

    assert count_jsonl(
        DATA_DIR / "synthetic_train.jsonl"
    ) == 150


def test_main_adapter_exists():
    assert MAIN_ADAPTER.exists()

    assert (
        MAIN_ADAPTER
        / "adapter_config.json"
    ).exists()

    assert (
        MAIN_ADAPTER
        / "adapter_model.safetensors"
    ).exists()


def test_final_adapter_exists():
    assert FINAL_ADAPTER.exists()

    assert (
        FINAL_ADAPTER
        / "adapter_config.json"
    ).exists()

    assert (
        FINAL_ADAPTER
        / "adapter_model.safetensors"
    ).exists()


def test_baseline_metrics_exist():
    path = (
        RESULTS_DIR
        / "baseline_metrics.json"
    )

    assert path.exists()

    data = load_json(path)

    assert data["test_examples"] == 270
    assert "quality_metrics" in data
    assert "generation_metrics" in data


def test_finetuned_metrics_exist():
    path = (
        RESULTS_DIR
        / "finetuned_metrics.json"
    )

    assert path.exists()

    data = load_json(path)

    assert data["test_examples"] == 270
    assert data["semantic_similarity"] > 0
    assert data["token_f1"] > 0
    assert data["rouge_l_f1"] > 0


def test_finetuned_improves_quality():
    baseline = load_json(
        RESULTS_DIR
        / "baseline_metrics.json"
    )

    finetuned = load_json(
        RESULTS_DIR
        / "finetuned_metrics.json"
    )

    baseline_semantic = (
        baseline[
            "quality_metrics"
        ][
            "mean_semantic_similarity"
        ]
    )

    baseline_token_f1 = (
        baseline[
            "quality_metrics"
        ][
            "mean_token_f1"
        ]
    )

    baseline_rouge = (
        baseline[
            "quality_metrics"
        ][
            "mean_rouge_l_f1"
        ]
    )

    assert (
        finetuned[
            "semantic_similarity"
        ]
        > baseline_semantic
    )

    assert (
        finetuned[
            "token_f1"
        ]
        > baseline_token_f1
    )

    assert (
        finetuned[
            "rouge_l_f1"
        ]
        > baseline_rouge
    )


def test_comparison_outputs_exist():
    assert (
        RESULTS_DIR
        / "baseline_vs_finetuned.json"
    ).exists()

    assert (
        RESULTS_DIR
        / "baseline_vs_finetuned.md"
    ).exists()


def test_training_results_exist():
    path = (
        RESULTS_DIR
        / "training_results.json"
    )

    assert path.exists()

    data = load_json(path)

    assert (
        data["max_sequence_length"]
        == 512
    )

    assert data["lora_r"] == 8

    assert (
        data["validation_examples"]
        == 270
    )


def test_hyperparameter_results_exist():
    path = (
        RESULTS_DIR
        / "hyperparameter_results.json"
    )

    assert path.exists()

    data = load_json(path)

    assert data["status"] == "complete"
    assert data["validation_winner"] == "rank_16"


def test_final_rank16_metrics_exist():
    path = (
        RESULTS_DIR
        / "final_rank16_metrics.json"
    )

    assert path.exists()

    data = load_json(path)

    assert data["test_examples"] == 270
    assert data["empty_responses"] == 0
    assert data["semantic_similarity"] > 0
    assert data["token_f1"] > 0
    assert data["rouge_l_f1"] > 0