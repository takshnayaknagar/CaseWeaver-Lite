from __future__ import annotations

import re
from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

_TIME_12H = r"^(?:1[0-2]|0?[1-9]):[0-5]\d\s?(?:AM|PM)$"
_TIME_24H = r"^(?:[01]?\d|2[0-3]):[0-5]\d$"


class CaseWeaverModel(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)


class Statement(CaseWeaverModel):
    statement_id: str = Field(min_length=1)
    witness_name: str = Field(min_length=1)
    text: str = Field(min_length=1)


class Case(CaseWeaverModel):
    case_id: str = Field(min_length=1)
    case_name: str = Field(min_length=1)
    incident_date: date
    statements: list[Statement] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_statement_ids(self) -> "Case":
        ids = [statement.statement_id for statement in self.statements]
        duplicates = sorted({item for item in ids if ids.count(item) > 1})
        if duplicates:
            raise ValueError(
                f"statement_id values must be unique; duplicates: {duplicates}"
            )
        return self

    def statement_ids(self) -> set[str]:
        return {statement.statement_id for statement in self.statements}

    def statement_map(self) -> dict[str, Statement]:
        return {statement.statement_id: statement for statement in self.statements}


class Event(CaseWeaverModel):
    event_id: Optional[str] = None
    description: str = Field(min_length=1)
    date: Optional[date] = None
    time: Optional[str] = None
    location: Optional[str] = None
    people: list[str] = Field(default_factory=list)
    source_statement_id: str = Field(min_length=1)
    source_quote: str = Field(min_length=1)
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)

    @field_validator("date", mode="before")
    @classmethod
    def parse_optional_date(cls, value: object) -> object:
        if value is None or value == "":
            return None
        if isinstance(value, date) and not isinstance(value, datetime):
            return value
        if isinstance(value, str):
            try:
                return date.fromisoformat(value.strip())
            except ValueError as exc:
                raise ValueError("date must be YYYY-MM-DD or omitted if unknown") from exc
        return value

    @field_validator("time")
    @classmethod
    def validate_time(cls, value: Optional[str]) -> Optional[str]:
        if value is None or value == "":
            return None
        compact = value.strip()
        if re.fullmatch(_TIME_12H, compact, flags=re.IGNORECASE) or re.fullmatch(
            _TIME_24H, compact
        ):
            return compact
        raise ValueError(
            "time must be 12-hour (e.g. 8:00 PM) or 24-hour (e.g. 20:00), or omitted if unknown"
        )

    @field_validator("location")
    @classmethod
    def empty_location_as_none(cls, value: Optional[str]) -> Optional[str]:
        if value is None or value == "":
            return None
        return value

    @field_validator("event_id")
    @classmethod
    def empty_event_id_as_none(cls, value: Optional[str]) -> Optional[str]:
        if value is None or value == "":
            return None
        return value


class Person(CaseWeaverModel):
    name: str = Field(min_length=1)
    role: Optional[str] = None
    aliases: list[str] = Field(default_factory=list)
    source_statement_ids: list[str] = Field(min_length=1)
    source_quotes: list[str] = Field(min_length=1)

    @field_validator("role")
    @classmethod
    def empty_role_as_none(cls, value: Optional[str]) -> Optional[str]:
        if value is None or value == "":
            return None
        return value

    @model_validator(mode="after")
    def matching_source_lists(self) -> "Person":
        if len(self.source_statement_ids) != len(self.source_quotes):
            raise ValueError(
                "source_statement_ids and source_quotes must have the same length"
            )
        if any(not item for item in self.source_statement_ids):
            raise ValueError("source_statement_ids must not contain empty values")
        if any(not item for item in self.source_quotes):
            raise ValueError("source_quotes must not contain empty values")
        return self


class Relationship(CaseWeaverModel):
    person_a: str = Field(min_length=1)
    person_b: str = Field(min_length=1)
    description: str = Field(min_length=1)
    source_statement_id: str = Field(min_length=1)
    source_quote: str = Field(min_length=1)


class Claim(CaseWeaverModel):
    claim_id: Optional[str] = None
    text: str = Field(min_length=1)
    speaker: Optional[str] = None
    source_statement_id: str = Field(min_length=1)
    source_quote: str = Field(min_length=1)

    @field_validator("claim_id", "speaker")
    @classmethod
    def empty_optional_as_none(cls, value: Optional[str]) -> Optional[str]:
        if value is None or value == "":
            return None
        return value


class Inconsistency(CaseWeaverModel):
    description: str = Field(min_length=1)
    claims: list[Claim] = Field(min_length=1)
    source_statement_ids: list[str] = Field(min_length=1)
    source_quotes: list[str] = Field(min_length=1)

    @model_validator(mode="after")
    def matching_source_lists(self) -> "Inconsistency":
        if len(self.source_statement_ids) != len(self.source_quotes):
            raise ValueError(
                "source_statement_ids and source_quotes must have the same length"
            )
        if any(not item for item in self.source_statement_ids):
            raise ValueError("source_statement_ids must not contain empty values")
        if any(not item for item in self.source_quotes):
            raise ValueError("source_quotes must not contain empty values")
        return self


class HeatmapFinding(CaseWeaverModel):
    """A pairwise discrepancy note. The score is a potential signal, not proof of dishonesty."""

    statement_a_id: str = Field(min_length=1)
    statement_b_id: str = Field(min_length=1)
    score: float = Field(ge=0.0, le=1.0)
    summary: str = Field(min_length=1)


class HeatmapResult(CaseWeaverModel):
    """Square statement-by-statement discrepancy heatmap.

    `scores[i][j]` is a potential discrepancy signal in [0, 1] between
    `statement_ids[i]` and `statement_ids[j]`. The matrix must be symmetric.
    A statement compared with itself must have score 0. These scores are not
    proof of dishonesty and are not credibility scores.
    """

    statement_ids: list[str] = Field(min_length=1)
    scores: list[list[float]]
    findings: list[HeatmapFinding] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_matrix(self) -> "HeatmapResult":
        ids = self.statement_ids
        if any(not item for item in ids):
            raise ValueError("statement_ids must not contain empty values")
        if len(ids) != len(set(ids)):
            raise ValueError("statement_ids must be unique")

        n = len(ids)
        if len(self.scores) != n:
            raise ValueError(
                f"scores must be a square matrix of size {n}x{n} to match statement_ids"
            )
        for i, row in enumerate(self.scores):
            if len(row) != n:
                raise ValueError(
                    f"scores must be a square matrix of size {n}x{n}; row {i} has length {len(row)}"
                )
        for i, row in enumerate(self.scores):
            for j, value in enumerate(row):
                if value < 0.0 or value > 1.0:
                    raise ValueError(
                        f"scores[{i}][{j}] must be between 0 and 1 inclusive, got {value}"
                    )
                if i == j and value != 0.0:
                    raise ValueError(
                        f"scores[{i}][{j}] must be 0 for a statement compared with itself"
                    )
                if self.scores[j][i] != value:
                    raise ValueError(
                        f"scores must be symmetric: scores[{i}][{j}]={value} "
                        f"!= scores[{j}][{i}]={self.scores[j][i]}"
                    )

        allowed = set(ids)
        for finding in self.findings:
            if finding.statement_a_id not in allowed or finding.statement_b_id not in allowed:
                raise ValueError(
                    "heatmap findings must reference statement_ids present on the heatmap"
                )
        return self
