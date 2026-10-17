
"""Simple local RAG engine for CaseWeaver Lite."""

from __future__ import annotations

import math
import requests

from core.gemma_client import ask_gemma


OLLAMA_URL = "http://localhost:11434"
EMBEDDING_MODEL = "nomic-embed-text"


def embed_text(text: str) -> list[float]:
    """Convert text into an embedding using Ollama."""
    response = requests.post(
        f"{OLLAMA_URL}/api/embeddings",
        json={
            "model": EMBEDDING_MODEL,
            "prompt": text,
        },
        timeout=60,
    )
    response.raise_for_status()

    embedding = response.json().get("embedding")
    if not embedding:
        raise ValueError("Ollama returned no embedding.")

    return embedding


def cosine_similarity(
    first: list[float],
    second: list[float],
) -> float:
    """Measure similarity between two embedding vectors."""
    if len(first) != len(second):
        raise ValueError("Embedding dimensions must match.")

    dot_product = sum(a * b for a, b in zip(first, second))
    first_norm = math.sqrt(sum(a * a for a in first))
    second_norm = math.sqrt(sum(b * b for b in second))

    if first_norm == 0 or second_norm == 0:
        return 0.0

    return dot_product / (first_norm * second_norm)


def retrieve_relevant_statements(
    query: str,
    statements: list[dict],
    top_k: int = 3,
) -> list[dict]:
    """Retrieve the most relevant statements while preserving source IDs."""
    if top_k < 1:
        raise ValueError("top_k must be at least 1.")

    if not query.strip():
        raise ValueError("Query cannot be empty.")

    query_embedding = embed_text(query)
    ranked = []

    for statement in statements:
        if not isinstance(statement, dict):
            continue

        statement_id = statement.get("statement_id")
        statement_text = statement.get("text")

        if not statement_id or not isinstance(statement_text, str):
            continue

        statement_embedding = embed_text(statement_text)
        score = cosine_similarity(query_embedding, statement_embedding)

        ranked.append({
            "statement_id": statement_id,
            "text": statement_text,
            "similarity": score,
        })

    ranked.sort(key=lambda item: item["similarity"], reverse=True)
    return ranked[:top_k]


def answer_from_evidence(
    question: str,
    relevant_statements: list[dict],
) -> str:
    """Answer a question using retrieved case evidence."""
    if not relevant_statements:
        return "No relevant statements were found."

    evidence = "\n\n".join(
        f"Statement ID: {item['statement_id']}\n"
        f"Statement: {item['text']}"
        for item in relevant_statements
    )

    prompt = f"""
You are assisting with case-evidence review.

Answer the question using only the evidence below.
Do not invent facts or treat an allegation as proven.
If the evidence does not answer the question, say so.
Cite the relevant statement IDs in your answer.

EVIDENCE:
{evidence}

QUESTION:
{question}
"""

    return ask_gemma(prompt)
