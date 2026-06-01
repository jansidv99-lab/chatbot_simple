import time

import pandas as pd
import streamlit as st
from opentelemetry import trace as otel_trace

from agents.graph import AnalysisState, graph
from ingestion.db import get_connection, get_date_ranges, get_row_counts
from utils.state import init_session_state

tracer = otel_trace.get_tracer(__name__)

_NODE_LABELS: dict[str, str] = {
    "supervisor":          "Routing question…",
    "schema_agent":        "Fetching schema…",
    "sql_planner":         "Planning SQL…",
    "sql_validator":       "Validating SQL…",
    "execute_sql":         "Executing query…",
    "clarification_agent": "Refining SQL…",
    "analytics_agent":     "Analysing results…",
    "validation_node":     "Checking analysis…",
    "response_formatter":  "Formatting response…",
}

st.set_page_config(page_title="F&O Analysis", page_icon="📊")
st.title("F&O Analysis")

init_session_state()

# ── DB readiness check ────────────────────────────────────────────────────────

@st.cache_data(ttl=30)
def _fetch_row_counts() -> tuple[dict[str, int | None], str | None]:
    try:
        conn = get_connection()
        try:
            return get_row_counts(conn), None
        finally:
            conn.close()
    except Exception as e:
        return {}, str(e)


@st.cache_data(ttl=30)
def _fetch_date_ranges() -> dict[str, dict]:
    try:
        conn = get_connection()
        try:
            return get_date_ranges(conn)
        finally:
            conn.close()
    except Exception:
        return {}


def _word_stream(text: str):
    for word in text.split():
        yield word + " "
        time.sleep(0.025)


counts, db_error = _fetch_row_counts()
date_ranges = _fetch_date_ranges()

_LABELS: dict[str, str] = {
    "daily_positions": "Positions",
    "daily_pl":        "P&L",
    "daily_trades":    "Trades",
    "daily_charges":   "Charges",
}

tables_exist = any(v is not None for v in counts.values())
has_data     = any(v is not None and v > 0 for v in counts.values())

# ── Sidebar ───────────────────────────────────────────────────────────────────

with st.sidebar:
    col1, col2 = st.columns([2, 1])
    with col1:
        if st.button("Clear history"):
            st.session_state.analysis_history = []
            st.rerun()
    with col2:
        if st.button("Refresh"):
            _fetch_row_counts.clear()
            _fetch_date_ranges.clear()
            st.rerun()

    st.divider()
    st.markdown("**Data Status**")

    if not tables_exist and not db_error:
        st.warning("No tables found.")
    elif tables_exist:
        for tbl, label in _LABELS.items():
            count = counts.get(tbl)
            if count is None:
                st.markdown(f"- {label}: *table missing*")
            elif count == 0:
                st.markdown(f"- {label}: *0 rows (empty)*")
            else:
                st.markdown(f"- {label}: **{count:,} rows**")

    if date_ranges:
        st.divider()
        st.markdown("**Date Coverage**")
        for tbl, dr in date_ranges.items():
            label = _LABELS.get(tbl, tbl)
            st.markdown(f"- {label}: {dr['min']} → {dr['max']}")

    st.divider()
    st.markdown(
        "**Examples:**\n"
        "- What was the total realized PnL by symbol?\n"
        "- Which symbol had the highest unrealized loss?\n"
        "- Show total brokerage charges by date."
    )

# ── Readiness gate ────────────────────────────────────────────────────────────

if db_error:
    st.error(
        f"Cannot connect to the database: {db_error}\n\n"
        "Check that PostgreSQL is running and the `PG_*` environment variables are set correctly."
    )
    st.stop()

if not tables_exist:
    st.warning(
        "No tables found in the database.  \n"
        "Go to the **Upload** page, click **Create Tables in DB**, then upload your data files."
    )
    st.stop()

if not has_data:
    st.warning(
        "Tables exist but all are empty.  \n"
        "Go to the **Upload** page and upload your Zerodha F&O Excel files before running analysis."
    )
    st.stop()

# ── Chat history ──────────────────────────────────────────────────────────────

for entry in st.session_state.analysis_history:
    with st.chat_message("user"):
        st.markdown(entry["question"])
    with st.chat_message("assistant"):
        st.markdown(entry["response"])
        if entry.get("sql"):
            with st.expander("SQL Query"):
                st.code(entry["sql"], language="sql")
        if entry.get("results"):
            with st.expander(f"Raw results ({len(entry['results'])} rows)"):
                st.dataframe(pd.DataFrame(entry["results"]).head(100))

# ── Analysis input ────────────────────────────────────────────────────────────

if question := st.chat_input("Ask about your F&O data…"):
    with st.chat_message("user"):
        st.markdown(question)

    initial_state: AnalysisState = {
        "question": question,
        "schema_context": "",
        "sql_query": "",
        "sql_valid": False,
        "analytics_valid": False,
        "validation_error": "",
        "query_results": [],
        "data_found": False,
        "analysis": "",
        "final_response": "",
        "retry_count_sql": 0,
        "retry_count_analysis": 0,
    }

    with st.chat_message("assistant"):
        result = dict(initial_state)
        with tracer.start_as_current_span("fo_analysis") as agent_span:
            agent_span.set_attribute("openinference.span.kind", "AGENT")
            agent_span.set_attribute("input.value", question)
            with st.status("Starting…", expanded=True) as status_widget:
                for chunk in graph.stream(initial_state, stream_mode="updates"):
                    node_name = next(iter(chunk))
                    result.update(chunk[node_name])
                    status_widget.update(label=_NODE_LABELS.get(node_name, f"{node_name}…"))
                status_widget.update(label="Done", state="complete", expanded=False)
            agent_span.set_attribute("output.value", result.get("final_response", "")[:500])

        if result.get("query_results"):
            st.write_stream(_word_stream(result["final_response"]))
        else:
            st.markdown(result["final_response"])

        if result.get("sql_query"):
            with st.expander("SQL Query"):
                st.code(result["sql_query"], language="sql")

        if result.get("query_results"):
            with st.expander(f"Raw results ({len(result['query_results'])} rows)"):
                st.dataframe(pd.DataFrame(result["query_results"]).head(100))

    st.session_state.analysis_history.append({
        "question": question,
        "response": result["final_response"],
        "sql": result.get("sql_query", ""),
        "results": result.get("query_results", [])[:100],
    })
