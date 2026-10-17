from __future__ import annotations

import copy
import hashlib
import json
from typing import Union

from pydantic import ValidationError

from core.schemas import (
    Case,
    Claim,
    Event,
    Inconsistency,
    Person,
    Relationship,
)

SourcedModel = Union[Event, Person, Relationship, Claim, Inconsistency]


class CaseValidationError(ValueError):
    """Raised when canonical case data or sourced evidence fails validation."""


def validate_case(case_data: dict) -> Case:
    if not isinstance(case_data, dict):
        raise CaseValidationError("case_data must be a dictionary")
    try:
        return Case.model_validate(case_data)
    except ValidationError as exc:
        raise CaseValidationError(f"Invalid case data: {exc}") from exc


def case_fingerprint(case_data: dict) -> str:
    case = validate_case(case_data)
    canonical = json.dumps(
        case.model_dump(mode="json"),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def validate_source_reference(case: Case, statement_id: str, quote: str) -> None:
    if not statement_id:
        raise CaseValidationError("source statement id must be a non-empty string")
    if not quote:
        raise CaseValidationError("source quotation must be a non-empty string")

    statement = case.statement_map().get(statement_id)
    if statement is None:
        known = ", ".join(sorted(case.statement_ids()))
        raise CaseValidationError(
            f"Unknown source_statement_id {statement_id!r}. Known ids: {known}"
        )
    if quote not in statement.text:
        raise CaseValidationError(
            f"source_quote is not an exact substring of statement {statement_id!r}: {quote!r}"
        )


def validate_sourced_model(case: Case, item: SourcedModel) -> None:
    if isinstance(item, (Event, Relationship, Claim)):
        validate_source_reference(case, item.source_statement_id, item.source_quote)
        return

    if isinstance(item, (Person, Inconsistency)):
        for statement_id, quote in zip(
            item.source_statement_ids, item.source_quotes, strict=True
        ):
            validate_source_reference(case, statement_id, quote)
        if isinstance(item, Inconsistency):
            for claim in item.claims:
                validate_sourced_model(case, claim)
        return

    raise CaseValidationError(f"Unsupported sourced model type: {type(item)!r}")


def parse_model_json(text: str) -> dict:
    if not isinstance(text, str) or not text.strip():
        raise CaseValidationError("model output is empty; expected a JSON object")

    payload = _strip_markdown_fences(text)
    try:
        parsed = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise CaseValidationError(
            f"model output is not valid JSON: {exc.msg}"
        ) from exc

    if not isinstance(parsed, dict):
        raise CaseValidationError(
            "model output must be a JSON object, not "
            f"{type(parsed).__name__}; refusing to fabricate a wrapper"
        )
    return parsed


def apply_what_if(events: list[dict], time_overrides: dict[str, str]) -> dict:
    """Apply hypothetical Event.time values on a deep copy of extracted events.

    Original `events` are never mutated. Case statements and source quotations
    are not accepted as inputs and cannot be changed here.
    """
    if not isinstance(events, list):
        raise CaseValidationError("events must be a list of event dictionaries")
    if not isinstance(time_overrides, dict):
        raise CaseValidationError("time_overrides must be a dictionary of event_id to time")

    counts: dict[str, int] = {}
    for event in events:
        if not isinstance(event, dict):
            raise CaseValidationError("each event must be a dictionary")
        event_id = event.get("event_id")
        if isinstance(event_id, str) and event_id:
            counts[event_id] = counts.get(event_id, 0) + 1
    duplicated = sorted(event_id for event_id in time_overrides if counts.get(event_id, 0) > 1)
    if duplicated:
        raise CaseValidationError(
            f"event_id appears more than once in events: {', '.join(duplicated)}; "
            "cannot apply an unambiguous time override"
        )

    copied = copy.deepcopy(events)
    remaining = {str(key): value for key, value in time_overrides.items()}
    changes: list[dict] = []

    for event in copied:
        if not isinstance(event, dict):
            raise CaseValidationError("each event must be a dictionary")
        event_id = event.get("event_id")
        if event_id is None or event_id == "" or event_id not in remaining:
            continue
        previous = event.get("time")
        event["time"] = remaining.pop(event_id)
        changes.append(
            {
                "event_id": event_id,
                "field": "time",
                "previous": previous,
                "updated": event["time"],
            }
        )

    if remaining:
        unknown = ", ".join(sorted(remaining))
        raise CaseValidationError(
            f"Unknown event_id in time_overrides: {unknown}. "
            "Events without event_id cannot be overridden."
        )

    validated: list[dict] = []
    for event in copied:
        try:
            validated.append(Event.model_validate(event).model_dump(mode="json"))
        except ValidationError as exc:
            raise CaseValidationError(f"Invalid hypothetical event: {exc}") from exc

    return {"events": validated, "changes": changes}


def _strip_markdown_fences(text: str) -> str:
    stripped = text.strip()
    if not stripped.startswith("```"):
        return stripped
    lines = stripped.splitlines()
    if len(lines) >= 2 and lines[-1].strip() == "```":
        return "\n".join(lines[1:-1]).strip()
    return "\n".join(lines[1:]).strip()
