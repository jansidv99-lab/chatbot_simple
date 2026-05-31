import os

import psycopg2

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
) VALUES (
    %(symbol)s, %(trade_date)s, %(segment)s, %(position_type)s,
    %(open_quantity)s, %(open_average)s, %(open_value)s,
    %(previous_close_price)s, %(closing_value)s,
    %(unrealized_profit)s, %(unrealized_profit_pct)s
)
ON CONFLICT (trade_date, symbol) DO NOTHING;
"""


def get_connection():
    return psycopg2.connect(
        host=os.environ.get("PG_HOST", "localhost"),
        port=int(os.environ.get("PG_PORT", "5432")),
        dbname=os.environ.get("PG_DB", "chatbot"),
        user=os.environ.get("PG_USER", "chatbot"),
        password=os.environ.get("PG_PASSWORD", "chatbot123"),
    )


def ensure_schema(conn) -> None:
    with conn.cursor() as cur:
        cur.execute(_CREATE_TABLE)
    conn.commit()


def insert_positions(conn, rows: list[dict]) -> tuple[int, int]:
    inserted = 0
    skipped = 0
    with conn.cursor() as cur:
        for row in rows:
            cur.execute(_INSERT, row)
            if cur.rowcount == 1:
                inserted += 1
            else:
                skipped += 1
    conn.commit()
    return inserted, skipped
