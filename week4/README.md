# Week 4 — Domain-Specific Customer Support Assistant

## Overview

This project fine-tunes `mistralai/Mistral-7B-Instruct-v0.3` for customer-support responses using QLoRA.

The workflow includes:

- Dataset curation
- Synthetic data generation
- Token-length analysis
- QLoRA memory feasibility testing
- Baseline benchmarking
- Parameter-efficient fine-tuning
- Fine-tuned benchmarking
- Hyperparameter experimentation
- W&B experiment tracking
- Adapter checkpoint export
- FastAPI deployment
- Automated testing

---

## Domain

Customer Support

---

## Base Model

`mistralai/Mistral-7B-Instruct-v0.3`

---

## Dataset

Primary dataset:

`bitext/Bitext-customer-support-llm-chatbot-training-dataset`

Curated splits:

- Training: 2,160
- Validation: 270
- Test: 270

Synthetic training examples:

- 150

Total fine-tuning examples:

- 2,310

The held-out test set was not used for training or hyperparameter selection.

---

## QLoRA Configuration

### Main Rank-8 Run

- LoRA rank: 8
- LoRA alpha: 16
- LoRA dropout: 0.05
- Target modules: `q_proj`, `v_proj`
- Quantization: 4-bit NF4
- Double quantization: enabled
- Compute dtype: FP16
- Sequence length: 512
- Learning rate: 2e-4
- Epochs: 1
- Batch size: 1
- Gradient accumulation: 8
- Effective batch size: 8
- Scheduler: cosine
- Optimizer: paged AdamW 8-bit

### Selected Final Configuration

A controlled hyperparameter experiment later selected:

- LoRA rank: 16
- LoRA alpha: 16
- LoRA dropout: 0.05
- Learning rate: 2e-4

All other major training settings were kept fixed.

---

## Hardware

Training was performed locally using:

- NVIDIA GeForce RTX 3050
- 8 GB VRAM

### Rank-8 Main Run

- Peak allocated VRAM: 5.114 GB
- Runtime: 81.96 minutes
- Final validation loss: 0.98934

### Rank-16 Hyperparameter Run

- Peak allocated VRAM: 5.146 GB
- Runtime: 65.87 minutes
- Final validation loss: 0.97976

---

## Baseline Benchmark

Held-out test examples:

- 270

| Metric | Baseline |
|---|---:|
| Semantic Similarity | 0.7307 |
| Token F1 | 0.3970 |
| ROUGE-L F1 | 0.2424 |
| Mean Latency | 5.44 s |
| Median Latency | 5.70 s |
| P95 Latency | 6.07 s |
| Mean Generated Tokens | 120.27 |
| Empty Responses | 0 |

---

## Rank-8 Fine-Tuned Benchmark

| Metric | Rank 8 |
|---|---:|
| Semantic Similarity | 0.8167 |
| Token F1 | 0.4414 |
| ROUGE-L F1 | 0.3469 |
| Mean Latency | 4.81 s |
| Median Latency | 4.70 s |
| P95 Latency | 6.63 s |
| Mean Generated Tokens | 94.72 |
| Empty Responses | 0 |

---

## Baseline vs Rank-8 Fine-Tuned

| Metric | Change |
|---|---:|
| Semantic Similarity | +11.78% |
| Token F1 | +11.19% |
| ROUGE-L F1 | +43.08% |
| Mean Latency | 11.58% faster |
| Median Latency | 17.50% faster |
| P95 Latency | 9.32% slower |

The rank-8 fine-tuned model improved on all three measured automatic quality metrics.

Semantic similarity, Token F1, and ROUGE-L are reference-based evaluation metrics and should not be reported as classification accuracy.

---

## Hyperparameter Experiment

A controlled LoRA-rank experiment compared:

- Rank 8
- Rank 16

Both configurations used the same:

- Base model
- Dataset
- Sequence length
- Learning rate
- LoRA alpha
- LoRA dropout
- Target modules
- Scheduler
- Batch size
- Gradient accumulation
- Number of epochs
- Random seed

Validation results:

| Configuration | Validation Loss |
|---|---:|
| LoRA rank 8 | 0.98934 |
| LoRA rank 16 | 0.97976 |

Rank 16 achieved the lower validation loss and was selected as the final configuration.

The held-out test set was not used for hyperparameter selection.

---

## Final Rank-16 Held-Out Benchmark

After rank 16 was selected using validation loss, it was evaluated once on the held-out test set.

| Metric | Rank 16 |
|---|---:|
| Semantic Similarity | 0.8185 |
| Token F1 | 0.4447 |
| ROUGE-L F1 | 0.3472 |
| Mean Latency | 5.18 s |
| Median Latency | 5.01 s |
| P95 Latency | 7.31 s |
| Mean Generated Tokens | 97.84 |
| Empty Responses | 0 |

Rank 16 slightly improved all three quality metrics compared with rank 8.

The final model selection was based on validation loss, while the held-out test set was used only for final evaluation.

---

## Experiment Tracking

Weights & Biases project:

`crh-week4-customer-support`

Tracked information includes:

- Training loss
- Learning rate
- Token accuracy
- Validation loss
- Runtime
- Training configuration

Tracked runs include:

- `mistral7b-qlora-r8-lr2e4`
- `mistral7b-qlora-r16-lr2e4`

---

## Exported Models

The project exports PEFT LoRA adapters rather than merged full-precision 7B checkpoints.

Rank-8 adapter:

`outputs/mistral7b-customer-support-r8/final_adapter`

Selected final rank-16 adapter:

`outputs/mistral7b-customer-support-r16/final_adapter`

Both exports were verified successfully.

Using PEFT adapters keeps the exported checkpoints compact while preserving the learned fine-tuning parameters.

---

## Production API

The production assistant uses:

- FastAPI
- Uvicorn
- Mistral-7B loaded in 4-bit NF4
- Selected rank-16 LoRA adapter

Production adapter:

`outputs/mistral7b-customer-support-r16/final_adapter`

Endpoints:

- `GET /`
- `GET /health`
- `POST /chat`
- `/docs`

API smoke testing confirmed:

- Model loading succeeded
- CUDA was available
- RTX 3050 was detected
- `/health` returned HTTP 200
- `/chat` returned HTTP 200
- Rank-16 adapter was loaded successfully

---

## Customer-Support Guardrails

The assistant is instructed to:

- Answer clearly and politely
- Avoid inventing company policies
- Avoid inventing prices
- Avoid inventing refund or return conditions
- Avoid inventing order details
- Avoid inventing account information
- Avoid claiming actions were completed when they were not
- Ask for missing information when necessary
- Direct users to official policy sources when a policy cannot be verified

These guardrails are applied through the system prompt used during inference.

---

## Testing

Automated tests verify:

- Dataset files
- Dataset sizes
- Main adapter files
- Baseline metrics
- Fine-tuned metrics
- Quality improvements
- Comparison artifacts
- Training results

Current verified result:

`8 passed`

Additional final tests can also verify:

- Hyperparameter results
- Rank-16 final benchmark
- Rank-16 adapter export

---

## RLHF Concepts

This project does not perform full RLHF training.

A typical RLHF-style workflow may involve:

1. Supervised fine-tuning
2. Preference data collection
3. Reward or preference modeling
4. Policy optimization or preference-based optimization

This Week 4 implementation focuses on:

- Instruction tuning
- Dataset curation
- Synthetic data generation
- Parameter-efficient fine-tuning
- QLoRA
- Hyperparameter comparison
- Model evaluation

No claim is made that full RLHF training was performed.

---

## Resume and Recovery

Long-running operations were designed with recovery in mind.

### Evaluation

Predictions are written incrementally to JSONL files.

If evaluation is interrupted, rerunning the script skips completed examples and continues from the remaining examples.

### Hyperparameter Training

Training checkpoints are saved periodically.

The hyperparameter script automatically detects the latest available checkpoint and resumes from it.

This avoids repeating long GPU operations unnecessarily.

---

## Limitations

- Automatic reference-based metrics do not fully measure customer satisfaction, factual correctness, or real-world business performance.
- The model has no access to live company order systems, customer accounts, or policy databases.
- The assistant therefore cannot independently verify company-specific policies or transaction information.
- Training was limited to one epoch because of available hardware and internship time constraints.
- Hyperparameter optimization was intentionally limited to a controlled LoRA-rank comparison rather than a large search.
- Evaluation used a curated held-out test set of 270 examples.
- Latency measurements were collected on a local RTX 3050 and may differ on other hardware.
- Rank 16 improved quality slightly but had somewhat higher tail latency than rank 8.
- Full RLHF was not performed.

---

## Project Structure

```text
week4/
├── app/
│   └── main.py
├── data/
│   └── processed/
├── outputs/
│   ├── mistral7b-customer-support-r8/
│   └── mistral7b-customer-support-r16/
├── results/
├── scripts/
│   ├── 01_check_environment.py
│   ├── 02_model_smoke_test.py
│   ├── 03_prepare_dataset.py
│   ├── 04_token_analysis.py
│   ├── 05_sequence_memory_test.py
│   ├── 06_baseline_eval.py
│   ├── 07_generate_synthetic.py
│   ├── 08_train_qlora.py
│   ├── 09_finetuned_eval.py
│   ├── 10_compare_models.py
│   ├── 11_hyperparameter_experiment.py
│   ├── 12_verify_export.py
│   └── 13_final_rank16_eval.py
├── tests/
│   └── test_project.py
├── config.py
├── run_api.py
├── requirements.txt
├── requirements-lock.txt
└── README.md