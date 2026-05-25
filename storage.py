"""
storage.py — ProTrader Terminal
Persistent storage layer using Neon PostgreSQL (free tier).
Drop-in replacement for the original JSON file-based storage.
All function signatures are identical — app.py needs zero changes.

Setup:
  1. Sign up at https://neon.tech (free, no credit card)
  2. Create a project, copy the connection string
  3. Add to .streamlit/secrets.toml:
       DATABASE_URL = "postgresql://user:pass@ep-xxx.ap-south-1.aws.neon.tech/neondb?sslmode=require"
  4. pip install psycopg2-binary
  5. Run your app — tables are created automatically on first launch

Connection string can also be set as an environment variable:
  export DATABASE_URL="postgresql://..."
"""

import json
import os
import time
import logging
from datetime import datetime
from contextlib import contextmanager

try:
    import psycopg2
    from psycopg2.pool import ThreadedConnectionPool
    PSYCOPG2_AVAILABLE = True
except ImportError:
    PSYCOPG2_AVAILABLE = False

# ─── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.WARNING)
log = logging.getLogger("storage")

# ─── Connection String Resolution ─────────────────────────────────────────────
def _get_db_url() -> str:
    """
    Tries to get the DATABASE_URL from:
    1. Streamlit secrets (st.secrets["DATABASE_URL"]) — preferred for Streamlit Cloud
    2. Environment variable DATABASE_URL — preferred for local dev / other hosts
    Returns empty string if neither is available.
    """
    # Try Streamlit secrets first
    try:
        import streamlit as st
        url = st.secrets.get("DATABASE_URL", "")
        if url:
            return url
    except Exception:
        pass

    # Fall back to environment variable
    return os.environ.get("DATABASE_URL", "")


DATABASE_URL = _get_db_url()

# ─── Connection Pool ───────────────────────────────────────────────────────────
# A pool of 1–5 connections is ideal for a single-user Streamlit app.
# Neon free tier allows up to ~100 connections but we stay conservative.
_pool: "ThreadedConnectionPool | None" = None

def _get_pool() -> "ThreadedConnectionPool | None":
    global _pool
    if not PSYCOPG2_AVAILABLE:
        return None
    if not DATABASE_URL:
        return None
    if _pool is None:
        try:
            _pool = ThreadedConnectionPool(minconn=1, maxconn=5, dsn=DATABASE_URL)
            log.info("[Storage] Connection pool created.")
        except Exception as e:
            log.error(f"[Storage] Failed to create connection pool: {e}")
            return None
    return _pool

@contextmanager
def _conn():
    """
    Context manager that checks out a connection from the pool,
    commits on success, rolls back on error, and always returns
    the connection to the pool.
    """
    pool = _get_pool()
    if pool is None:
        raise RuntimeError(
            "[Storage] No database connection available. "
            "Check DATABASE_URL in .streamlit/secrets.toml or environment variables."
        )
    conn = pool.getconn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        pool.putconn(conn)

# ─── Schema Bootstrap ─────────────────────────────────────────────────────────
_schema_initialised = False

def _init_schema() -> None:
    """
    Creates the kv_store table and its index on first call.
    Safe to call multiple times — uses IF NOT EXISTS.
    Also creates a separate trade_log table for time-series analytics.
    """
    global _schema_initialised
    if _schema_initialised:
        return

    if not PSYCOPG2_AVAILABLE or not DATABASE_URL:
        log.warning(
            "[Storage] psycopg2 or DATABASE_URL not available. "
            "Falling back to in-memory dict storage (data will NOT persist)."
        )
        _schema_initialised = True
        return

    ddl = """
        CREATE TABLE IF NOT EXISTS kv_store (
            key        TEXT        PRIMARY KEY,
            value      TEXT        NOT NULL,
            updated_at TIMESTAMPTZ DEFAULT NOW()
        );

        CREATE INDEX IF NOT EXISTS idx_kv_updated
            ON kv_store (updated_at DESC);

        CREATE TABLE IF NOT EXISTS trade_log (
            id         SERIAL      PRIMARY KEY,
            category   TEXT        NOT NULL,
            symbol     TEXT,
            pnl        NUMERIC,
            win        BOOLEAN,
            strength   NUMERIC,
            rec        TEXT,
            trade_date DATE        DEFAULT CURRENT_DATE,
            logged_at  TIMESTAMPTZ DEFAULT NOW(),
            meta       TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_tradelog_date
            ON trade_log (trade_date DESC);

        CREATE TABLE IF NOT EXISTS daily_pnl (
            trade_date DATE    PRIMARY KEY,
            pnl        NUMERIC NOT NULL DEFAULT 0,
            trades     INTEGER NOT NULL DEFAULT 0,
            updated_at TIMESTAMPTZ DEFAULT NOW()
        );
    """
    try:
        with _conn() as conn:
            with conn.cursor() as cur:
                cur.execute(ddl)
        log.info("[Storage] Schema initialised.")
        _schema_initialised = True
    except Exception as e:
        log.error(f"[Storage] Schema init failed: {e}")
        _schema_initialised = True   # Don't retry in a loop


# ─── In-memory fallback (used if DB is unavailable) ───────────────────────────
_mem: dict = {}

def _use_fallback() -> bool:
    return not PSYCOPG2_AVAILABLE or not DATABASE_URL


# ─── Core API ─────────────────────────────────────────────────────────────────

def save(key: str, data) -> None:
    """
    Save any JSON-serialisable value under key.
    Replaces existing value atomically (upsert).
    """
    _init_schema()

    if _use_fallback():
        _mem[key] = data
        return

    try:
        serialised = json.dumps(data, default=str)
        with _conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO kv_store (key, value, updated_at)
                    VALUES (%s, %s, NOW())
                    ON CONFLICT (key) DO UPDATE
                        SET value      = EXCLUDED.value,
                            updated_at = NOW()
                    """,
                    (key, serialised),
                )
    except Exception as e:
        log.error(f"[Storage] save({key}): {e}")


def load(key: str, default=None):
    """
    Load value stored under key.
    Returns default if key does not exist or on error.
    """
    _init_schema()

    if _use_fallback():
        return _mem.get(key, default)

    try:
        with _conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT value FROM kv_store WHERE key = %s",
                    (key,),
                )
                row = cur.fetchone()
                if row is None:
                    return default
                return json.loads(row[0])
    except Exception as e:
        log.error(f"[Storage] load({key}): {e}")
        return default


def append_record(key: str, record: dict) -> None:
    """
    Append a dict record to the list stored under key.
    Creates a new list if key does not exist yet.
    Adds a _saved_at timestamp to the record automatically.
    """
    _init_schema()
    existing = load(key, default=[])
    if not isinstance(existing, list):
        existing = []
    record["_saved_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    existing.append(record)
    save(key, existing)


def delete(key: str) -> None:
    """Delete the value stored under key. No-op if key does not exist."""
    _init_schema()

    if _use_fallback():
        _mem.pop(key, None)
        return

    try:
        with _conn() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM kv_store WHERE key = %s", (key,))
    except Exception as e:
        log.error(f"[Storage] delete({key}): {e}")


def list_keys() -> list:
    """Return a list of all stored keys."""
    _init_schema()

    if _use_fallback():
        return list(_mem.keys())

    try:
        with _conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT key FROM kv_store ORDER BY key")
                return [row[0] for row in cur.fetchall()]
    except Exception as e:
        log.error(f"[Storage] list_keys(): {e}")
        return []


# ─── Extended Analytics API ───────────────────────────────────────────────────
# These functions are NEW additions that did not exist in the JSON version.
# They are completely optional — app.py does not call them unless you add them.

def log_trade(
    category: str,
    symbol: str,
    pnl: float,
    win: bool,
    strength: float = 0.0,
    rec: str = "",
    meta: dict = None,
) -> None:
    """
    Append a completed trade to the structured trade_log table.
    Enables SQL-based analytics: win rate by strength band, by weekday, etc.

    Call this alongside the existing journal append in app.py:
        db.log_trade("EQUITY", pos["symbol"], net, net >= 0, pos["strength"], pos["rec"])
    """
    _init_schema()
    if _use_fallback():
        return   # silently skip in fallback mode

    try:
        with _conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO trade_log
                        (category, symbol, pnl, win, strength, rec, trade_date, meta)
                    VALUES (%s, %s, %s, %s, %s, %s, CURRENT_DATE, %s)
                    """,
                    (
                        category,
                        symbol,
                        float(pnl),
                        bool(win),
                        float(strength),
                        rec,
                        json.dumps(meta or {}),
                    ),
                )
        # Also roll up into daily_pnl
        _update_daily_pnl(float(pnl))
    except Exception as e:
        log.error(f"[Storage] log_trade(): {e}")


def _update_daily_pnl(pnl: float) -> None:
    """Upsert today's P&L roll-up in the daily_pnl table."""
    try:
        with _conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO daily_pnl (trade_date, pnl, trades)
                    VALUES (CURRENT_DATE, %s, 1)
                    ON CONFLICT (trade_date) DO UPDATE
                        SET pnl        = daily_pnl.pnl + EXCLUDED.pnl,
                            trades     = daily_pnl.trades + 1,
                            updated_at = NOW()
                    """,
                    (pnl,),
                )
    except Exception as e:
        log.error(f"[Storage] _update_daily_pnl(): {e}")


def get_daily_pnl_series(days: int = 90) -> list:
    """
    Return a list of dicts [{date, pnl, trades}, ...] for the last N days.
    Useful for a calendar P&L chart in the analytics tab.
    """
    _init_schema()
    if _use_fallback():
        return []
    try:
        with _conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT trade_date::text, pnl, trades
                    FROM   daily_pnl
                    WHERE  trade_date >= CURRENT_DATE - INTERVAL '%s days'
                    ORDER  BY trade_date ASC
                    """,
                    (days,),
                )
                return [
                    {"date": r[0], "pnl": float(r[1]), "trades": r[2]}
                    for r in cur.fetchall()
                ]
    except Exception as e:
        log.error(f"[Storage] get_daily_pnl_series(): {e}")
        return []


def get_win_rate_by_strength(bins: list = None) -> list:
    """
    Return win-rate breakdown by signal-strength band.
    Default bins: [0,55,65,75,85,100]

    Returns a list of dicts:
        [{"band": "55–65%", "trades": 12, "win_rate": 58.3, "avg_pnl": 420.5}, ...]

    Add this to the analytics tab for calibrating the min_strength slider.
    """
    _init_schema()
    if _use_fallback():
        return []

    if bins is None:
        bins = [0, 55, 65, 75, 85, 100]

    results = []
    try:
        with _conn() as conn:
            with conn.cursor() as cur:
                for i in range(len(bins) - 1):
                    lo, hi = bins[i], bins[i + 1]
                    cur.execute(
                        """
                        SELECT
                            COUNT(*)                            AS trades,
                            ROUND(AVG(win::int) * 100, 1)      AS win_rate,
                            ROUND(AVG(pnl)::numeric, 0)        AS avg_pnl
                        FROM trade_log
                        WHERE strength >= %s AND strength < %s
                        """,
                        (lo, hi),
                    )
                    row = cur.fetchone()
                    if row and row[0] > 0:
                        results.append(
                            {
                                "band":     f"{lo}–{hi}%",
                                "trades":   int(row[0]),
                                "win_rate": float(row[1] or 0),
                                "avg_pnl":  float(row[2] or 0),
                            }
                        )
    except Exception as e:
        log.error(f"[Storage] get_win_rate_by_strength(): {e}")

    return results


def health_check() -> dict:
    """
    Returns a dict with connection status and row counts.
    Useful for a diagnostics panel in the sidebar.

    Example:
        st.write(db.health_check())
    """
    if _use_fallback():
        return {
            "status":   "fallback",
            "message":  "Using in-memory storage. Set DATABASE_URL to enable PostgreSQL.",
            "kv_rows":  len(_mem),
            "db_url_set": bool(DATABASE_URL),
        }
    try:
        with _conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM kv_store")
                kv_rows = cur.fetchone()[0]
                cur.execute("SELECT COUNT(*) FROM trade_log")
                trade_rows = cur.fetchone()[0]
                cur.execute("SELECT COUNT(*) FROM daily_pnl")
                daily_rows = cur.fetchone()[0]
        return {
            "status":      "connected",
            "kv_rows":     kv_rows,
            "trade_rows":  trade_rows,
            "daily_rows":  daily_rows,
            "db_url_set":  True,
        }
    except Exception as e:
        return {
            "status":  "error",
            "message": str(e),
            "db_url_set": bool(DATABASE_URL),
        }
