
from copy import deepcopy

from modules.timeline import (
    sort_events,
    sort_events_with_adjustments,
    validate_event,
)


def make_event(event_id, date_value, time_value, quote="At 8:00 PM, I saw Alex."):
    return {
        "event_id": event_id,
        "description": "Witness observed Alex",
        "date": date_value,
        "time": time_value,
        "people": ["Alex"],
        "location": None,
        "source_statement_id": "S1",
        "source_quote": quote,
        "confidence": 0.9,
    }


def test_sort_events_chronologically():
    events = [
        make_event("E2", "2026-10-15", "20:00"),
        make_event("E1", "2026-10-15", "19:45"),
        make_event("E3", "2026-10-15", "20:15"),
    ]

    result = sort_events(events)

    assert [event["event_id"] for event in result] == ["E1", "E2", "E3"]


def test_unknown_times_are_placed_after_known_times():
    events = [
        make_event("UNKNOWN", None, None),
        make_event("KNOWN", "2026-10-15", "20:00"),
        make_event("NO_TIME", "2026-10-15", None),
    ]

    result = sort_events(events)

    assert [event["event_id"] for event in result] == [
        "KNOWN", "UNKNOWN", "NO_TIME"
    ]


def test_equal_timestamps_keep_original_order():
    events = [
        make_event("FIRST", "2026-10-15", "20:00"),
        make_event("SECOND", "2026-10-15", "20:00"),
    ]

    assert [e["event_id"] for e in sort_events(events)] == [
        "FIRST", "SECOND"
    ]


def test_sorting_does_not_mutate_original_list():
    events = [
        make_event("LATER", "2026-10-15", "20:00"),
        make_event("EARLIER", "2026-10-15", "19:00"),
    ]
    original = deepcopy(events)

    sort_events(events)

    assert events == original


def test_what_if_adjustment_sorts_copy_without_mutation():
    events = [
        make_event("E1", "2026-10-15", "19:00"),
        make_event("E2", "2026-10-15", "20:00"),
    ]
    original = deepcopy(events)

    result = sort_events_with_adjustments(events, {"E2": "18:00"})

    assert [e["event_id"] for e in result] == ["E2", "E1"]
    assert events == original


def test_invalid_what_if_time_is_ignored():
    events = [make_event("E1", "2026-10-15", "19:00")]

    result = sort_events_with_adjustments(events, {"E1": "29:75"})

    assert result[0]["time"] == "19:00"


def test_what_if_accepts_canonical_twelve_hour_time():
    events = [make_event("E1", "2026-10-15", "19:00")]

    result = sort_events_with_adjustments(events, {"E1": "8:30 PM"})

    assert result[0]["time"] == "8:30 PM"


def test_quote_must_be_verbatim():
    event = make_event("E1", "2026-10-15", "20:00")
    statements = {"S1": "At 8:00 PM, I saw Alex."}

    assert validate_event(event, statements) is True

    event["source_quote"] = "I saw Alex at 8:00 PM."
    assert validate_event(event, statements) is False


def test_unknown_time_is_allowed():
    event = make_event("E1", None, None)

    assert validate_event(event, {"S1": "At 8:00 PM, I saw Alex."})


def test_confidence_must_be_numeric_in_range():
    event = make_event("E1", "2026-10-15", "20:00")

    assert validate_event(event, {"S1": "At 8:00 PM, I saw Alex."}) is True

    event["confidence"] = "high"
    assert validate_event(event, {"S1": "At 8:00 PM, I saw Alex."}) is False

    event["confidence"] = 1.5
    assert validate_event(event, {"S1": "At 8:00 PM, I saw Alex."}) is False

    event["confidence"] = None
    assert validate_event(event, {"S1": "At 8:00 PM, I saw Alex."}) is True


def test_legacy_time_fields_are_rejected():
    event = make_event("E1", "2026-10-15", "20:00")
    assert validate_event(event, {"S1": "At 8:00 PM, I saw Alex."}) is True
    assert "time_start" not in event
    assert "time_end" not in event
    assert "time_precision" not in event


def test_invalid_date_is_rejected():
    event = make_event("E1", "2026-02-30", "20:00")

    assert validate_event(event, {"S1": "At 8:00 PM, I saw Alex."}) is False


def test_missing_source_statement_is_rejected():
    event = make_event("E1", "2026-10-15", "20:00")

    assert validate_event(event, {}) is False

import json
import sys
import types


def make_gemma_event(statement_id, quote, event_id="S1-E001"):
    return {
        "event_id": event_id,
        "description": "Witness starts security shift",
        "date": "2026-10-15",
        "time": "19:45",
        "people": ["Alex"],
        "location": None,
        "source_statement_id": statement_id,
        "source_quote": quote,
        "confidence": "high",
    }


def install_mock_gemma(monkeypatch, ask_gemma):
    """Provide a fake shared Gemma client for extraction tests."""
    fake_client = types.ModuleType("core.gemma_client")
    fake_client.ask_gemma = ask_gemma
    monkeypatch.setitem(sys.modules, "core.gemma_client", fake_client)


def test_extract_events_accepts_valid_evidence(monkeypatch):
    from modules.timeline import extract_events

    quote = "I started my shift at 7:45 PM."
    event = make_gemma_event("S1", quote)

    install_mock_gemma(
        monkeypatch,
        lambda prompt: json.dumps([event]),
    )

    case_data = {
        "case_id": "CW-001",
        "incident_date": "2026-10-15",
        "statements": [
            {
                "statement_id": "S1",
                "witness_name": "Alex",
                "text": quote,
            }
        ],
    }

    result = extract_events(case_data)

    assert len(result) == 1
    assert result[0]["source_quote"] == quote
    assert result[0]["source_statement_id"] == "S1"
    assert result[0]["time"] == "19:45"
    assert result[0]["confidence"] == 0.9
    assert "time_start" not in result[0]
    assert "time_end" not in result[0]
    assert "time_precision" not in result[0]


def test_extract_events_rejects_fabricated_quote(monkeypatch):
    from modules.timeline import extract_events

    event = make_gemma_event("S1", "I saw the suspect.")

    install_mock_gemma(
        monkeypatch,
        lambda prompt: json.dumps([event]),
    )

    result = extract_events({
        "incident_date": "2026-10-15",
        "statements": [
            {
                "statement_id": "S1",
                "text": "I started my shift at 7:45 PM.",
            }
        ],
    })

    assert result == []


def test_extract_events_handles_invalid_json(monkeypatch):
    from modules.timeline import extract_events

    install_mock_gemma(monkeypatch, lambda prompt: "not valid JSON")

    result = extract_events({
        "statements": [
            {"statement_id": "S1", "text": "I started my shift."}
        ]
    })

    assert result == []




def test_extract_events_continues_after_client_failure(monkeypatch):
    from modules.timeline import extract_events

    quote = "I entered the museum at 8:05 PM."
    valid_event = make_gemma_event(
        "S2", quote, event_id="S2-E001"
    )
    valid_event["date"] = "2026-10-15"
    valid_event["time"] = "20:05"

    def fake_ask_gemma(prompt):
        if "First witness statement." in prompt:
            raise ConnectionError("Simulated model connection failure")
        return json.dumps([valid_event])

    install_mock_gemma(monkeypatch, fake_ask_gemma)

    result = extract_events({
        "incident_date": "2026-10-15",
        "statements": [
            {"statement_id": "S1", "text": "First witness statement."},
            {"statement_id": "S2", "text": quote},
        ],
    })

    assert len(result) == 1
    assert result[0]["source_statement_id"] == "S2"
