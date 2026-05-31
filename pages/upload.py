import streamlit as st

from ingestion.db import (
    ensure_schema,
    get_connection,
    insert_charges,
    insert_pl,
    insert_positions,
    insert_trades,
    list_tables,
)
from ingestion.parser import (
    parse_pnl_excel,
    parse_positions_excel,
    parse_tradebook_excel,
    validate_file,
    validate_pnl_file,
    validate_tradebook_file,
)

st.set_page_config(page_title="Upload Data", page_icon="📤")
st.title("Upload Data")

# ── Database ─────────────────────────────────────────────────────────────────

st.subheader("Database")

if st.button("Create Tables in DB"):
    try:
        conn = get_connection()
        try:
            ensure_schema(conn)
        finally:
            conn.close()
        st.success("All tables created (or already exist).")
    except Exception as e:
        st.error(f"Failed to create tables: {e}")

try:
    conn = get_connection()
    try:
        tables = list_tables(conn)
    finally:
        conn.close()
    if tables:
        st.write("Tables in DB: " + ", ".join(tables))
    else:
        st.info("No tables found. Click 'Create Tables in DB' first.")
except Exception as e:
    st.warning(f"Cannot connect to DB: {e}")

st.divider()

# ── Upload Positions ──────────────────────────────────────────────────────────

st.subheader("Upload Positions")
st.write(
    "Upload a Zerodha F&O positions Excel file (.xlsx). "
    "Duplicate rows (same trade date + symbol) will be silently skipped."
)

uploaded_positions = st.file_uploader("Choose positions file", type=["xlsx"])

if uploaded_positions is not None:
    file_bytes = uploaded_positions.getvalue()
    try:
        validate_file(uploaded_positions.name, file_bytes)
    except ValueError as e:
        st.error(f"Validation failed: {e}")
        st.stop()
    try:
        rows = parse_positions_excel(file_bytes)
    except Exception as e:
        st.error(f"Failed to parse file: {e}")
        st.stop()
    st.info(f"Parsed {len(rows)} rows. Inserting into database…")
    try:
        conn = get_connection()
        try:
            inserted, skipped = insert_positions(conn, rows)
        finally:
            conn.close()
    except Exception as e:
        st.error(f"Database error: {e}")
        st.stop()
    st.success(f"Done. {inserted} rows inserted, {skipped} duplicates skipped.")

st.divider()

# ── Upload P&L File ───────────────────────────────────────────────────────────

st.subheader("Upload P&L File")
st.write(
    "Upload a Zerodha F&O P&L Excel file (.xlsx). "
    "Inserts into daily_pl and daily_charges."
)

uploaded_pnl = st.file_uploader("Choose P&L file", type=["xlsx"], key="pnl")

if uploaded_pnl is not None:
    file_bytes = uploaded_pnl.getvalue()
    try:
        validate_pnl_file(uploaded_pnl.name, file_bytes)
    except ValueError as e:
        st.error(f"Validation failed: {e}")
        st.stop()
    try:
        pl_rows, charges = parse_pnl_excel(file_bytes)
    except Exception as e:
        st.error(f"Failed to parse file: {e}")
        st.stop()
    st.info(f"Parsed {len(pl_rows)} P&L rows. Inserting into database…")
    try:
        conn = get_connection()
        try:
            pl_inserted, pl_skipped = insert_pl(conn, pl_rows)
            ch_inserted, ch_skipped = insert_charges(conn, charges)
        finally:
            conn.close()
    except Exception as e:
        st.error(f"Database error: {e}")
        st.stop()
    st.success(
        f"daily_pl: {pl_inserted} rows inserted, {pl_skipped} duplicates skipped. "
        f"daily_charges: {ch_inserted} row inserted, {ch_skipped} duplicates skipped."
    )

st.divider()

# ── Upload Trade Book ─────────────────────────────────────────────────────────

st.subheader("Upload Trade Book")
st.write(
    "Upload a Zerodha F&O tradebook Excel file (.xlsx). "
    "Trades are aggregated by symbol + date before inserting."
)

uploaded_tb = st.file_uploader("Choose tradebook file", type=["xlsx"], key="tradebook")

if uploaded_tb is not None:
    file_bytes = uploaded_tb.getvalue()
    try:
        validate_tradebook_file(uploaded_tb.name, file_bytes)
    except ValueError as e:
        st.error(f"Validation failed: {e}")
        st.stop()
    try:
        trade_rows = parse_tradebook_excel(file_bytes)
    except Exception as e:
        st.error(f"Failed to parse file: {e}")
        st.stop()
    st.info(f"Parsed {len(trade_rows)} aggregated rows. Inserting into database…")
    try:
        conn = get_connection()
        try:
            inserted, skipped = insert_trades(conn, trade_rows)
        finally:
            conn.close()
    except Exception as e:
        st.error(f"Database error: {e}")
        st.stop()
    st.success(f"Done. {inserted} rows inserted, {skipped} duplicates skipped.")
