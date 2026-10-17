"""CaseWeaver Lite - Streamlit Frontend Dashboard.

Phase 1: App Foundation
- Sidebar with Case Selector & Navigation
- System Disclaimer Banner (Non-guilt principle)
- Backend Module Availability & Integration Status
- Fictional Sample Case Loader (State v. Sterling)
- Dark Mode Themed Layout
"""

from __future__ import annotations

import copy
import json
from typing import Any

import streamlit as st

# ==============================================================================
# Page Configuration & Dark Theme Styling
# ==============================================================================
st.set_page_config(
    page_title="CaseWeaver Lite",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded",
)

CUSTOM_CSS = """
<style>
/* Main Dark Theme Palette */
[data-testid="stAppViewContainer"] {
    background-color: #0b111e;
    color: #e2e8f0;
}
[data-testid="stSidebar"] {
    background-color: #080d17;
    border-right: 1px solid #1e293b;
}

/* Card Styling */
.cw-card {
    background-color: #162032;
    border: 1px solid #1e293b;
    border-radius: 8px;
    padding: 1.2rem;
    margin-bottom: 1rem;
    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.2);
}

.cw-card-title {
    font-size: 0.9rem;
    color: #94a3b8;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-bottom: 0.4rem;
}

.cw-card-value {
    font-size: 1.8rem;
    font-weight: 700;
    color: #38bdf8;
    margin-bottom: 0.2rem;
}

.cw-card-sub {
    font-size: 0.8rem;
    color: #64748b;
}

/* Disclaimer Banner */
.cw-disclaimer {
    background-color: rgba(245, 158, 11, 0.12);
    border-left: 4px solid #f59e0b;
    border-radius: 4px;
    padding: 0.75rem 1rem;
    margin-bottom: 1.25rem;
    color: #fcd34d;
    font-size: 0.875rem;
    display: flex;
    align-items: center;
    gap: 0.5rem;
}

/* Badges */
.cw-badge-demo {
    background-color: #0369a1;
    color: #e0f2fe;
    font-size: 0.75rem;
    padding: 0.2rem 0.55rem;
    border-radius: 9999px;
    font-weight: 600;
    display: inline-block;
}

.cw-badge-ok {
    background-color: rgba(16, 185, 129, 0.2);
    color: #34d399;
    border: 1px solid #059669;
    font-size: 0.75rem;
    padding: 0.15rem 0.5rem;
    border-radius: 4px;
    font-weight: 500;
}

.cw-badge-missing {
    background-color: rgba(239, 68, 68, 0.2);
    color: #f87171;
    border: 1px solid #dc2626;
    font-size: 0.75rem;
    padding: 0.15rem 0.5rem;
    border-radius: 4px;
    font-weight: 500;
}
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# ==============================================================================
# Shared Backend Module Detection & Safe Imports
# ==============================================================================
MODULE_STATUS = {
    "identity": {"available": False, "source": None, "fn": None, "error": None},
    "inconsistency": {"available": False, "source": None, "fn": None, "error": None},
    "timeline": {"available": False, "source": None, "fn": None, "error": None},
    "gemma": {"available": False, "source": None, "fn": None, "error": None},
}

# 1. Identity Module
try:
    from modules.identity_engine import extract_identities  # type: ignore
    MODULE_STATUS["identity"] = {"available": True, "source": "modules.identity_engine", "fn": extract_identities, "error": None}
except ImportError:
    try:
        from modules.identity import extract_identities  # type: ignore
        MODULE_STATUS["identity"] = {"available": True, "source": "modules.identity", "fn": extract_identities, "error": None}
    except ImportError as e:
        MODULE_STATUS["identity"] = {"available": False, "source": "modules/identity_engine.py", "fn": None, "error": str(e)}

# 2. Inconsistency Module
try:
    from modules.inconsistency_detector import detect_inconsistencies  # type: ignore
    MODULE_STATUS["inconsistency"] = {"available": True, "source": "modules.inconsistency_detector", "fn": detect_inconsistencies, "error": None}
except ImportError:
    try:
        from modules.inconsistencies import detect_inconsistencies  # type: ignore
        MODULE_STATUS["inconsistency"] = {"available": True, "source": "modules.inconsistencies", "fn": detect_inconsistencies, "error": None}
    except ImportError as e:
        MODULE_STATUS["inconsistency"] = {"available": False, "source": "modules/inconsistency_detector.py", "fn": None, "error": str(e)}

# 3. Timeline Module
try:
    from modules.timeline import extract_events  # type: ignore
    MODULE_STATUS["timeline"] = {"available": True, "source": "modules.timeline", "fn": extract_events, "error": None}
except ImportError as e:
    MODULE_STATUS["timeline"] = {"available": False, "source": "modules/timeline.py", "fn": None, "error": "Module not yet created by team"}

# 4. Gemma Client
try:
    from core.gemma_client import ask_gemma  # type: ignore
    MODULE_STATUS["gemma"] = {"available": True, "source": "core.gemma_client", "fn": ask_gemma, "error": None}
except ImportError as e:
    MODULE_STATUS["gemma"] = {"available": False, "source": "core/gemma_client.py", "fn": None, "error": "Module not yet created by team"}


# ==============================================================================
# Fictional Sample Case Data (Explicitly Labeled Demo Data)
# ==============================================================================
SAMPLE_CASES: dict[str, dict[str, Any]] = {
    "State v. Sterling (CW-001) [Demo]": {
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
                "text": "He was a shorter man, maybe 5'8\", and he got into a dark blue truck before leaving around 14:05. No, he was definitely on the sidewalk when I walked past.",
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
}


# ==============================================================================
# Session State Initialization
# ==============================================================================
if "active_case" not in st.session_state:
    st.session_state.active_case = copy.deepcopy(SAMPLE_CASES["State v. Sterling (CW-001) [Demo]"])

if "analysis_results" not in st.session_state:
    st.session_state.analysis_results = {
        "identities": None,
        "inconsistencies": None,
        "timeline": None,
        "is_stale": False,
    }


# ==============================================================================
# Sidebar Layout
# ==============================================================================
with st.sidebar:
    st.markdown("## ⚖️ CaseWeaver Lite")
    st.caption("Investigative Evidence & Timeline Assistant")
    st.divider()

    st.subheader("Active Case")
    case_choice = st.selectbox(
        "Select Case File:",
        options=list(SAMPLE_CASES.keys()) + ["+ New Blank Case Entry"],
        index=0,
        help="Select a fictional pre-loaded sample case or enter custom case data.",
    )

    if case_choice == "+ New Blank Case Entry":
        if st.session_state.active_case.get("case_id") != "NEW":
            st.session_state.active_case = {
                "case_id": "NEW",
                "case_name": "Custom Investigation",
                "incident_date": "2026-10-17",
                "summary": "User entered case",
                "is_demo": False,
                "statements": [],
            }
            st.session_state.analysis_results["is_stale"] = True
    else:
        if st.session_state.active_case.get("case_name") != SAMPLE_CASES[case_choice]["case_name"]:
            st.session_state.active_case = copy.deepcopy(SAMPLE_CASES[case_choice])
            st.session_state.analysis_results = {
                "identities": None,
                "inconsistencies": None,
                "timeline": None,
                "is_stale": False,
            }

    st.divider()

    st.subheader("Navigation")
    active_nav = st.radio(
        "Navigate Workspace:",
        options=["Overview", "Timeline", "Evidence", "Contradictions", "What-If Analysis"],
        index=0,
        label_visibility="collapsed",
    )

    st.divider()
    # Teammate Module Status in Sidebar
    st.subheader("Backend Integrations")
    for mod_key, mod_info in MODULE_STATUS.items():
        status_badge = (
            '<span class="cw-badge-ok">Available</span>'
            if mod_info["available"]
            else '<span class="cw-badge-missing">Unavailable</span>'
        )
        st.markdown(
            f"**{mod_key.capitalize()}**: {status_badge}<br><small style='color:#64748b;'>{mod_info['source']}</small>",
            unsafe_allow_html=True,
        )


# ==============================================================================
# Main View & Mandatory Disclaimer
# ==============================================================================
st.markdown(
    """
    <div class="cw-disclaimer">
        <span>⚠️</span>
        <span><strong>AI-assisted evidence organization.</strong> Findings require human verification and are not conclusions of guilt.</span>
    </div>
    """,
    unsafe_allow_html=True,
)

current_case = st.session_state.active_case
is_demo = current_case.get("is_demo", False)

# Top Case Header
col_header_1, col_header_2 = st.columns([3, 1])
with col_header_1:
    demo_badge = '<span class="cw-badge-demo">FICTIONAL DEMO CASE</span>' if is_demo else ""
    st.markdown(
        f"<h2>{current_case.get('case_name', 'Untitled Case')} {demo_badge}</h2>",
        unsafe_allow_html=True,
    )
    st.caption(
        f"Case ID: {current_case.get('case_id')} | Incident Date: {current_case.get('incident_date')} | "
        f"{len(current_case.get('statements', []))} Witness Statements"
    )

with col_header_2:
    if st.button("🔄 Reset to Default Sample", use_container_width=True):
        st.session_state.active_case = copy.deepcopy(SAMPLE_CASES["State v. Sterling (CW-001) [Demo]"])
        st.session_state.analysis_results = {
            "identities": None,
            "inconsistencies": None,
            "timeline": None,
            "is_stale": False,
        }
        st.rerun()


# ==============================================================================
# View: Overview (Phase 1 Foundation)
# ==============================================================================
if active_nav == "Overview":
    st.markdown("### Metric Subheader")
    col1, col2, col3 = st.columns(3)

    num_stmts = len(current_case.get("statements", []))
    with col1:
        st.markdown(
            f"""
            <div class="cw-card">
                <div class="cw-card-title">Witness Statements Analysed</div>
                <div class="cw-card-value">{num_stmts}</div>
                <div class="cw-card-sub">Recorded Statements</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col2:
        st.markdown(
            """
            <div class="cw-card">
                <div class="cw-card-title">Extracted Events</div>
                <div class="cw-card-value">--</div>
                <div class="cw-card-sub">Pending Module Analysis</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col3:
        st.markdown(
            """
            <div class="cw-card">
                <div class="cw-card-title">Active Contradictions</div>
                <div class="cw-card-value">--</div>
                <div class="cw-card-sub">Differences Requiring Review</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("### Case File Details")
    with st.expander("📝 View & Edit Case Metadata", expanded=False):
        c_id = st.text_input("Case ID", value=current_case.get("case_id", ""))
        c_name = st.text_input("Case Name", value=current_case.get("case_name", ""))
        c_date = st.text_input("Incident Date", value=current_case.get("incident_date", ""))
        c_summary = st.text_area("Summary", value=current_case.get("summary", ""))
        if st.button("Save Metadata"):
            current_case["case_id"] = c_id
            current_case["case_name"] = c_name
            current_case["incident_date"] = c_date
            current_case["summary"] = c_summary
            st.success("Metadata updated.")

    if st.session_state.get("statement_status_msg"):
        st.success(st.session_state.statement_status_msg)
        st.session_state.statement_status_msg = None

    with st.expander("➕ Add Witness Statement", expanded=False):
        with st.form("add_statement_form", clear_on_submit=True):
            col_f1, col_f2 = st.columns(2)
            with col_f1:
                new_witness = st.text_input("Witness Name *", placeholder="e.g. Marcus Vance")
                new_role = st.text_input("Witness Role (Optional)", placeholder="e.g. Bystander, Security Guard")
            with col_f2:
                new_id = st.text_input("Statement ID (Optional, auto-generated if blank)", placeholder="e.g. ST-005")
                new_date = st.text_input("Interview Date/Time (Optional)", placeholder="e.g. 2026-10-15 15:00")

            new_text = st.text_area("Verbatim Statement Text *", placeholder="Exact verbatim statement as given by the witness...")

            submit_stmt = st.form_submit_button("Add Witness Statement", type="primary", use_container_width=True)
            if submit_stmt:
                witness_clean = new_witness.strip()
                text_clean = new_text.strip()
                if not witness_clean:
                    st.error("Witness Name is required and cannot be empty.")
                elif not text_clean:
                    st.error("Verbatim Statement Text is required and cannot be empty.")
                else:
                    existing_stmts = current_case.setdefault("statements", [])
                    existing_ids = {
                        str(s.get("statement_id") or s.get("id") or "").strip()
                        for s in existing_stmts
                    }
                    custom_id = new_id.strip()
                    if custom_id and custom_id in existing_ids:
                        st.error(f"Statement ID '{custom_id}' already exists in this case. Please provide a unique ID or leave blank to auto-generate.")
                    else:
                        if custom_id:
                            assigned_id = custom_id
                        else:
                            idx = len(existing_stmts) + 1
                            while f"ST-{idx:03d}" in existing_ids:
                                idx += 1
                            assigned_id = f"ST-{idx:03d}"

                        new_statement: dict[str, Any] = {
                            "statement_id": assigned_id,
                            "witness_name": witness_clean,
                            "text": text_clean,
                        }
                        if new_role.strip():
                            new_statement["role"] = new_role.strip()
                        if new_date.strip():
                            new_statement["interview_date"] = new_date.strip()

                        existing_stmts.append(new_statement)
                        st.session_state.analysis_results["is_stale"] = True
                        st.session_state.statement_status_msg = f"Witness statement '{assigned_id}' for '{witness_clean}' was successfully added."
                        st.rerun()

    st.markdown("### Recorded Statements (Workspace Preview)")
    if current_case.get("statements"):
        for stmt in current_case["statements"]:
            with st.container():
                st.markdown(
                    f"""
                    <div class="cw-card">
                        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom: 0.5rem;">
                            <strong style="color:#38bdf8;">{stmt.get('witness_name', 'Unknown')}</strong>
                            <span style="color:#94a3b8; font-size:0.8rem;">ID: {stmt.get('statement_id')}</span>
                        </div>
                        <p style="margin: 0; font-size: 0.95rem; color: #cbd5e1; font-style: italic;">
                            "{stmt.get('text', '')}"
                        </p>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
    else:
        st.info("No witness statements in this case file yet. Use the sidebar to load the sample case or enter statements.")

    # Analysis Action Bar
    st.divider()
    col_act1, col_act2 = st.columns([1, 4])
    with col_act1:
        if st.button("🚀 Analyze Case", type="primary", use_container_width=True):
            with st.spinner("Executing available analysis pipelines..."):
                # Safe execution of available modules
                if MODULE_STATUS["identity"]["available"] and MODULE_STATUS["identity"]["fn"]:
                    try:
                        st.session_state.analysis_results["identities"] = MODULE_STATUS["identity"]["fn"](current_case)
                    except Exception as err:
                        st.session_state.analysis_results["identities"] = {"error": str(err)}

                if MODULE_STATUS["inconsistency"]["available"] and MODULE_STATUS["inconsistency"]["fn"]:
                    try:
                        st.session_state.analysis_results["inconsistencies"] = MODULE_STATUS["inconsistency"]["fn"](current_case)
                    except Exception as err:
                        st.session_state.analysis_results["inconsistencies"] = {"error": str(err)}

                st.session_state.analysis_results["is_stale"] = False
                st.success("Analysis cycle completed.")

    with col_act2:
        export_json = json.dumps(
            {
                "case": current_case,
                "analysis": st.session_state.analysis_results,
            },
            indent=2,
        )
        st.download_button(
            label="📥 Export Case JSON",
            data=export_json,
            file_name=f"{current_case.get('case_id', 'case')}_export.json",
            mime="application/json",
        )

# ==============================================================================
# View: Evidence Workspace (Phase 2)
# ==============================================================================
elif active_nav == "Evidence":
    import html

    st.markdown("### 📁 Evidence Workspace")
    st.caption("Verbatim witness statements and recorded testimonies with source traceability.")

    statements = current_case.get("statements", [])
    if not statements:
        st.info("No witness statements recorded in this case file. Load a sample case from the sidebar or add statements in Overview.")
    else:
        # Collect unique witnesses safely without fabricating missing names
        witness_names = sorted(
            list(
                {
                    str(s.get("witness_name") or s.get("witness") or "Unnamed Witness").strip()
                    for s in statements
                    if (s.get("witness_name") or s.get("witness"))
                }
            )
        )
        witness_options = ["All Witnesses"] + witness_names

        # Filters toolbar
        col_search, col_filter, col_reset = st.columns([3, 2, 1])

        with col_search:
            search_query = st.text_input(
                "🔍 Search statements & witnesses:",
                key="evidence_search_input",
                placeholder="Type keywords, witness names, or IDs...",
            )

        with col_filter:
            selected_witness = st.selectbox(
                "Filter by Witness:",
                options=witness_options,
                key="evidence_witness_select",
            )

        with col_reset:
            st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
            if st.button("Reset Filters", use_container_width=True):
                st.session_state.evidence_search_input = ""
                st.session_state.evidence_witness_select = "All Witnesses"
                st.rerun()

        # Filtering logic: preserve original items, never mutate
        filtered_statements: list[dict[str, Any]] = []
        for stmt in statements:
            w_name = str(stmt.get("witness_name") or stmt.get("witness") or "Unnamed Witness")
            s_id = str(stmt.get("statement_id") or stmt.get("id") or "Unassigned ID")
            text = str(stmt.get("text") or stmt.get("statement") or stmt.get("quote") or "")

            # Witness filter
            if selected_witness != "All Witnesses" and w_name != selected_witness:
                continue

            # Case-insensitive text search across witness name, ID, and statement text
            if search_query:
                q = search_query.strip().lower()
                if (q not in w_name.lower()) and (q not in s_id.lower()) and (q not in text.lower()):
                    continue

            filtered_statements.append(stmt)

        # Counter display
        total_count = len(statements)
        matched_count = len(filtered_statements)
        st.markdown(
            f"<div style='margin-bottom: 1rem; color: #94a3b8; font-size: 0.9rem;'>"
            f"Showing <strong style='color:#38bdf8;'>{matched_count}</strong> of <strong>{total_count}</strong> recorded statement(s)"
            f"</div>",
            unsafe_allow_html=True,
        )

        # Render statement cards
        if not filtered_statements:
            st.warning("No witness statements match the selected filter or search criteria.")
        else:
            for stmt in filtered_statements:
                w_name = stmt.get("witness_name") or stmt.get("witness") or "Unnamed Witness"
                s_id = stmt.get("statement_id") or stmt.get("id") or "Unassigned ID"
                raw_text = stmt.get("text") or stmt.get("statement") or stmt.get("quote") or ""
                interview_date = stmt.get("interview_date") or stmt.get("date")
                role = stmt.get("role")

                # Metadata elements (never fabricate missing timestamps or dates)
                meta_items: list[str] = [f"Source ID: <code>{html.escape(str(s_id))}</code>"]
                if role:
                    meta_items.append(f"Role: <span>{html.escape(str(role))}</span>")
                if interview_date:
                    meta_items.append(f"Recorded: <span>{html.escape(str(interview_date))}</span>")
                meta_html = " &nbsp;|&nbsp; ".join(meta_items)

                escaped_name = html.escape(str(w_name))
                if raw_text:
                    body_html = f'"{html.escape(str(raw_text))}"'
                else:
                    body_html = '<span style="color: #64748b; font-style: italic;">[No statement text recorded]</span>'

                st.markdown(
                    f"""
                    <div class="cw-card" style="border-left: 3px solid #38bdf8;">
                        <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 0.4rem;">
                            <div>
                                <span style="font-size: 1.1rem; font-weight: 600; color: #f1f5f9;">{escaped_name}</span>
                                <div style="font-size: 0.8rem; color: #94a3b8; margin-top: 0.2rem;">
                                    {meta_html}
                                </div>
                            </div>
                            <span class="cw-badge-demo" style="background:#1e293b; border:1px solid #334155; color:#38bdf8;">
                                {html.escape(str(s_id))}
                            </span>
                        </div>
                        <div style="background-color: #0d1524; border-radius: 6px; padding: 0.85rem; margin-top: 0.6rem; border: 1px solid #1e293b;">
                            <span style="color: #64748b; font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.05em; display: block; margin-bottom: 0.25rem;">
                                Verbatim Witness Statement:
                            </span>
                            <div style="color: #e2e8f0; font-size: 0.95rem; line-height: 1.5; font-style: italic;">
                                {body_html}
                            </div>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

elif active_nav == "Timeline":
    st.subheader("⏱️ Timeline")
    st.info("Phase 3 will implement the Evidence-linked Timeline with chronological event ordering.")

elif active_nav == "Contradictions":
    st.subheader("⚖️ Contradictions")
    st.info("Phase 4 will implement the neutral side-by-side contradiction analysis flagged for human review.")

elif active_nav == "What-If Analysis":
    st.subheader("🔀 What-If Analysis")
    st.info("Phase 5 will implement hypothetical scenario modeling on deep copies of timeline events.")
