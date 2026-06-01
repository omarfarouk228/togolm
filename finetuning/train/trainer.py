"""
Fine-tuning script for TogoLM using QLoRA + SFTTrainer.

Requires a GPU environment (Colab, Kaggle, cloud VM).
Run via the Colab notebook at finetuning/notebooks/train_colab.ipynb
or directly with:
    python -m finetuning.train.trainer

Dependencies (install in GPU environment):
    pip install transformers peft trl bitsandbytes datasets accelerate
"""

import json
from pathlib import Path

from finetuning.train.config import (
    DataConfig,
    LoraConfig,
    ModelConfig,
    TrainingConfig,
)

ALPACA_TEMPLATE = """Below is an instruction from a user about Togo. Write a response that answers the request accurately.

### Instruction:
{instruction}

### Response:
{output}"""

SHAREGPT_TEMPLATE = "{conversations}"


def _load_dataset(data_config: DataConfig):
    from datasets import Dataset, DatasetDict

    def _read(path: str) -> list[dict]:
        rows = []
        with open(path, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    rows.append(json.loads(line))
        return rows

    train_rows = _read(data_config.train_file)
    eval_rows = _read(data_config.eval_file)

    if data_config.max_samples:
        train_rows = train_rows[: data_config.max_samples]

    return DatasetDict(
        {
            "train": Dataset.from_list(train_rows),
            "eval": Dataset.from_list(eval_rows),
        }
    )


def _formatting_fn(data_config: DataConfig):
    """Return a function that converts a dataset row to a training string."""
    if data_config.dataset_format == "alpaca":
        def fmt(example):
            return ALPACA_TEMPLATE.format(
                instruction=example["instruction"],
                output=example["output"],
            )
    else:
        def fmt(example):
            convs = example["conversations"]
            parts = []
            for turn in convs:
                role = turn["from"]
                if role == "system":
                    parts.append(f"<|system|>\n{turn['value']}</s>")
                elif role == "human":
                    parts.append(f"<|user|>\n{turn['value']}</s>")
                elif role == "gpt":
                    parts.append(f"<|assistant|>\n{turn['value']}</s>")
            return "\n".join(parts)

    return fmt


def train(
    model_cfg: ModelConfig | None = None,
    lora_cfg: LoraConfig | None = None,
    training_cfg: TrainingConfig | None = None,
    data_cfg: DataConfig | None = None,
):
    import torch
    from peft import LoraConfig as PeftLoraConfig
    from peft import get_peft_model, prepare_model_for_kbit_training
    from transformers import (
        AutoModelForCausalLM,
        AutoTokenizer,
        BitsAndBytesConfig,
        TrainingArguments,
    )
    from trl import SFTTrainer

    model_cfg = model_cfg or ModelConfig()
    lora_cfg = lora_cfg or LoraConfig()
    training_cfg = training_cfg or TrainingConfig()
    data_cfg = data_cfg or DataConfig()

    print(f"Loading base model: {model_cfg.base_model}")

    bnb_config = BitsAndBytesConfig(
        load_in_4bit=model_cfg.load_in_4bit,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=getattr(torch, model_cfg.bnb_4bit_compute_dtype),
        bnb_4bit_use_double_quant=True,
    )

    model = AutoModelForCausalLM.from_pretrained(
        model_cfg.base_model,
        quantization_config=bnb_config,
        device_map="auto",
        trust_remote_code=True,
    )
    model = prepare_model_for_kbit_training(model)

    tokenizer = AutoTokenizer.from_pretrained(
        model_cfg.base_model,
        trust_remote_code=True,
    )
    tokenizer.pad_token = tokenizer.eos_token
    tokenizer.padding_side = "right"

    peft_config = PeftLoraConfig(
        r=lora_cfg.r,
        lora_alpha=lora_cfg.lora_alpha,
        target_modules=lora_cfg.target_modules,
        lora_dropout=lora_cfg.lora_dropout,
        bias=lora_cfg.bias,
        task_type=lora_cfg.task_type,
    )
    model = get_peft_model(model, peft_config)
    model.print_trainable_parameters()

    dataset = _load_dataset(data_cfg)
    formatting_fn = _formatting_fn(data_cfg)

    Path(training_cfg.output_dir).mkdir(parents=True, exist_ok=True)

    training_args = TrainingArguments(
        output_dir=training_cfg.output_dir,
        num_train_epochs=training_cfg.num_train_epochs,
        per_device_train_batch_size=training_cfg.per_device_train_batch_size,
        gradient_accumulation_steps=training_cfg.gradient_accumulation_steps,
        learning_rate=training_cfg.learning_rate,
        warmup_ratio=training_cfg.warmup_ratio,
        lr_scheduler_type=training_cfg.lr_scheduler_type,
        weight_decay=training_cfg.weight_decay,
        fp16=training_cfg.fp16,
        bf16=training_cfg.bf16,
        logging_steps=training_cfg.logging_steps,
        save_steps=training_cfg.save_steps,
        eval_steps=training_cfg.eval_steps,
        eval_strategy=training_cfg.eval_strategy,
        save_total_limit=training_cfg.save_total_limit,
        load_best_model_at_end=training_cfg.load_best_model_at_end,
        report_to=training_cfg.report_to,
        seed=training_cfg.seed,
    )

    trainer = SFTTrainer(
        model=model,
        train_dataset=dataset["train"],
        eval_dataset=dataset["eval"],
        formatting_func=formatting_fn,
        max_seq_length=model_cfg.max_seq_length,
        tokenizer=tokenizer,
        args=training_args,
        peft_config=peft_config,
    )

    print("Starting training...")
    trainer.train()

    print(f"Saving model to {training_cfg.output_dir}/final")
    trainer.save_model(f"{training_cfg.output_dir}/final")
    tokenizer.save_pretrained(f"{training_cfg.output_dir}/final")
    print("Training complete.")


if __name__ == "__main__":
    train()
