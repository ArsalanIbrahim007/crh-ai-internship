import sys
from pathlib import Path

# Allow scripts/ files to import config.py from the Week 4 root.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

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

from config import (
    MODEL_NAME,
    MAX_SEQ_LENGTH,
    BNB_4BIT_QUANT_TYPE,
    BNB_4BIT_USE_DOUBLE_QUANT,
    LORA_R,
    LORA_ALPHA,
    LORA_DROPOUT,
    LORA_TARGET_MODULES,
    LEARNING_RATE,
    SEED,
)


def gb(num_bytes: int) -> float:
    return round(num_bytes / (1024 ** 3), 3)


def print_gpu_memory(label: str) -> None:
    allocated = torch.cuda.memory_allocated()
    reserved = torch.cuda.memory_reserved()
    max_allocated = torch.cuda.max_memory_allocated()

    print(f"\nGPU MEMORY — {label}")
    print("-" * 60)
    print(f"Allocated:      {gb(allocated)} GB")
    print(f"Reserved:       {gb(reserved)} GB")
    print(f"Peak allocated: {gb(max_allocated)} GB")


def main() -> None:
    print("=" * 70)
    print("WEEK 4 — MISTRAL 7B QLORA SMOKE TEST")
    print("=" * 70)

    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is unavailable. Aborting smoke test.")

    torch.manual_seed(SEED)
    torch.cuda.manual_seed_all(SEED)

    torch.cuda.empty_cache()
    torch.cuda.reset_peak_memory_stats()

    gpu_name = torch.cuda.get_device_name(0)

    print(f"GPU:        {gpu_name}")
    print(f"Base model: {MODEL_NAME}")
    print(f"LoRA rank:  {LORA_R}")
    print(f"Targets:    {LORA_TARGET_MODULES}")
    print(f"Max length: {MAX_SEQ_LENGTH}")

    # --------------------------------------------------------
    # 1. QUANTIZATION CONFIG
    # --------------------------------------------------------

    print("\n[1/7] Creating 4-bit NF4 configuration...")

    quant_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type=BNB_4BIT_QUANT_TYPE,
        bnb_4bit_use_double_quant=BNB_4BIT_USE_DOUBLE_QUANT,
        bnb_4bit_compute_dtype=torch.float16,
    )

    # --------------------------------------------------------
    # 2. TOKENIZER
    # --------------------------------------------------------

    print("[2/7] Loading tokenizer...")

    tokenizer = AutoTokenizer.from_pretrained(
        MODEL_NAME,
        use_fast=True,
    )

    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    tokenizer.padding_side = "right"

    # --------------------------------------------------------
    # 3. BASE MODEL
    # --------------------------------------------------------

    print("[3/7] Loading Mistral-7B in 4-bit...")
    print("      First run will download the model files.")

    model = AutoModelForCausalLM.from_pretrained(
        MODEL_NAME,
        quantization_config=quant_config,
        device_map={"": 0},
        torch_dtype=torch.float16,
        low_cpu_mem_usage=True,
    )

    model.config.use_cache = False

    print_gpu_memory("BASE MODEL LOADED")

    # --------------------------------------------------------
    # 4. PREPARE FOR K-BIT TRAINING
    # --------------------------------------------------------

    print("\n[4/7] Preparing quantized model for training...")

    model = prepare_model_for_kbit_training(
        model,
        use_gradient_checkpointing=True,
    )

    # --------------------------------------------------------
    # 5. ATTACH LORA
    # --------------------------------------------------------

    print("[5/7] Attaching LoRA adapters...")

    lora_config = LoraConfig(
        r=LORA_R,
        lora_alpha=LORA_ALPHA,
        lora_dropout=LORA_DROPOUT,
        bias="none",
        task_type="CAUSAL_LM",
        target_modules=LORA_TARGET_MODULES,
    )

    model = get_peft_model(model, lora_config)

    trainable_params = 0
    total_params = 0

    for _, param in model.named_parameters():
        total_params += param.numel()

        if param.requires_grad:
            trainable_params += param.numel()

    trainable_pct = 100 * trainable_params / total_params

    print(f"\nTrainable parameters: {trainable_params:,}")
    print(f"Total parameters:     {total_params:,}")
    print(f"Trainable percentage: {trainable_pct:.4f}%")

    if trainable_params == 0:
        raise RuntimeError("LoRA attached but zero parameters are trainable.")

    print_gpu_memory("LORA ATTACHED")

    # --------------------------------------------------------
    # 6. BUILD ONE TINY TRAINING EXAMPLE
    # --------------------------------------------------------

    print("\n[6/7] Creating one customer-support training example...")

    messages = [
        {
            "role": "user",
            "content": (
                "My order arrived damaged. What should I do?"
            ),
        },
        {
            "role": "assistant",
            "content": (
                "I'm sorry your order arrived damaged. "
                "Please provide your order number and a photo of the damaged "
                "item so the support team can review the issue and help with "
                "the appropriate replacement or refund process."
            ),
        },
    ]

    formatted_text = tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=False,
    )

    encoded = tokenizer(
        formatted_text,
        return_tensors="pt",
        truncation=True,
        max_length=MAX_SEQ_LENGTH,
        padding=False,
    )

    input_ids = encoded["input_ids"].to("cuda")
    attention_mask = encoded["attention_mask"].to("cuda")

    labels = input_ids.clone()

    print(f"Training tokens: {input_ids.shape[1]}")

    # --------------------------------------------------------
    # 7. ONE REAL OPTIMIZER STEP
    # --------------------------------------------------------

    print("\n[7/7] Running forward + backward + optimizer step...")

    optimizer = torch.optim.AdamW(
        (p for p in model.parameters() if p.requires_grad),
        lr=LEARNING_RATE,
    )

    model.train()
    optimizer.zero_grad(set_to_none=True)

    outputs = model(
        input_ids=input_ids,
        attention_mask=attention_mask,
        labels=labels,
    )

    loss = outputs.loss

    print(f"Forward loss: {loss.item():.6f}")

    if not torch.isfinite(loss):
        raise RuntimeError(f"Loss is not finite: {loss.item()}")

    loss.backward()

    grad_params = 0

    for param in model.parameters():
        if param.requires_grad and param.grad is not None:
            grad_params += 1

    if grad_params == 0:
        raise RuntimeError(
            "Backward pass completed but no trainable parameter received gradients."
        )

    optimizer.step()

    print(f"LoRA tensors with gradients: {grad_params}")

    print_gpu_memory("AFTER TRAINING STEP")

    print()
    print("=" * 70)
    print("RESULT: QLORA SMOKE TEST PASSED")
    print("=" * 70)
    print("Verified:")
    print("  [PASS] Mistral-7B-Instruct-v0.3 loaded")
    print("  [PASS] 4-bit NF4 quantization loaded")
    print("  [PASS] LoRA adapters attached")
    print("  [PASS] Forward loss computed")
    print("  [PASS] Backward gradients computed")
    print("  [PASS] Optimizer step completed")
    print()
    print("This proves the local machine can perform a real QLoRA")
    print("training step. It does NOT yet prove full-dataset training fits.")


if __name__ == "__main__":
    main()