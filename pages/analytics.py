import pandas as pd
import streamlit as st
from opentelemetry import trace as otel_trace

from agents.graph import AnalysisState, graph

tracer = otel_trace.get_tracer(__name__)

st.set_page_config(page_title="F&O Analysis", page_icon="📊")
st.title("F&O Analysis")

if "analysis_history" not in st.session_state:
    st.session_state.analysis_history = []

with st.sidebar:
    if st.button("Clear history"):
        st.session_state.analysis_history = []
        st.rerun()
    st.markdown(
        "Ask natural-language questions about your F&O data.\n\n"
        "**Examples:**\n"
        "- What was the total realized PnL by symbol?\n"
        "- Which symbol had the highest unrealized loss?\n"
        "- Show total brokerage charges by date."
    )

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
        "retry_count": 0,
    }

    with st.chat_message("assistant"):
        with st.spinner("Analysing…"):
            with tracer.start_as_current_span("fo_analysis") as agent_span:
                agent_span.set_attribute("openinference.span.kind", "AGENT")
                agent_span.set_attribute("input.value", question)
                result = graph.invoke(initial_state)
                agent_span.set_attribute("output.value", result.get("final_response", "")[:500])

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
