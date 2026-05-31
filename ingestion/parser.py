import datetime
from io import BytesIO

import openpyxl

_SHEET = "F&O"
_HEADER_ROW = 15
_DATA_START_ROW = 16
_COL_SYMBOL = 2  # B
_COL_TRADE_DATE = 3  # C
_COL_LAST = 12  # L


def validate_file(filename: str, file_bytes: bytes) -> None:
    if not filename.lower().endswith(".xlsx"):
        raise ValueError(f"Expected an .xlsx file, got '{filename}'.")
    wb = openpyxl.load_workbook(BytesIO(file_bytes), data_only=True, read_only=True)
    if _SHEET not in wb.sheetnames:
        raise ValueError(f"Sheet '{_SHEET}' not found in workbook (found: {wb.sheetnames}).")
    ws = wb[_SHEET]
    header_b = ws.cell(row=_HEADER_ROW, column=_COL_SYMBOL).value
    if str(header_b or "").strip().lower() != "symbol":
        raise ValueError(
            f"Expected 'Symbol' in cell B{_HEADER_ROW}, got '{header_b}'. "
            "File layout may not match the expected format."
        )
    has_data = any(
        ws.cell(row=r, column=_COL_SYMBOL).value not in (None, "")
        for r in range(_DATA_START_ROW, _DATA_START_ROW + 5)
    )
    if not has_data:
        raise ValueError("No data rows found after the header row.")


def _to_date(value) -> datetime.date:
    if isinstance(value, datetime.datetime):
        return value.date()
    if isinstance(value, datetime.date):
        return value
    return datetime.date.fromisoformat(str(value).strip())


def parse_positions_excel(file_bytes: bytes) -> list[dict]:
    wb = openpyxl.load_workbook(BytesIO(file_bytes), data_only=True)
    ws = wb[_SHEET]
    rows = []
    for row in ws.iter_rows(min_row=_DATA_START_ROW, min_col=_COL_SYMBOL, max_col=_COL_LAST):
        symbol = row[0].value
        if symbol is None or str(symbol).strip() == "":
            continue
        rows.append(
            {
                "symbol": str(symbol).strip(),
                "trade_date": _to_date(row[1].value),
                "segment": str(row[2].value).strip() if row[2].value is not None else None,
                "position_type": str(row[3].value).strip() if row[3].value is not None else None,
                "open_quantity": float(row[4].value) if row[4].value is not None else None,
                "open_average": float(row[5].value) if row[5].value is not None else None,
                "open_value": float(row[6].value) if row[6].value is not None else None,
                "previous_close_price": float(row[7].value) if row[7].value is not None else None,
                "closing_value": float(row[8].value) if row[8].value is not None else None,
                "unrealized_profit": float(row[9].value) if row[9].value is not None else None,
                "unrealized_profit_pct": float(row[10].value) if row[10].value is not None else None,
            }
        )
    return rows
