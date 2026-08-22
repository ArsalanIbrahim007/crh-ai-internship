from pathlib import Path


# ============================================================
# PROJECT
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parent

DATA_DIR = PROJECT_ROOT / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
PROCESSED_DATA_DIR = DATA_DIR / "processed"

OUTPUT_DIR = PROJECT_ROOT / "outputs"
RESULTS_DIR = PROJECT_ROOT / "results"

for directory in (
    DATA_DIR,
    RAW_DATA_DIR,
    PROCESSED_DATA_DIR,
    OUTPUT_DIR,
    RESULTS_DIR,
):
    directory.mkdir(parents=True, exist_ok=True)


# ============================================================
# REPRODUCIBILITY
# ============================================================

SEED = 42


# ============================================================
# DOMAIN
# ============================================================

DOMAIN = "customer_support"

SYSTEM_PROMPT = (
    "You are a helpful customer support assistant. "
    "Answer the customer's request clearly, politely, and concisely. "
    "Do not invent company policies, prices, order details, or actions "
    "that are not provided in the conversation."
)


# ============================================================
# DATASET
# ============================================================

DATASET_NAME = (
    "bitext/Bitext-customer-support-llm-chatbot-training-dataset"
)

# Balanced sample from every intent.
SAMPLES_PER_INTENT = 100

# Exact per-intent split:
# 80 train + 10 validation + 10 test = 100
TRAIN_PER_INTENT = 80
VAL_PER_INTENT = 10
TEST_PER_INTENT = 10


# ============================================================
# BASE MODEL
# ============================================================

MODEL_NAME = "mistralai/Mistral-7B-Instruct-v0.3"

# Smoke test passed at 128.
# Do not increase production training length until token
# distribution has been measured from the curated dataset.
MAX_SEQ_LENGTH = 512

# ============================================================
# QLORA
# ============================================================

LOAD_IN_4BIT = True
BNB_4BIT_QUANT_TYPE = "nf4"
BNB_4BIT_USE_DOUBLE_QUANT = True
COMPUTE_DTYPE = "float16"


# ============================================================
# LORA
# ============================================================

LORA_R = 8
LORA_ALPHA = 16
LORA_DROPOUT = 0.05

LORA_TARGET_MODULES = [
    "q_proj",
    "v_proj",
]


# ============================================================
# TRAINING
# ============================================================

LEARNING_RATE = 2e-4

PER_DEVICE_TRAIN_BATCH_SIZE = 1
GRADIENT_ACCUMULATION_STEPS = 8

NUM_TRAIN_EPOCHS = 1
# ============================================================
# EVALUATION
# ============================================================

GENERATION_MAX_NEW_TOKENS = 128

EMBEDDING_MODEL_NAME = (
    "sentence-transformers/all-MiniLM-L6-v2"
)
# ============================================================
# SYNTHETIC DATA
# ============================================================

SYNTHETIC_EXAMPLES = 150
# ============================================================
# EXPERIMENT TRACKING
# ============================================================

WANDB_PROJECT = "crh-week4-customer-support"

MAIN_RUN_NAME = "mistral7b-qlora-r8-lr2e4"


# ============================================================
# MAIN TRAINING RUN
# ============================================================

TRAIN_OUTPUT_DIR = (
    OUTPUT_DIR / "mistral7b-customer-support-r8"
)

LOGGING_STEPS = 10
EVAL_STEPS = 50
SAVE_STEPS = 50
SAVE_TOTAL_LIMIT = 2

WARMUP_RATIO = 0.03
