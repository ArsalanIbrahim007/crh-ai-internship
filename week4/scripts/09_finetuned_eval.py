import gc
import json
import time
from pathlib import Path
from statistics import median

import numpy as np
import torch

from peft import PeftModel
from rouge_score import rouge_scorer
from sentence_transformers import SentenceTransformer
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
)


# ======================================================================
# CONFIG
# ======================================================================

ROOT = Path(__file__).resolve().parents[1]

MODEL_NAME = "mistralai/Mistral-7B-Instruct-v0.3"

TEST_FILE = ROOT / "data" / "processed" / "test.jsonl"

ADAPTER_DIR = (
    ROOT
    / "outputs"
    / "mistral7b-customer-support-r8"
    / "final_adapter"
)

RESULTS_DIR = ROOT / "results"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

PREDICTIONS_FILE = RESULTS_DIR / "finetuned_predictions.jsonl"
SCORED_FILE = RESULTS_DIR / "finetuned_predictions_scored.jsonl"
METRICS_FILE = RESULTS_DIR / "finetuned_metrics.json"

MAX_NEW_TOKENS = 128

EMBEDDING_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

SYSTEM_PROMPT = (
    "You are a helpful customer support assistant. "
    "Answer the customer's request clearly, politely, and concisely. "
    "Do not invent company policies, prices, order details, or actions "
    "that are not provided in the conversation."
)


# ======================================================================
# HELPERS
# ======================================================================

def load_jsonl(path):
    rows = []

    with open(path, "r", encoding="utf-8") as f:
        for line_number, line in enumerate(f):
            line = line.strip()

            if not line:
                continue

            row = json.loads(line)

            # Stable ID based on held-out test-set position.
            if "example_id" not in row:
                row["example_id"] = line_number

            rows.append(row)

    return rows


def append_jsonl(path, record):
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
        f.flush()


def token_f1(reference, prediction):
    ref_tokens = reference.lower().split()
    pred_tokens = prediction.lower().split()

    if not ref_tokens and not pred_tokens:
        return 1.0

    if not ref_tokens or not pred_tokens:
        return 0.0

    ref_counts = {}
    pred_counts = {}

    for token in ref_tokens:
        ref_counts[token] = ref_counts.get(token, 0) + 1

    for token in pred_tokens:
        pred_counts[token] = pred_counts.get(token, 0) + 1

    overlap = 0

    for token, ref_count in ref_counts.items():
        overlap += min(ref_count, pred_counts.get(token, 0))

    if overlap == 0:
        return 0.0

    precision = overlap / len(pred_tokens)
    recall = overlap / len(ref_tokens)

    return 2 * precision * recall / (precision + recall)


def percentile(values, q):
    if not values:
        return 0.0

    return float(np.percentile(values, q))


# ======================================================================
# START
# ======================================================================

print("=" * 72)
print("WEEK 4 — FINE-TUNED MODEL BENCHMARK")
print("=" * 72)

if not TEST_FILE.exists():
    raise FileNotFoundError(f"Missing test file: {TEST_FILE}")

if not ADAPTER_DIR.exists():
    raise FileNotFoundError(f"Missing adapter directory: {ADAPTER_DIR}")

tests = load_jsonl(TEST_FILE)

print(f"Model:             {MODEL_NAME}")
print(f"Adapter:           {ADAPTER_DIR}")
print(f"Max new tokens:    {MAX_NEW_TOKENS}")
print(f"Held-out examples: {len(tests)}")

# ======================================================================
# RESUME
# ======================================================================

completed_records = {}

if PREDICTIONS_FILE.exists():
    with open(PREDICTIONS_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()

            if not line:
                continue

            record = json.loads(line)
            completed_records[str(record["example_id"])] = record

print(f"Resuming from {len(completed_records)} completed predictions.")
print(
    f"Remaining predictions: "
    f"{len(tests) - len(completed_records)}"
)


# ======================================================================
# TOKENIZER
# ======================================================================

print("\n[1/5] Loading tokenizer...")

tokenizer = AutoTokenizer.from_pretrained(
    MODEL_NAME,
    use_fast=True,
)

if tokenizer.pad_token is None:
    tokenizer.pad_token = tokenizer.eos_token

tokenizer.padding_side = "left"


# ======================================================================
# BASE MODEL
# ======================================================================

print("[2/5] Loading Mistral-7B in NF4...")

bnb_config = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_quant_type="nf4",
    bnb_4bit_use_double_quant=True,
    bnb_4bit_compute_dtype=torch.float16,
)

model = AutoModelForCausalLM.from_pretrained(
    MODEL_NAME,
    quantization_config=bnb_config,
    torch_dtype=torch.float16,
    device_map={"": 0},
)

model.config.use_cache = True


# ======================================================================
# ADAPTER
# ======================================================================

print("[3/5] Loading trained LoRA adapter...")

model = PeftModel.from_pretrained(
    model,
    str(ADAPTER_DIR),
    is_trainable=False,
)

model.eval()

print("Fine-tuned adapter loaded successfully.")


# ======================================================================
# GENERATION
# ======================================================================

print("\n[4/5] Generating fine-tuned responses...")

run_start = time.perf_counter()

for index, example in enumerate(tests):
    example_id = str(example["example_id"])

    if example_id in completed_records:
        continue

    instruction = example["instruction"]
    reference = example["response"]

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

    prompt = tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True,
    )

    inputs = tokenizer(
        prompt,
        return_tensors="pt",
        add_special_tokens=False,
    )

    inputs = {
        key: value.to(model.device)
        for key, value in inputs.items()
    }

    input_length = inputs["input_ids"].shape[1]

    torch.cuda.synchronize()
    start = time.perf_counter()

    with torch.inference_mode():
        generated = model.generate(
            **inputs,
            max_new_tokens=MAX_NEW_TOKENS,
            do_sample=False,
            num_beams=1,
            pad_token_id=tokenizer.eos_token_id,
            eos_token_id=tokenizer.eos_token_id,
            use_cache=True,
        )

    torch.cuda.synchronize()
    latency = time.perf_counter() - start

    generated_tokens = generated[0][input_length:]

    prediction = tokenizer.decode(
        generated_tokens,
        skip_special_tokens=True,
    ).strip()

    record = {
        "example_id": example["example_id"],
        "instruction": instruction,
        "reference": reference,
        "prediction": prediction,
        "intent": example.get("intent"),
        "category": example.get("category"),
        "latency_seconds": latency,
        "generated_tokens": int(len(generated_tokens)),
    }

    append_jsonl(PREDICTIONS_FILE, record)

    completed_records[example_id] = record

    completed = len(completed_records)

    if completed % 10 == 0 or completed == len(tests):
        elapsed_minutes = (
            time.perf_counter() - run_start
        ) / 60

        print(
            f"  Completed {completed:3d}/{len(tests)}"
            f" | latest {latency:.2f}s"
            f" | run {elapsed_minutes:.1f} min"
        )


print("\nGeneration complete.")


# ======================================================================
# UNLOAD 7B MODEL BEFORE SEMANTIC MODEL
# ======================================================================

del model
gc.collect()

if torch.cuda.is_available():
    torch.cuda.empty_cache()


# ======================================================================
# METRICS
# ======================================================================

print("\n[5/5] Calculating fine-tuned metrics...")

records = []

with open(PREDICTIONS_FILE, "r", encoding="utf-8") as f:
    for line in f:
        line = line.strip()

        if line:
            records.append(json.loads(line))

# Remove accidental duplicates safely.
unique_records = {}

for record in records:
    unique_records[str(record["example_id"])] = record

records = list(unique_records.values())

records.sort(
    key=lambda x: int(x["example_id"])
    if str(x["example_id"]).isdigit()
    else str(x["example_id"])
)

if len(records) != len(tests):
    raise RuntimeError(
        f"Expected {len(tests)} completed predictions, "
        f"found {len(records)}."
    )

references = [r["reference"] for r in records]
predictions = [r["prediction"] for r in records]

print("Loading semantic evaluation model on CPU...")

embedding_model = SentenceTransformer(
    EMBEDDING_MODEL_NAME,
    device="cpu",
)

reference_embeddings = embedding_model.encode(
    references,
    batch_size=32,
    show_progress_bar=True,
    normalize_embeddings=True,
)

prediction_embeddings = embedding_model.encode(
    predictions,
    batch_size=32,
    show_progress_bar=True,
    normalize_embeddings=True,
)

semantic_scores = np.sum(
    reference_embeddings * prediction_embeddings,
    axis=1,
)

rouge = rouge_scorer.RougeScorer(
    ["rougeL"],
    use_stemmer=True,
)

token_f1_scores = []
rouge_l_scores = []

scored_records = []

for i, record in enumerate(records):
    tf1 = token_f1(
        record["reference"],
        record["prediction"],
    )

    rouge_l = rouge.score(
        record["reference"],
        record["prediction"],
    )["rougeL"].fmeasure

    semantic = float(semantic_scores[i])

    token_f1_scores.append(tf1)
    rouge_l_scores.append(rouge_l)

    scored = dict(record)

    scored["semantic_similarity"] = semantic
    scored["token_f1"] = tf1
    scored["rouge_l_f1"] = rouge_l

    scored_records.append(scored)


with open(SCORED_FILE, "w", encoding="utf-8") as f:
    for record in scored_records:
        f.write(
            json.dumps(
                record,
                ensure_ascii=False,
            )
            + "\n"
        )


latencies = [
    float(r["latency_seconds"])
    for r in records
]

generated_token_counts = [
    int(r["generated_tokens"])
    for r in records
]

empty_responses = sum(
    1
    for r in records
    if not r["prediction"].strip()
)

metrics = {
    "model": MODEL_NAME,
    "adapter": str(ADAPTER_DIR),
    "test_examples": len(records),

    "semantic_similarity": float(
        np.mean(semantic_scores)
    ),

    "token_f1": float(
        np.mean(token_f1_scores)
    ),

    "rouge_l_f1": float(
        np.mean(rouge_l_scores)
    ),

    "mean_generated_tokens": float(
        np.mean(generated_token_counts)
    ),

    "mean_latency_seconds": float(
        np.mean(latencies)
    ),

    "median_latency_seconds": float(
        median(latencies)
    ),

    "p95_latency_seconds": percentile(
        latencies,
        95,
    ),

    "empty_responses": int(
        empty_responses
    ),

    "generation_settings": {
        "max_new_tokens": MAX_NEW_TOKENS,
        "do_sample": False,
        "num_beams": 1,
    },
}


with open(
    METRICS_FILE,
    "w",
    encoding="utf-8",
) as f:
    json.dump(
        metrics,
        f,
        indent=2,
        ensure_ascii=False,
    )


# ======================================================================
# RESULTS
# ======================================================================

print("\n" + "=" * 72)
print("FINE-TUNED BENCHMARK RESULTS")
print("=" * 72)

print(f"Test examples:        {metrics['test_examples']}")

print("\nQuality:")
print(
    f"  Semantic similarity: "
    f"{metrics['semantic_similarity']:.4f}"
)

print(
    f"  Token F1:            "
    f"{metrics['token_f1']:.4f}"
)

print(
    f"  ROUGE-L F1:          "
    f"{metrics['rouge_l_f1']:.4f}"
)

print("\nGeneration:")
print(
    f"  Mean tokens:          "
    f"{metrics['mean_generated_tokens']:.2f}"
)

print(
    f"  Mean latency:         "
    f"{metrics['mean_latency_seconds']:.2f}s"
)

print(
    f"  Median latency:       "
    f"{metrics['median_latency_seconds']:.2f}s"
)

print(
    f"  P95 latency:          "
    f"{metrics['p95_latency_seconds']:.2f}s"
)

print(
    f"  Empty responses:      "
    f"{metrics['empty_responses']}"
)

print("\nFiles:")
print(f"  {PREDICTIONS_FILE}")
print(f"  {SCORED_FILE}")
print(f"  {METRICS_FILE}")

print("\n" + "=" * 72)
print("RESULT: FINE-TUNED BENCHMARK PASSED")
print("=" * 72)