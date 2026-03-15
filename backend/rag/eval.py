"""
Módulo de evaluación del pipeline RAG.

Usa el mismo LLM (Gemini) ya configurado en LlamaIndex para puntuar
4 métricas estilo RAGAS por cada pregunta, sin dependencias adicionales.

Métricas (0.0 – 1.0):
  faithfulness      → ¿La respuesta está soportada por el contexto recuperado?
  answer_relevancy  → ¿La respuesta responde la pregunta formulada?
  context_recall    → ¿Los chunks recuperados contienen la información del ground truth?
  context_precision → ¿Los chunks recuperados son relevantes para la pregunta?
"""

import re
from llama_index.core import Settings
from llama_index.core import VectorStoreIndex

from rag.query import query_rag


# ── Scoring via LLM ───────────────────────────────────────────

def _llm_score(prompt: str) -> float:
    """
    Envía el prompt al LLM configurado y extrae un número 0-10 de la respuesta.
    Normaliza a 0.0 – 1.0. Devuelve 0.5 si no se puede parsear.
    """
    try:
        response = Settings.llm.complete(prompt)
        text = str(response).strip()
        numbers = re.findall(r'\d+(?:\.\d+)?', text)
        if numbers:
            val = float(numbers[0])
            return round(min(max(val / 10.0, 0.0), 1.0), 4)
    except Exception as exc:
        print(f"⚠️  Error en scoring LLM: {exc}")
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
    Evalúa una única pregunta contra el índice RAG.
    Retorna dict con answer, scores individuales y nodes_retrieved.
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
    """Calcula métricas agregadas (media) a partir de los resultados por pregunta."""
    n = len(results)
    if n == 0:
        return {"faithfulness": 0.0, "answer_relevancy": 0.0, "context_recall": 0.0, "context_precision": 0.0}
    keys = ["faithfulness", "answer_relevancy", "context_recall", "context_precision"]
    return {k: round(sum(r[k] for r in results) / n, 4) for k in keys}
