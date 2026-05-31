import datetime
import io
import os
from unittest.mock import MagicMock

import openpyxl
import pytest

from ingestion.parser import parse_positions_excel, validate_file

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_XLSX_PATH = os.path.join(
    os.path.dirname(__file__),
    "..",
    "raw_data_files",
    "daily_poistions",
    "positions-19-5.xlsx",
)


def _real_file_bytes() -> bytes:
    with open(_XLSX_PATH, "rb") as f:
        return f.read()


def _make_minimal_xlsx(include_fo_sheet: bool = True, add_data_row: bool = True) -> bytes:
    wb = openpyxl.Workbook()
    if include_fo_sheet:
        ws = wb.active
        ws.title = "F&O"
        ws["B15"] = "Symbol"
        if add_data_row:
            ws["B16"] = "TESTSYM"
            ws["C16"] = "2026-01-01"
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Parser tests — against the real Excel file
# ---------------------------------------------------------------------------


def test_parse_returns_correct_row_count():
    rows = parse_positions_excel(_real_file_bytes())
    assert len(rows) == 5


def test_parse_maps_symbol_correctly():
    rows = parse_positions_excel(_real_file_bytes())
    assert rows[0]["symbol"] == "NIFTY26MAY23050PE"


def test_parse_maps_trade_date_as_date_obj():
    rows = parse_positions_excel(_real_file_bytes())
    assert isinstance(rows[0]["trade_date"], datetime.date)
    assert rows[0]["trade_date"] == datetime.date(2026, 5, 19)


def test_parse_excludes_client_id():
    rows = parse_positions_excel(_real_file_bytes())
    for row in rows:
        assert "client_id" not in row


def test_parse_numeric_fields_are_float():
    rows = parse_positions_excel(_real_file_bytes())
    numeric_keys = [
        "open_quantity", "open_average", "open_value",
        "previous_close_price", "closing_value",
        "unrealized_profit", "unrealized_profit_pct",
    ]
    for key in numeric_keys:
        assert isinstance(rows[0][key], float), f"{key} is not float"


# ---------------------------------------------------------------------------
# Validation tests — using synthetic workbooks
# ---------------------------------------------------------------------------


def test_validate_rejects_non_xlsx():
    with pytest.raises(ValueError, match=r"\.xlsx"):
        validate_file("positions.csv", b"fake")


def test_validate_rejects_missing_fo_sheet():
    wb = openpyxl.Workbook()
    wb.active.title = "Sheet1"
    buf = io.BytesIO()
    wb.save(buf)
    with pytest.raises(ValueError, match="F&O"):
        validate_file("test.xlsx", buf.getvalue())


def test_validate_rejects_empty_data():
    xlsx = _make_minimal_xlsx(include_fo_sheet=True, add_data_row=False)
    with pytest.raises(ValueError, match="No data rows"):
        validate_file("test.xlsx", xlsx)


# ---------------------------------------------------------------------------
# DB layer tests — fully mocked
# ---------------------------------------------------------------------------


def test_ensure_schema_executes_create_table():
    from ingestion.db import ensure_schema

    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

    ensure_schema(mock_conn)

    execute_args = mock_cursor.execute.call_args[0][0]
    assert "CREATE TABLE IF NOT EXISTS daily_positions" in execute_args
    mock_conn.commit.assert_called_once()


def test_insert_returns_inserted_count():
    from ingestion.db import insert_positions

    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.rowcount = 1
    mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

    rows = [{"symbol": "A", "trade_date": datetime.date(2026, 1, 1)} for _ in range(3)]
    inserted, skipped = insert_positions(mock_conn, rows)

    assert inserted == 3
    assert skipped == 0


def test_insert_returns_skipped_count():
    from ingestion.db import insert_positions

    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.rowcount = 0
    mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

    rows = [{"symbol": "A", "trade_date": datetime.date(2026, 1, 1)} for _ in range(2)]
    inserted, skipped = insert_positions(mock_conn, rows)

    assert inserted == 0
    assert skipped == 2


def test_insert_commits_on_success():
    from ingestion.db import insert_positions

    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.rowcount = 1
    mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

    insert_positions(mock_conn, [{"symbol": "X", "trade_date": datetime.date(2026, 1, 1)}])
    mock_conn.commit.assert_called_once()
