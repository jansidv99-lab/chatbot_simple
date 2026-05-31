import os
import warnings

import psycopg2
from psycopg2.extras import execute_values

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS daily_positions (
    symbol                VARCHAR    NOT NULL,
    trade_date            DATE       NOT NULL,
    segment               VARCHAR,
    position_type         VARCHAR,
    open_quantity         NUMERIC,
    open_average          NUMERIC,
    open_value            NUMERIC,
    previous_close_price  NUMERIC,
    closing_value         NUMERIC,
    unrealized_profit     NUMERIC,
    unrealized_profit_pct NUMERIC,
    PRIMARY KEY (trade_date, symbol)
);
"""

_INSERT = """
INSERT INTO daily_positions (
    symbol, trade_date, segment, position_type,
    open_quantity, open_average, open_value,
    previous_close_price, closing_value,
    unrealized_profit, unrealized_profit_pct
) VALUES %s
ON CONFLICT (trade_date, symbol) DO NOTHING
RETURNING symbol
"""

_COLUMN_ORDER = [
    "symbol", "trade_date", "segment", "position_type",
    "open_quantity", "open_average", "open_value",
    "previous_close_price", "closing_value",
    "unrealized_profit", "unrealized_profit_pct",
]


def get_connection():
    password = os.environ.get("PG_PASSWORD")
    if password is None:
        warnings.warn(
            "PG_PASSWORD env var is not set; falling back to default 'chatbot123'. "
            "Set PG_PASSWORD explicitly in production.",
            stacklevel=2,
        )
        password = "chatbot123"
    return psycopg2.connect(
        host=os.environ.get("PG_HOST", "localhost"),
        port=int(os.environ.get("PG_PORT", "5432")),
        dbname=os.environ.get("PG_DB", "chatbot"),
        user=os.environ.get("PG_USER", "chatbot"),
        password=password,
    )


def ensure_schema(conn) -> None:
    with conn.cursor() as cur:
        cur.execute(_CREATE_TABLE)
    conn.commit()


def insert_positions(conn, rows: list[dict]) -> tuple[int, int]:
    values = [tuple(row[col] for col in _COLUMN_ORDER) for row in rows]
    with conn.cursor() as cur:
        returned = execute_values(cur, _INSERT, values, fetch=True)
    conn.commit()
    inserted = len(returned)
    skipped = len(rows) - inserted
    return inserted, skipped
