"""
RAG pipeline evaluation with RAGAS.
Usage:
    pip install ragas
    python eval_pipeline.py --questions questions.json

questions.json format:
[
  {
    "question": "What is Bayes' theorem?",
    "ground_truth": "Bayes' theorem states that P(A|B) = P(B|A)*P(A)/P(B)."
  },
  ...
]

Reported metrics:
  - faithfulness      → Is the answer supported by the retrieved context?
  - answer_relevancy  → Does the answer address the question asked?
  - context_recall    → Were the correct chunks retrieved?
  - context_precision → Were the retrieved chunks relevant?
"""

import os
import sys
import json
import argparse
from pathlib import Path
from datetime import datetime, timezone

# ── Optional dependencies ────────────────────────────────────
try:
    from datasets import Dataset
    from ragas import evaluate
    from ragas.metrics import faithfulness, answer_relevancy, context_recall, context_precision
except ImportError:
    print("❌ ragas or datasets not installed. Run: pip install ragas")
    sys.exit(1)

# ── RAG pipeline ─────────────────────────────────────────────
# Ensure the backend is in the path when running from /backend/
sys.path.insert(0, str(Path(__file__).parent))

from rag.ingest import get_settings, get_qdrant_client, get_vector_store, load_existing_index, STORAGE_DIR
from rag.query import query_rag


def load_questions(path: str) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    assert isinstance(data, list), "The file must be a JSON list of objects."
    for item in data:
        assert "question" in item and "ground_truth" in item, (
            "Each question requires 'question' and 'ground_truth'."
        )
    return data


def run_evaluation(questions: list[dict], top_k: int = 5) -> dict:
    print("🔧 Loading settings and index...")
    get_settings()
    index = load_existing_index()

    rows = {"question": [], "answer": [], "contexts": [], "ground_truth": []}

    for i, item in enumerate(questions, 1):
        q = item["question"]
        print(f"[{i}/{len(questions)}] Querying: {q[:80]}...")
        result = query_rag(index, q, top_k=top_k)
        rows["question"].append(q)
        rows["answer"].append(result["answer"])
        rows["contexts"].append([s.text for s in result["sources"]])
        rows["ground_truth"].append(item["ground_truth"])

    dataset = Dataset.from_dict(rows)
    print("\n⚙️  Computing RAGAS metrics...")
    scores = evaluate(
        dataset=dataset,
        metrics=[faithfulness, answer_relevancy, context_recall, context_precision],
    )
    return scores


def main():
    parser = argparse.ArgumentParser(description="RAG evaluation with RAGAS")
    parser.add_argument("--questions", required=True, help="Path to the questions JSON file")
    parser.add_argument("--top_k", type=int, default=5, help="Chunks retrieved per query")
    parser.add_argument("--output", default="eval_results.json", help="Output file")
    args = parser.parse_args()

    questions = load_questions(args.questions)
    scores = run_evaluation(questions, top_k=args.top_k)

    result = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "n_questions": len(questions),
        "top_k": args.top_k,
        "metrics": {
            "faithfulness": float(scores["faithfulness"]),
            "answer_relevancy": float(scores["answer_relevancy"]),
            "context_recall": float(scores["context_recall"]),
            "context_precision": float(scores["context_precision"]),
        },
    }

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"\n✅ Evaluation completed → {args.output}")
    print(json.dumps(result["metrics"], indent=2))


if __name__ == "__main__":
    main()
