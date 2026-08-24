import gc
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

import torch
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from peft import PeftModel
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
)


# ============================================================
# PROJECT SETUP
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from config import (
    MODEL_NAME,
    SYSTEM_PROMPT,
)


MAIN_ADAPTER = (
    PROJECT_ROOT
    / "outputs"
    / "mistral7b-customer-support-r16"
    / "final_adapter"
)

MAX_NEW_TOKENS = 128


# ============================================================
# MODEL STATE
# ============================================================

model = None
tokenizer = None


# ============================================================
# REQUEST / RESPONSE MODELS
# ============================================================

class ChatRequest(BaseModel):
    message: str = Field(
        ...,
        min_length=1,
        max_length=4000,
    )

    max_new_tokens: int = Field(
        default=128,
        ge=1,
        le=256,
    )


class ChatResponse(BaseModel):
    response: str
    model: str
    adapter: str


class HealthResponse(BaseModel):
    status: str
    model_loaded: bool
    cuda_available: bool
    gpu: str | None


# ============================================================
# MODEL LOADING
# ============================================================

def load_model():
    global model
    global tokenizer

    if not torch.cuda.is_available():
        raise RuntimeError(
            "CUDA is required for this local 7B assistant."
        )

    if not MAIN_ADAPTER.exists():
        raise FileNotFoundError(
            f"Adapter not found: {MAIN_ADAPTER}"
        )

    print("=" * 72)
    print("Loading customer-support assistant...")
    print(f"Base model: {MODEL_NAME}")
    print(f"Adapter:    {MAIN_ADAPTER}")
    print(
        f"GPU:        {torch.cuda.get_device_name(0)}"
    )
    print("=" * 72)

    tokenizer = AutoTokenizer.from_pretrained(
        str(MAIN_ADAPTER),
        use_fast=True,
    )

    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    tokenizer.padding_side = "left"

    quant_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_use_double_quant=True,
        bnb_4bit_compute_dtype=torch.float16,
    )

    base_model = AutoModelForCausalLM.from_pretrained(
        MODEL_NAME,
        quantization_config=quant_config,
        torch_dtype=torch.float16,
        device_map={"": 0},
        low_cpu_mem_usage=True,
    )

    model = PeftModel.from_pretrained(
        base_model,
        str(MAIN_ADAPTER),
        is_trainable=False,
    )

    model.config.use_cache = True
    model.eval()

    print("Assistant model loaded successfully.")


def unload_model():
    global model
    global tokenizer

    model = None
    tokenizer = None

    gc.collect()

    if torch.cuda.is_available():
        torch.cuda.empty_cache()


# ============================================================
# FASTAPI LIFESPAN
# ============================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    load_model()

    yield

    unload_model()


# ============================================================
# APP
# ============================================================

app = FastAPI(
    title="Week 4 Domain-Specific Customer Support Assistant",
    description=(
        "Mistral-7B-Instruct-v0.3 with a QLoRA customer-support adapter."
    ),
    version="1.0.0",
    lifespan=lifespan,
)


# ============================================================
# ROUTES
# ============================================================

@app.get("/")
def root():
    return {
        "message": (
            "Customer Support Assistant API"
        ),
        "docs": "/docs",
        "health": "/health",
        "chat": "/chat",
    }


@app.get(
    "/health",
    response_model=HealthResponse,
)
def health():
    gpu = None

    if torch.cuda.is_available():
        gpu = torch.cuda.get_device_name(0)

    return HealthResponse(
        status="ok" if model is not None else "loading",
        model_loaded=model is not None,
        cuda_available=torch.cuda.is_available(),
        gpu=gpu,
    )


@app.post(
    "/chat",
    response_model=ChatResponse,
)
def chat(request: ChatRequest):
    if model is None or tokenizer is None:
        raise HTTPException(
            status_code=503,
            detail="Model is not loaded.",
        )

    user_message = request.message.strip()

    if not user_message:
        raise HTTPException(
            status_code=400,
            detail="Message cannot be empty.",
        )

    messages = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT,
        },
        {
            "role": "user",
            "content": user_message,
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

    try:
        with torch.inference_mode():
            generated = model.generate(
                **inputs,
                max_new_tokens=(
                    request.max_new_tokens
                ),
                do_sample=False,
                num_beams=1,
                pad_token_id=(
                    tokenizer.eos_token_id
                ),
                eos_token_id=(
                    tokenizer.eos_token_id
                ),
                use_cache=True,
            )

    except RuntimeError as exc:
        if "out of memory" in str(exc).lower():
            torch.cuda.empty_cache()

            raise HTTPException(
                status_code=503,
                detail=(
                    "GPU memory was exhausted. "
                    "Try again after the current "
                    "request finishes."
                ),
            ) from exc

        raise

    generated_tokens = (
        generated[0][input_length:]
    )

    response_text = tokenizer.decode(
        generated_tokens,
        skip_special_tokens=True,
    ).strip()

    return ChatResponse(
        response=response_text,
        model=MODEL_NAME,
        adapter="mistral7b-customer-support-r16",
    )