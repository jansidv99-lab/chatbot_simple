import streamlit as st

from ingestion.db import ensure_schema, get_connection, insert_positions
from ingestion.parser import parse_positions_excel, validate_file

st.set_page_config(page_title="Upload Positions", page_icon="📤")


@st.cache_resource
def _init_schema():
    conn = get_connection()
    ensure_schema(conn)
    conn.close()


try:
    _init_schema()
except Exception as e:
    st.error(f"Database unavailable at startup: {e}")

st.title("Upload Positions")
st.write(
    "Upload a Zerodha F&O positions Excel file (.xlsx). "
    "Duplicate rows (same trade date + symbol) will be silently skipped."
)

uploaded_file = st.file_uploader("Choose positions file", type=["xlsx"])

if uploaded_file is not None:
    file_bytes = uploaded_file.getvalue()

    try:
        validate_file(uploaded_file.name, file_bytes)
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
        inserted, skipped = insert_positions(conn, rows)
        conn.close()
    except Exception as e:
        st.error(f"Database error: {e}")
        st.stop()

    st.success(f"Done. {inserted} rows inserted, {skipped} duplicates skipped.")
