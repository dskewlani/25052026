"""
angel_api.py — Angel One SmartAPI Integration
=============================================
Provides real-time LTP (Last Traded Price) for:
  • Equity (NSE/BSE)
  • Options (BANKNIFTY / NIFTY / stocks)
  • Futures (BANKNIFTY / NIFTY / stocks)

Angel One SmartAPI is FREE — just needs:
  • API Key      (from MyAngelOne > API settings)
  • Client ID    (your Angel login ID)
  • Password     (your Angel trading password)
  • TOTP Secret  (from MyAngelOne > Enable TOTP)

Add to .streamlit/secrets.toml:
  [angel]
  api_key    = "abc123"
  client_id  = "A12345"
  password   = "yourpassword"
  totp_secret = "BASE32TOTPSECRET"

Angel One SmartAPI docs: https://smartapi.angelbroking.com/docs
"""

import time
import threading
import requests
from datetime import datetime, date, timedelta
from typing import Optional, Dict, Tuple

# Check if SmartAPI package is available
try:
    from SmartApi import SmartConnect as _SmartConnect
    _SMARTAPI_AVAILABLE = True
except ImportError:
    _SMARTAPI_AVAILABLE = False
    _SmartConnect = None

# ─── Session state ────────────────────────────────────────────────────────────
_angel_session: Dict = {}          # {"obj": SmartConnect, "token": str, "ts": float}
_SESSION_TTL   = 3600              # re-login every hour
_session_lock  = threading.Lock()

# ─── Price cache ──────────────────────────────────────────────────────────────
_ltp_cache: Dict[str, Tuple[float, float]] = {}   # token -> (ltp, timestamp)
_LTP_TTL   = 10                    # seconds

# ─── NSE Option Token Cache ───────────────────────────────────────────────────
# Angel One needs an instrument "token" for each contract
# We fetch the full symbol master once and build a lookup table
_instrument_df           = None    # pandas DataFrame of all instruments
_instrument_loaded_ts    = 0.0
_INSTRUMENT_TTL          = 3600    # refresh instrument list every hour


# ═══════════════════════════════════════════════════════════════════════════════
#  CREDENTIAL LOADING
# ═══════════════════════════════════════════════════════════════════════════════

def _load_creds() -> Optional[Dict]:
    """
    Load Angel One credentials from Streamlit secrets or environment variables.
    Returns dict with keys: api_key, client_id, password, totp_secret
    Returns None if credentials not configured.
    """
    # Try Streamlit secrets first
    try:
        import streamlit as st
        angel = st.secrets.get("angel", {})
        if angel.get("api_key") and angel.get("client_id"):
            return {
                "api_key":     str(angel["api_key"]).strip(),
                "client_id":   str(angel["client_id"]).strip(),
                "password":    str(angel["password"]).strip(),
                "totp_secret": str(angel.get("totp_secret", "")).strip(),
            }
    except Exception:
        pass

    # Try environment variables
    import os
    api_key = os.environ.get("ANGEL_API_KEY", "").strip()
    client_id = os.environ.get("ANGEL_CLIENT_ID", "").strip()
    if api_key and client_id:
        return {
            "api_key":     api_key,
            "client_id":   client_id,
            "password":    os.environ.get("ANGEL_PASSWORD", "").strip(),
            "totp_secret": os.environ.get("ANGEL_TOTP_SECRET", "").strip(),
        }

    return None


# ═══════════════════════════════════════════════════════════════════════════════
#  SESSION MANAGEMENT
# ═══════════════════════════════════════════════════════════════════════════════

def _get_angel_session() -> Optional[object]:
    """
    Returns an authenticated SmartConnect object.
    Caches session; re-authenticates when expired.
    Returns None if credentials not set or login fails.
    """
    global _angel_session

    with _session_lock:
        now = time.time()
        sess = _angel_session

        # Return cached session if still valid
        if sess.get("obj") and (now - sess.get("ts", 0)) < _SESSION_TTL:
            return sess["obj"]

        creds = _load_creds()
        if not creds:
            return None   # Not configured

        try:
            if not _SMARTAPI_AVAILABLE:
                return None
            from SmartApi import SmartConnect
            import pyotp

            obj = SmartConnect(api_key=creds["api_key"])

            # Generate TOTP if secret provided
            totp_val = ""
            if creds.get("totp_secret"):
                totp_val = pyotp.TOTP(creds["totp_secret"]).now()

            data = obj.generateSession(
                creds["client_id"],
                creds["password"],
                totp_val,
            )

            if data and data.get("status"):
                _angel_session = {
                    "obj": obj,
                    "token": data["data"].get("jwtToken", ""),
                    "ts": now,
                }
                return obj
            else:
                return None
        except Exception as e:
            return None


def is_configured() -> bool:
    """Returns True if Angel One credentials are available."""
    return _load_creds() is not None


# ═══════════════════════════════════════════════════════════════════════════════
#  INSTRUMENT MASTER
# ═══════════════════════════════════════════════════════════════════════════════

def _load_instrument_master() -> Optional[object]:
    """
    Downloads Angel One instrument master CSV and returns as DataFrame.
    Cached for _INSTRUMENT_TTL seconds.
    The instrument master maps symbol names → exchange tokens needed for LTP.
    """
    global _instrument_df, _instrument_loaded_ts

    now = time.time()
    if _instrument_df is not None and (now - _instrument_loaded_ts) < _INSTRUMENT_TTL:
        return _instrument_df

    try:
        import pandas as pd
        # Angel One instrument master — updated daily
        url = "https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json"
        resp = requests.get(url, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            df = pd.DataFrame(data)
            _instrument_df = df
            _instrument_loaded_ts = now
            return df
    except Exception:
        pass

    return None


def _get_token(symbol: str, exchange: str = "NSE") -> Optional[str]:
    """
    Look up Angel One instrument token for a symbol.
    symbol: e.g. "RELIANCE-EQ", "BANKNIFTY25MAY5500CE", "NIFTY25MAYFUT"
    exchange: "NSE", "BSE", "NFO" (options/futures)
    Returns token string or None.
    """
    df = _load_instrument_master()
    if df is None:
        return None

    try:
        # Filter by exchange and symbol name
        mask = (df["exch_seg"] == exchange) & (df["symbol"] == symbol)
        rows = df[mask]
        if not rows.empty:
            return str(rows.iloc[0]["token"])
    except Exception:
        pass

    return None


def _search_option_token(index: str, strike: int, opt_type: str,
                          expiry_date: date) -> Optional[str]:
    """
    Find the Angel One token for an options contract.
    Handles different symbol naming patterns Angel uses.
    """
    df = _load_instrument_master()
    if df is None:
        return None

    try:
        import pandas as pd

        # Angel One NFO option symbol format examples:
        # "BANKNIFTY25MAY5500CE", "NIFTY25MAY2250CE"
        # Expiry month: 3-letter uppercase e.g. MAY, JUN

        # Filter to NFO exchange, options instrumenttype
        nfo = df[df["exch_seg"] == "NFO"].copy()

        # Further filter by option type (CE/PE) and instrumenttype
        nfo = nfo[nfo["instrumenttype"].isin(["OPTIDX", "OPTSTK"])]

        # Filter by name (index base name)
        base = "BANKNIFTY" if "BANK" in index.upper() else "NIFTY"
        nfo = nfo[nfo["name"] == base]

        # Filter by strike
        nfo["strike_f"] = pd.to_numeric(nfo["strike"], errors="coerce") / 100.0
        nfo = nfo[nfo["strike_f"] == float(strike)]

        # Filter by option type
        nfo = nfo[nfo["symbol"].str.endswith(opt_type)]

        # Filter by expiry date
        exp_str = expiry_date.strftime("%d%b%Y").upper()   # e.g. "29MAY2025"
        exp_str2 = expiry_date.strftime("%d%b%y").upper()  # e.g. "29MAY25"

        for fmt in [exp_str, exp_str2]:
            mask = nfo["expiry"].str.upper() == fmt
            rows = nfo[mask]
            if not rows.empty:
                return str(rows.iloc[0]["token"])

        # Fallback: match by expiry column directly
        if "expiry" in nfo.columns:
            try:
                nfo["expiry_dt"] = pd.to_datetime(nfo["expiry"], dayfirst=True, errors="coerce")
                target = pd.Timestamp(expiry_date)
                close  = nfo[nfo["expiry_dt"] == target]
                if not close.empty:
                    return str(close.iloc[0]["token"])
            except Exception:
                pass

    except Exception:
        pass

    return None


def _search_equity_token(symbol: str) -> Optional[str]:
    """Find NSE equity token for a symbol like RELIANCE, INFY, etc."""
    df = _load_instrument_master()
    if df is None:
        return None
    try:
        # NSE equity symbols end with "-EQ"
        nse = df[df["exch_seg"] == "NSE"]
        eq_sym = symbol.replace(".NS", "").upper() + "-EQ"
        rows = nse[nse["symbol"] == eq_sym]
        if not rows.empty:
            return str(rows.iloc[0]["token"])
    except Exception:
        pass
    return None


# ═══════════════════════════════════════════════════════════════════════════════
#  LTP FETCHING
# ═══════════════════════════════════════════════════════════════════════════════

def _get_ltp_by_token(exchange: str, token: str) -> Optional[float]:
    """
    Fetch LTP from Angel One getMarketData API for a given exchange + token.
    Uses FULL mode which gives LTP, open, high, low, close, volume.
    Returns LTP as float or None.
    """
    # Check cache first
    cache_key = f"{exchange}:{token}"
    cached = _ltp_cache.get(cache_key)
    if cached and (time.time() - cached[1]) < _LTP_TTL:
        return cached[0]

    obj = _get_angel_session()
    if not obj:
        return None

    try:
        result = obj.getMarketData(
            mode="LTP",
            exchangeTokens={exchange: [token]},
        )
        if result and result.get("status"):
            fetched = result.get("data", {}).get("fetched", [])
            if fetched:
                ltp = float(fetched[0].get("ltp", 0))
                if ltp > 0:
                    _ltp_cache[cache_key] = (ltp, time.time())
                    return ltp
    except Exception:
        pass

    return None


def get_option_ltp(index: str, strike: int, opt_type: str,
                   expiry_str: str) -> Optional[float]:
    """
    Get live LTP for an options contract via Angel One.
    index:      "BANKNIFTY" or "NIFTY"
    strike:     int e.g. 55000
    opt_type:   "CE" or "PE"
    expiry_str: "YYYY-MM-DD" format
    Returns LTP as float or None.
    """
    try:
        exp_date = date.fromisoformat(expiry_str)
        token = _search_option_token(index, strike, opt_type, exp_date)
        if token:
            return _get_ltp_by_token("NFO", token)
    except Exception:
        pass
    return None


def get_equity_ltp(symbol: str) -> Optional[float]:
    """
    Get live LTP for an NSE equity symbol.
    symbol: e.g. "RELIANCE", "RELIANCE.NS", "INFY"
    Returns LTP as float or None.
    """
    try:
        token = _search_equity_token(symbol)
        if token:
            return _get_ltp_by_token("NSE", token)
    except Exception:
        pass
    return None


def get_index_ltp(index: str) -> Optional[float]:
    """
    Get live LTP for NIFTY or BANKNIFTY index.
    Uses Angel One's index token lookup.
    """
    # Angel One index tokens (fixed, don't change)
    INDEX_TOKENS = {
        "NIFTY":      ("NSE", "26000"),
        "BANKNIFTY":  ("NSE", "26009"),
        "NIFTY50":    ("NSE", "26000"),
        "SENSEX":     ("BSE", "1"),
        "INDIAVIX":   ("NSE", "26002"),
    }
    key = index.upper().replace(" ", "").replace("^", "")
    # Handle yfinance-style symbols
    key = {"^NSEI": "NIFTY", "^NSEBANK": "BANKNIFTY", "^INDIAVIX": "INDIAVIX",
           "^BSESN": "SENSEX"}.get(index.upper(), key)

    if key in INDEX_TOKENS:
        exchange, token = INDEX_TOKENS[key]
        return _get_ltp_by_token(exchange, token)
    return None


def get_bulk_ltp(contracts: list) -> Dict[str, float]:
    """
    Fetch LTP for multiple contracts in one API call (batched).
    contracts: list of dicts with keys: exchange, token, key
    Returns dict: {key: ltp}
    """
    obj = _get_angel_session()
    if not obj:
        return {}

    # Group by exchange
    by_exchange: Dict[str, list] = {}
    key_map: Dict[str, str] = {}  # "exchange:token" -> key

    for c in contracts:
        ex  = c["exchange"]
        tok = c["token"]
        k   = c["key"]
        by_exchange.setdefault(ex, []).append(tok)
        key_map[f"{ex}:{tok}"] = k

    result = {}
    try:
        resp = obj.getMarketData(mode="LTP", exchangeTokens=by_exchange)
        if resp and resp.get("status"):
            for item in resp.get("data", {}).get("fetched", []):
                ex  = item.get("exchange", "")
                tok = item.get("symbolToken", "")
                ltp = float(item.get("ltp", 0))
                lookup = f"{ex}:{tok}"
                if lookup in key_map and ltp > 0:
                    result[key_map[lookup]] = ltp
    except Exception:
        pass

    return result


# ═══════════════════════════════════════════════════════════════════════════════
#  OPTION CHAIN SNAPSHOT
# ═══════════════════════════════════════════════════════════════════════════════

def get_option_chain_ltp(index: str, expiry_str: str,
                          strikes: list) -> Dict[str, float]:
    """
    Bulk-fetch LTP for multiple option strikes (CE+PE) in one call.
    Returns dict: {"55000_CE": 412.5, "55000_PE": 88.3, ...}
    Much faster than individual lookups.
    """
    df = _load_instrument_master()
    if df is None:
        return {}

    try:
        import pandas as pd
        exp_date = date.fromisoformat(expiry_str)
        base     = "BANKNIFTY" if "BANK" in index.upper() else "NIFTY"

        nfo = df[df["exch_seg"] == "NFO"].copy()
        nfo = nfo[nfo["instrumenttype"].isin(["OPTIDX", "OPTSTK"])]
        nfo = nfo[nfo["name"] == base]
        nfo["strike_f"] = pd.to_numeric(nfo["strike"], errors="coerce") / 100.0

        exp_str  = exp_date.strftime("%d%b%Y").upper()
        exp_str2 = exp_date.strftime("%d%b%y").upper()

        # Filter to our expiry
        mask = nfo["expiry"].str.upper().isin([exp_str, exp_str2])
        nfo  = nfo[mask]

        # Build contract list for bulk fetch
        contracts = []
        strike_token_map = {}  # "STRIKE_TYPE" -> token
        for _, row in nfo.iterrows():
            s = int(row["strike_f"]) if row["strike_f"] == int(row["strike_f"]) else None
            if s is None or s not in strikes:
                continue
            ot = "CE" if row["symbol"].endswith("CE") else "PE" if row["symbol"].endswith("PE") else None
            if ot is None:
                continue
            k   = f"{s}_{ot}"
            tok = str(row["token"])
            contracts.append({"exchange": "NFO", "token": tok, "key": k})
            strike_token_map[k] = tok

        if not contracts:
            return {}

        return get_bulk_ltp(contracts)

    except Exception:
        return {}


# ═══════════════════════════════════════════════════════════════════════════════
#  STATUS CHECK
# ═══════════════════════════════════════════════════════════════════════════════

def get_status() -> Dict:
    """
    Returns status dict for display in UI.
    {configured, authenticated, message}
    """
    creds = _load_creds()
    if not creds:
        return {
            "configured":    False,
            "authenticated": False,
            "message":       "Angel One API not configured. Add credentials to secrets.toml",
        }

    obj = _get_angel_session()
    if obj:
        return {
            "configured":    True,
            "authenticated": True,
            "message":       f"✅ Angel One connected (Client: {creds['client_id']})",
        }
    else:
        return {
            "configured":    True,
            "authenticated": False,
            "message":       "❌ Angel One login failed. Check credentials in secrets.toml",
        }
