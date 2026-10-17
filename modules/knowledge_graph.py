
"""Build an evidence-linked knowledge graph for CaseWeaver Lite."""

from __future__ import annotations

import networkx as nx


def build_knowledge_graph(identity_result: dict) -> nx.MultiDiGraph:
    """Build a graph from identity_engine.extract_identities() output.

    Person nodes represent extracted identities.
    Relationship edges preserve the statement and quotation supporting each claim.
    The graph records reported claims, not verified facts.
    """
    graph = nx.MultiDiGraph()

    if not isinstance(identity_result, dict):
        raise TypeError("identity_result must be a dictionary")

    # Add people as nodes.
    people = identity_result.get("people", [])
    if not isinstance(people, list):
        people = []

    for person in people:
        if not isinstance(person, dict):
            continue

        person_id = person.get("person_id")
        name = person.get("canonical_name")

        if not person_id or not name:
            continue

        graph.add_node(
            str(person_id),
            node_type="person",
            name=str(name),
            aliases=list(person.get("aliases") or []),
            is_witness=bool(person.get("is_witness", False)),
        )

        # Preserve each mention as evidence on the person node.
        mentions = person.get("mentions", [])
        if isinstance(mentions, list):
            graph.nodes[str(person_id)]["mentions"] = [
                mention.copy()
                for mention in mentions
                if isinstance(mention, dict)
            ]

    # Add evidence-backed relationship edges.
    relationships = identity_result.get("relationships", [])
    if not isinstance(relationships, list):
        relationships = []

    for relationship in relationships:
        if not isinstance(relationship, dict):
            continue

        source = relationship.get("from_person_id")
        target = relationship.get("to_person_id")

        # Don't create relationships to people absent from the result.
        if source not in graph or target not in graph:
            continue

        graph.add_edge(
            str(source),
            str(target),
            relation=str(relationship.get("type", "unknown")),
            statement_id=relationship.get("statement_id"),
            attributed_to=relationship.get("attributed_to"),
            quotation=relationship.get("quotation"),
            evidence_status="reported_claim",
        )

    graph.graph["case_id"] = identity_result.get("case_id")
    graph.graph["evidence_note"] = (
        "Edges represent reported claims and are not independently verified facts."
    )

    return graph


def graph_summary(graph: nx.MultiDiGraph) -> dict:
    """Return a compact summary suitable for an API or user interface."""
    return {
        "case_id": graph.graph.get("case_id"),
        "people_count": graph.number_of_nodes(),
        "relationship_count": graph.number_of_edges(),
        "people": [
            {
                "person_id": person_id,
                "name": attributes.get("name"),
                "is_witness": attributes.get("is_witness", False),
            }
            for person_id, attributes in graph.nodes(data=True)
        ],
        "relationships": [
            {
                "from_person_id": source,
                "to_person_id": target,
                "type": attributes.get("relation"),
                "statement_id": attributes.get("statement_id"),
                "quotation": attributes.get("quotation"),
                "evidence_status": attributes.get("evidence_status"),
            }
            for source, target, attributes in graph.edges(data=True)
        ],
    }
