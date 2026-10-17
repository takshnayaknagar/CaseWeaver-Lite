
from unittest.mock import patch

import pytest

from modules.rag_engine import (
    answer_from_evidence,
    cosine_similarity,
    retrieve_relevant_statements,
)


def test_cosine_similarity_identical_vectors():
    assert cosine_similarity([1.0, 0.0], [1.0, 0.0]) == pytest.approx(1.0)


def test_cosine_similarity_orthogonal_vectors():
    assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)


def test_cosine_similarity_rejects_different_dimensions():
    with pytest.raises(ValueError):
        cosine_similarity([1.0], [1.0, 2.0])


def test_retrieval_ranks_relevant_statements():
    statements = [
        {"statement_id": "S1", "text": "Bob entered at 8 PM."},
        {"statement_id": "S2", "text": "A window was broken."},
    ]

    # Mock embeddings so this test doesn't need Ollama.
    with patch(
        "modules.rag_engine.embed_text",
        side_effect=[[1.0, 0.0], [1.0, 0.0], [0.0, 1.0]],
    ):
        results = retrieve_relevant_statements(
            "When did Bob enter?",
            statements,
            top_k=2,
        )

    assert results[0]["statement_id"] == "S1"
    assert results[1]["statement_id"] == "S2"


def test_retrieval_rejects_empty_query():
    with pytest.raises(ValueError):
        retrieve_relevant_statements("  ", [])


def test_answer_uses_gemma_with_evidence():
    evidence = [
        {"statement_id": "S1", "text": "Alice saw Bob at 8 PM."}
    ]

    with patch(
        "modules.rag_engine.ask_gemma",
        return_value="Bob was reported at 8 PM (S1).",
    ) as mock_gemma:
        answer = answer_from_evidence(
            "When was Bob seen?",
            evidence,
        )

    assert answer == "Bob was reported at 8 PM (S1)."
    prompt = mock_gemma.call_args.args[0]
    assert "S1" in prompt
    assert "Alice saw Bob at 8 PM." in prompt


def test_answer_without_evidence_does_not_call_gemma():
    with patch("modules.rag_engine.ask_gemma") as mock_gemma:
        answer = answer_from_evidence("What happened?", [])

    assert answer == "No relevant statements were found."
    mock_gemma.assert_not_called()
