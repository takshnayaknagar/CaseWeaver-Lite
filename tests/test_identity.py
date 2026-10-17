from __future__ import annotations

import json

from modules import identity_engine
from modules.identity_engine import extract_identities


def _case():
    return {
        "case_id": "CW-001",
        "statements": [
            {
                "statement_id": "S1",
                "witness_name": "Alex",
                "text": "At 8:00 PM, I saw Maya near the exhibition room.",
            }
        ],
    }


def _mock_gemma(monkeypatch, reply):
    monkeypatch.setattr(identity_engine, "ask_gemma", lambda prompt: reply)


def test_flat_prompt_shape_parses_and_merges_people(monkeypatch):
    reply = json.dumps(
        {
            "people": [
                {
                    "canonical_name": "Maya",
                    "aliases": [],
                    "statement_id": "S1",
                    "quotations": ["I saw Maya near the exhibition room."],
                }
            ],
            "relationships": [],
        }
    )
    _mock_gemma(monkeypatch, reply)

    result = extract_identities(_case())

    names = [p["canonical_name"] for p in result["people"]]
    assert names == ["Alex", "Maya"]
    maya = next(p for p in result["people"] if p["canonical_name"] == "Maya")
    assert maya["mentions"] == [
        {
            "statement_id": "S1",
            "witness": "Alex",
            "quotations": ["I saw Maya near the exhibition room."],
        }
    ]


def test_nested_mentions_shape_still_accepted(monkeypatch):
    reply = json.dumps(
        {
            "people": [
                {
                    "canonical_name": "Maya",
                    "aliases": [],
                    "mentions": [
                        {
                            "statement_id": "S1",
                            "quotations": ["I saw Maya near the exhibition room."],
                        }
                    ],
                }
            ],
            "relationships": [],
        }
    )
    _mock_gemma(monkeypatch, reply)

    result = extract_identities(_case())

    assert "Maya" in [p["canonical_name"] for p in result["people"]]
    assert not any("not valid JSON" in w for w in result["warnings"])


def test_fenced_json_is_parsed(monkeypatch):
    inner = json.dumps({"people": [], "relationships": []})
    _mock_gemma(monkeypatch, f"```json\n{inner}\n```")

    result = extract_identities(_case())

    assert not any("not valid JSON" in w for w in result["warnings"])
    assert [p["canonical_name"] for p in result["people"]] == ["Alex"]


def test_trailing_comma_is_salvaged(monkeypatch):
    _mock_gemma(
        monkeypatch,
        '```json\n{"people": [], "relationships": [],}\n```',
    )

    result = extract_identities(_case())

    assert not any("not valid JSON" in w for w in result["warnings"])


def test_unclosed_brackets_are_salvaged(monkeypatch):
    _mock_gemma(
        monkeypatch,
        '```json\n{"people": [{"canonical_name": "Maya", "aliases": [],\n```',
    )

    result = extract_identities(_case())

    assert not any("not valid JSON" in w for w in result["warnings"])
    assert "Maya" in [p["canonical_name"] for p in result["people"]]


def test_invalid_json_falls_back_to_witness_only(monkeypatch):
    _mock_gemma(monkeypatch, "utterly not JSON")

    result = extract_identities(_case())

    assert any("not valid JSON" in w for w in result["warnings"])
    assert any("witness-only" in w for w in result["warnings"])
    # The witness is still present; nothing was fabricated.
    assert [p["canonical_name"] for p in result["people"]] == ["Alex"]


def test_structurally_wrong_nesting_is_not_guessed(monkeypatch):
    # Bracket counts balance overall but the mention object's closing brace
    # is missing, so correct nesting is ambiguous. The module must fall
    # back rather than repair into a wrong-but-parseable shape.
    _mock_gemma(
        monkeypatch,
        '```json\n{"people": [\n  {"canonical_name": "Alex", "aliases": [],\n'
        '   "mentions": [\n    {"statement_id": "S1", "quotations": ["x"]\n  },\n'
        '  {"canonical_name": "Maya", "aliases": [], "mentions": []}\n]}\n```',
    )

    result = extract_identities(_case())

    assert any("not valid JSON" in w for w in result["warnings"])
    assert [p["canonical_name"] for p in result["people"]] == ["Alex"]


def test_missing_client_returns_witness_only(monkeypatch):
    monkeypatch.setattr(identity_engine, "ask_gemma", None)

    result = extract_identities(_case())

    assert any("unavailable" in w for w in result["warnings"])
    assert [p["canonical_name"] for p in result["people"]] == ["Alex"]


def test_client_failure_returns_witness_only(monkeypatch):
    def boom(prompt):
        raise ConnectionError("down")

    monkeypatch.setattr(identity_engine, "ask_gemma", boom)

    result = extract_identities(_case())

    assert any("Gemma client failed" in w for w in result["warnings"])
    assert [p["canonical_name"] for p in result["people"]] == ["Alex"]


def test_fabricated_quote_and_alias_are_dropped(monkeypatch):
    reply = json.dumps(
        {
            "people": [
                {
                    "canonical_name": "Maya",
                    "aliases": ["M"],
                    "statement_id": "S1",
                    "quotations": ["Maya was seen by nobody in particular."],
                }
            ],
            "relationships": [
                {
                    "type": "observed",
                    "from_name": "Alex",
                    "to_name": "Maya",
                    "statement_id": "S1",
                    "quotation": "I never said this.",
                }
            ],
        }
    )
    _mock_gemma(monkeypatch, reply)

    result = extract_identities(_case())

    maya = next(p for p in result["people"] if p["canonical_name"] == "Maya")
    assert maya["aliases"] == []
    assert maya["mentions"] == []
    assert result["relationships"] == []
    assert any("Dropped unsupported alias" in w for w in result["warnings"])
