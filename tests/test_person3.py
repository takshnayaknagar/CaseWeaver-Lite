"""Automated tests for modules/identity_engine.py and modules/inconsistency_detector.py.

The shared Gemma client is mocked at the call site in each module (both modules
bind ``ask_gemma`` into their own namespace at import time), so these tests
never contact a real Ollama server and need no network access. All test data is
deterministic.
"""

from __future__ import annotations

import json
from unittest.mock import Mock

from core.gemma_client import GemmaClientError
from modules import identity_engine, inconsistency_detector
from modules.identity_engine import extract_identities
from modules.inconsistency_detector import detect_inconsistencies


# --------------------------------------------------------------------------
# Deterministic test data
# --------------------------------------------------------------------------

IDENTITY_STATEMENTS = [
    {
        "statement_id": "s1",
        "witness": "Alice Smith",
        "text": "Bob Jones entered the shop at 8 PM while Alice Smith was waiting outside.",
    },
    {
        "statement_id": "s2",
        "witness": "Charlie Doe",
        "text": "Charlie Doe spoke to Bob Jones near the bus stop at 9 PM.",
    },
]

IDENTITY_TEXTS = {s["statement_id"]: s["text"] for s in IDENTITY_STATEMENTS}

IDENTITY_MODEL_OK = {
    "people": [
        {
            "canonical_name": "Bob Jones",
            "aliases": ["Bob"],
            "mentions": [
                {"statement_id": "s1", "quotations": ["Bob Jones entered the shop at 8 PM"]},
                {"statement_id": "s2", "quotations": ["Charlie Doe spoke to Bob Jones"]},
            ],
        }
    ],
    "relationships": [
        {
            "type": "observed",
            "from_name": "Alice Smith",
            "to_name": "Bob Jones",
            "statement_id": "s1",
            "quotation": "Bob Jones entered the shop at 8 PM while Alice Smith was waiting outside.",
        },
        {
            "type": "spoke_to",
            "from_name": "Charlie Doe",
            "to_name": "Bob Jones",
            "statement_id": "s2",
            "quotation": "Charlie Doe spoke to Bob Jones near the bus stop at 9 PM.",
        },
    ],
}

DETECTOR_STATEMENTS = [
    {
        "statement_id": "s1",
        "witness": "Alice Smith",
        "text": "The blue car left the parking lot at 8 PM.",
    },
    {
        "statement_id": "s2",
        "witness": "Charlie Doe",
        "text": "The blue car left the parking lot at 9 PM.",
    },
]

DETECTOR_TEXTS = {s["statement_id"]: s["text"] for s in DETECTOR_STATEMENTS}

DETECTOR_MODEL_OK = {
    "inconsistencies": [
        {
            "type": "direct_contradiction",
            "description": "The statements report different departure times for the blue car.",
            "statement_ids": ["s1", "s2"],
            "quotations": [
                {"statement_id": "s1", "quotation": "left the parking lot at 8 PM"},
                {"statement_id": "s2", "quotation": "left the parking lot at 9 PM"},
            ],
            "confidence": 0.9,
        }
    ]
}


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------


def _install_gemma(monkeypatch, *, return_value=None, side_effect=None):
    """Patch the ask_gemma binding inside both modules under test."""
    if side_effect is not None:
        mock = Mock(side_effect=side_effect)
    else:
        mock = Mock(return_value=return_value)
    monkeypatch.setattr(identity_engine, "ask_gemma", mock)
    monkeypatch.setattr(inconsistency_detector, "ask_gemma", mock)
    return mock


def _identity_case():
    return {"case_id": "CASE-42", "statements": [dict(s) for s in IDENTITY_STATEMENTS]}


def _detector_case():
    return {"case_id": "CASE-42", "statements": [dict(s) for s in DETECTOR_STATEMENTS]}


def _person(result, name):
    matches = [p for p in result["people"] if p["canonical_name"] == name]
    assert len(matches) == 1, f"expected exactly one person named {name!r}"
    return matches[0]


def _assert_quotes_come_from_source(quotation_records, texts_by_id):
    """Every output quotation must be an exact substring of its cited statement."""
    for record in quotation_records:
        text = texts_by_id.get(record["statement_id"])
        assert text is not None, f"unknown statement_id {record['statement_id']!r} leaked into output"
        assert record["quotation"] in text, (
            f"quotation {record['quotation']!r} is not copied from statement "
            f"{record['statement_id']!r}: {text!r}"
        )


# --------------------------------------------------------------------------
# extract_identities
# --------------------------------------------------------------------------


class TestExtractIdentities:
    def test_success_merges_model_output_with_witnesses(self, monkeypatch):
        mock = _install_gemma(monkeypatch, return_value=json.dumps(IDENTITY_MODEL_OK))

        result = extract_identities(_identity_case())

        mock.assert_called_once()
        # The prompt must carry the real statement ids, witnesses and texts.
        prompt = mock.call_args[0][0]
        assert "statement_id: s1" in prompt
        assert "witness: Alice Smith" in prompt
        assert IDENTITY_TEXTS["s1"] in prompt
        assert IDENTITY_TEXTS["s2"] in prompt

        assert result["case_id"] == "CASE-42"
        assert result["warnings"] == []
        assert len(result["relationships"]) == 2

        assert [p["canonical_name"] for p in result["people"]] == [
            "Alice Smith",
            "Bob Jones",
            "Charlie Doe",
        ]

        alice = _person(result, "Alice Smith")
        assert alice["is_witness"] is True
        assert alice["aliases"] == []
        assert alice["mentions"] == [
            {"statement_id": "s1", "witness": "Alice Smith", "quotations": []}
        ]

        bob = _person(result, "Bob Jones")
        assert bob["person_id"] == "p_bob_jones"
        assert bob["is_witness"] is False
        assert bob["aliases"] == ["Bob"]
        assert bob["mentions"] == [
            {
                "statement_id": "s1",
                "witness": "Alice Smith",
                "quotations": ["Bob Jones entered the shop at 8 PM"],
            },
            {
                "statement_id": "s2",
                "witness": "Charlie Doe",
                "quotations": ["Charlie Doe spoke to Bob Jones"],
            },
        ]
        _assert_quotes_come_from_source(
            [
                {"statement_id": m["statement_id"], "quotation": q}
                for m in bob["mentions"]
                for q in m["quotations"]
            ],
            IDENTITY_TEXTS,
        )

    def test_success_relationship_schema(self, monkeypatch):
        _install_gemma(monkeypatch, return_value=json.dumps(IDENTITY_MODEL_OK))

        result = extract_identities(_identity_case())

        by_name = {p["canonical_name"]: p for p in result["people"]}
        assert [(r["type"], r["from_person_id"], r["to_person_id"]) for r in result["relationships"]] == [
            ("observed", by_name["Alice Smith"]["person_id"], by_name["Bob Jones"]["person_id"]),
            ("spoke_to", by_name["Charlie Doe"]["person_id"], by_name["Bob Jones"]["person_id"]),
        ]
        for rel in result["relationships"]:
            assert set(rel) == {
                "type",
                "from_person_id",
                "to_person_id",
                "statement_id",
                "attributed_to",
                "quotation",
            }
            assert rel["statement_id"] in IDENTITY_TEXTS
            assert rel["quotation"] in IDENTITY_TEXTS[rel["statement_id"]]

    def test_statement_id_resolved_case_insensitively(self, monkeypatch):
        model = {
            "people": [
                {
                    "canonical_name": "Bob Jones",
                    "aliases": [],
                    "mentions": [
                        {"statement_id": "S1", "quotations": ["Bob Jones entered the shop at 8 PM"]}
                    ],
                }
            ],
            "relationships": [],
        }
        _install_gemma(monkeypatch, return_value=json.dumps(model))

        result = extract_identities(_identity_case())

        bob = _person(result, "Bob Jones")
        assert [m["statement_id"] for m in bob["mentions"]] == ["s1"]
        assert bob["mentions"][0]["quotations"] == ["Bob Jones entered the shop at 8 PM"]

    def test_fabricated_quotation_is_dropped(self, monkeypatch):
        model = {
            "people": [
                {
                    "canonical_name": "Bob Jones",
                    "mentions": [
                        {
                            "statement_id": "s1",
                            "quotations": ["Bob Jones flew a helicopter over the shop"],
                        }
                    ],
                }
            ],
            "relationships": [],
        }
        _install_gemma(monkeypatch, return_value=json.dumps(model))

        result = extract_identities(_identity_case())

        bob = _person(result, "Bob Jones")
        assert bob["mentions"] == []
        assert any("Dropped quotation not found in s1" in w for w in result["warnings"])

    def test_mention_with_unknown_statement_id_is_dropped(self, monkeypatch):
        model = {
            "people": [
                {
                    "canonical_name": "Bob Jones",
                    "mentions": [
                        {"statement_id": "s99", "quotations": ["Bob Jones"]}
                    ],
                }
            ],
            "relationships": [],
        }
        _install_gemma(monkeypatch, return_value=json.dumps(model))

        result = extract_identities(_identity_case())

        bob = _person(result, "Bob Jones")
        assert bob["mentions"] == []
        assert any("unknown statement_id" in w and "s99" in w for w in result["warnings"])

    def test_unsupported_person_and_alias_are_dropped(self, monkeypatch):
        model = {
            "people": [
                {"canonical_name": "Zed Quill", "mentions": []},
                {"canonical_name": "Bob Jones", "aliases": ["Bobby"], "mentions": []},
            ],
            "relationships": [],
        }
        _install_gemma(monkeypatch, return_value=json.dumps(model))

        result = extract_identities(_identity_case())

        names = [p["canonical_name"] for p in result["people"]]
        assert "Zed Quill" not in names
        assert any("Dropped unsupported person" in w and "Zed Quill" in w for w in result["warnings"])
        assert _person(result, "Bob Jones")["aliases"] == []
        assert any("Dropped unsupported alias" in w and "Bobby" in w for w in result["warnings"])

    def test_relationship_with_fabricated_quotation_or_unknown_id_is_dropped(self, monkeypatch):
        model = {
            "people": [],
            "relationships": [
                {
                    "type": "observed",
                    "from_name": "Alice Smith",
                    "to_name": "Bob Jones",
                    "statement_id": "s1",
                    "quotation": "They were college roommates.",
                },
                {
                    "type": "observed",
                    "from_name": "Alice Smith",
                    "to_name": "Bob Jones",
                    "statement_id": "s404",
                    "quotation": "Bob Jones entered the shop at 8 PM while Alice Smith was waiting outside.",
                },
            ],
        }
        _install_gemma(monkeypatch, return_value=json.dumps(model))

        result = extract_identities(_identity_case())

        assert result["relationships"] == []
        dropped = [w for w in result["warnings"] if "Dropped relationship with invalid quotation" in w]
        assert len(dropped) == 2

    def test_relationship_quotation_must_name_both_endpoints(self, monkeypatch):
        model = {
            "people": [{"canonical_name": "Bob Jones", "mentions": []}],
            "relationships": [
                {
                    "type": "observed",
                    "from_name": "Alice Smith",
                    "to_name": "Bob Jones",
                    "statement_id": "s1",
                    "quotation": "Bob Jones entered the shop at 8 PM",
                }
            ],
        }
        _install_gemma(monkeypatch, return_value=json.dumps(model))

        result = extract_identities(_identity_case())

        assert result["relationships"] == []
        assert any("does not support both endpoints" in w for w in result["warnings"])

    def test_disallowed_relationship_type_is_ignored(self, monkeypatch):
        model = {
            "people": [],
            "relationships": [
                {
                    "type": "married_to",
                    "from_name": "Alice Smith",
                    "to_name": "Bob Jones",
                    "statement_id": "s1",
                    "quotation": "Bob Jones entered the shop at 8 PM while Alice Smith was waiting outside.",
                }
            ],
        }
        _install_gemma(monkeypatch, return_value=json.dumps(model))

        result = extract_identities(_identity_case())

        assert result["relationships"] == []

    def test_malformed_json_falls_back_to_witness_only(self, monkeypatch):
        mock = _install_gemma(monkeypatch, return_value="Sorry, I cannot produce that JSON.")

        result = extract_identities(_identity_case())

        mock.assert_called_once()
        assert [p["canonical_name"] for p in result["people"]] == ["Alice Smith", "Charlie Doe"]
        assert all(p["is_witness"] for p in result["people"])
        assert result["relationships"] == []
        assert any("not valid JSON" in w for w in result["warnings"])

    def test_fenced_json_with_prose_is_recovered(self, monkeypatch):
        payload = {"people": [], "relationships": []}
        raw = "Sure, here is the analysis:\n```json\n" + json.dumps(payload) + "\n```\nDone."
        _install_gemma(monkeypatch, return_value=raw)

        result = extract_identities(_identity_case())

        assert [p["canonical_name"] for p in result["people"]] == ["Alice Smith", "Charlie Doe"]
        assert result["relationships"] == []
        assert not any("not valid JSON" in w for w in result["warnings"])

    def test_client_exception_returns_witness_only(self, monkeypatch):
        mock = _install_gemma(
            monkeypatch,
            side_effect=GemmaClientError("Could not connect to Ollama at http://localhost:11434."),
        )

        result = extract_identities(_identity_case())

        mock.assert_called_once()
        assert [p["canonical_name"] for p in result["people"]] == ["Alice Smith", "Charlie Doe"]
        assert result["relationships"] == []
        assert any("Gemma client failed" in w and "Could not connect" in w for w in result["warnings"])

    def test_client_returning_none_reports_no_content(self, monkeypatch):
        _install_gemma(monkeypatch, return_value=None)

        result = extract_identities(_identity_case())

        assert any("Gemma returned no content" in w for w in result["warnings"])
        assert [p["canonical_name"] for p in result["people"]] == ["Alice Smith", "Charlie Doe"]

    def test_missing_client_module_returns_witness_only(self, monkeypatch):
        monkeypatch.setattr(identity_engine, "ask_gemma", None)

        result = extract_identities(_identity_case())

        assert any("unavailable" in w for w in result["warnings"])
        assert [p["canonical_name"] for p in result["people"]] == ["Alice Smith", "Charlie Doe"]

    def test_non_dict_case_data_is_rejected(self, monkeypatch):
        mock = _install_gemma(monkeypatch, return_value="{}")

        result = extract_identities(["not", "a", "dict"])

        mock.assert_not_called()
        assert result["people"] == []
        assert result["relationships"] == []
        assert result["case_id"] is None
        assert any("must be a dict" in w for w in result["warnings"])

    def test_no_statements_skips_model(self, monkeypatch):
        mock = _install_gemma(monkeypatch, return_value=json.dumps(IDENTITY_MODEL_OK))

        result = extract_identities({"case_id": "CASE-42"})

        mock.assert_not_called()
        assert result["people"] == []
        assert any("No witness statements" in w for w in result["warnings"])


# --------------------------------------------------------------------------
# detect_inconsistencies
# --------------------------------------------------------------------------


class TestDetectInconsistencies:
    def test_success_returns_validated_conflict(self, monkeypatch):
        mock = _install_gemma(monkeypatch, return_value=json.dumps(DETECTOR_MODEL_OK))

        result = detect_inconsistencies(_detector_case())

        mock.assert_called_once()
        prompt = mock.call_args[0][0]
        assert "statement_id: s1" in prompt
        assert "statement_id: s2" in prompt
        assert DETECTOR_TEXTS["s1"] in prompt
        assert DETECTOR_TEXTS["s2"] in prompt

        assert len(result) == 1
        item = result[0]
        assert set(item) == {"type", "description", "statement_ids", "quotations", "confidence"}
        assert item["type"] == "direct_contradiction"
        assert item["description"] == "The statements report different departure times for the blue car."
        assert item["statement_ids"] == ["s1", "s2"]
        assert item["confidence"] == 0.9
        assert item["quotations"] == [
            {
                "statement_id": "s1",
                "witness": "Alice Smith",
                "quotation": "left the parking lot at 8 PM",
            },
            {
                "statement_id": "s2",
                "witness": "Charlie Doe",
                "quotation": "left the parking lot at 9 PM",
            },
        ]
        _assert_quotes_come_from_source(item["quotations"], DETECTOR_TEXTS)

    def test_string_quotations_are_matched_to_their_statement(self, monkeypatch):
        model = {
            "inconsistencies": [
                {
                    "type": "missing_detail",
                    "description": "One account specifies 8 PM and the other 9 PM.",
                    "statement_ids": ["s1", "s2"],
                    "quotations": [
                        "The blue car left the parking lot at 8 PM",
                        "The blue car left the parking lot at 9 PM",
                    ],
                    "confidence": 0.6,
                }
            ]
        }
        _install_gemma(monkeypatch, return_value=json.dumps(model))

        result = detect_inconsistencies(_detector_case())

        assert len(result) == 1
        item = result[0]
        assert item["statement_ids"] == ["s1", "s2"]
        assert [(q["statement_id"], q["witness"]) for q in item["quotations"]] == [
            ("s1", "Alice Smith"),
            ("s2", "Charlie Doe"),
        ]
        _assert_quotes_come_from_source(item["quotations"], DETECTOR_TEXTS)

    def test_statement_ids_resolved_case_insensitively(self, monkeypatch):
        model = {
            "inconsistencies": [
                {
                    "type": "direct_contradiction",
                    "description": "The departure times differ.",
                    "statement_ids": ["S1", "S2"],
                    "quotations": [
                        {"statement_id": "S1", "quotation": "left the parking lot at 8 PM"},
                        {"statement_id": "S2", "quotation": "left the parking lot at 9 PM"},
                    ],
                    "confidence": 0.8,
                }
            ]
        }
        _install_gemma(monkeypatch, return_value=json.dumps(model))

        result = detect_inconsistencies(_detector_case())

        assert len(result) == 1
        assert result[0]["statement_ids"] == ["s1", "s2"]
        assert [q["statement_id"] for q in result[0]["quotations"]] == ["s1", "s2"]

    def test_fabricated_quotation_drops_the_conflict(self, monkeypatch):
        model = {
            "inconsistencies": [
                {
                    "type": "direct_contradiction",
                    "description": "The car colour is disputed.",
                    "statement_ids": ["s1", "s2"],
                    "quotations": [
                        {"statement_id": "s1", "quotation": "the car was red"},
                        {"statement_id": "s2", "quotation": "left the parking lot at 9 PM"},
                    ],
                    "confidence": 0.9,
                }
            ]
        }
        _install_gemma(monkeypatch, return_value=json.dumps(model))

        result = detect_inconsistencies(_detector_case())

        # Only one quotation survives validation, so the item needs a second
        # statement and is dropped entirely.
        assert result == []

    def test_unknown_statement_id_drops_the_conflict(self, monkeypatch):
        model = {
            "inconsistencies": [
                {
                    "type": "direct_contradiction",
                    "description": "The departure times differ.",
                    "statement_ids": ["s9", "s2"],
                    "quotations": [
                        {"statement_id": "s9", "quotation": "left the parking lot at 8 PM"},
                        {"statement_id": "s2", "quotation": "left the parking lot at 9 PM"},
                    ],
                    "confidence": 0.9,
                }
            ]
        }
        _install_gemma(monkeypatch, return_value=json.dumps(model))

        result = detect_inconsistencies(_detector_case())

        assert result == []

    def test_disallowed_type_is_dropped(self, monkeypatch):
        model = {
            "inconsistencies": [
                {
                    "type": "temporal_shift",
                    "description": "The times differ.",
                    "statement_ids": ["s1", "s2"],
                    "quotations": [
                        {"statement_id": "s1", "quotation": "left the parking lot at 8 PM"},
                        {"statement_id": "s2", "quotation": "left the parking lot at 9 PM"},
                    ],
                    "confidence": 0.9,
                }
            ]
        }
        _install_gemma(monkeypatch, return_value=json.dumps(model))

        assert detect_inconsistencies(_detector_case()) == []

    def test_direct_contradiction_with_identical_wording_is_dropped(self, monkeypatch):
        model = {
            "inconsistencies": [
                {
                    "type": "direct_contradiction",
                    "description": "The wording is identical.",
                    "statement_ids": ["s1", "s2"],
                    "quotations": [
                        {"statement_id": "s1", "quotation": "left the parking lot"},
                        {"statement_id": "s2", "quotation": "left the parking lot"},
                    ],
                    "confidence": 0.9,
                }
            ]
        }
        _install_gemma(monkeypatch, return_value=json.dumps(model))

        assert detect_inconsistencies(_detector_case()) == []

    def test_duplicate_conflicts_are_deduplicated(self, monkeypatch):
        model = {
            "inconsistencies": [
                {
                    "type": "direct_contradiction",
                    "description": "First description.",
                    "statement_ids": ["s1", "s2"],
                    "quotations": [
                        {"statement_id": "s1", "quotation": "at 8 PM"},
                        {"statement_id": "s2", "quotation": "at 9 PM"},
                    ],
                    "confidence": 0.8,
                },
                {
                    "type": "direct_contradiction",
                    "description": "Second description.",
                    "statement_ids": ["s2", "s1"],
                    "quotations": [
                        {"statement_id": "s2", "quotation": "at 9 PM"},
                        {"statement_id": "s1", "quotation": "at 8 PM"},
                    ],
                    "confidence": 0.7,
                },
            ]
        }
        _install_gemma(monkeypatch, return_value=json.dumps(model))

        result = detect_inconsistencies(_detector_case())

        assert len(result) == 1
        assert result[0]["description"] == "First description."

    def test_accusatory_description_is_neutralised(self, monkeypatch):
        model = {
            "inconsistencies": [
                {
                    "type": "direct_contradiction",
                    "description": "Charlie is lying about the departure time.",
                    "statement_ids": ["s1", "s2"],
                    "quotations": [
                        {"statement_id": "s1", "quotation": "left the parking lot at 8 PM"},
                        {"statement_id": "s2", "quotation": "left the parking lot at 9 PM"},
                    ],
                    "confidence": 0.9,
                }
            ]
        }
        _install_gemma(monkeypatch, return_value=json.dumps(model))

        result = detect_inconsistencies(_detector_case())

        assert len(result) == 1
        assert "lying" not in result[0]["description"].lower()
        assert result[0]["description"] == "Charlie is inconsistent about the departure time."

    def test_confidence_is_clamped_to_unit_interval(self, monkeypatch):
        model = {
            "inconsistencies": [
                {
                    "type": "missing_detail",
                    "description": "The times differ between the accounts.",
                    "statement_ids": ["s1", "s2"],
                    "quotations": [
                        {"statement_id": "s1", "quotation": "The blue car left the parking lot at 8 PM"},
                        {"statement_id": "s2", "quotation": "The blue car left the parking lot at 9 PM"},
                    ],
                    "confidence": 7,
                },
                {
                    "type": "perspective_difference",
                    "description": "The accounts emphasise different details.",
                    "statement_ids": ["s1", "s2"],
                    "quotations": [
                        {"statement_id": "s1", "quotation": "blue car"},
                        {"statement_id": "s2", "quotation": "parking lot"},
                    ],
                    "confidence": "high",
                },
            ]
        }
        _install_gemma(monkeypatch, return_value=json.dumps(model))

        result = detect_inconsistencies(_detector_case())

        assert [item["confidence"] for item in result] == [1.0, 0.0]

    def test_malformed_json_returns_model_unavailable_status(self, monkeypatch):
        mock = _install_gemma(monkeypatch, return_value="I cannot compare those statements.")

        result = detect_inconsistencies(_detector_case())

        mock.assert_called_once()
        assert len(result) == 1
        item = result[0]
        assert item["type"] == "model_unavailable"
        assert "malformed JSON" in item["description"]
        assert item["statement_ids"] == ["s1", "s2"]
        assert item["quotations"] == []
        assert item["confidence"] == 0.0

    def test_client_exception_returns_model_unavailable_status(self, monkeypatch):
        mock = _install_gemma(
            monkeypatch,
            side_effect=GemmaClientError("Ollama request timed out after 90s"),
        )

        result = detect_inconsistencies(_detector_case())

        mock.assert_called_once()
        assert len(result) == 1
        item = result[0]
        assert item["type"] == "model_unavailable"
        assert "failed or returned no content" in item["description"]
        assert item["statement_ids"] == ["s1", "s2"]
        assert item["confidence"] == 0.0

    def test_client_returning_none_returns_model_unavailable_status(self, monkeypatch):
        _install_gemma(monkeypatch, return_value=None)

        result = detect_inconsistencies(_detector_case())

        assert len(result) == 1
        assert result[0]["type"] == "model_unavailable"

    def test_fewer_than_two_usable_statements_skips_model(self, monkeypatch):
        mock = _install_gemma(monkeypatch, return_value=json.dumps(DETECTOR_MODEL_OK))
        case = {
            "case_id": "CASE-42",
            "statements": [
                {"statement_id": "s1", "witness": "Alice Smith", "text": "Something happened."},
                {"statement_id": "s2", "witness": "Charlie Doe", "text": ""},
            ],
        }

        assert detect_inconsistencies(case) == []
        mock.assert_not_called()

    def test_non_dict_case_data_returns_empty_list(self, monkeypatch):
        mock = _install_gemma(monkeypatch, return_value=json.dumps(DETECTOR_MODEL_OK))

        assert detect_inconsistencies(None) == []
        assert detect_inconsistencies(["not", "a", "dict"]) == []
        mock.assert_not_called()
