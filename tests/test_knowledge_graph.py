
from modules.knowledge_graph import build_knowledge_graph, graph_summary


def test_build_knowledge_graph():
    result = {
        "case_id": "demo",
        "people": [
            {
                "person_id": "p_alice",
                "canonical_name": "Alice",
                "aliases": [],
                "is_witness": True,
                "mentions": [],
            },
            {
                "person_id": "p_bob",
                "canonical_name": "Bob",
                "aliases": [],
                "is_witness": False,
                "mentions": [],
            },
        ],
        "relationships": [
            {
                "from_person_id": "p_alice",
                "to_person_id": "p_bob",
                "type": "observed",
                "statement_id": "S1",
                "attributed_to": "Alice",
                "quotation": "I saw Bob",
            }
        ],
    }

    graph = build_knowledge_graph(result)
    summary = graph_summary(graph)

    assert graph.number_of_nodes() == 2
    assert graph.number_of_edges() == 1
    assert graph.has_edge("p_alice", "p_bob")
    assert summary["case_id"] == "demo"
    assert summary["relationships"][0]["statement_id"] == "S1"
    assert summary["relationships"][0]["evidence_status"] == "reported_claim"
from modules.identity_engine import extract_identities


def test_identity_engine_output_can_build_knowledge_graph():
    case_data = {
        "case_id": "integration_demo",
        "statements": [
            {
                "statement_id": "S1",
                "witness": "Alice",
                "text": "I saw Bob enter the shop at 8 PM.",
            }
        ],
    }

    # Mock Gemma's output so this test doesn't depend on Ollama.
    identity_result = extract_identities(case_data)

    graph = build_knowledge_graph(identity_result)
    summary = graph_summary(graph)

    assert summary["case_id"] == "integration_demo"
    assert graph.number_of_nodes() >= 1
    assert "p_alice" in graph
