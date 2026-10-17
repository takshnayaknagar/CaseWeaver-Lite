from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import requests
from pydantic import ValidationError

from core.analysis import (
    CaseValidationError,
    apply_what_if,
    case_fingerprint,
    parse_model_json,
    validate_case,
    validate_source_reference,
)
from core.gemma_client import (
    DEFAULT_OLLAMA_HOST,
    DEFAULT_OLLAMA_MODEL,
    GemmaClientError,
    ask_gemma,
)
from core.schemas import Event, HeatmapResult

SAMPLE_CASE_PATH = Path(__file__).resolve().parents[1] / "data" / "sample_case.json"


def _sample_case() -> dict:
    return json.loads(SAMPLE_CASE_PATH.read_text(encoding="utf-8"))


def _sample_event(**overrides) -> dict:
    event = {
        "event_id": "E1",
        "description": "Maya near the exhibition room",
        "time": "8:00 PM",
        "people": ["Maya"],
        "source_statement_id": "S1",
        "source_quote": "I saw Maya near the exhibition room",
    }
    event.update(overrides)
    return event


def test_sample_case_validates_and_fingerprint_is_stable():
    data = _sample_case()
    case = validate_case(data)
    assert case.case_id == "CW-001"
    assert len(case.statements) == 4
    first = case_fingerprint(data)
    second = case_fingerprint(deepcopy(data))
    assert first == second
    assert len(first) == 64


def test_duplicate_statement_ids_fail():
    data = _sample_case()
    data["statements"][1]["statement_id"] = "S1"
    with pytest.raises(CaseValidationError):
        validate_case(data)


def test_unknown_source_id_and_inexact_quote_fail():
    case = validate_case(_sample_case())
    with pytest.raises(CaseValidationError, match="Unknown source_statement_id"):
        validate_source_reference(case, "S9", "I saw Maya near the exhibition room")
    with pytest.raises(CaseValidationError, match="exact substring"):
        validate_source_reference(case, "S1", "this quote is not in the statement")


def test_empty_source_id_or_quote_fail():
    case = validate_case(_sample_case())
    with pytest.raises(CaseValidationError, match="statement id"):
        validate_source_reference(case, "", "I saw Maya near the exhibition room")
    with pytest.raises(CaseValidationError, match="quotation"):
        validate_source_reference(case, "S1", "")


def test_parse_model_json_accepts_object_and_fenced_json():
    assert parse_model_json('{"status": "ok"}') == {"status": "ok"}
    fenced = "```json\n{\"events\": []}\n```"
    assert parse_model_json(fenced) == {"events": []}


def test_parse_model_json_rejects_malformed_and_non_objects():
    with pytest.raises(CaseValidationError, match="not valid JSON"):
        parse_model_json("{not json")
    with pytest.raises(CaseValidationError, match="JSON object"):
        parse_model_json("[1, 2]")
    with pytest.raises(CaseValidationError, match="empty"):
        parse_model_json("   ")


def test_what_if_copies_events_and_does_not_mutate_originals():
    original = [_sample_event()]
    snapshot = deepcopy(original)
    result = apply_what_if(original, {"E1": "8:30 PM"})

    assert original == snapshot
    assert original[0]["time"] == "8:00 PM"
    assert original[0]["source_quote"] == "I saw Maya near the exhibition room"
    assert result["events"][0]["time"] == "8:30 PM"
    assert result["events"][0]["source_quote"] == original[0]["source_quote"]
    assert result["changes"] == [
        {
            "event_id": "E1",
            "field": "time",
            "previous": "8:00 PM",
            "updated": "8:30 PM",
        }
    ]


def test_what_if_empty_overrides_returns_copy_without_changes():
    original = [_sample_event()]
    result = apply_what_if(original, {})
    assert result["changes"] == []
    assert result["events"][0]["time"] == "8:00 PM"
    assert original[0]["time"] == "8:00 PM"


def test_what_if_unknown_event_id_fails():
    with pytest.raises(CaseValidationError, match="Unknown event_id"):
        apply_what_if([_sample_event()], {"MISSING": "9:00 PM"})


def test_what_if_duplicate_event_id_fails():
    original = [_sample_event(), _sample_event(event_id="E1", description="Second sighting")]
    snapshot = deepcopy(original)
    with pytest.raises(CaseValidationError, match="more than once"):
        apply_what_if(original, {"E1": "9:00 PM"})
    assert original == snapshot


def test_what_if_invalid_hypothetical_time_fails():
    with pytest.raises(CaseValidationError, match="Invalid hypothetical event"):
        apply_what_if([_sample_event()], {"E1": "25:99"})
    with pytest.raises(CaseValidationError, match="time must be 12-hour"):
        apply_what_if([_sample_event()], {"E1": "noon-ish"})


def test_heatmap_accepts_symmetric_zero_diagonal_matrix():
    result = HeatmapResult.model_validate(
        {
            "statement_ids": ["S1", "S2"],
            "scores": [[0.0, 0.4], [0.4, 0.0]],
            "findings": [
                {
                    "statement_a_id": "S1",
                    "statement_b_id": "S2",
                    "score": 0.4,
                    "summary": "Possible time conflict",
                }
            ],
        }
    )
    assert result.scores[0][0] == 0.0
    assert result.scores[0][1] == result.scores[1][0]


def test_heatmap_rejects_non_square_nonsymmetric_and_nonzero_diagonal():
    with pytest.raises(ValidationError):
        HeatmapResult.model_validate(
            {"statement_ids": ["S1", "S2"], "scores": [[0.0, 0.1], [0.1]]}
        )
    with pytest.raises(ValidationError):
        HeatmapResult.model_validate(
            {"statement_ids": ["S1", "S2"], "scores": [[0.0, 0.2], [0.3, 0.0]]}
        )
    with pytest.raises(ValidationError):
        HeatmapResult.model_validate(
            {"statement_ids": ["S1", "S2"], "scores": [[0.1, 0.0], [0.0, 0.0]]}
        )


def test_heatmap_rejects_out_of_bounds_scores():
    with pytest.raises(ValidationError, match="between 0 and 1"):
        HeatmapResult.model_validate(
            {"statement_ids": ["S1", "S2"], "scores": [[0.0, 1.5], [1.5, 0.0]]}
        )
    with pytest.raises(ValidationError, match="between 0 and 1"):
        HeatmapResult.model_validate(
            {"statement_ids": ["S1", "S2"], "scores": [[-0.1, 0.0], [0.0, 0.0]]}
        )


def test_heatmap_rejects_unknown_finding_statement_ids():
    with pytest.raises(ValidationError, match="must reference"):
        HeatmapResult.model_validate(
            {
                "statement_ids": ["S1", "S2"],
                "scores": [[0.0, 0.4], [0.4, 0.0]],
                "findings": [
                    {
                        "statement_a_id": "S9",
                        "statement_b_id": "S2",
                        "score": 0.4,
                        "summary": "Bad reference",
                    }
                ],
            }
        )


def test_heatmap_rejects_duplicate_statement_ids():
    with pytest.raises(ValidationError, match="unique"):
        HeatmapResult.model_validate(
            {"statement_ids": ["S1", "S1"], "scores": [[0.0, 0.0], [0.0, 0.0]]}
        )


def test_ask_gemma_uses_default_host_and_model(monkeypatch):
    monkeypatch.delenv("OLLAMA_HOST", raising=False)
    monkeypatch.delenv("OLLAMA_MODEL", raising=False)
    response = MagicMock()
    response.ok = True
    response.json.return_value = {"message": {"content": '{"ok": true}'}}

    with patch("core.gemma_client.requests.post", return_value=response) as post:
        content = ask_gemma("Return JSON")

    assert content == '{"ok": true}'
    assert post.call_args.args[0] == f"{DEFAULT_OLLAMA_HOST}/api/chat"
    assert post.call_args.kwargs["json"]["model"] == DEFAULT_OLLAMA_MODEL
    assert post.call_args.kwargs["json"]["stream"] is False


def test_ask_gemma_raises_on_connection_timeout_http_and_invalid_json(monkeypatch):
    monkeypatch.delenv("OLLAMA_HOST", raising=False)
    monkeypatch.delenv("OLLAMA_MODEL", raising=False)

    with patch(
        "core.gemma_client.requests.post",
        side_effect=requests.ConnectionError("down"),
    ):
        with pytest.raises(GemmaClientError, match="Could not connect"):
            ask_gemma("hello")

    with patch(
        "core.gemma_client.requests.post",
        side_effect=requests.Timeout("slow"),
    ):
        with pytest.raises(GemmaClientError, match="timed out"):
            ask_gemma("hello")

    http_response = MagicMock()
    http_response.ok = False
    http_response.status_code = 500
    http_response.text = "internal error"
    with patch("core.gemma_client.requests.post", return_value=http_response):
        with pytest.raises(GemmaClientError, match="HTTP error 500"):
            ask_gemma("hello")

    bad_json = MagicMock()
    bad_json.ok = True
    bad_json.json.side_effect = ValueError("nope")
    with patch("core.gemma_client.requests.post", return_value=bad_json):
        with pytest.raises(GemmaClientError, match="non-JSON"):
            ask_gemma("hello")


def test_ask_gemma_rejects_malformed_response_structures(monkeypatch):
    monkeypatch.delenv("OLLAMA_HOST", raising=False)
    monkeypatch.delenv("OLLAMA_MODEL", raising=False)

    not_object = MagicMock()
    not_object.ok = True
    not_object.json.return_value = [1, 2]
    with patch("core.gemma_client.requests.post", return_value=not_object):
        with pytest.raises(GemmaClientError, match="invalid JSON response"):
            ask_gemma("hello")

    missing_message = MagicMock()
    missing_message.ok = True
    missing_message.json.return_value = {}
    with patch("core.gemma_client.requests.post", return_value=missing_message):
        with pytest.raises(GemmaClientError, match="message.content"):
            ask_gemma("hello")

    empty_content = MagicMock()
    empty_content.ok = True
    empty_content.json.return_value = {"message": {"content": "   "}}
    with patch("core.gemma_client.requests.post", return_value=empty_content):
        with pytest.raises(GemmaClientError, match="message.content"):
            ask_gemma("hello")


def test_event_time_field_is_used_for_what_if():
    parsed = Event.model_validate(_sample_event())
    assert parsed.time == "8:00 PM"
    assert not hasattr(parsed, "time_start")
