import gc
import json
import os
import sys
import time
from pathlib import Path

import torch
from datasets import Dataset
from peft import (
    LoraConfig,
    prepare_model_for_kbit_training,
)
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
    set_seed,
)
from trl import SFTConfig, SFTTrainer


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
    BNB_4BIT_QUANT_TYPE,
    BNB_4BIT_USE_DOUBLE_QUANT,
    LORA_R,
    LORA_ALPHA,
    LORA_DROPOUT,
    LORA_TARGET_MODULES,
    LEARNING_RATE,
    PER_DEVICE_TRAIN_BATCH_SIZE,
    GRADIENT_ACCUMULATION_STEPS,
    NUM_TRAIN_EPOCHS,
    TRAIN_OUTPUT_DIR,
    WANDB_PROJECT,
    MAIN_RUN_NAME,
    LOGGING_STEPS,
    EVAL_STEPS,
    SAVE_STEPS,
    SAVE_TOTAL_LIMIT,
    WARMUP_RATIO,
    SEED,
)


TRAIN_PATH = (
    PROCESSED_DATA_DIR / "train.jsonl"
)

SYNTHETIC_PATH = (
    PROCESSED_DATA_DIR / "synthetic_train.jsonl"
)

VALIDATION_PATH = (
    PROCESSED_DATA_DIR / "validation.jsonl"
)

TRAINING_RESULTS_PATH = (
    RESULTS_DIR / "training_results.json"
)


def load_jsonl(path: Path) -> list[dict]:
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


def build_text(
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


def prepare_dataset(
    records: list[dict],
    tokenizer,
) -> Dataset:
    rows = []

    for record in records:
        text = build_text(
            tokenizer,
            record["instruction"],
            record["response"],
        )

        rows.append(
            {
                "text": text,
            }
        )

    return Dataset.from_list(rows)


def main() -> None:
    print("=" * 72)
    print("WEEK 4 — MAIN MISTRAL-7B QLORA TRAINING")
    print("=" * 72)

    if not torch.cuda.is_available():
        raise RuntimeError(
            "CUDA is unavailable."
        )

    set_seed(SEED)

    os.environ["WANDB_PROJECT"] = (
        WANDB_PROJECT
    )

    # Avoid uploading large checkpoints to W&B.
    # Metrics and experiment configuration are enough.
    os.environ["WANDB_LOG_MODEL"] = "false"

    print(
        f"GPU:              "
        f"{torch.cuda.get_device_name(0)}"
    )

    print(
        f"Base model:       "
        f"{MODEL_NAME}"
    )

    print(
        f"Sequence length:  "
        f"{MAX_SEQ_LENGTH}"
    )

    print(
        f"LoRA rank:        "
        f"{LORA_R}"
    )

    print(
        f"Learning rate:    "
        f"{LEARNING_RATE}"
    )

    # --------------------------------------------------------
    # 1. LOAD DATA
    # --------------------------------------------------------

    print("\n[1/8] Loading datasets...")

    real_train = load_jsonl(
        TRAIN_PATH
    )

    synthetic_train = load_jsonl(
        SYNTHETIC_PATH
    )

    validation = load_jsonl(
        VALIDATION_PATH
    )

    combined_train = (
        real_train
        + synthetic_train
    )

    print(
        f"Real train:       "
        f"{len(real_train):,}"
    )

    print(
        f"Synthetic train:  "
        f"{len(synthetic_train):,}"
    )

    print(
        f"Combined train:   "
        f"{len(combined_train):,}"
    )

    print(
        f"Validation:       "
        f"{len(validation):,}"
    )

    if len(real_train) != 2160:
        raise RuntimeError(
            "Expected 2,160 curated "
            "training examples."
        )

    if len(synthetic_train) != 150:
        raise RuntimeError(
            "Expected 150 synthetic "
            "training examples."
        )

    if len(validation) != 270:
        raise RuntimeError(
            "Expected 270 validation "
            "examples."
        )

    # --------------------------------------------------------
    # 2. TOKENIZER
    # --------------------------------------------------------

    print("\n[2/8] Loading tokenizer...")

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

    tokenizer.padding_side = "right"

    # --------------------------------------------------------
    # 3. FORMAT DATA
    # --------------------------------------------------------

    print(
        "[3/8] Formatting instruction "
        "tuning datasets..."
    )

    train_dataset = prepare_dataset(
        combined_train,
        tokenizer,
    )

    eval_dataset = prepare_dataset(
        validation,
        tokenizer,
    )

    print(
        f"Formatted train rows: "
        f"{len(train_dataset):,}"
    )

    print(
        f"Formatted eval rows:  "
        f"{len(eval_dataset):,}"
    )

    # --------------------------------------------------------
    # 4. QUANTIZATION
    # --------------------------------------------------------

    print(
        "[4/8] Creating QLoRA "
        "quantization config..."
    )

    quant_config = BitsAndBytesConfig(
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

    # --------------------------------------------------------
    # 5. MODEL
    # --------------------------------------------------------

    print(
        "[5/8] Loading Mistral-7B "
        "in NF4..."
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

    model.config.use_cache = False

    model = prepare_model_for_kbit_training(
        model,
        use_gradient_checkpointing=True,
        gradient_checkpointing_kwargs={
            "use_reentrant": False,
        },
    )

    # --------------------------------------------------------
    # 6. LORA
    # --------------------------------------------------------

    print(
        "[6/8] Configuring LoRA..."
    )

    peft_config = LoraConfig(
        r=LORA_R,
        lora_alpha=LORA_ALPHA,
        lora_dropout=LORA_DROPOUT,
        bias="none",
        task_type="CAUSAL_LM",
        target_modules=(
            LORA_TARGET_MODULES
        ),
    )

    # --------------------------------------------------------
    # 7. TRAINER
    # --------------------------------------------------------

    print(
        "[7/8] Building SFT trainer..."
    )

    TRAIN_OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    training_args = SFTConfig(
        output_dir=str(
            TRAIN_OUTPUT_DIR
        ),

        # Dataset
        dataset_text_field="text",
        max_length=MAX_SEQ_LENGTH,
        packing=False,

        # Core training
        num_train_epochs=(
            NUM_TRAIN_EPOCHS
        ),
        per_device_train_batch_size=(
            PER_DEVICE_TRAIN_BATCH_SIZE
        ),
        per_device_eval_batch_size=1,
        gradient_accumulation_steps=(
            GRADIENT_ACCUMULATION_STEPS
        ),
        learning_rate=(
            LEARNING_RATE
        ),

        # Precision / memory
        fp16=True,
        bf16=False,
        gradient_checkpointing=True,
        gradient_checkpointing_kwargs={
            "use_reentrant": False,
        },
        optim="paged_adamw_8bit",

        # Scheduler
        lr_scheduler_type="cosine",
        warmup_ratio=WARMUP_RATIO,

        # Logging
        logging_strategy="steps",
        logging_steps=LOGGING_STEPS,
        logging_first_step=True,

        # Validation
        eval_strategy="steps",
        eval_steps=EVAL_STEPS,

        # Checkpoints
        save_strategy="steps",
        save_steps=SAVE_STEPS,
        save_total_limit=SAVE_TOTAL_LIMIT,

        # Experiment tracking
        report_to="wandb",
        run_name=MAIN_RUN_NAME,

        # Reproducibility
        seed=SEED,
        data_seed=SEED,

        # Windows
        dataloader_num_workers=0,

        # Useful metrics
        include_num_input_tokens_seen=True,
    )

    trainer = SFTTrainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=eval_dataset,
        processing_class=tokenizer,
        peft_config=peft_config,
    )

    trainable = sum(
        parameter.numel()
        for parameter
        in trainer.model.parameters()
        if parameter.requires_grad
    )

    total = sum(
        parameter.numel()
        for parameter
        in trainer.model.parameters()
    )

    print()
    print(
        f"Trainable parameters: "
        f"{trainable:,}"
    )

    print(
        f"Total parameters:     "
        f"{total:,}"
    )

    print(
        f"Trainable percentage: "
        f"{100 * trainable / total:.4f}%"
    )

    # --------------------------------------------------------
    # 8. TRAIN
    # --------------------------------------------------------

    print()
    print(
        "[8/8] Starting QLoRA training..."
    )

    torch.cuda.reset_peak_memory_stats()

    start_time = time.perf_counter()

    train_result = trainer.train()

    elapsed_seconds = (
        time.perf_counter()
        - start_time
    )

    # Final validation loss.
    eval_metrics = trainer.evaluate()

    peak_vram_gb = round(
        torch.cuda.max_memory_allocated()
        / (1024 ** 3),
        3,
    )

    # --------------------------------------------------------
    # SAVE FINAL ADAPTER
    # --------------------------------------------------------

    final_adapter_dir = (
        TRAIN_OUTPUT_DIR
        / "final_adapter"
    )

    trainer.model.save_pretrained(
        final_adapter_dir
    )

    tokenizer.save_pretrained(
        final_adapter_dir
    )

    # --------------------------------------------------------
    # SAVE MEASUREMENTS
    # --------------------------------------------------------

    results = {
        "run_name": MAIN_RUN_NAME,
        "base_model": MODEL_NAME,
        "train_examples_real": (
            len(real_train)
        ),
        "train_examples_synthetic": (
            len(synthetic_train)
        ),
        "train_examples_total": (
            len(combined_train)
        ),
        "validation_examples": (
            len(validation)
        ),
        "max_sequence_length": (
            MAX_SEQ_LENGTH
        ),
        "lora_r": LORA_R,
        "lora_alpha": LORA_ALPHA,
        "lora_dropout": (
            LORA_DROPOUT
        ),
        "lora_targets": (
            LORA_TARGET_MODULES
        ),
        "learning_rate": (
            LEARNING_RATE
        ),
        "epochs": (
            NUM_TRAIN_EPOCHS
        ),
        "batch_size": (
            PER_DEVICE_TRAIN_BATCH_SIZE
        ),
        "gradient_accumulation_steps": (
            GRADIENT_ACCUMULATION_STEPS
        ),
        "effective_batch_size": (
            PER_DEVICE_TRAIN_BATCH_SIZE
            * GRADIENT_ACCUMULATION_STEPS
        ),
        "train_runtime_seconds": (
            round(
                elapsed_seconds,
                2,
            )
        ),
        "train_runtime_minutes": (
            round(
                elapsed_seconds / 60,
                2,
            )
        ),
        "peak_allocated_vram_gb": (
            peak_vram_gb
        ),
        "train_metrics": (
            train_result.metrics
        ),
        "eval_metrics": (
            eval_metrics
        ),
        "final_adapter": str(
            final_adapter_dir
        ),
    }

    with TRAINING_RESULTS_PATH.open(
        "w",
        encoding="utf-8",
    ) as f:
        json.dump(
            results,
            f,
            indent=2,
            default=str,
        )

    print()
    print("=" * 72)
    print("MAIN QLORA TRAINING COMPLETE")
    print("=" * 72)

    print(
        f"Runtime:          "
        f"{elapsed_seconds / 60:.2f} min"
    )

    print(
        f"Peak VRAM:        "
        f"{peak_vram_gb:.3f} GB"
    )

    print(
        f"Final train loss: "
        f"{train_result.metrics.get('train_loss')}"
    )

    print(
        f"Final eval loss:  "
        f"{eval_metrics.get('eval_loss')}"
    )

    print()
    print(
        f"Adapter saved:"
    )
    print(
        f"  {final_adapter_dir}"
    )

    print()
    print(
        f"Training results:"
    )
    print(
        f"  {TRAINING_RESULTS_PATH}"
    )

    print()
    print("=" * 72)
    print(
        "RESULT: MAIN QLORA RUN PASSED"
    )
    print("=" * 72)

    del trainer
    del model

    gc.collect()
    torch.cuda.empty_cache()


if __name__ == "__main__":
    main()