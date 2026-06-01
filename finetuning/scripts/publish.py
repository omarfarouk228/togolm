"""
Publish a fine-tuned TogoLM adapter to the HuggingFace Hub.

Only the LoRA adapter weights are uploaded (~100 MB), not the full base model
(~14 GB). Users load the adapter on top of the same base model at inference time.

Usage:
    python -m finetuning.scripts.publish \\
        --model finetuning/checkpoints/togolm-7b/final \\
        --repo togolm/togolm-7b-v1 \\
        [--private] [--token <HF_TOKEN>]

Set the HF_TOKEN env var (or use `huggingface-cli login`) to authenticate.
"""

import argparse
import os
from pathlib import Path


def publish(
    model_dir: Path,
    repo_id: str,
    private: bool = False,
    token: str | None = None,
) -> str:
    """Push a LoRA adapter checkpoint to the HuggingFace Hub.

    Args:
        model_dir: Path to the saved adapter directory (output of trainer.save_model).
        repo_id:   HuggingFace repo in the form ``username/model-name``.
        private:   Create the repo as private (default: public).
        token:     HuggingFace API token. Falls back to HF_TOKEN env var.

    Returns:
        The URL of the published model on the Hub.
    """
    from peft import PeftModel  # noqa: F401 — validates peft is installed early
    from transformers import AutoTokenizer

    token = token or os.environ.get("HF_TOKEN")
    if not token:
        raise ValueError(
            "HuggingFace token required. "
            "Set the HF_TOKEN env var or pass --token."
        )

    model_dir = Path(model_dir)
    if not model_dir.exists():
        raise FileNotFoundError(f"Model directory not found: {model_dir}")

    # Determine base model from adapter_config.json
    import json

    adapter_config_path = model_dir / "adapter_config.json"
    if not adapter_config_path.exists():
        raise FileNotFoundError(
            f"adapter_config.json not found in {model_dir}. "
            "Is this a valid LoRA adapter directory?"
        )
    with open(adapter_config_path) as f:
        adapter_config = json.load(f)
    base_model = adapter_config.get("base_model_name_or_path", "unknown")

    print(f"Publishing adapter from: {model_dir}")
    print(f"Base model             : {base_model}")
    print(f"Target repo            : https://huggingface.co/{repo_id}")
    print(f"Visibility             : {'private' if private else 'public'}")

    # Upload adapter weights
    from huggingface_hub import HfApi

    api = HfApi(token=token)
    api.create_repo(repo_id=repo_id, exist_ok=True, private=private)

    api.upload_folder(
        folder_path=str(model_dir),
        repo_id=repo_id,
        repo_type="model",
        commit_message="Add TogoLM LoRA adapter",
    )

    # Upload tokenizer (if present next to adapter or in a sibling dir)
    tokenizer_path = model_dir
    try:
        tokenizer = AutoTokenizer.from_pretrained(str(tokenizer_path))
        tokenizer.push_to_hub(repo_id, token=token, private=private)
        print("Tokenizer uploaded.")
    except Exception:
        pass  # tokenizer may already be included in the adapter folder

    print(f"\nModel published: https://huggingface.co/{repo_id}")
    return f"https://huggingface.co/{repo_id}"


def main():
    parser = argparse.ArgumentParser(
        description="Publish a TogoLM LoRA adapter to HuggingFace Hub"
    )
    parser.add_argument(
        "--model",
        type=Path,
        required=True,
        help="Path to the saved adapter directory",
    )
    parser.add_argument(
        "--repo",
        type=str,
        required=True,
        help="HuggingFace repo id (e.g. togolm/togolm-7b-v1)",
    )
    parser.add_argument(
        "--private",
        action="store_true",
        default=False,
        help="Create the repository as private",
    )
    parser.add_argument(
        "--token",
        type=str,
        default=None,
        help="HuggingFace API token (default: HF_TOKEN env var)",
    )
    args = parser.parse_args()

    publish(
        model_dir=args.model,
        repo_id=args.repo,
        private=args.private,
        token=args.token,
    )


if __name__ == "__main__":
    main()
