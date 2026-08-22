import sys
import platform

import torch
import transformers
import datasets
import peft
import bitsandbytes as bnb


def gb(value: int) -> float:
    return round(value / (1024 ** 3), 2)


print("=" * 60)
print("WEEK 4 — ENVIRONMENT CHECK")
print("=" * 60)

print(f"Python:       {sys.version.split()[0]}")
print(f"OS:           {platform.platform()}")
print(f"PyTorch:      {torch.__version__}")
print(f"Transformers: {transformers.__version__}")
print(f"Datasets:     {datasets.__version__}")
print(f"PEFT:         {peft.__version__}")
print(f"bitsandbytes: {bnb.__version__}")

print()
print("CUDA")
print("-" * 60)

cuda_ok = torch.cuda.is_available()

print(f"Available:    {cuda_ok}")

if not cuda_ok:
    raise SystemExit(
        "\nERROR: CUDA is not available. "
        "Do not continue to 7B QLoRA training until this is fixed."
    )

device = torch.cuda.current_device()
props = torch.cuda.get_device_properties(device)

print(f"Device:       {device}")
print(f"GPU:          {props.name}")
print(f"Total VRAM:   {gb(props.total_memory)} GB")
print(f"CUDA version: {torch.version.cuda}")

free_bytes, total_bytes = torch.cuda.mem_get_info()

print(f"Free VRAM:    {gb(free_bytes)} GB")
print(f"Used VRAM:    {gb(total_bytes - free_bytes)} GB")

print()
print("=" * 60)
print("RESULT: ENVIRONMENT READY FOR MODEL LOAD TEST")
print("=" * 60)