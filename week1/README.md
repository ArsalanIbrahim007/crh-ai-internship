**Name:** Arsalan Ibrahim
**Internship ID:** CRH-2026-AI-034
**Organisation:** Code Room Hub
**Programme:** Artificial Intelligence Internship 
**Mode:** Remote
**Submission:** Week 1 - Modern LLMs and Transformer Architecture

---

# Week 1 — Modern LLMs and Transformer Architecture

Decoder block built from scratch, six open models benchmarked on local hardware, and a
dashboard comparing them across six dimensions.

**Hardware:** RTX 3050, 8 GB VRAM, Windows 11
**Setup:** bf16 compute dtype, batch size 1, greedy decoding, 128 new tokens, 5 prompts per model
**Precision:** every model in 4-bit NF4 via BitsAndBytes, except the quantization study

The benchmark was run twice on separate sessions. Headline numbers below are from run 2; the
difference between the runs is reported in *Measurement reliability* and is itself a result.

---

## Files

| File | What it does |
|---|---|
| `01_transformer_decoder_from_scratch.ipynb` | Decoder block built by hand in PyTorch. Runs on CPU. |
| `02_model_benchmarking_local.ipynb` | Loads and measures six models. Needs a CUDA GPU. |
| `03_benchmark_dashboard.ipynb` | Reads the results file and produces the comparison. Runs in seconds. |
| `results/benchmark_results.json` | Run 2 measurements plus every generated response. |
| `results/backup_run1.json` | Run 1, kept for the variance comparison. |

Run in order. Notebook 3 only needs the JSON, so it re-runs without touching a GPU, and every
figure in it is computed from the file rather than hardcoded.

---

## Notebook 1 — decoder block from scratch

Written without `nn.TransformerDecoderLayer` or any prebuilt attention. Where the 2017 paper
and current open models differ, the modern choice is implemented and the difference is noted.

Contains: scaled dot-product attention with causal masking, sinusoidal positional encoding,
rotary positional embeddings (RoPE), multi-head attention, grouped query attention, RMSNorm,
SwiGLU feed-forward, pre-norm residual blocks, KV cache, and a small stacked language model
with weight tying.

**Correctness checks, all passing:**

- Changing the last token leaves every earlier position's logits unchanged — the causal mask
  works end to end, not just in isolation.
- Feeding a sequence one token at a time through the KV cache produces logits identical to a
  single full forward pass, to 1.4e-04. The cache is a pure speedup, not an approximation.
- RoPE dot products depend only on the gap between positions, not absolute positions.
- GQA with 8 query heads and 2 KV heads gives the same output shape with a cache 4x smaller.

Measured KV cache speedup: 2.21x at 128 generated tokens, with byte-identical output.

**Not implemented:** sliding window attention, long-context scaling, training loop. This is an
inference-shaped implementation.

---

## Notebook 2 — benchmarking six models

### Why precision was held constant instead of size

Size-matching all six is not possible. Mistral's smallest open-weight release is 7B and the
smallest Phi instruct model is 3.8B, while Llama, Qwen, Gemma and DeepSeek publish models in
the 1-2 B range.

Precision was fixed instead: all six in 4-bit NF4. That keeps one variable constant, lets a 7B
model sit next to a 1B one on an 8 GB card, and covers the quantization requirement in the same
pass. **The cost is that size becomes the uncontrolled variable** — a slower model may simply be
a larger one. Parameter count stays in every table so this remains visible.

### Models

| Model | Repo | Params |
|---|---|---|
| Llama-3.2-1B | `meta-llama/Llama-3.2-1B-Instruct` | 1.24 B |
| Qwen2.5-1.5B | `Qwen/Qwen2.5-1.5B-Instruct` | 1.54 B |
| Gemma-2-2B | `google/gemma-2-2b-it` | 2.61 B |
| DeepSeek-R1-Distill-1.5B | `deepseek-ai/DeepSeek-R1-Distill-Qwen-1.5B` | 1.78 B |
| Phi-3.5-mini | `microsoft/Phi-3.5-mini-instruct` | 3.82 B |
| Mistral-7B-v0.3 | `mistralai/Mistral-7B-Instruct-v0.3` | 7.25 B |

DeepSeek-R1-Distill-Qwen-1.5B is a **Qwen2 architecture** distilled from R1, not an original
DeepSeek design. It shares Qwen's tokenizer exactly — identical vocabulary size and identical
token counts on every test string — which the tokenizer comparison confirms independently.

### Measurement method

Prefill and decode are timed separately. Prefill processes the whole prompt in one parallel
pass and is what a user perceives as lag; decode produces one token per forward pass and sets
the streaming rate. A single "inference speed" number hides that distinction.

One warmup run per model is discarded, and `torch.cuda.synchronize()` is called before every
clock read — CUDA calls are asynchronous, so without it the measurement is of how fast Python
queues work, not how fast the GPU computes.

---

## Results (run 2)

| Model | Params | Layers | Quality | Decode (tok/s) | TTFT (ms) | Peak VRAM (GB) | Context | $/1M tok |
|---|---|---|---|---|---|---|---|---|
| Llama-3.2-1B | 1.24 | 16 | 2.6 | 37.4 | 50.9 | 1.05 | 131,072 | 2.60 |
| Phi-3.5-mini | 3.82 | 32 | 2.8 | 29.4 | 61.8 | 2.34 | 131,072 | 3.31 |
| Qwen2.5-1.5B | 1.54 | 28 | 3.8 | 23.7 | 61.2 | 1.18 | 32,768 | 4.10 |
| DeepSeek-R1-Distill-1.5B | 1.78 | 28 | 1.4 | 23.7 | 50.2 | 1.64 | 131,072 | 4.10 |
| Mistral-7B-v0.3 | 7.25 | 32 | 2.8 | 22.2 | 88.2 | 4.19 | 32,768 | 4.38 |
| Gemma-2-2B | 2.61 | 26 | 4.0 | 19.6 | 72.0 | 2.28 | 8,192 | 4.96 |

Every model fit comfortably. The largest peak was Mistral at 4.19 GB, 49% of the card.

---

## Measurement reliability

The full benchmark was run twice, in separate sessions, on identical cached weights.

| Model | Run 1 | Run 2 | Change |
|---|---|---|---|
| Llama-3.2-1B | 36.5 | 37.4 | +2.5% |
| Phi-3.5-mini | 31.1 | 29.4 | −5.5% |
| Qwen2.5-1.5B | 22.8 | 23.7 | +3.9% |
| DeepSeek-R1-Distill-1.5B | 26.3 | 23.7 | **−9.9%** |
| Mistral-7B-v0.3 | 21.3 | 22.2 | +4.2% |
| Gemma-2-2B | 19.7 | 19.6 | −0.5% |

**Memory was deterministic to three decimal places across both runs.** Peak VRAM came out at
exactly 1.047, 1.176, 2.284, 1.644, 2.343 and 4.188 GB in both. Speed was not.

**Speed variance reordered the table.** DeepSeek moved 9.9% and dropped from a clear third
place into a tie with Qwen. Every other ordering held.

The practical consequence: **differences smaller than roughly 10% between models are not
meaningful on this setup.** Llama's lead over Phi (27%) and Phi's lead over the middle group
(24%) survive; the gap between Qwen, DeepSeek and Mistral does not. Any conclusion drawn from a
single run about those three would have been an artifact.

Both correlations were stable across runs: size vs speed −0.38 then −0.34, depth vs speed
−0.58 then −0.66. Quantization memory saving was identical at 62.7% both times.

---

## Findings

### 1. Advertised context is not usable context

The KV cache grows linearly with sequence length. Grouped query attention shrinks it by sharing
one key/value head across several query heads. Five of the six models use GQA. **Phi-3.5-mini
does not** — 32 query heads and 32 key/value heads, no sharing at all.

| Model | GQA | KV heads | KV cache at 4k | KV cache at advertised limit | Usable on this card |
|---|---|---|---|---|---|
| Llama-3.2-1B | yes | 8 / 32 | 134 MB | 4.29 GB | 100% |
| Qwen2.5-1.5B | yes | 2 / 12 | 117 MB | 0.94 GB | 100% |
| Gemma-2-2B | yes | 4 / 8 | 436 MB | 0.87 GB | 100% |
| DeepSeek-R1-Distill-1.5B | yes | 2 / 12 | 117 MB | 3.76 GB | 100% |
| **Phi-3.5-mini** | **no** | **32 / 32** | **1,611 MB** | **51.54 GB** | **12.3%** |
| Mistral-7B-v0.3 | yes | 8 / 32 | 537 MB | 4.29 GB | 100% |

Phi and Llama both advertise 131,072 tokens. Phi would need roughly **51 GB of KV cache** to
reach it; Llama needs 4.29 GB. On this 8 GB card Phi reaches about 16,100 tokens — 12% of its
own specification — while every other model reaches its full advertised limit.

**The context number on a model card means nothing without the KV head configuration.**

Gemma is a second illustration: it has the fewest attention heads of any model here and the
second-largest cache per token, because its head dimension is 256 against Llama's 64. One
config number in isolation is not informative.

These figures are computed from each model's own config file, not measured, since the test
prompts were too short to grow the cache. That is a limitation, but the arithmetic is exact.

### 2. Parameter count does not predict inference speed

Correlation between size and decode speed: **−0.34**. Between layer count and decode speed:
**−0.66**.

- Phi-3.5-mini is **2.5x the size of Qwen2.5-1.5B and 24% faster**
- Mistral-7B is **5.8x the size of Llama-3.2-1B and only 41% slower**

Depth explains more than size, and the reason is structural: decode runs one forward pass per
token and every layer in it is sequential. Llama has 16 layers where the others have 26-32, so
it does roughly half the sequential work per token. It is not the whole explanation — Phi has
32 layers and still places second — but neither variable alone accounts for the ordering.

### 3. Quantization is a memory technique, not a speed technique

Qwen2.5-1.5B run both ways on the same card:

| | bf16 | 4-bit NF4 | Change |
|---|---|---|---|
| Weights | 3.09 GB | 1.15 GB | −62.7% |
| Peak VRAM | 3.11 GB | 1.18 GB | −62.2% |
| Decode | 28.7 tok/s | 23.0 tok/s | **−19.9%** |
| TTFT | 46.9 ms | 53.0 ms | +13.0% |
| Load time | 10.62 s | 4.07 s | −61.7% |

4-bit weights are dequantized back to bf16 before every matmul, and that unpacking is work the
bf16 model never does. It costs on both phases: 20% slower decode and 13% slower prefill.

Quantization earns its place by making models fit, not by making them fast. On this card
Mistral-7B at bf16 would need roughly 14 GB against 8.6 GB available, so the alternative to
4-bit is not a faster model but no model.

Load time dropping 62% is a side effect of moving less data to the GPU, not of the model being
cheaper to run.

**Not measured:** accuracy loss from NF4. There is no held-out evaluation here that could detect
it, so no claim is made that the loss is negligible.

### 4. Tokenizer choice is a cost decision

| Model | Vocab | English tokens | Urdu tokens | Urdu / English |
|---|---|---|---|---|
| Gemma-2-2B | 256,000 | 43 | **11** | 0.26 |
| Qwen2.5-1.5B | 151,665 | 42 | 19 | 0.45 |
| DeepSeek-R1-Distill-1.5B | 151,665 | 42 | 19 | 0.45 |
| Llama-3.2-1B | 128,256 | **40** | 19 | 0.48 |
| Mistral-7B-v0.3 | 32,768 | 48 | 30 | 0.62 |
| Phi-3.5-mini | 32,011 | 48 | **32** | 0.67 |

Phi needs **three times** the tokens Gemma does for the same Urdu sentence. That is 3x the cost,
3x the forward passes, and a context window that fills 3x faster for identical text. The
32k-vocabulary models are English-first and everything else pays for it.

Vocabulary size does **not** predict English efficiency — Llama has half Gemma's vocabulary and
produces the fewest English tokens of any model here. How a tokenizer was trained matters more
than how large it is.

Cost per token also inverts cost per answer. Gemma is the most expensive per token at $4.96/M
and among the most token-efficient in Urdu, so for non-English workloads it is cheaper per
finished reply than the ranking suggests.

### 5. The fastest model was not the best one

Llama leads decode speed and places **fifth of six** on output quality. Gemma is **last on speed
and first on quality**. Selecting on throughput alone would have chosen badly, which is the
argument for a multi-dimensional dashboard rather than a speed table.

DeepSeek scoring worst (1.4/5) measured a mismatch rather than a bad model: it is a reasoning
distill being asked to behave like a chat model inside 128 tokens, and it spent them looping or
drifting into meta-commentary instead of answering.

---

## Limitations

Stated deliberately — every one of these bounds what the numbers above can support.

- **Size is not controlled.** Mistral is 5.8x the Llama entry. Slower does not mean worse built.
- **Batch size 1 throughout.** Decode at batch 1 is bandwidth bound and leaves most of the card's
  compute idle. Production serving batches many requests through one forward pass, so every
  cost figure here is pessimistic.
- **Run-to-run variance reaches 10%** and reordered part of the table between the two runs. See
  *Measurement reliability*. Differences below that threshold are not meaningful.
- **Five prompts, hand-scored.** A smoke test that models produce coherent on-topic text, not a
  capability evaluation.
- **The 128-token budget penalises verbosity, not error.** On the arithmetic prompt all six
  computed the intermediate result correctly but only three had room to state the answer.
  Gemma's ranking benefits from being concise.
- **Prompt 1 was poorly worded.** All six read "KV cache" as a generic key-value store rather
  than the attention cache. That is a fact about the prompt, not the models, and it is why
  prompt 1 scores lowest of the five across every model.
- **Long-context behaviour is calculated, not measured.** Prompts were short, so the KV cache
  never grew large enough to observe directly.
- **One card.** Decode is bandwidth bound, so these tokens-per-second figures do not transfer to
  different hardware.
- **GPU optimization is partial.** 4-bit quantization, SDPA attention, KV cache reuse, warmup
  discarding and explicit synchronization are all in place. FlashAttention 2 (no Windows wheel),
  `torch.compile` and batching are not, and no before/after optimization measurement was taken.

---

## Reproducing

```bash
python -m venv .venv
# Windows: .venv\Scripts\Activate.ps1     Linux/WSL2: source .venv/bin/activate
pip install torch --index-url https://download.pytorch.org/whl/cu128
pip install transformers accelerate bitsandbytes jupyter ipywidgets pandas matplotlib
hf auth login
jupyter notebook
```

Llama and Gemma are gated; accept the licence on each model page with the account whose token
is used. The other four need no permission.

Roughly 30 GB of weights are downloaded. Two things learned the hard way:

- On an unstable connection, `hf download <repo> --max-workers 1` is far more robust than
  letting the notebook fetch them. The default is 8 parallel workers, and only *completed* files
  are committed to cache, so a dropped connection with several large shards in flight loses all
  of them at once. Sequential downloads bank each shard as it finishes.
- `hf download mistralai/Mistral-7B-Instruct-v0.3` pulls 29 GB by default because the repo ships
  the weights twice, sharded and consolidated. `--exclude "consolidated*"` halves that; the
  consolidated file is never loaded by `transformers`.

To re-run notebook 2 from scratch, delete `results/benchmark_results.json` first. Section 5
restores previous results from that file and skips any model already in it, so leaving it in
place produces no new measurements.
