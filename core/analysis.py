from __future__ import annotations

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
