"""
Training configuration for TogoLM fine-tuning.

Targets Mistral 7B Instruct v0.3 with QLoRA (4-bit) — fits in 16GB VRAM (Colab T4).
Swap BASE_MODEL for "meta-llama/Meta-Llama-3-8B-Instruct" to use LLaMA 3 instead.
"""

from dataclasses import dataclass, field


@dataclass
class ModelConfig:
    base_model: str = "mistralai/Mistral-7B-Instruct-v0.3"
    load_in_4bit: bool = True  # QLoRA: 4-bit NF4 quantization
    bnb_4bit_compute_dtype: str = "bfloat16"
    max_seq_length: int = 2048


@dataclass
class LoraConfig:
    r: int = 16  # Rank — higher = more capacity, more VRAM
    lora_alpha: int = 32  # Scaling factor (alpha/r = 2 is common)
    target_modules: list[str] = field(
        default_factory=lambda: [
            "q_proj",
            "k_proj",
            "v_proj",
            "o_proj",
            "gate_proj",
            "up_proj",
            "down_proj",
        ]
    )
    lora_dropout: float = 0.05
    bias: str = "none"
    task_type: str = "CAUSAL_LM"


@dataclass
class TrainingConfig:
    output_dir: str = "finetuning/checkpoints/togolm-7b"
    num_train_epochs: int = 3
    per_device_train_batch_size: int = 2
    gradient_accumulation_steps: int = 8  # effective batch = 16
    learning_rate: float = 2e-4
    warmup_ratio: float = 0.03
    lr_scheduler_type: str = "cosine"
    weight_decay: float = 0.01
    fp16: bool = False
    bf16: bool = True  # Use bfloat16 on Ampere+ GPUs (A100, T4)
    logging_steps: int = 10
    save_steps: int = 100
    eval_steps: int = 100
    eval_strategy: str = "steps"
    save_total_limit: int = 2
    load_best_model_at_end: bool = True
    report_to: str = "none"  # Set to "wandb" for experiment tracking
    seed: int = 42


@dataclass
class DataConfig:
    train_file: str = "finetuning/datasets/togolm_sft_train.jsonl"
    eval_file: str = "finetuning/datasets/togolm_sft_eval.jsonl"
    dataset_format: str = "alpaca"  # "alpaca" or "sharegpt"
    max_samples: int | None = None  # None = use all


# Convenience: instantiate defaults
model_config = ModelConfig()
lora_config = LoraConfig()
training_config = TrainingConfig()
data_config = DataConfig()
