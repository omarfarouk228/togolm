"""
Format raw Q&A pairs into training-ready JSONL.

Supports two output formats:
  - alpaca   : {"instruction": ..., "input": ..., "output": ...}
  - sharegpt : {"conversations": [{"from": "human", ...}, {"from": "gpt", ...}]}

The Alpaca format with a context "input" field teaches the model to answer
grounded in provided context — this is RAG-style fine-tuning.

Usage:
    uv run python -m finetuning.dataset.formatter \
        --input finetuning/datasets/qa_raw.jsonl \
        --output finetuning/datasets/togolm_sft.jsonl \
        --format alpaca
"""

import argparse
import json
import random
from pathlib import Path

SYSTEM_MESSAGE = (
    "Tu es TogoLM, un assistant IA expert des connaissances togolaises. "
    "Tu maîtrises la législation, l'économie, l'éducation et l'actualité du Togo. "
    "Tu réponds toujours avec précision en te basant sur les faits fournis."
)

# Instruction templates — varied phrasing so the model learns the pattern,
# not just the exact wording
INSTRUCTION_TEMPLATES = [
    "En te basant sur le contexte suivant, réponds à la question.\n\nCONTEXTE :\n{context}\n\nQUESTION : {question}",
    "Voici des informations sur le Togo. Réponds à la question posée.\n\n{context}\n\nQuestion : {question}",
    "Utilise le contexte ci-dessous pour répondre.\n\nContexte :\n{context}\n\n{question}",
    "{question}\n\nContexte disponible :\n{context}",
]


def _make_context_line(pair: dict) -> str:
    parts = []
    if pair.get("source"):
        parts.append(f"Source : {pair['source']}")
    if pair.get("title"):
        parts.append(f"Titre : {pair['title']}")
    return "\n".join(parts)


def to_alpaca(pair: dict) -> dict:
    context = _make_context_line(pair)
    template = random.choice(INSTRUCTION_TEMPLATES)
    instruction = template.format(context=context, question=pair["question"])
    return {
        "instruction": instruction,
        "input": "",
        "output": pair["answer"],
        "source": pair.get("source", ""),
        "category": pair.get("category", ""),
    }


def to_sharegpt(pair: dict) -> dict:
    context = _make_context_line(pair)
    template = random.choice(INSTRUCTION_TEMPLATES)
    user_message = template.format(context=context, question=pair["question"])
    return {
        "conversations": [
            {"from": "system", "value": SYSTEM_MESSAGE},
            {"from": "human", "value": user_message},
            {"from": "gpt", "value": pair["answer"]},
        ]
    }


def format_dataset(
    input_path: Path,
    output_path: Path,
    fmt: str = "alpaca",
    train_split: float = 0.9,
    seed: int = 42,
) -> tuple[int, int]:
    """
    Read qa_raw.jsonl, convert to training format, write train + eval splits.
    Returns (train_count, eval_count).
    """
    random.seed(seed)

    with open(input_path, encoding="utf-8") as f:
        pairs = [json.loads(line) for line in f if line.strip()]

    # Filter out empty or very short answers
    pairs = [p for p in pairs if len(p.get("answer", "").split()) >= 10]

    random.shuffle(pairs)
    split_idx = int(len(pairs) * train_split)
    train_pairs = pairs[:split_idx]
    eval_pairs = pairs[split_idx:]

    converter = to_alpaca if fmt == "alpaca" else to_sharegpt

    output_path.parent.mkdir(parents=True, exist_ok=True)
    train_path = output_path.with_stem(output_path.stem + "_train")
    eval_path = output_path.with_stem(output_path.stem + "_eval")

    with open(train_path, "w", encoding="utf-8") as f:
        for pair in train_pairs:
            f.write(json.dumps(converter(pair), ensure_ascii=False) + "\n")

    with open(eval_path, "w", encoding="utf-8") as f:
        for pair in eval_pairs:
            f.write(json.dumps(converter(pair), ensure_ascii=False) + "\n")

    print(f"Train: {len(train_pairs)} examples -> {train_path}")
    print(f"Eval : {len(eval_pairs)} examples -> {eval_path}")
    return len(train_pairs), len(eval_pairs)


def main():
    parser = argparse.ArgumentParser(description="Format Q&A pairs for SFT training")
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("finetuning/datasets/qa_raw.jsonl"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("finetuning/datasets/togolm_sft.jsonl"),
    )
    parser.add_argument(
        "--format",
        choices=["alpaca", "sharegpt"],
        default="alpaca",
    )
    parser.add_argument("--train-split", type=float, default=0.9)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    format_dataset(
        input_path=args.input,
        output_path=args.output,
        fmt=args.format,
        train_split=args.train_split,
        seed=args.seed,
    )


if __name__ == "__main__":
    main()
