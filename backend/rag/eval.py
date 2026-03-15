"""
RAG pipeline evaluation module.

Uses the same LLM (Gemini) already configured in LlamaIndex to score
4 RAGAS-style metrics per question, without additional dependencies.

Metrics (0.0 - 1.0):
  faithfulness      → Is the answer supported by the retrieved context?
  answer_relevancy  → Does the answer address the question asked?
  context_recall    → Do the retrieved chunks contain the ground truth information?
  context_precision → Are the retrieved chunks relevant to the question?
"""

import re
from llama_index.core import Settings
from llama_index.core import VectorStoreIndex

from rag.query import query_rag


# ── Scoring via LLM ───────────────────────────────────────────

def _llm_score(prompt: str) -> float:
    """
    Sends the prompt to the configured LLM and extracts a number 0-10 from the response.
    Normalizes to 0.0 - 1.0. Returns 0.5 if it cannot be parsed.
    """
    try:
        response = Settings.llm.complete(prompt)
        text = str(response).strip()
        numbers = re.findall(r'\d+(?:\.\d+)?', text)
        if numbers:
            val = float(numbers[0])
            return round(min(max(val / 10.0, 0.0), 1.0), 4)
    except Exception as exc:
        print(f"⚠️  Error in LLM scoring: {exc}")
    return 0.5


def _score_faithfulness(answer: str, context: str) -> float:
    return _llm_score(
        "You are an evaluation assistant. "
        "Rate from 0 to 10 how much the answer is ONLY supported by the given context. "
        "Score 10 = every claim in the answer appears in the context. "
        "Score 0 = the answer contains claims not present in the context. "
        "Reply with a single number 0-10.\n\n"
        f"Context:\n{context[:3000]}\n\n"
        f"Answer:\n{answer}\n\n"
        "Score (0-10):"
    )


def _score_answer_relevancy(question: str, answer: str) -> float:
    return _llm_score(
        "You are an evaluation assistant. "
        "Rate from 0 to 10 how directly and completely the answer addresses the question. "
        "Score 10 = complete and focused answer. Score 0 = irrelevant or off-topic answer. "
        "Reply with a single number 0-10.\n\n"
        f"Question:\n{question}\n\n"
        f"Answer:\n{answer}\n\n"
        "Score (0-10):"
    )


def _score_context_recall(ground_truth: str, context: str) -> float:
    return _llm_score(
        "You are an evaluation assistant. "
        "Rate from 0 to 10 how much of the ground truth information is COVERED by the retrieved context. "
        "Score 10 = all ground truth facts are present in the context. "
        "Score 0 = no ground truth facts are present in the context. "
        "Reply with a single number 0-10.\n\n"
        f"Ground truth:\n{ground_truth}\n\n"
        f"Context:\n{context[:3000]}\n\n"
        "Score (0-10):"
    )


def _score_context_precision(question: str, context: str) -> float:
    return _llm_score(
        "You are an evaluation assistant. "
        "Rate from 0 to 10 how relevant the retrieved context chunks are to the question. "
        "Penalize chunks that are clearly irrelevant or noisy. "
        "Score 10 = all retrieved chunks are highly relevant. "
        "Score 0 = all retrieved chunks are irrelevant. "
        "Reply with a single number 0-10.\n\n"
        f"Question:\n{question}\n\n"
        f"Context:\n{context[:3000]}\n\n"
        "Score (0-10):"
    )


# ── Main evaluation function ──────────────────────────────────

def evaluate_question(
    index: VectorStoreIndex,
    question: str,
    ground_truth: str,
    top_k: int = 5,
) -> dict:
    """
    Evaluates a single question against the RAG index.
    Returns a dict with answer, individual scores and nodes_retrieved.
    """
    result = query_rag(index, question, top_k=top_k)
    answer = result["answer"]
    context = "\n\n---\n\n".join(s.text for s in result["sources"])

    return {
        "question": question,
        "answer": answer,
        "ground_truth": ground_truth,
        "faithfulness": _score_faithfulness(answer, context),
        "answer_relevancy": _score_answer_relevancy(question, answer),
        "context_recall": _score_context_recall(ground_truth, context),
        "context_precision": _score_context_precision(question, context),
        "nodes_retrieved": result["nodes_retrieved"],
    }


def aggregate_metrics(results: list[dict]) -> dict:
    """Calculates aggregated metrics (mean) from the per-question results."""
    n = len(results)
    if n == 0:
        return {"faithfulness": 0.0, "answer_relevancy": 0.0, "context_recall": 0.0, "context_precision": 0.0}
    keys = ["faithfulness", "answer_relevancy", "context_recall", "context_precision"]
    return {k: round(sum(r[k] for r in results) / n, 4) for k in keys}
