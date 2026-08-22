import gc
import json
import re
import sys
import time
from collections import Counter
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F
from sentence_transformers import SentenceTransformer
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
)


# ============================================================
# PROJECT IMPORTS
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from config import (
    MODEL_NAME,
    PROCESSED_DATA_DIR,
    RESULTS_DIR,
    SYSTEM_PROMPT,
    MAX_SEQ_LENGTH,
    GENERATION_MAX_NEW_TOKENS,
    EMBEDDING_MODEL_NAME,
    BNB_4BIT_QUANT_TYPE,
    BNB_4BIT_USE_DOUBLE_QUANT,
    SEED,
)


# ============================================================
# PATHS
# ============================================================

TEST_PATH = (
    PROCESSED_DATA_DIR / "test.jsonl"
)

PREDICTIONS_PATH = (
    RESULTS_DIR / "baseline_predictions.jsonl"
)

METRICS_PATH = (
    RESULTS_DIR / "baseline_metrics.json"
)


# ============================================================
# TEXT HELPERS
# ============================================================

def normalize_text(text: str) -> str:
    text = text.lower().strip()

    text = re.sub(
        r"\s+",
        " ",
        text,
    )

    return text


def word_tokens(text: str) -> list[str]:
    return re.findall(
        r"\b\w+\b",
        normalize_text(text),
    )


# ============================================================
# TOKEN F1
# ============================================================

def token_f1(
    prediction: str,
    reference: str,
) -> float:
    pred_tokens = word_tokens(
        prediction
    )

    ref_tokens = word_tokens(
        reference
    )

    if not pred_tokens and not ref_tokens:
        return 1.0

    if not pred_tokens or not ref_tokens:
        return 0.0

    pred_counter = Counter(
        pred_tokens
    )

    ref_counter = Counter(
        ref_tokens
    )

    common = sum(
        (
            pred_counter
            & ref_counter
        ).values()
    )

    if common == 0:
        return 0.0

    precision = (
        common / len(pred_tokens)
    )

    recall = (
        common / len(ref_tokens)
    )

    return (
        2
        * precision
        * recall
        / (precision + recall)
    )


# ============================================================
# ROUGE-L
# ============================================================

def lcs_length(
    a: list[str],
    b: list[str],
) -> int:
    if len(a) < len(b):
        a, b = b, a

    previous = [
        0
    ] * (len(b) + 1)

    for token_a in a:
        current = [0]

        for j, token_b in enumerate(
            b,
            start=1,
        ):
            if token_a == token_b:
                current.append(
                    previous[j - 1] + 1
                )
            else:
                current.append(
                    max(
                        previous[j],
                        current[j - 1],
                    )
                )

        previous = current

    return previous[-1]


def rouge_l_f1(
    prediction: str,
    reference: str,
) -> float:
    pred_tokens = word_tokens(
        prediction
    )

    ref_tokens = word_tokens(
        reference
    )

    if not pred_tokens and not ref_tokens:
        return 1.0

    if not pred_tokens or not ref_tokens:
        return 0.0

    lcs = lcs_length(
        pred_tokens,
        ref_tokens,
    )

    precision = (
        lcs / len(pred_tokens)
    )

    recall = (
        lcs / len(ref_tokens)
    )

    if precision + recall == 0:
        return 0.0

    return (
        2
        * precision
        * recall
        / (precision + recall)
    )


# ============================================================
# FILE HELPERS
# ============================================================

def load_jsonl(
    path: Path,
) -> list[dict]:
    records = []

    with path.open(
        "r",
        encoding="utf-8",
    ) as f:
        for line in f:
            line = line.strip()

            if line:
                records.append(
                    json.loads(line)
                )

    return records


def append_jsonl(
    path: Path,
    record: dict,
) -> None:
    with path.open(
        "a",
        encoding="utf-8",
    ) as f:
        f.write(
            json.dumps(
                record,
                ensure_ascii=False,
            )
            + "\n"
        )

        # Flush immediately so interruption
        # does not lose completed examples.
        f.flush()


# ============================================================
# GENERATION
# ============================================================

def build_prompt(
    tokenizer,
    instruction: str,
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
    ]

    return tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True,
    )


def generate_response(
    model,
    tokenizer,
    instruction: str,
) -> tuple[str, int, float]:
    prompt = build_prompt(
        tokenizer,
        instruction,
    )

    inputs = tokenizer(
        prompt,
        return_tensors="pt",
        truncation=True,
        max_length=MAX_SEQ_LENGTH,
    )

    inputs = {
        key: value.to("cuda")
        for key, value
        in inputs.items()
    }

    input_length = (
        inputs["input_ids"]
        .shape[1]
    )

    torch.cuda.synchronize()
    start = time.perf_counter()

    with torch.inference_mode():
        outputs = model.generate(
            **inputs,
            max_new_tokens=(
                GENERATION_MAX_NEW_TOKENS
            ),
            do_sample=False,
            num_beams=1,
            pad_token_id=(
                tokenizer.pad_token_id
            ),
            eos_token_id=(
                tokenizer.eos_token_id
            ),
        )

    torch.cuda.synchronize()

    elapsed = (
        time.perf_counter()
        - start
    )

    generated_ids = outputs[
        0,
        input_length:
    ]

    response = tokenizer.decode(
        generated_ids,
        skip_special_tokens=True,
    ).strip()

    generated_tokens = len(
        generated_ids
    )

    return (
        response,
        generated_tokens,
        elapsed,
    )


# ============================================================
# SEMANTIC SIMILARITY
# ============================================================

def calculate_semantic_scores(
    predictions: list[str],
    references: list[str],
) -> list[float]:
    print(
        "\nLoading semantic evaluation model on CPU..."
    )

    embedding_model = (
        SentenceTransformer(
            EMBEDDING_MODEL_NAME,
            device="cpu",
        )
    )

    prediction_embeddings = (
        embedding_model.encode(
            predictions,
            batch_size=32,
            convert_to_tensor=True,
            show_progress_bar=True,
        )
    )

    reference_embeddings = (
        embedding_model.encode(
            references,
            batch_size=32,
            convert_to_tensor=True,
            show_progress_bar=True,
        )
    )

    similarities = (
        F.cosine_similarity(
            prediction_embeddings,
            reference_embeddings,
            dim=1,
        )
        .cpu()
        .numpy()
    )

    return [
        float(value)
        for value in similarities
    ]


# ============================================================
# MAIN
# ============================================================

def main() -> None:
    print("=" * 70)
    print("WEEK 4 — BASELINE MODEL BENCHMARK")
    print("=" * 70)

    print(f"Model: {MODEL_NAME}")
    print(
        f"Sequence length: "
        f"{MAX_SEQ_LENGTH}"
    )
    print(
        f"Max new tokens: "
        f"{GENERATION_MAX_NEW_TOKENS}"
    )

    if not TEST_PATH.exists():
        raise FileNotFoundError(
            TEST_PATH
        )

    test_records = load_jsonl(
        TEST_PATH
    )

    print(
        f"Held-out test examples: "
        f"{len(test_records):,}"
    )

    if len(test_records) != 270:
        print(
            "WARNING: Expected 270 test "
            "examples from dataset curation."
        )

    # --------------------------------------------------------
    # REPRODUCIBILITY
    # --------------------------------------------------------

    torch.manual_seed(SEED)
    torch.cuda.manual_seed_all(
        SEED
    )

    # --------------------------------------------------------
    # RESUME STATE
    # --------------------------------------------------------

    completed = {}

    if PREDICTIONS_PATH.exists():
        existing = load_jsonl(
            PREDICTIONS_PATH
        )

        completed = {
            int(row["example_id"]): row
            for row in existing
        }

        print(
            f"Resuming from "
            f"{len(completed):,} "
            f"completed predictions."
        )

    remaining = (
        len(test_records)
        - len(completed)
    )

    print(
        f"Remaining predictions: "
        f"{remaining:,}"
    )

    # --------------------------------------------------------
    # MODEL
    # --------------------------------------------------------

    if remaining > 0:
        print(
            "\n[1/4] Loading tokenizer..."
        )

        tokenizer = (
            AutoTokenizer
            .from_pretrained(
                MODEL_NAME,
                use_fast=True,
            )
        )

        if tokenizer.pad_token is None:
            tokenizer.pad_token = (
                tokenizer.eos_token
            )

        tokenizer.padding_side = "left"

        print(
            "[2/4] Loading baseline "
            "Mistral-7B in NF4..."
        )

        quant_config = (
            BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_quant_type=(
                    BNB_4BIT_QUANT_TYPE
                ),
                bnb_4bit_use_double_quant=(
                    BNB_4BIT_USE_DOUBLE_QUANT
                ),
                bnb_4bit_compute_dtype=(
                    torch.float16
                ),
            )
        )

        model = (
            AutoModelForCausalLM
            .from_pretrained(
                MODEL_NAME,
                quantization_config=(
                    quant_config
                ),
                device_map={"": 0},
                torch_dtype=torch.float16,
                low_cpu_mem_usage=True,
            )
        )

        model.eval()

        print(
            "\n[3/4] Generating baseline "
            "responses..."
        )

        run_start = (
            time.perf_counter()
        )

        for example_id, record in enumerate(
            test_records
        ):
            if example_id in completed:
                continue

            try:
                (
                    prediction,
                    generated_tokens,
                    latency,
                ) = generate_response(
                    model,
                    tokenizer,
                    record["instruction"],
                )

            except Exception as exc:
                print(
                    f"\nERROR on example "
                    f"{example_id}: {exc}"
                )

                raise

            output_record = {
                "example_id": (
                    example_id
                ),
                "model_type": (
                    "baseline"
                ),
                "model": MODEL_NAME,
                "intent": (
                    record["intent"]
                ),
                "category": (
                    record["category"]
                ),
                "instruction": (
                    record["instruction"]
                ),
                "reference": (
                    record["response"]
                ),
                "prediction": (
                    prediction
                ),
                "generated_tokens": (
                    generated_tokens
                ),
                "latency_seconds": (
                    round(
                        latency,
                        4,
                    )
                ),
            }

            append_jsonl(
                PREDICTIONS_PATH,
                output_record,
            )

            completed[
                example_id
            ] = output_record

            done = len(completed)

            if (
                done % 10 == 0
                or done
                == len(test_records)
            ):
                elapsed = (
                    time.perf_counter()
                    - run_start
                )

                print(
                    f"  Completed "
                    f"{done:>3}/"
                    f"{len(test_records)} "
                    f"| latest "
                    f"{latency:.2f}s "
                    f"| run "
                    f"{elapsed / 60:.1f} min"
                )

        # ----------------------------------------------------
        # UNLOAD 7B MODEL
        # ----------------------------------------------------

        print(
            "\nGeneration complete."
        )

        del model
        del tokenizer

        gc.collect()
        torch.cuda.empty_cache()

    else:
        print(
            "\nAll baseline predictions "
            "already exist."
        )

    # --------------------------------------------------------
    # LOAD COMPLETE RESULTS
    # --------------------------------------------------------

    predictions_data = (
        load_jsonl(
            PREDICTIONS_PATH
        )
    )

    predictions_data = sorted(
        predictions_data,
        key=lambda row: (
            int(row["example_id"])
        ),
    )

    if (
        len(predictions_data)
        != len(test_records)
    ):
        raise RuntimeError(
            "Prediction count does not "
            "match test-set size."
        )

    print(
        "\n[4/4] Calculating "
        "baseline metrics..."
    )

    predictions = [
        row["prediction"]
        for row in predictions_data
    ]

    references = [
        row["reference"]
        for row in predictions_data
    ]

    # --------------------------------------------------------
    # LEXICAL METRICS
    # --------------------------------------------------------

    token_f1_scores = [
        token_f1(
            prediction,
            reference,
        )
        for prediction, reference
        in zip(
            predictions,
            references,
        )
    ]

    rouge_scores = [
        rouge_l_f1(
            prediction,
            reference,
        )
        for prediction, reference
        in zip(
            predictions,
            references,
        )
    ]

    # --------------------------------------------------------
    # SEMANTIC METRIC
    # --------------------------------------------------------

    semantic_scores = (
        calculate_semantic_scores(
            predictions,
            references,
        )
    )

    # --------------------------------------------------------
    # ADD PER-EXAMPLE METRICS
    # --------------------------------------------------------

    enriched_path = (
        RESULTS_DIR
        / "baseline_predictions_scored.jsonl"
    )

    if enriched_path.exists():
        enriched_path.unlink()

    for (
        record,
        lexical_f1,
        rouge_l,
        semantic,
    ) in zip(
        predictions_data,
        token_f1_scores,
        rouge_scores,
        semantic_scores,
    ):
        enriched = dict(
            record
        )

        enriched[
            "token_f1"
        ] = round(
            lexical_f1,
            6,
        )

        enriched[
            "rouge_l_f1"
        ] = round(
            rouge_l,
            6,
        )

        enriched[
            "semantic_similarity"
        ] = round(
            semantic,
            6,
        )

        append_jsonl(
            enriched_path,
            enriched,
        )

    # --------------------------------------------------------
    # AGGREGATE METRICS
    # --------------------------------------------------------

    latencies = np.array(
        [
            row["latency_seconds"]
            for row
            in predictions_data
        ],
        dtype=float,
    )

    generated_token_counts = (
        np.array(
            [
                row[
                    "generated_tokens"
                ]
                for row
                in predictions_data
            ],
            dtype=float,
        )
    )

    empty_predictions = sum(
        1
        for prediction in predictions
        if not prediction.strip()
    )

    metrics = {
        "benchmark": (
            "baseline"
        ),
        "model": MODEL_NAME,
        "test_examples": (
            len(predictions)
        ),
        "generation": {
            "max_new_tokens": (
                GENERATION_MAX_NEW_TOKENS
            ),
            "do_sample": False,
            "num_beams": 1,
        },
        "quality_metrics": {
            "mean_semantic_similarity": (
                round(
                    float(
                        np.mean(
                            semantic_scores
                        )
                    ),
                    6,
                )
            ),
            "mean_token_f1": (
                round(
                    float(
                        np.mean(
                            token_f1_scores
                        )
                    ),
                    6,
                )
            ),
            "mean_rouge_l_f1": (
                round(
                    float(
                        np.mean(
                            rouge_scores
                        )
                    ),
                    6,
                )
            ),
        },
        "generation_metrics": {
            "empty_responses": (
                int(
                    empty_predictions
                )
            ),
            "empty_response_rate": (
                round(
                    empty_predictions
                    / len(predictions),
                    6,
                )
            ),
            "mean_generated_tokens": (
                round(
                    float(
                        np.mean(
                            generated_token_counts
                        )
                    ),
                    2,
                )
            ),
            "mean_latency_seconds": (
                round(
                    float(
                        np.mean(
                            latencies
                        )
                    ),
                    4,
                )
            ),
            "median_latency_seconds": (
                round(
                    float(
                        np.median(
                            latencies
                        )
                    ),
                    4,
                )
            ),
            "p95_latency_seconds": (
                round(
                    float(
                        np.percentile(
                            latencies,
                            95,
                        )
                    ),
                    4,
                )
            ),
        },
    }

    with METRICS_PATH.open(
        "w",
        encoding="utf-8",
    ) as f:
        json.dump(
            metrics,
            f,
            indent=2,
        )

    # --------------------------------------------------------
    # REPORT
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("BASELINE BENCHMARK RESULTS")
    print("=" * 70)

    print(
        f"Test examples:        "
        f"{len(predictions):,}"
    )

    print()
    print("Quality:")
    print(
        f"  Semantic similarity: "
        f"{metrics['quality_metrics']['mean_semantic_similarity']:.4f}"
    )
    print(
        f"  Token F1:            "
        f"{metrics['quality_metrics']['mean_token_f1']:.4f}"
    )
    print(
        f"  ROUGE-L F1:          "
        f"{metrics['quality_metrics']['mean_rouge_l_f1']:.4f}"
    )

    print()
    print("Generation:")
    print(
        f"  Mean tokens:          "
        f"{metrics['generation_metrics']['mean_generated_tokens']:.2f}"
    )
    print(
        f"  Mean latency:         "
        f"{metrics['generation_metrics']['mean_latency_seconds']:.2f}s"
    )
    print(
        f"  Median latency:       "
        f"{metrics['generation_metrics']['median_latency_seconds']:.2f}s"
    )
    print(
        f"  P95 latency:          "
        f"{metrics['generation_metrics']['p95_latency_seconds']:.2f}s"
    )
    print(
        f"  Empty responses:      "
        f"{empty_predictions}"
    )

    print()
    print("Files:")
    print(
        f"  {PREDICTIONS_PATH}"
    )
    print(
        f"  {enriched_path}"
    )
    print(
        f"  {METRICS_PATH}"
    )

    print()
    print("=" * 70)
    print(
        "RESULT: BASELINE BENCHMARK PASSED"
    )
    print("=" * 70)


if __name__ == "__main__":
    main()