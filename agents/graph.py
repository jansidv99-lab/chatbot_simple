import functools
import os
import re

import psycopg2
from langchain_ollama import ChatOllama
from langgraph.graph import END, StateGraph
from opentelemetry import trace as otel_trace
from typing_extensions import TypedDict

from ingestion.db import get_connection, list_tables

tracer = otel_trace.get_tracer(__name__)

# ── LLM (lazy — reads env vars at first call, not at import time) ────────────

@functools.lru_cache(maxsize=1)
def _get_llm() -> ChatOllama:
    return ChatOllama(
        base_url=os.environ.get("OLLAMA_HOST", "http://localhost:11434"),
        model=os.environ.get("MODEL_NAME", "gemma4:e2b"),
    )

# ── Static schema context ────────────────────────────────────────────────────

_SCHEMA = """
Tables available in PostgreSQL (schema: public):

daily_positions (PK: trade_date, symbol)
  symbol VARCHAR, trade_date DATE, segment VARCHAR, position_type VARCHAR,
  open_quantity NUMERIC, open_average NUMERIC, open_value NUMERIC,
  previous_close_price NUMERIC, closing_value NUMERIC,
  unrealized_profit NUMERIC, unrealized_profit_pct NUMERIC

daily_pl (PK: trade_date, symbol)
  symbol VARCHAR, trade_date DATE, quantity NUMERIC,
  buy_value NUMERIC, sell_value NUMERIC,
  realized_pnl NUMERIC, realized_pnl_pct NUMERIC,
  previous_closing_price NUMERIC, open_quantity NUMERIC,
  open_quantity_type VARCHAR, open_value NUMERIC,
  unrealized_pnl NUMERIC, unrealized_pnl_pct NUMERIC

daily_trades (PK: trade_date, symbol)
  symbol VARCHAR, trade_date DATE, trade_type VARCHAR,
  quantity NUMERIC, price NUMERIC, order_execution_time TIMESTAMP

daily_charges (PK: date)
  date DATE, brokerage NUMERIC, exchange_transaction_charges NUMERIC,
  clearing_charges NUMERIC, central_gst NUMERIC, state_gst NUMERIC,
  integrated_gst NUMERIC, securities_transaction_tax NUMERIC,
  sebi_turnover_fees NUMERIC, stamp_duty NUMERIC, ipft NUMERIC
""".strip()

# ── State ────────────────────────────────────────────────────────────────────


class AnalysisState(TypedDict):
    question: str
    schema_context: str
    sql_query: str
    sql_valid: bool
    analytics_valid: bool
    validation_error: str
    query_results: list[dict]
    data_found: bool
    analysis: str
    final_response: str
    retry_count: int


# ── Helpers ──────────────────────────────────────────────────────────────────

def _assert_select_only(sql: str) -> None:
    first_word = sql.strip().split()[0].upper() if sql.strip() else ""
    if first_word != "SELECT":
        raise ValueError(f"Only SELECT queries are allowed, got: {first_word!r}")


def _extract_sql(text: str) -> str:
    """Pull SQL out of a fenced code block or return text as-is."""
    match = re.search(r"```(?:sql)?\s*(.*?)```", text, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return text.strip()


def _rows_to_text(rows: list) -> str:
    if not rows:
        return "(no rows)"
    headers = list(rows[0].keys())
    lines = [" | ".join(headers)]
    lines.append("-" * len(lines[0]))
    for row in rows[:50]:
        lines.append(" | ".join(str(row.get(h, "")) for h in headers))
    if len(rows) > 50:
        lines.append(f"... and {len(rows) - 50} more rows")
    return "\n".join(lines)


# ── Nodes ────────────────────────────────────────────────────────────────────

def supervisor(state: AnalysisState) -> AnalysisState:
    prompt = (
        "You are a data assistant. The user has these PostgreSQL tables:\n"
        "daily_positions, daily_pl, daily_trades, daily_charges\n\n"
        "They contain Zerodha F&O trading data: positions, P&L, trades, and brokerage charges.\n\n"
        """The platform contains three primary business datasets.The three workbooks represent three different grains of the same domain:
Tradebook: event-level executions, with symbol, date, buy/sell, quantity, price, order time.
Positions: current open positions, with quantity, average price, market value, and unrealized P&L.
P&L: realized P&L, unrealized P&L, and charges split by symbol and account head.

1. Tradebook (Execution Grain)

Represents individual trade executions.

Contains:
- symbol
- trade date
- buy/sell side
- quantity
- execution price
- order time

Use when user asks about:
- trades
- turnover
- buy/sell activity
- trade history
- execution counts
- trading frequency
- trade performance

Business grain:
ONE ROW = ONE EXECUTED TRADE

--------------------------------------------------

2. Positions (Position Snapshot Grain)

Represents current open positions.

Contains:
- symbol
- quantity
- average price
- market value
- unrealized P&L

Use when user asks about:
- open positions
- current exposure
- unrealized profit
- unrealized loss
- current holdings
- risk concentration
- portfolio exposure

Business grain:
ONE ROW = ONE OPEN POSITION

--------------------------------------------------

3. P&L (Financial Summary Grain)

Represents realized and unrealized performance.

Contains:
- realized P&L
- unrealized P&L
- charges
- account-level summaries
- symbol-level summaries

Use when user asks about:
- profitability
- gains
- losses
- net performance
- brokerage impact
- charges
- performance attribution

Business grain:
ONE ROW = ONE P&L RECORD """
        f"User question: {state['question']}\n\n"
        "Can this question be answered using only these tables? "
        "Reply with exactly one word: YES or NO."
    )
    with tracer.start_as_current_span("supervisor") as span:
        span.set_attribute("openinference.span.kind", "LLM")
        span.set_attribute("llm.model_name", os.environ.get("MODEL_NAME", "gemma4:e2b"))
        span.set_attribute("input.value", state["question"])
        response = _get_llm().invoke(prompt).content.strip().upper()
        span.set_attribute("output.value", response)
    if "YES" in response:
        return {**state, "final_response": ""}
    return {
        **state,
        "final_response": (
            "I can only answer questions about your F&O trading data "
            "(positions, P&L, trades, charges). Please ask something related to that data."
        ),
    }


def schema_agent(state: AnalysisState) -> AnalysisState:
    with tracer.start_as_current_span("schema_agent") as span:
        span.set_attribute("openinference.span.kind", "TOOL")
        span.set_attribute("tool.name", "list_tables")
        span.set_attribute("input.value", "fetch available tables and schema")
        try:
            conn = get_connection()
            try:
                tables = list_tables(conn)
            finally:
                conn.close()
            table_note = f"Confirmed tables in DB: {', '.join(tables)}" if tables else "Warning: no tables found yet."
        except Exception as e:
            table_note = f"Could not connect to DB: {e}"
        schema_context = f"{_SCHEMA}\n\n{table_note}"
        span.set_attribute("output.value", table_note)
    return {**state, "schema_context": schema_context}


def sql_planner(state: AnalysisState) -> AnalysisState:
    prompt = (
        f"Schema:\n{state['schema_context']}\n\n"
        f"Question: {state['question']}\n\n"
        "Write a single read-only PostgreSQL SELECT query that answers this question. "
        "Always include LIMIT 500 unless the question explicitly asks for all rows. "
        "Return ONLY the SQL inside a ```sql``` code block. No explanation."
    )
    with tracer.start_as_current_span("sql_planner") as span:
        span.set_attribute("openinference.span.kind", "LLM")
        span.set_attribute("llm.model_name", os.environ.get("MODEL_NAME", "gemma4:e2b"))
        span.set_attribute("input.value", state["question"])
        raw = _get_llm().invoke(prompt).content
        sql = _extract_sql(raw)
        span.set_attribute("output.value", sql)
    return {**state, "sql_query": sql}


def sql_validator(state: AnalysisState) -> AnalysisState:
    sql = state["sql_query"]
    with tracer.start_as_current_span("sql_validator") as span:
        span.set_attribute("openinference.span.kind", "TOOL")
        span.set_attribute("tool.name", "sql_explain")
        span.set_attribute("input.value", sql)
        try:
            _assert_select_only(sql)
            conn = get_connection()
            try:
                with conn.cursor() as cur:
                    cur.execute("EXPLAIN " + sql)
            finally:
                conn.rollback()
                conn.close()
            span.set_attribute("output.value", "valid")
            return {**state, "sql_valid": True, "validation_error": ""}
        except psycopg2.Error as e:
            span.set_attribute("output.value", str(e))
            return {**state, "sql_valid": False, "validation_error": str(e)}
        except Exception as e:
            span.set_attribute("output.value", str(e))
            return {**state, "sql_valid": False, "validation_error": str(e)}


def execute_sql(state: AnalysisState) -> AnalysisState:
    with tracer.start_as_current_span("execute_sql") as span:
        span.set_attribute("openinference.span.kind", "TOOL")
        span.set_attribute("tool.name", "postgres_query")
        span.set_attribute("input.value", state["sql_query"])
        try:
            _assert_select_only(state["sql_query"])
            conn = get_connection()
            try:
                with conn.cursor() as cur:
                    cur.execute(state["sql_query"])
                    columns = [desc[0] for desc in cur.description] if cur.description else []
                    rows = [dict(zip(columns, row)) for row in cur.fetchall()]
            finally:
                conn.close()
            span.set_attribute("output.value", f"{len(rows)} rows returned")
            return {**state, "query_results": rows, "data_found": len(rows) > 0}
        except Exception as e:
            span.set_attribute("output.value", str(e))
            return {
                **state,
                "query_results": [],
                "data_found": False,
                "validation_error": str(e),
                "sql_valid": False,
            }


def clarification_agent(state: AnalysisState) -> AnalysisState:
    retry_count = state.get("retry_count", 0) + 1
    error = state.get("validation_error") or "The query returned no rows."
    prompt = (
        f"Schema:\n{state['schema_context']}\n\n"
        f"Question: {state['question']}\n\n"
        f"Previous SQL:\n```sql\n{state['sql_query']}\n```\n\n"
        f"Problem: {error}\n\n"
        "Fix the SQL query to correctly answer the question. "
        "Return ONLY the corrected SQL inside a ```sql``` code block."
    )
    with tracer.start_as_current_span("clarification_agent") as span:
        span.set_attribute("openinference.span.kind", "LLM")
        span.set_attribute("llm.model_name", os.environ.get("MODEL_NAME", "gemma4:e2b"))
        span.set_attribute("input.value", state["question"])
        raw = _get_llm().invoke(prompt).content
        sql = _extract_sql(raw)
        span.set_attribute("output.value", sql)
    return {**state, "sql_query": sql, "retry_count": retry_count, "sql_valid": False, "validation_error": ""}


def analytics_agent(state: AnalysisState) -> AnalysisState:
    results_text = _rows_to_text(state["query_results"])
    prompt = (
        f"Question: {state['question']}\n\n"
        f"Query results:\n{results_text}\n\n"
        "Analyse these results and provide a clear, concise answer to the question. "
        "Include specific numbers. Use markdown formatting."
    )
    with tracer.start_as_current_span("analytics_agent") as span:
        span.set_attribute("openinference.span.kind", "LLM")
        span.set_attribute("llm.model_name", os.environ.get("MODEL_NAME", "gemma4:e2b"))
        span.set_attribute("input.value", state["question"])
        analysis = _get_llm().invoke(prompt).content.strip()
        span.set_attribute("output.value", analysis)
    return {**state, "analysis": analysis}


def validation_node(state: AnalysisState) -> AnalysisState:
    with tracer.start_as_current_span("validation_node") as span:
        span.set_attribute("openinference.span.kind", "CHAIN")
        analysis = state.get("analysis", "")
        span.set_attribute("input.value", analysis[:500])
        has_content = len(analysis) > 20
        has_numbers = bool(re.search(r"\d[\d.,]+", analysis))
        if has_content and has_numbers:
            span.set_attribute("output.value", "pass")
            return {**state, "analytics_valid": True}
        span.set_attribute("output.value", "fail: too vague or missing numbers")
        return {**state, "analytics_valid": False, "validation_error": "Analysis is too vague or missing numbers."}


def response_formatter(state: AnalysisState) -> AnalysisState:
    with tracer.start_as_current_span("response_formatter") as span:
        span.set_attribute("openinference.span.kind", "CHAIN")
        span.set_attribute("input.value", state.get("analysis", "")[:500])
        if state.get("analysis"):
            final = state["analysis"]
        else:
            final = (
                "I was unable to answer your question after several attempts. "
                "Please try rephrasing or check that the relevant data has been uploaded."
            )
        span.set_attribute("output.value", final[:500])
        return {**state, "final_response": final}


# ── Conditional edge functions ───────────────────────────────────────────────

def _route_supervisor(state: AnalysisState) -> str:
    return "schema_agent" if not state.get("final_response") else END


def _route_validator(state: AnalysisState) -> str:
    return "execute_sql" if state["sql_valid"] else "clarification_agent"


def _route_execute(state: AnalysisState) -> str:
    return "analytics_agent" if state["data_found"] else "clarification_agent"


def _route_clarification(state: AnalysisState) -> str:
    return "sql_validator" if state.get("retry_count", 0) < 3 else "response_formatter"


def _route_validation(state: AnalysisState) -> str:
    if state.get("analytics_valid"):
        return "response_formatter"
    return "clarification_agent" if state.get("retry_count", 0) < 3 else "response_formatter"


# ── Graph ────────────────────────────────────────────────────────────────────

_builder = StateGraph(AnalysisState)

_builder.add_node("supervisor", supervisor)
_builder.add_node("schema_agent", schema_agent)
_builder.add_node("sql_planner", sql_planner)
_builder.add_node("sql_validator", sql_validator)
_builder.add_node("execute_sql", execute_sql)
_builder.add_node("clarification_agent", clarification_agent)
_builder.add_node("analytics_agent", analytics_agent)
_builder.add_node("validation_node", validation_node)
_builder.add_node("response_formatter", response_formatter)

_builder.set_entry_point("supervisor")
_builder.add_conditional_edges("supervisor", _route_supervisor)
_builder.add_edge("schema_agent", "sql_planner")
_builder.add_edge("sql_planner", "sql_validator")
_builder.add_conditional_edges("sql_validator", _route_validator)
_builder.add_conditional_edges("execute_sql", _route_execute)
_builder.add_conditional_edges("clarification_agent", _route_clarification)
_builder.add_edge("analytics_agent", "validation_node")
_builder.add_conditional_edges("validation_node", _route_validation)
_builder.add_edge("response_formatter", END)

graph = _builder.compile()
