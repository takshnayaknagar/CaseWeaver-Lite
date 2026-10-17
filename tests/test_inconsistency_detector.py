from __future__ import annotations

import json

from modules import inconsistency_detector
from modules.inconsistencies import detect_inconsistencies as detect_inconsistencies_api
from modules.inconsistency_detector import detect_inconsistencies


def _sample_case():
    return {
        "case_id": "CW-001",
        "incident_date": "2026-10-15",
        "statements": [
            {
                "statement_id": "S1",
                "witness_name": "Alex",
                "text": (
                    "I started my security shift at 7:45 PM. At approximately "
                    "8:00 PM, I saw Maya near the exhibition room. At 8:15 PM, "
                    "I saw Daniel leaving the museum. I did not see Ryan that evening."
                ),
            },
            {
                "statement_id": "S2",
                "witness_name": "Maya",
                "text": (
                    "I entered the exhibition room at 7:55 PM and confirmed that "
                    "the diamond was present. I left at 8:10 PM. I saw Ryan near "
                    "the storage room at approximately 8:20 PM."
                ),
            },
        ],
    }


def _mock_gemma(monkeypatch, reply):
    monkeypatch.setattr(inconsistency_detector, "ask_gemma", lambda prompt: reply)


def test_reported_maya_mismatch_rejected_with_unrelated_quotes(monkeypatch):
    """Regression test 1: The reported Maya mismatch must be rejected.

    Finding claims seeing Maya at 8:00 PM vs 8:10 PM, but provides only
    the unrelated 7:45 PM shift-start and 7:55 PM exhibition-room quotes.
    """
    model_output = {
        "inconsistencies": [
            {
                "type": "direct_contradiction",
                "description": "Conflict about seeing Maya at 8:00 PM versus 8:10 PM.",
                "statement_ids": ["S1", "S2"],
                "quotations": [
                    {
                        "statement_id": "S1",
                        "quotation": "I started my security shift at 7:45 PM.",
                    },
                    {
                        "statement_id": "S2",
                        "quotation": (
                            "I entered the exhibition room at 7:55 PM and "
                            "confirmed that the diamond was present."
                        ),
                    },
                ],
                "confidence": 0.9,
            }
        ]
    }
    _mock_gemma(monkeypatch, json.dumps(model_output))

    result = detect_inconsistencies(_sample_case())

    assert result == [], "Unrelated evidence must not support the claimed conflict"


def test_maya_valid_finding_accepted(monkeypatch):
    """Valid inconsistency where both quotations directly support the conflicting claims."""
    model_output = {
        "inconsistencies": [
            {
                "type": "direct_contradiction",
                "description": "Alex reports seeing Maya at 8:00 PM, but Maya reports leaving at 8:10 PM.",
                "statement_ids": ["S1", "S2"],
                "quotations": [
                    {
                        "statement_id": "S1",
                        "quotation": "At approximately 8:00 PM, I saw Maya near the exhibition room.",
                    },
                    {
                        "statement_id": "S2",
                        "quotation": "I left at 8:10 PM.",
                    },
                ],
                "confidence": 0.85,
            }
        ]
    }
    _mock_gemma(monkeypatch, json.dumps(model_output))

    result = detect_inconsistencies(_sample_case())

    assert len(result) == 1
    finding = result[0]
    assert finding["type"] == "direct_contradiction"
    assert "seeing Maya" in finding["description"]
    assert finding["statement_ids"] == ["S1", "S2"]
    assert len(finding["quotations"]) == 2
    assert finding["quotations"][0]["quotation"] == "At approximately 8:00 PM, I saw Maya near the exhibition room."
    assert finding["quotations"][1]["quotation"] == "I left at 8:10 PM."
    assert finding["confidence"] == 0.85


def test_fabricated_quotation_rejected(monkeypatch):
    """Regression test 2: A fabricated quotation drops the finding."""
    model_output = {
        "inconsistencies": [
            {
                "type": "direct_contradiction",
                "description": "Conflict about seeing Maya at 8:00 PM.",
                "statement_ids": ["S1", "S2"],
                "quotations": [
                    {
                        "statement_id": "S1",
                        "quotation": "At approximately 8:00 PM, I saw Maya near the exhibition room.",
                    },
                    {
                        "statement_id": "S2",
                        "quotation": "I never visited the museum that night.",  # Fabricated!
                    },
                ],
                "confidence": 0.9,
            }
        ]
    }
    _mock_gemma(monkeypatch, json.dumps(model_output))

    result = detect_inconsistencies(_sample_case())

    assert result == [], "Fabricated quotation must cause the finding to be rejected"


def test_quotation_in_wrong_statement_rejected(monkeypatch):
    """Regression test 3: Quotation attributed to the wrong statement is rejected."""
    model_output = {
        "inconsistencies": [
            {
                "type": "direct_contradiction",
                "description": "Alex reports seeing Maya at 8:00 PM, but Maya reports leaving at 8:10 PM.",
                "statement_ids": ["S1", "S2"],
                "quotations": [
                    {
                        "statement_id": "S1",
                        # This text belongs to S2, not S1:
                        "quotation": "I left at 8:10 PM.",
                    },
                    {
                        "statement_id": "S2",
                        "quotation": "I left at 8:10 PM.",
                    },
                ],
                "confidence": 0.8,
            }
        ]
    }
    _mock_gemma(monkeypatch, json.dumps(model_output))

    result = detect_inconsistencies(_sample_case())

    assert result == [], "Quotation attributed to wrong statement ID must be rejected"


def test_unknown_statement_id_rejected(monkeypatch):
    """Quotation citing non-existent statement ID is rejected."""
    model_output = {
        "inconsistencies": [
            {
                "type": "direct_contradiction",
                "description": "Conflict about departure.",
                "statement_ids": ["S1", "S99"],
                "quotations": [
                    {
                        "statement_id": "S1",
                        "quotation": "At approximately 8:00 PM, I saw Maya near the exhibition room.",
                    },
                    {
                        "statement_id": "S99",
                        "quotation": "I left at 8:10 PM.",
                    },
                ],
                "confidence": 0.8,
            }
        ]
    }
    _mock_gemma(monkeypatch, json.dumps(model_output))

    assert detect_inconsistencies(_sample_case()) == []


def test_valid_inconsistency_schema_and_api_compatibility(monkeypatch):
    """Regression test 4 & 6: Schema and public API compatibility with frontend."""
    case = {
        "statements": [
            {"statement_id": "s1", "witness": "Alice Smith", "text": "The blue car left the parking lot at 8 PM."},
            {"statement_id": "s2", "witness": "Charlie Doe", "text": "The blue car left the parking lot at 9 PM."},
        ]
    }
    model_output = {
        "inconsistencies": [
            {
                "type": "direct_contradiction",
                "description": "The statements report different departure times for the blue car.",
                "statement_ids": ["s1", "s2"],
                "quotations": [
                    {"statement_id": "s1", "quotation": "The blue car left the parking lot at 8 PM."},
                    {"statement_id": "s2", "quotation": "The blue car left the parking lot at 9 PM."},
                ],
                "confidence": 0.9,
            }
        ]
    }
    _mock_gemma(monkeypatch, json.dumps(model_output))

    # Test direct detector module
    result = detect_inconsistencies(case)
    assert len(result) == 1
    item = result[0]
    assert set(item.keys()) == {"type", "description", "statement_ids", "quotations", "confidence"}
    assert item["type"] == "direct_contradiction"
    assert item["statement_ids"] == ["s1", "s2"]
    assert item["confidence"] == 0.9
    assert len(item["quotations"]) == 2
    for q in item["quotations"]:
        assert set(q.keys()) == {"statement_id", "witness", "quotation"}

    # Test public facade module (modules/inconsistencies.py)
    wrapped = detect_inconsistencies_api(case)
    assert isinstance(wrapped, dict)
    assert "inconsistencies" in wrapped
    assert len(wrapped["inconsistencies"]) == 1


def test_missing_or_malformed_evidence_fields_rejected(monkeypatch):
    """Regression test 5: Missing or malformed evidence fields rejected."""
    case = _sample_case()

    # Missing quotations entirely
    _mock_gemma(monkeypatch, json.dumps({"inconsistencies": [{"type": "direct_contradiction", "description": "foo"}]}))
    assert detect_inconsistencies(case) == []

    # Non-list quotations
    _mock_gemma(monkeypatch, json.dumps({"inconsistencies": [{"type": "direct_contradiction", "description": "foo", "quotations": "not list"}]}))
    assert detect_inconsistencies(case) == []

    # Quotation missing quotation text
    _mock_gemma(monkeypatch, json.dumps({"inconsistencies": [{"type": "direct_contradiction", "description": "foo", "quotations": [{"statement_id": "S1"}]}]}))
    assert detect_inconsistencies(case) == []

    # Disallowed type
    _mock_gemma(monkeypatch, json.dumps({"inconsistencies": [{"type": "rumor_clash", "description": "foo", "quotations": [{"statement_id": "S1", "quotation": "bar"}]}]}))
    assert detect_inconsistencies(case) == []

    # Missing description
    _mock_gemma(monkeypatch, json.dumps({"inconsistencies": [{"type": "direct_contradiction", "description": "", "quotations": [{"statement_id": "S1", "quotation": "bar"}]}]}))
    assert detect_inconsistencies(case) == []


def test_one_sided_support_rejected(monkeypatch):
    """A finding must be rejected if one side's evidence does not support the claim."""
    model_output = {
        "inconsistencies": [
            {
                "type": "direct_contradiction",
                "description": "Conflict about seeing Maya at 8:00 PM versus 8:10 PM.",
                "statement_ids": ["S1", "S2"],
                "quotations": [
                    {
                        "statement_id": "S1",
                        # S1 supports the 8:00 PM claim:
                        "quotation": "At approximately 8:00 PM, I saw Maya near the exhibition room.",
                    },
                    {
                        "statement_id": "S2",
                        # S2 does NOT support the 8:10 PM claim (mentions unrelated 7:55 PM entry):
                        "quotation": "I entered the exhibition room at 7:55 PM and confirmed that the diamond was present.",
                    },
                ],
                "confidence": 0.8,
            }
        ]
    }
    _mock_gemma(monkeypatch, json.dumps(model_output))

    result = detect_inconsistencies(_sample_case())

    assert result == [], "Both sides must support the claimed conflict"


def test_claims_format_support(monkeypatch):
    """Model returning 'claims' structure is accepted and normalized."""
    case = _sample_case()
    model_output = {
        "inconsistencies": [
            {
                "type": "direct_contradiction",
                "description": "Alex reports seeing Maya at 8:00 PM, but Maya reports leaving at 8:10 PM.",
                "claims": [
                    {
                        "source_statement_id": "S1",
                        "source_quote": "At approximately 8:00 PM, I saw Maya near the exhibition room.",
                    },
                    {
                        "source_statement_id": "S2",
                        "source_quote": "I left at 8:10 PM.",
                    },
                ],
                "confidence": 0.85,
            }
        ]
    }
    _mock_gemma(monkeypatch, json.dumps(model_output))

    result = detect_inconsistencies(case)

    assert len(result) == 1
    assert result[0]["statement_ids"] == ["S1", "S2"]
    assert len(result[0]["quotations"]) == 2


def test_accusatory_language_is_neutralized(monkeypatch):
    """Guilt/accusatory language in descriptions is neutralized."""
    case = {
        "statements": [
            {"statement_id": "s1", "witness": "Alice", "text": "The blue car left at 8 PM."},
            {"statement_id": "s2", "witness": "Charlie", "text": "The blue car left at 9 PM."},
        ]
    }
    model_output = {
        "inconsistencies": [
            {
                "type": "direct_contradiction",
                "description": "Charlie is a liar and lying about the departure time.",
                "statement_ids": ["s1", "s2"],
                "quotations": [
                    {"statement_id": "s1", "quotation": "The blue car left at 8 PM."},
                    {"statement_id": "s2", "quotation": "The blue car left at 9 PM."},
                ],
                "confidence": 0.9,
            }
        ]
    }
    _mock_gemma(monkeypatch, json.dumps(model_output))

    result = detect_inconsistencies(case)

    assert len(result) == 1
    assert "liar" not in result[0]["description"].lower()
    assert "lying" not in result[0]["description"].lower()
    assert "inconsistent" in result[0]["description"]


def test_client_failure_returns_empty_list(monkeypatch):
    """Connection errors from the model client return an empty list gracefully."""
    def boom(prompt):
        raise ConnectionError("Connection refused")

    monkeypatch.setattr(inconsistency_detector, "ask_gemma", boom)

    result = detect_inconsistencies(_sample_case())

    assert result == []


def _vehicle_case():
    """Two statements about a vehicle: a red sedan vs a dark blue truck."""
    return {
        "statements": [
            {
                "statement_id": "ST-001",
                "witness": "Jane Doe",
                "text": (
                    "I saw a man, around 6 feet tall, standing next to a red "
                    "sedan at the intersection at 14:00."
                ),
            },
            {
                "statement_id": "ST-002",
                "witness": "John Smith",
                "text": (
                    "He was a shorter man, and he got into a dark blue truck "
                    "before leaving around 14:05."
                ),
            },
        ]
    }


def _vehicle_model_output(description):
    return {
        "inconsistencies": [
            {
                "type": "direct_contradiction",
                "description": description,
                "statement_ids": ["ST-001", "ST-002"],
                "quotations": [
                    {
                        "statement_id": "ST-001",
                        "quotation": "standing next to a red sedan at the intersection at 14:00",
                    },
                    {
                        "statement_id": "ST-002",
                        "quotation": "he got into a dark blue truck before leaving around 14:05",
                    },
                ],
                "confidence": 0.9,
            }
        ]
    }


def test_hybrid_colour_claim_rejected(monkeypatch):
    """Regression: the explanation says 'red truck', but no cited quotation
    states a red truck — Jane Doe says 'red sedan' and John Smith says
    'dark blue truck'. The unsupported descriptor pair must drop the finding
    rather than present invented evidence.
    """
    _mock_gemma(
        monkeypatch,
        json.dumps(
            _vehicle_model_output(
                "One witness describes a red truck while the other describes "
                "a dark blue truck."
            )
        ),
    )

    assert detect_inconsistencies(_vehicle_case()) == []


def test_supported_colour_claim_accepted(monkeypatch):
    """The same finding phrased with the details the quotations actually
    state ('red sedan' vs 'dark blue truck') is kept.
    """
    _mock_gemma(
        monkeypatch,
        json.dumps(
            _vehicle_model_output(
                "One witness describes a red sedan while the other describes "
                "a dark blue truck."
            )
        ),
    )

    result = detect_inconsistencies(_vehicle_case())

    assert len(result) == 1
    assert "red sedan" in result[0]["description"]
    assert "dark blue truck" in result[0]["description"]
