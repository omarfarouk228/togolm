"""Push model card README to togolm/togolm-7b-instruct-v1 on HuggingFace Hub."""

import os

from huggingface_hub import HfApi

HF_REPO = "togolm/togolm-7b-instruct-v1"

README = """\
---
language:
  - fr
license: mit
base_model: mistralai/Mistral-7B-Instruct-v0.3
tags:
  - mistral
  - lora
  - qlora
  - unsloth
  - togo
  - africa
  - french
  - government
  - fine-tuned
datasets:
  - togolm/togolm-corpus-v1
pipeline_tag: text-generation
---

# TogoLM — Mistral 7B Instruct v1

**TogoLM** is the first open-source language model fine-tuned specifically on Togolese knowledge.
It is based on [Mistral 7B Instruct v0.3](https://huggingface.co/mistralai/Mistral-7B-Instruct-v0.3)
and adapted with QLoRA on a curated Q&A dataset drawn from official Togolese government sources.

> Built by [Omar Farouk KOUGBADA](https://github.com/omarfarouk228) — GDE Flutter, Senior Software and AI Engineer, CEO KOF CORPORATION.

---

## Model Details

| Property | Value |
|---|---|
| **Base model** | `mistralai/Mistral-7B-Instruct-v0.3` |
| **Fine-tuning method** | QLoRA (4-bit NF4 + LoRA adapters) |
| **LoRA rank / alpha** | r=16 / α=32 |
| **Training epochs** | 3 |
| **Effective batch size** | 16 (2 × 8 grad accumulation steps) |
| **Learning rate** | 2e-4 (cosine schedule, 3 % warmup) |
| **Max sequence length** | 2048 tokens |
| **Training hardware** | Kaggle T4 × 2 (via Unsloth) |
| **Training framework** | [Unsloth](https://github.com/unslothai/unsloth) + HuggingFace TRL SFTTrainer |
| **Precision** | FP16 |
| **Language** | French (fr) |
| **License** | MIT |

---

## Training Dataset

The SFT dataset ([`togolm/togolm-corpus-v1`](https://huggingface.co/datasets/togolm/togolm-corpus-v1))
consists of instruction–response pairs generated from the **TogoLM corpus** — a curated collection of
documents scraped from Togolese official sources:

| Source | Domain |
|---|---|
| `jo.gouv.tg` | Journal Officiel — laws and decrees |
| `presidence.gouv.tg` | Presidency — presidential acts and speeches |
| `assemblee-nationale.tg` | National Assembly — parliamentary texts |
| `inseed.tg` | National Statistics Institute — economic and demographic data |
| `service-public.gouv.tg` | Public services directory |
| `finances.gouv.tg` / `education.gouv.tg` / `agriculture.gouv.tg` | Ministries |
| `icilome.com` | Local news and analysis |

Q&A pairs were generated using **Gemini 2.5 Flash** and formatted in the Alpaca instruction template.

---

## Usage

### Load with Unsloth (recommended)

```python
from unsloth import FastLanguageModel

model, tokenizer = FastLanguageModel.from_pretrained(
    model_name="togolm/togolm-7b-instruct-v1",
    max_seq_length=2048,
    load_in_4bit=True,
)
FastLanguageModel.for_inference(model)

prompt = \"\"\"Below is an instruction about Togo. Write a response that answers it accurately.

### Instruction:
Quel est le taux d'imposition sur les sociétés au Togo ?

### Response:
\"\"\"

inputs = tokenizer(prompt, return_tensors="pt").to("cuda")
outputs = model.generate(**inputs, max_new_tokens=256, do_sample=False)
print(tokenizer.decode(outputs[0], skip_special_tokens=True))
```

### Load with standard Transformers + PEFT

```python
from transformers import AutoTokenizer, AutoModelForCausalLM
from peft import PeftModel

base = AutoModelForCausalLM.from_pretrained(
    "mistralai/Mistral-7B-Instruct-v0.3",
    load_in_4bit=True,
    device_map="auto",
)
model = PeftModel.from_pretrained(base, "togolm/togolm-7b-instruct-v1")
tokenizer = AutoTokenizer.from_pretrained("togolm/togolm-7b-instruct-v1")
```

---

## Prompt Format

The model was fine-tuned with the **Alpaca** instruction template:

```
Below is an instruction about Togo. Write a response that answers it accurately.

### Instruction:
{your question about Togo}

### Response:
```

---

## Intended Use

- Answering questions about Togolese law, administration, statistics, and public services in French
- Retrieval-augmented generation (RAG) combined with the TogoLM corpus
- Research on low-resource African languages and francophone AI

## Out-of-Scope Use

- General-purpose chat or tasks unrelated to Togo
- Legal or medical advice — always verify with official Togolese sources
- Languages other than French (coverage is limited)

---

## Project

This model is part of **TogoLM** — the first open-source AI infrastructure layer focused on Togo,
covering corpus collection, RAG engine, fine-tuned LLM, and a public REST API.

- GitHub: [github.com/omarfarouk228/togolm](https://github.com/omarfarouk228/togolm)
- Dataset: [togolm/togolm-corpus-v1](https://huggingface.co/datasets/togolm/togolm-corpus-v1)

---

## Citation

```bibtex
@misc{togolm2026,
  author       = {Kougbada, Omar Farouk},
  title        = {TogoLM: Open-Source AI Infrastructure for Togo},
  year         = {2026},
  howpublished = {\\url{https://huggingface.co/togolm/togolm-7b-instruct-v1}},
}
```
"""


def main():
    token = os.environ.get("HF_TOKEN")
    if not token:
        raise OSError("Set HF_TOKEN environment variable before running.")

    api = HfApi(token=token)
    api.upload_file(
        path_or_fileobj=README.encode(),
        path_in_repo="README.md",
        repo_id=HF_REPO,
        repo_type="model",
        commit_message="Add model card",
    )
    print(f"Model card pushed to https://huggingface.co/{HF_REPO}")


if __name__ == "__main__":
    main()
