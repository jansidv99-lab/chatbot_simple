import os
import warnings

import psycopg2
from psycopg2.extras import execute_values

# ── Schema ───────────────────────────────────────────────────────────────────

_CREATE_POSITIONS = """
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

_CREATE_DAILY_PL = """
CREATE TABLE IF NOT EXISTS daily_pl (
    symbol                 VARCHAR  NOT NULL,
    trade_date             DATE     NOT NULL,
    quantity               NUMERIC,
    buy_value              NUMERIC,
    sell_value             NUMERIC,
    realized_pnl           NUMERIC,
    realized_pnl_pct       NUMERIC,
    previous_closing_price NUMERIC,
    open_quantity          NUMERIC,
    open_quantity_type     VARCHAR,
    open_value             NUMERIC,
    unrealized_pnl         NUMERIC,
    unrealized_pnl_pct     NUMERIC,
    PRIMARY KEY (trade_date, symbol)
);
"""

_CREATE_DAILY_TRADES = """
CREATE TABLE IF NOT EXISTS daily_trades (
    symbol               VARCHAR    NOT NULL,
    trade_date           DATE       NOT NULL,
    trade_type           VARCHAR,
    quantity             NUMERIC,
    price                NUMERIC,
    order_execution_time TIMESTAMP,
    PRIMARY KEY (trade_date, symbol)
);
"""

_CREATE_DAILY_CHARGES = """
CREATE TABLE IF NOT EXISTS daily_charges (
    date                          DATE PRIMARY KEY,
    brokerage                     NUMERIC,
    exchange_transaction_charges  NUMERIC,
    clearing_charges              NUMERIC,
    central_gst                   NUMERIC,
    state_gst                     NUMERIC,
    integrated_gst                NUMERIC,
    securities_transaction_tax    NUMERIC,
    sebi_turnover_fees            NUMERIC,
    stamp_duty                    NUMERIC,
    ipft                          NUMERIC
);
"""

# ── Positions ────────────────────────────────────────────────────────────────

_INSERT_POSITIONS = """
INSERT INTO daily_positions (
    symbol, trade_date, segment, position_type,
    open_quantity, open_average, open_value,
    previous_close_price, closing_value,
    unrealized_profit, unrealized_profit_pct
) VALUES %s
ON CONFLICT (trade_date, symbol) DO NOTHING
RETURNING symbol
"""

_POSITIONS_COLS = [
    "symbol", "trade_date", "segment", "position_type",
    "open_quantity", "open_average", "open_value",
    "previous_close_price", "closing_value",
    "unrealized_profit", "unrealized_profit_pct",
]

# ── Daily P&L ────────────────────────────────────────────────────────────────

_INSERT_PL = """
INSERT INTO daily_pl (
    symbol, trade_date, quantity, buy_value, sell_value,
    realized_pnl, realized_pnl_pct, previous_closing_price,
    open_quantity, open_quantity_type, open_value,
    unrealized_pnl, unrealized_pnl_pct
) VALUES %s
ON CONFLICT (trade_date, symbol) DO NOTHING
RETURNING symbol
"""

_PL_COLS = [
    "symbol", "trade_date", "quantity", "buy_value", "sell_value",
    "realized_pnl", "realized_pnl_pct", "previous_closing_price",
    "open_quantity", "open_quantity_type", "open_value",
    "unrealized_pnl", "unrealized_pnl_pct",
]

# ── Daily Trades ─────────────────────────────────────────────────────────────

_INSERT_TRADES = """
INSERT INTO daily_trades (
    symbol, trade_date, trade_type, quantity, price, order_execution_time
) VALUES %s
ON CONFLICT (trade_date, symbol) DO NOTHING
RETURNING symbol
"""

_TRADES_COLS = [
    "symbol", "trade_date", "trade_type", "quantity", "price", "order_execution_time",
]

# ── Daily Charges ─────────────────────────────────────────────────────────────

_INSERT_CHARGES = """
INSERT INTO daily_charges (
    date, brokerage, exchange_transaction_charges, clearing_charges,
    central_gst, state_gst, integrated_gst, securities_transaction_tax,
    sebi_turnover_fees, stamp_duty, ipft
) VALUES (
    %(date)s, %(brokerage)s, %(exchange_transaction_charges)s, %(clearing_charges)s,
    %(central_gst)s, %(state_gst)s, %(integrated_gst)s, %(securities_transaction_tax)s,
    %(sebi_turnover_fees)s, %(stamp_duty)s, %(ipft)s
)
ON CONFLICT (date) DO NOTHING
RETURNING date
"""


# ── Connection ───────────────────────────────────────────────────────────────

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


# ── Schema management ────────────────────────────────────────────────────────

def ensure_schema(conn) -> None:
    with conn.cursor() as cur:
        cur.execute(_CREATE_POSITIONS)
        cur.execute(_CREATE_DAILY_PL)
        cur.execute(_CREATE_DAILY_TRADES)
        cur.execute(_CREATE_DAILY_CHARGES)
    conn.commit()


def list_tables(conn) -> list[str]:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'public' ORDER BY table_name"
        )
        return [row[0] for row in cur.fetchall()]


# ── Insert functions ─────────────────────────────────────────────────────────

def insert_positions(conn, rows: list[dict]) -> tuple[int, int]:
    values = [tuple(row[col] for col in _POSITIONS_COLS) for row in rows]
    with conn.cursor() as cur:
        returned = execute_values(cur, _INSERT_POSITIONS, values, fetch=True)
    conn.commit()
    inserted = len(returned)
    skipped = len(rows) - inserted
    return inserted, skipped


def insert_pl(conn, rows: list[dict]) -> tuple[int, int]:
    values = [tuple(row[col] for col in _PL_COLS) for row in rows]
    with conn.cursor() as cur:
        returned = execute_values(cur, _INSERT_PL, values, fetch=True)
    conn.commit()
    inserted = len(returned)
    skipped = len(rows) - inserted
    return inserted, skipped


def insert_trades(conn, rows: list[dict]) -> tuple[int, int]:
    values = [tuple(row[col] for col in _TRADES_COLS) for row in rows]
    with conn.cursor() as cur:
        returned = execute_values(cur, _INSERT_TRADES, values, fetch=True)
    conn.commit()
    inserted = len(returned)
    skipped = len(rows) - inserted
    return inserted, skipped


def insert_charges(conn, charges: dict) -> tuple[int, int]:
    with conn.cursor() as cur:
        cur.execute(_INSERT_CHARGES, charges)
        returned = cur.fetchall()
    conn.commit()
    inserted = len(returned)
    skipped = 1 - inserted
    return inserted, skipped
