"""CaseWeaver Lite — FastAPI Backend.

Thin REST wrapper around the teammate analysis modules.
Does not reimplement analysis logic; calls the real functions directly.
In-memory case store for the current server session only.
"""

from __future__ import annotations

import copy
import sys
import traceback
import uuid
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Ensure the project root is on sys.path so `modules.*` imports work
# regardless of where uvicorn is invoked from.
# ---------------------------------------------------------------------------
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# ---------------------------------------------------------------------------
# Safe teammate module imports
# ---------------------------------------------------------------------------
_identity_fn = None
_identity_err: str | None = None
try:
    from modules.identity_engine import extract_identities
    _identity_fn = extract_identities
except ImportError as exc:
    _identity_err = str(exc)

_inconsistency_fn = None
_inconsistency_err: str | None = None
try:
    from modules.inconsistency_detector import detect_inconsistencies
    _inconsistency_fn = detect_inconsistencies
except ImportError as exc:
    _inconsistency_err = str(exc)

_timeline_fn = None
_timeline_err: str | None = None
try:
    from modules.timeline import extract_events  # type: ignore[import-not-found]
    _timeline_fn = extract_events
except ImportError as exc:
    _timeline_err = "Module not yet created by team"

_gemma_fn = None
_gemma_err: str | None = None
try:
    from core.gemma_client import ask_gemma  # type: ignore[import-not-found]
    _gemma_fn = ask_gemma
except ImportError:
    _gemma_err = "Module not yet created by team"

# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------
app = FastAPI(
    title="CaseWeaver Lite API",
    description="REST backend for the CaseWeaver Lite evidence-organization tool.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",   # Vite default
        "http://localhost:3000",
        "http://localhost:5174",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# In-memory case store (session-only — lost on server restart)
# ---------------------------------------------------------------------------
SAMPLE_CASE: dict[str, Any] = {
    "case_id": "CW-001",
    "case_name": "State v. Sterling",
    "incident_date": "2026-10-15",
    "summary": "Investigation into the incident at 5th & Pine near the Red Truck warehouse.",
    "is_demo": True,
    "statements": [
        {
            "statement_id": "ST-001",
            "witness_name": "Jane Doe",
            "role": "Bystander",
            "interview_date": "2026-10-15",
            "text": "I saw a man, around 6 feet tall, standing next to a red sedan at the intersection at 14:00. I saw him arrive at the truck.",
        },
        {
            "statement_id": "ST-002",
            "witness_name": "John Smith",
            "role": "Shopkeeper",
            "interview_date": "2026-10-16",
            "text": 'He was a shorter man, maybe 5\'8", and he got into a dark blue truck before leaving around 14:05. No, he was definitely on the sidewalk when I walked past.',
        },
        {
            "statement_id": "ST-003",
            "witness_name": "D. Miller",
            "role": "Delivery Driver",
            "interview_date": "2026-10-15",
            "text": "At 14:02, I saw someone standing motionless near the Red Truck location. He just stood there for a couple of minutes.",
        },
        {
            "statement_id": "ST-004",
            "witness_name": "J. Patel",
            "role": "Pedestrian",
            "interview_date": "2026-10-15",
            "text": "At 14:05, I walked past D. Miller near the Red Truck. At 14:06, he was definitely walking towards the intersection.",
        },
    ],
}

# shortcut: single-case store; upgrade to dict[str, case] when multi-case is needed
_active_case: dict[str, Any] = copy.deepcopy(SAMPLE_CASE)

# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class StatementIn(BaseModel):
    witness_name: str = Field(..., min_length=1)
    text: str = Field(..., min_length=1)
    statement_id: str | None = None
    role: str | None = None
    interview_date: str | None = None


class CaseIn(BaseModel):
    case_id: str = Field(default="CW-001")
    case_name: str = Field(default="Untitled Case")
    incident_date: str | None = None
    summary: str | None = None
    statements: list[StatementIn] = Field(default_factory=list)


class ModuleStatus(BaseModel):
    available: bool
    source: str
    error: str | None = None


class HealthResponse(BaseModel):
    status: str = "ok"
    modules: dict[str, ModuleStatus]


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/api/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        modules={
            "identity": ModuleStatus(
                available=_identity_fn is not None,
                source="modules.identity_engine",
                error=_identity_err,
            ),
            "inconsistency": ModuleStatus(
                available=_inconsistency_fn is not None,
                source="modules.inconsistency_detector",
                error=_inconsistency_err,
            ),
            "timeline": ModuleStatus(
                available=_timeline_fn is not None,
                source="modules.timeline",
                error=_timeline_err,
            ),
            "gemma": ModuleStatus(
                available=_gemma_fn is not None,
                source="core.gemma_client",
                error=_gemma_err,
            ),
        },
    )


@app.get("/api/case")
def get_case() -> dict[str, Any]:
    """Return the current in-memory case."""
    return _active_case


@app.put("/api/case")
def replace_case(body: CaseIn) -> dict[str, Any]:
    """Replace the active case entirely."""
    global _active_case
    _active_case = body.model_dump(exclude_none=True)
    _active_case.setdefault("statements", [])
    return _active_case


@app.post("/api/case/reset")
def reset_case() -> dict[str, Any]:
    """Reset to the built-in demo case."""
    global _active_case
    _active_case = copy.deepcopy(SAMPLE_CASE)
    return _active_case


@app.post("/api/case/statements")
def add_statement(body: StatementIn) -> dict[str, Any]:
    """Append a witness statement.  Auto-generates an ID if omitted."""
    stmts = _active_case.setdefault("statements", [])
    existing_ids = {str(s.get("statement_id", "")) for s in stmts}

    custom_id = (body.statement_id or "").strip()
    if custom_id and custom_id in existing_ids:
        raise HTTPException(
            status_code=409,
            detail=f"Statement ID '{custom_id}' already exists.",
        )

    if custom_id:
        assigned_id = custom_id
    else:
        idx = len(stmts) + 1
        while f"ST-{idx:03d}" in existing_ids:
            idx += 1
        assigned_id = f"ST-{idx:03d}"

    stmt: dict[str, Any] = {
        "statement_id": assigned_id,
        "witness_name": body.witness_name.strip(),
        "text": body.text.strip(),
    }
    if body.role and body.role.strip():
        stmt["role"] = body.role.strip()
    if body.interview_date and body.interview_date.strip():
        stmt["interview_date"] = body.interview_date.strip()

    stmts.append(stmt)
    return stmt


@app.delete("/api/case/statements/{statement_id}")
def delete_statement(statement_id: str) -> dict[str, Any]:
    """Remove a witness statement from the active case by ID."""
    stmts = _active_case.setdefault("statements", [])
    for position, stmt in enumerate(stmts):
        if str(stmt.get("statement_id", "")) == statement_id:
            del stmts[position]
            return {"deleted": statement_id}
    raise HTTPException(
        status_code=404,
        detail=f"Statement ID '{statement_id}' not found.",
    )


# ---- Analysis endpoints --------------------------------------------------

@app.post("/api/analyze/identities")
def analyze_identities() -> dict[str, Any]:
    if _identity_fn is None:
        raise HTTPException(
            status_code=503,
            detail=f"Identity module unavailable: {_identity_err}",
        )
    try:
        return _identity_fn(copy.deepcopy(_active_case))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/analyze/inconsistencies")
def analyze_inconsistencies() -> list[dict[str, Any]]:
    if _inconsistency_fn is None:
        raise HTTPException(
            status_code=503,
            detail=f"Inconsistency module unavailable: {_inconsistency_err}",
        )
    try:
        return _inconsistency_fn(copy.deepcopy(_active_case))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/analyze/timeline")
def analyze_timeline() -> list[dict[str, Any]]:
    if _timeline_fn is None:
        raise HTTPException(
            status_code=503,
            detail=f"Timeline module unavailable: {_timeline_err}",
        )
    try:
        return _timeline_fn(copy.deepcopy(_active_case))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/analyze/all")
def analyze_all() -> dict[str, Any]:
    """Run every available analysis module; return partial results on failure."""
    case_copy = copy.deepcopy(_active_case)
    results: dict[str, Any] = {}

    if _identity_fn is not None:
        try:
            results["identities"] = _identity_fn(case_copy)
        except Exception as exc:
            results["identities"] = {"error": str(exc)}
    else:
        results["identities"] = {"error": _identity_err}

    if _inconsistency_fn is not None:
        try:
            results["inconsistencies"] = _inconsistency_fn(case_copy)
        except Exception as exc:
            results["inconsistencies"] = {"error": str(exc)}
    else:
        results["inconsistencies"] = {"error": _inconsistency_err}

    if _timeline_fn is not None:
        try:
            results["timeline"] = _timeline_fn(case_copy)
        except Exception as exc:
            results["timeline"] = {"error": str(exc)}
    else:
        results["timeline"] = {"error": _timeline_err}

    return results
