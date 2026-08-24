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
from transformers.trainer_utils import get_last_checkpoint
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
    LORA_ALPHA,
    LORA_DROPOUT,
    LORA_TARGET_MODULES,
    LEARNING_RATE,
    PER_DEVICE_TRAIN_BATCH_SIZE,
    GRADIENT_ACCUMULATION_STEPS,
    NUM_TRAIN_EPOCHS,
    WANDB_PROJECT,
    LOGGING_STEPS,
    SAVE_STEPS,
    SAVE_TOTAL_LIMIT,
    WARMUP_RATIO,
    SEED,
)


# ============================================================
# EXPERIMENT SETTINGS
# ============================================================

EXPERIMENT_LORA_R = 16

EXPERIMENT_RUN_NAME = (
    "mistral7b-qlora-r16-lr2e4"
)

EXPERIMENT_OUTPUT_DIR = (
    PROJECT_ROOT
    / "outputs"
    / "mistral7b-customer-support-r16"
)

EXPERIMENT_RESULTS_PATH = (
    RESULTS_DIR
    / "hyperparameter_results.json"
)

MAIN_RESULTS_PATH = (
    RESULTS_DIR
    / "training_results.json"
)


# ============================================================
# DATA PATHS
# ============================================================

TRAIN_PATH = (
    PROCESSED_DATA_DIR
    / "train.jsonl"
)

SYNTHETIC_PATH = (
    PROCESSED_DATA_DIR
    / "synthetic_train.jsonl"
)

VALIDATION_PATH = (
    PROCESSED_DATA_DIR
    / "validation.jsonl"
)


# ============================================================
# HELPERS
# ============================================================

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


def load_json(path: Path) -> dict:
    with path.open(
        "r",
        encoding="utf-8",
    ) as f:
        return json.load(f)


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


def find_resume_checkpoint(
    output_dir: Path,
):
    if not output_dir.exists():
        return None

    try:
        return get_last_checkpoint(
            str(output_dir)
        )
    except Exception:
        return None


# ============================================================
# MAIN
# ============================================================

def main() -> None:
    print("=" * 72)
    print(
        "WEEK 4 — HYPERPARAMETER EXPERIMENT"
    )
    print("=" * 72)

    if not torch.cuda.is_available():
        raise RuntimeError(
            "CUDA is unavailable."
        )

    # --------------------------------------------------------
    # Prevent accidental rerun after successful completion
    # --------------------------------------------------------

    if EXPERIMENT_RESULTS_PATH.exists():
        existing = load_json(
            EXPERIMENT_RESULTS_PATH
        )

        if existing.get(
            "status"
        ) == "complete":
            print()
            print(
                "Hyperparameter experiment is "
                "already complete."
            )

            print(
                f"Results: "
                f"{EXPERIMENT_RESULTS_PATH}"
            )

            print()
            print(
                "No training was repeated."
            )

            return

    set_seed(SEED)

    os.environ["WANDB_PROJECT"] = (
        WANDB_PROJECT
    )

    os.environ["WANDB_LOG_MODEL"] = (
        "false"
    )

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
        f"Main LoRA rank:   8"
    )

    print(
        f"Experiment rank:  "
        f"{EXPERIMENT_LORA_R}"
    )

    print(
        f"Learning rate:    "
        f"{LEARNING_RATE}"
    )

    print(
        "Validation:       end only"
    )

    print(
        f"Checkpoint every: "
        f"{SAVE_STEPS} steps"
    )


    # ========================================================
    # 1. LOAD DATA
    # ========================================================

    print(
        "\n[1/8] Loading datasets..."
    )

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


    # ========================================================
    # 2. TOKENIZER
    # ========================================================

    print(
        "\n[2/8] Loading tokenizer..."
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

    tokenizer.padding_side = "right"


    # ========================================================
    # 3. FORMAT DATA
    # ========================================================

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


    # ========================================================
    # 4. QUANTIZATION
    # ========================================================

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


    # ========================================================
    # 5. MODEL
    # ========================================================

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


    # ========================================================
    # 6. LORA
    # ========================================================

    print(
        "[6/8] Configuring "
        "experimental LoRA..."
    )

    peft_config = LoraConfig(
        r=EXPERIMENT_LORA_R,

        # Intentionally unchanged from
        # the main run so rank is the
        # explicit experimental variable.
        lora_alpha=LORA_ALPHA,

        lora_dropout=LORA_DROPOUT,
        bias="none",
        task_type="CAUSAL_LM",

        target_modules=(
            LORA_TARGET_MODULES
        ),
    )


    # ========================================================
    # 7. TRAINER
    # ========================================================

    print(
        "[7/8] Building SFT trainer..."
    )

    EXPERIMENT_OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    training_args = SFTConfig(
        output_dir=str(
            EXPERIMENT_OUTPUT_DIR
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

        # IMPORTANT:
        # No repeated validation during
        # training. We evaluate once at
        # the end to save time.
        eval_strategy="no",

        # Checkpoints remain enabled
        # for automatic resume.
        save_strategy="steps",
        save_steps=SAVE_STEPS,
        save_total_limit=(
            SAVE_TOTAL_LIMIT
        ),

        # Experiment tracking
        report_to="wandb",
        run_name=(
            EXPERIMENT_RUN_NAME
        ),

        # Reproducibility
        seed=SEED,
        data_seed=SEED,

        # Windows
        dataloader_num_workers=0,

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


    # ========================================================
    # 8. RESUME + TRAIN
    # ========================================================

    print()
    print(
        "[8/8] Checking checkpoints..."
    )

    latest_checkpoint = (
        find_resume_checkpoint(
            EXPERIMENT_OUTPUT_DIR
        )
    )

    if latest_checkpoint:
        print(
            "Resume checkpoint found:"
        )
        print(
            f"  {latest_checkpoint}"
        )
        print(
            "Training will continue from "
            "this checkpoint."
        )
    else:
        print(
            "No checkpoint found."
        )
        print(
            "Starting experiment from "
            "step 0."
        )

    print()
    print(
        "Starting rank-16 QLoRA "
        "experiment..."
    )

    torch.cuda.reset_peak_memory_stats()

    start_time = time.perf_counter()

    train_result = trainer.train(
        resume_from_checkpoint=(
            latest_checkpoint
            if latest_checkpoint
            else None
        )
    )

    elapsed_seconds = (
        time.perf_counter()
        - start_time
    )


    # ========================================================
    # FINAL VALIDATION
    # ========================================================

    print()
    print(
        "Running final validation..."
    )

    eval_metrics = trainer.evaluate()

    peak_vram_gb = round(
        torch.cuda.max_memory_allocated()
        / (1024 ** 3),
        3,
    )


    # ========================================================
    # SAVE EXPERIMENT ADAPTER
    # ========================================================

    final_adapter_dir = (
        EXPERIMENT_OUTPUT_DIR
        / "final_adapter"
    )

    trainer.model.save_pretrained(
        final_adapter_dir
    )

    tokenizer.save_pretrained(
        final_adapter_dir
    )


    # ========================================================
    # COMPARE AGAINST MAIN RANK-8 RUN
    # ========================================================

    main_eval_loss = None
    main_train_loss = None

    if MAIN_RESULTS_PATH.exists():
        main_results = load_json(
            MAIN_RESULTS_PATH
        )

        main_eval_loss = (
            main_results
            .get(
                "eval_metrics",
                {},
            )
            .get(
                "eval_loss"
            )
        )

        main_train_loss = (
            main_results
            .get(
                "train_metrics",
                {},
            )
            .get(
                "train_loss"
            )
        )

    experiment_eval_loss = (
        eval_metrics.get(
            "eval_loss"
        )
    )

    experiment_train_loss = (
        train_result.metrics.get(
            "train_loss"
        )
    )

    if (
        main_eval_loss is not None
        and experiment_eval_loss is not None
    ):
        if experiment_eval_loss < main_eval_loss:
            validation_winner = "rank_16"
        elif experiment_eval_loss > main_eval_loss:
            validation_winner = "rank_8"
        else:
            validation_winner = "tie"
    else:
        validation_winner = "unknown"


    # ========================================================
    # SAVE RESULTS
    # ========================================================

    results = {
        "status": "complete",

        "experiment": (
            "LoRA rank comparison"
        ),

        "base_model": MODEL_NAME,

        "controlled_variable": {
            "name": "lora_r",
            "main_value": 8,
            "experiment_value": (
                EXPERIMENT_LORA_R
            ),
        },

        "fixed_hyperparameters": {
            "learning_rate": LEARNING_RATE,
            "lora_alpha": LORA_ALPHA,
            "lora_dropout": (
                LORA_DROPOUT
            ),
            "lora_targets": (
                LORA_TARGET_MODULES
            ),
            "max_sequence_length": (
                MAX_SEQ_LENGTH
            ),
            "epochs": NUM_TRAIN_EPOCHS,
            "batch_size": (
                PER_DEVICE_TRAIN_BATCH_SIZE
            ),
            "gradient_accumulation_steps": (
                GRADIENT_ACCUMULATION_STEPS
            ),
            "seed": SEED,
        },

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

        "experiment_trainable_parameters": (
            trainable
        ),

        "experiment_total_parameters": (
            total
        ),

        "train_runtime_seconds": round(
            elapsed_seconds,
            2,
        ),

        "train_runtime_minutes": round(
            elapsed_seconds / 60,
            2,
        ),

        "peak_allocated_vram_gb": (
            peak_vram_gb
        ),

        "main_rank_8": {
            "train_loss": (
                main_train_loss
            ),
            "eval_loss": (
                main_eval_loss
            ),
        },

        "experiment_rank_16": {
            "train_loss": (
                experiment_train_loss
            ),
            "eval_loss": (
                experiment_eval_loss
            ),
        },

        "validation_winner": (
            validation_winner
        ),

        "selection_rule": (
            "Lower validation loss wins. "
            "The held-out test set is not "
            "used for hyperparameter "
            "selection."
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

        "resume_checkpoint_used": (
            latest_checkpoint
        ),
    }

    with EXPERIMENT_RESULTS_PATH.open(
        "w",
        encoding="utf-8",
    ) as f:
        json.dump(
            results,
            f,
            indent=2,
            default=str,
        )


    # ========================================================
    # OUTPUT
    # ========================================================

    print()
    print("=" * 72)
    print(
        "HYPERPARAMETER EXPERIMENT COMPLETE"
    )
    print("=" * 72)

    print(
        f"Experiment:       "
        f"LoRA rank 8 vs 16"
    )

    print(
        f"Runtime:          "
        f"{elapsed_seconds / 60:.2f} min"
    )

    print(
        f"Peak VRAM:        "
        f"{peak_vram_gb:.3f} GB"
    )

    print()

    print(
        f"Rank 8 eval loss: "
        f"{main_eval_loss}"
    )

    print(
        f"Rank 16 eval loss:"
        f" {experiment_eval_loss}"
    )

    print()

    print(
        f"Validation winner:"
        f" {validation_winner}"
    )

    print()

    print(
        "IMPORTANT:"
    )

    print(
        "  Selection used validation "
        "loss only."
    )

    print(
        "  The held-out test set was "
        "not used."
    )

    print()

    print(
        "Rank-16 adapter:"
    )

    print(
        f"  {final_adapter_dir}"
    )

    print()

    print(
        "Results:"
    )

    print(
        f"  {EXPERIMENT_RESULTS_PATH}"
    )

    print()

    print("=" * 72)
    print(
        "RESULT: HYPERPARAMETER "
        "EXPERIMENT PASSED"
    )
    print("=" * 72)

    del trainer
    del model

    gc.collect()
    torch.cuda.empty_cache()


if __name__ == "__main__":
    main()