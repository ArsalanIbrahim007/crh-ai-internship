import gc
import json
import sys
from pathlib import Path

import torch
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
)
from peft import (
    LoraConfig,
    get_peft_model,
    prepare_model_for_kbit_training,
)


# ============================================================
# PROJECT IMPORTS
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from config import (
    MODEL_NAME,
    PROCESSED_DATA_DIR,
    SYSTEM_PROMPT,
    BNB_4BIT_QUANT_TYPE,
    BNB_4BIT_USE_DOUBLE_QUANT,
    LORA_R,
    LORA_ALPHA,
    LORA_DROPOUT,
    LORA_TARGET_MODULES,
    LEARNING_RATE,
    SEED,
)


TEST_SEQUENCE_LENGTH = 512


# ============================================================
# HELPERS
# ============================================================

def gb(num_bytes: int) -> float:
    return round(num_bytes / (1024 ** 3), 3)


def gpu_memory() -> dict:
    free_bytes, total_bytes = torch.cuda.mem_get_info()

    return {
        "allocated_gb": gb(torch.cuda.memory_allocated()),
        "reserved_gb": gb(torch.cuda.memory_reserved()),
        "peak_allocated_gb": gb(
            torch.cuda.max_memory_allocated()
        ),
        "free_gb": gb(free_bytes),
        "total_gb": gb(total_bytes),
    }


def print_gpu_memory(label: str) -> None:
    memory = gpu_memory()

    print()
    print(f"GPU MEMORY — {label}")
    print("-" * 70)
    print(
        f"Allocated:      "
        f"{memory['allocated_gb']} GB"
    )
    print(
        f"Reserved:       "
        f"{memory['reserved_gb']} GB"
    )
    print(
        f"Peak allocated: "
        f"{memory['peak_allocated_gb']} GB"
    )
    print(
        f"Free:           "
        f"{memory['free_gb']} GB"
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


def format_example(
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


def find_longest_example(
    tokenizer,
    records: list[dict],
) -> tuple[dict, str, int]:
    longest_record = None
    longest_text = None
    longest_length = -1

    for record in records:
        text = format_example(
            tokenizer,
            record["instruction"],
            record["response"],
        )

        encoded = tokenizer(
            text,
            add_special_tokens=False,
            truncation=False,
        )

        length = len(
            encoded["input_ids"]
        )

        if length > longest_length:
            longest_length = length
            longest_record = record
            longest_text = text

    return (
        longest_record,
        longest_text,
        longest_length,
    )


# ============================================================
# MAIN
# ============================================================

def main() -> None:
    print("=" * 70)
    print("WEEK 4 — 512-TOKEN QLORA MEMORY TEST")
    print("=" * 70)

    if not torch.cuda.is_available():
        raise RuntimeError(
            "CUDA unavailable."
        )

    torch.manual_seed(SEED)
    torch.cuda.manual_seed_all(SEED)

    gc.collect()
    torch.cuda.empty_cache()
    torch.cuda.reset_peak_memory_stats()

    print(
        f"GPU:          "
        f"{torch.cuda.get_device_name(0)}"
    )
    print(f"Model:        {MODEL_NAME}")
    print(
        f"Test length:  "
        f"{TEST_SEQUENCE_LENGTH}"
    )

    # --------------------------------------------------------
    # 1. TOKENIZER
    # --------------------------------------------------------

    print("\n[1/8] Loading tokenizer...")

    tokenizer = AutoTokenizer.from_pretrained(
        MODEL_NAME,
        use_fast=True,
    )

    if tokenizer.pad_token is None:
        tokenizer.pad_token = (
            tokenizer.eos_token
        )

    tokenizer.padding_side = "right"

    # --------------------------------------------------------
    # 2. FIND LONGEST REAL EXAMPLE
    # --------------------------------------------------------

    print(
        "[2/8] Finding longest curated example..."
    )

    paths = [
        PROCESSED_DATA_DIR / "train.jsonl",
        PROCESSED_DATA_DIR / "validation.jsonl",
        PROCESSED_DATA_DIR / "test.jsonl",
    ]

    records = []

    for path in paths:
        if not path.exists():
            raise FileNotFoundError(path)

        records.extend(
            load_jsonl(path)
        )

    (
        longest_record,
        longest_text,
        original_length,
    ) = find_longest_example(
        tokenizer,
        records,
    )

    print(
        f"Longest real sequence: "
        f"{original_length} tokens"
    )
    print(
        f"Intent: "
        f"{longest_record['intent']}"
    )

    if original_length > TEST_SEQUENCE_LENGTH:
        print(
            f"Sequence will be truncated "
            f"to {TEST_SEQUENCE_LENGTH}."
        )
    else:
        print(
            "Sequence fits inside the "
            "512-token test."
        )

    # --------------------------------------------------------
    # 3. QUANTIZATION
    # --------------------------------------------------------

    print(
        "[3/8] Creating NF4 configuration..."
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
    # 4. LOAD MODEL
    # --------------------------------------------------------

    print(
        "[4/8] Loading Mistral-7B "
        "in 4-bit..."
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

    print_gpu_memory(
        "BASE MODEL LOADED"
    )

    # --------------------------------------------------------
    # 5. PREPARE + LORA
    # --------------------------------------------------------

    print(
        "\n[5/8] Preparing k-bit model "
        "and attaching LoRA..."
    )

    model = prepare_model_for_kbit_training(
        model,
        use_gradient_checkpointing=True,
        gradient_checkpointing_kwargs={
            "use_reentrant": False
        },
    )

    lora_config = LoraConfig(
        r=LORA_R,
        lora_alpha=LORA_ALPHA,
        lora_dropout=LORA_DROPOUT,
        bias="none",
        task_type="CAUSAL_LM",
        target_modules=(
            LORA_TARGET_MODULES
        ),
    )

    model = get_peft_model(
        model,
        lora_config,
    )

    trainable = sum(
        p.numel()
        for p in model.parameters()
        if p.requires_grad
    )

    total = sum(
        p.numel()
        for p in model.parameters()
    )

    print(
        f"Trainable parameters: "
        f"{trainable:,}"
    )

    print(
        f"Trainable percentage: "
        f"{100 * trainable / total:.4f}%"
    )

    print_gpu_memory(
        "LORA ATTACHED"
    )

    # --------------------------------------------------------
    # 6. TOKENIZE AT 512
    # --------------------------------------------------------

    print(
        "\n[6/8] Tokenizing real example "
        "at 512 tokens..."
    )

    encoded = tokenizer(
        longest_text,
        return_tensors="pt",
        truncation=True,
        max_length=TEST_SEQUENCE_LENGTH,
        padding="max_length",
    )

    input_ids = (
        encoded["input_ids"]
        .to("cuda")
    )

    attention_mask = (
        encoded["attention_mask"]
        .to("cuda")
    )

    labels = input_ids.clone()

    # Padding should not contribute
    # to the language-model loss.
    labels[
        attention_mask == 0
    ] = -100

    actual_tokens = int(
        attention_mask.sum().item()
    )

    print(
        f"Actual non-padding tokens: "
        f"{actual_tokens}"
    )
    print(
        f"Tensor sequence length: "
        f"{input_ids.shape[1]}"
    )

    # --------------------------------------------------------
    # 7. REAL TRAINING STEP
    # --------------------------------------------------------

    print(
        "\n[7/8] Running forward + "
        "backward + optimizer step..."
    )

    optimizer = torch.optim.AdamW(
        (
            p
            for p in model.parameters()
            if p.requires_grad
        ),
        lr=LEARNING_RATE,
    )

    model.train()

    optimizer.zero_grad(
        set_to_none=True
    )

    try:
        outputs = model(
            input_ids=input_ids,
            attention_mask=attention_mask,
            labels=labels,
        )

        loss = outputs.loss

        print(
            f"Forward loss: "
            f"{loss.item():.6f}"
        )

        if not torch.isfinite(loss):
            raise RuntimeError(
                f"Non-finite loss: "
                f"{loss.item()}"
            )

        loss.backward()

        gradient_tensors = sum(
            1
            for p in model.parameters()
            if (
                p.requires_grad
                and p.grad is not None
            )
        )

        optimizer.step()

        print(
            f"LoRA tensors with gradients: "
            f"{gradient_tensors}"
        )

    except torch.cuda.OutOfMemoryError:
        print()
        print("=" * 70)
        print(
            "RESULT: 512-TOKEN TEST FAILED — CUDA OOM"
        )
        print("=" * 70)

        print_gpu_memory(
            "AT OOM"
        )

        raise

    # --------------------------------------------------------
    # 8. RESULTS
    # --------------------------------------------------------

    print_gpu_memory(
        "AFTER 512-TOKEN TRAINING STEP"
    )

    memory = gpu_memory()

    print()
    print("[8/8] Evaluating result...")

    headroom = (
        memory["total_gb"]
        - memory["peak_allocated_gb"]
    )

    print(
        f"Approx. allocation headroom: "
        f"{headroom:.3f} GB"
    )

    print()
    print("=" * 70)
    print(
        "RESULT: 512-TOKEN QLORA "
        "MEMORY TEST PASSED"
    )
    print("=" * 70)

    print(
        f"Original longest example: "
        f"{original_length} tokens"
    )
    print(
        f"Test sequence length:      "
        f"{TEST_SEQUENCE_LENGTH}"
    )
    print(
        f"Peak allocated VRAM:       "
        f"{memory['peak_allocated_gb']} GB"
    )
    print(
        f"Total VRAM:                "
        f"{memory['total_gb']} GB"
    )
    print(
        f"Approx. headroom:           "
        f"{headroom:.3f} GB"
    )

    print()
    print(
        "A successful result proves that a "
        "single 512-token training example "
        "fits with the current QLoRA setup."
    )


if __name__ == "__main__":
    main()