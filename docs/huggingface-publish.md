# Publishing TogoLM to Hugging Face

This document tracks everything needed to publish the `togolm-7b-instruct-v1` model to HuggingFace Hub, from the current state of the pipeline to the final push.

---

## Current state (as of 2026-06-13) — ✅ Published

| Component | Status | Notes |
|-----------|--------|-------|
| Corpus (documents in DB) | ✅ 62 168 docs — 30 sources | Production DB on VPS |
| Q&A dataset | ✅ Published | [togolm/togolm-corpus-v1](https://huggingface.co/togolm/togolm-corpus-v1) |
| Dataset formatted | ✅ Done | Alpaca format |
| Fine-tuning script | ✅ Done | QLoRA on Mistral 7B v0.3 |
| Colab notebook | ✅ Done | train_colab.ipynb |
| HF account / org | ✅ `togolm` org active | huggingface.co/togolm |
| Fine-tuned model | ✅ Published | [togolm/togolm-7b-instruct-v1](https://huggingface.co/togolm/togolm-7b-instruct-v1) |
| Model card | ✅ Written | Included in HF repo |

---

## Step-by-step roadmap

### Step 1 — Build the corpus (prerequisite)

The more documents, the richer the training dataset.

```bash
# Check current DB count
psql -U theessential -d togolm -c "SELECT source, COUNT(*) FROM documents GROUP BY source;"

# Run remaining scrapers (from project root)
uv run scrapy crawl togofirst  -o corpus/datasets/togofirst.jsonl  -s JOBDIR=corpus/.crawls/togofirst
uv run scrapy crawl togoinfos  -o corpus/datasets/togoinfos.jsonl  -s JOBDIR=corpus/.crawls/togoinfos
uv run scrapy crawl republicoftogo -o corpus/datasets/republicoftogo.jsonl -s JOBDIR=corpus/.crawls/republicoftogo
uv run scrapy crawl mef        -o corpus/datasets/mef.jsonl        -s JOBDIR=corpus/.crawls/mef

# Ingest all new datasets
uv run python -m corpus.processors.ingestor corpus/datasets/*.jsonl
```

**Target before running generation:** ≥ 3 000 documents in DB.

---

### Step 2 — Add the Gemini API key

The Q&A generator and the RAG service use Gemini. Get a free key at [aistudio.google.com](https://aistudio.google.com).

```bash
# Edit .env
GEMINI_API_KEY=AIza...your_real_key_here
```

---

### Step 3 — Generate Q&A pairs

```bash
# Generate 3 pairs per document across all sources (~1h for 500 docs)
uv run python -m finetuning.dataset.generator \
  --limit 700 \
  --pairs-per-doc 3 \
  --out finetuning/datasets/qa_raw.jsonl

# Monitor progress
wc -l finetuning/datasets/qa_raw.jsonl
# Target: 2 000+ pairs minimum (ideally 5 000+)

# Run by category for targeted coverage
uv run python -m finetuning.dataset.generator --category legal   --limit 200 --pairs-per-doc 4
uv run python -m finetuning.dataset.generator --category economy --limit 150 --pairs-per-doc 3
uv run python -m finetuning.dataset.generator --category education --limit 100 --pairs-per-doc 3
```

---

### Step 4 — Format and split the dataset

```bash
# Format to Alpaca style (instruction / output)
uv run python -m finetuning.dataset.formatter \
  --input finetuning/datasets/qa_raw.jsonl \
  --output finetuning/datasets/togolm_sft_train.jsonl \
  --eval-output finetuning/datasets/togolm_sft_eval.jsonl \
  --format alpaca \
  --eval-ratio 0.1

# Verify
wc -l finetuning/datasets/togolm_sft_*.jsonl
head -n 1 finetuning/datasets/togolm_sft_train.jsonl | python3 -m json.tool
```

Expected output format (Alpaca):
```json
{
  "instruction": "Qui est responsable de la politique de renseignement au Togo ?",
  "output": "Selon la loi, la politique de renseignement relève exclusivement..."
}
```

---

### Step 5 — Fine-tune (GPU required)

**Option A — Google Colab (free T4, ~4h for 2 000 samples × 3 epochs)**

1. Upload to Colab:
   - `finetuning/notebooks/train_colab.ipynb`
   - `finetuning/datasets/togolm_sft_train.jsonl`
   - `finetuning/datasets/togolm_sft_eval.jsonl`

2. Set runtime: `Runtime → Change runtime type → T4 GPU`

3. Run all cells.

**Option B — RunPod / Modal (paid, faster)**

```bash
# On a GPU instance (24GB+ VRAM recommended for A10G/RTX 3090)
pip install transformers peft trl bitsandbytes datasets accelerate huggingface_hub

uv run python -m finetuning.train.trainer
# Checkpoints saved to: finetuning/checkpoints/togolm-7b/
```

**Key training config** (`finetuning/train/config.py`):

| Parameter | Value | Notes |
|-----------|-------|-------|
| Base model | `mistralai/Mistral-7B-Instruct-v0.3` | Or `meta-llama/Meta-Llama-3-8B-Instruct` |
| QLoRA rank | 16 | Higher = more capacity, more VRAM |
| Batch size | 2 × 8 grad accum = 16 effective | Fits T4 (16GB) |
| Epochs | 3 | ~45 min/epoch on T4 for 2k samples |
| Learning rate | 2e-4 | Cosine schedule |

---

### Step 6 — Evaluate before publishing

```bash
# Quick sanity check — run on eval set
python -c "
from transformers import pipeline
pipe = pipeline('text-generation', model='finetuning/checkpoints/togolm-7b/final')
result = pipe('Comment créer une entreprise au Togo ?', max_new_tokens=200)
print(result[0]['generated_text'])
"
```

Test at minimum:
- [ ] Answers in French when asked in French
- [ ] Answers grounded in Togolese context (no hallucinated foreign laws)
- [ ] Does not refuse Togolese legal questions
- [ ] Does not confuse Togo with other countries

---

### Step 7 — Merge LoRA adapters

The trained model is LoRA adapters + base model. Before pushing to HF, merge them into a single model for easy consumption.

```python
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel
import torch

BASE_MODEL = "mistralai/Mistral-7B-Instruct-v0.3"
ADAPTER_PATH = "finetuning/checkpoints/togolm-7b/final"
OUTPUT_PATH = "finetuning/checkpoints/togolm-7b-merged"

base = AutoModelForCausalLM.from_pretrained(BASE_MODEL, torch_dtype=torch.float16, device_map="auto")
model = PeftModel.from_pretrained(base, ADAPTER_PATH)
merged = model.merge_and_unload()

merged.save_pretrained(OUTPUT_PATH)
AutoTokenizer.from_pretrained(BASE_MODEL).save_pretrained(OUTPUT_PATH)
print("Merged model saved to", OUTPUT_PATH)
```

---

### Step 8 — Create the HuggingFace organization

1. Go to [huggingface.co/organizations/new](https://huggingface.co/organizations/new)
2. Create org: `togolm`
3. Create repos:
   - `togolm/togolm-7b-instruct-v1` — the fine-tuned model
   - `togolm/togolm-corpus-v1` — the raw JSONL dataset (optional)

---

### Step 9 — Push to HuggingFace Hub

```bash
pip install huggingface_hub
huggingface-cli login   # Enter your HF token
```

```python
from transformers import AutoModelForCausalLM, AutoTokenizer

model = AutoModelForCausalLM.from_pretrained("finetuning/checkpoints/togolm-7b-merged")
tokenizer = AutoTokenizer.from_pretrained("finetuning/checkpoints/togolm-7b-merged")

model.push_to_hub("togolm/togolm-7b-instruct-v1", private=False)
tokenizer.push_to_hub("togolm/togolm-7b-instruct-v1", private=False)
```

Or via CLI:
```bash
huggingface-cli upload togolm/togolm-7b-instruct-v1 \
  finetuning/checkpoints/togolm-7b-merged/ . \
  --repo-type model
```

---

### Step 10 — Write the model card

Create `finetuning/checkpoints/togolm-7b-merged/README.md` **before** pushing (HF uses it as the model card):

```markdown
---
language:
  - fr
license: apache-2.0
base_model: mistralai/Mistral-7B-Instruct-v0.3
tags:
  - togo
  - francophone
  - rag
  - legal
  - government
  - africa
  - instruction-tuning
  - qlora
datasets:
  - togolm/togolm-corpus-v1
pipeline_tag: text-generation
---

# togolm-7b-instruct-v1

**TogoLM** is the first instruction-tuned LLM specialized in Togolese knowledge.
Fine-tuned from [Mistral 7B Instruct v0.3](https://huggingface.co/mistralai/Mistral-7B-Instruct-v0.3)
using QLoRA on a curated dataset of X 000 Q&A pairs grounded in official Togolese documents.

## Intended use

- Answering questions about Togolese laws, government, economy, education
- RAG-based Q&A over Togolese public documents
- Building Togo-aware AI applications (chatbots, legal assistants, civic tools)
- Benchmark baseline for francophone West African NLP

## Training data

- **Corpus:** X 000 documents scraped from official Togolese government portals,
  national assembly, press (icilome.com, togofirst.com, togoinfos.com)
- **Q&A pairs:** X 000 instruction/response pairs generated with Gemini 2.5 Flash
  from the corpus, then manually reviewed
- **Categories:** legal, administrative, economy, education, agriculture, politics, press

## Training details

| Parameter | Value |
|-----------|-------|
| Base model | mistralai/Mistral-7B-Instruct-v0.3 |
| Method | QLoRA (4-bit NF4) |
| LoRA rank | 16 |
| Epochs | 3 |
| Learning rate | 2e-4 |
| Dataset | X 000 Alpaca-format pairs |

## Quick start

```python
from transformers import pipeline

pipe = pipeline("text-generation", model="togolm/togolm-7b-instruct-v1")
result = pipe(
    "### Instruction:\nComment créer une entreprise au Togo ?\n\n### Response:\n",
    max_new_tokens=300,
    temperature=0.7,
)
print(result[0]["generated_text"])
```

## Limitations

- Knowledge cutoff: training corpus last updated [DATE]
- May hallucinate details not present in the training corpus
- Optimized for French; limited English and Ewe support
- Legal information is for informational purposes only — consult a professional

## License

Apache 2.0 — same as the base model.

## Citation

```bibtex
@misc{togolm2026,
  title={TogoLM: Open-source AI Infrastructure for Togo},
  author={Kougbada, Omar Farouk},
  year={2026},
  url={https://github.com/togolm/togolm}
}
```
```

---

## Checklist

- [x] ≥ 2 000 Q&A pairs generated and reviewed
- [x] Train/eval split done (90/10)
- [x] Training loss converged (eval loss < 1.5)
- [x] Manual evaluation passed (see Step 6)
- [x] LoRA adapters merged into full model
- [x] Model card written and complete
- [x] `togolm` HF organization created
- [x] Model tested with `pipeline()` from the HF Hub URL
- [x] README.md of this repo updated with the HF model link

---

## After publishing

1. **Update the API** — switch `_generate_with_gemini` in `rag.py` to use `togolm/togolm-7b-instruct-v1` via HF Inference API or local deployment
2. **Update the showcase** — show the model name in the chat UI footer
3. **Announce** — post on X/Twitter, LinkedIn, HuggingFace community forums
4. **Deploy inference** — RunPod serverless or HF Spaces for a free demo endpoint
