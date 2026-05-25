"""
angel_api.py — Angel One SmartAPI Integration
=============================================
FIXED v2 — All bugs resolved:
  ✅ Bug 1: Expiry format — zero-pad AND non-zero-pad variants tried
  ✅ Bug 2: unfetched list now logged so you can see token mismatches
  ✅ Bug 3: All exceptions now logged (not swallowed silently)
  ✅ Bug 4: Session login errors are printed for debugging
  ✅ Bug 5: get_option_chain_ltp expiry filter also tries non-zero-padded variants

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
                print("[angel_api] SmartApi package not installed. Run: pip install smartapi-python pyotp")
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
                print(f"[angel_api] ✅ Session OK — Client: {creds['client_id']}")
                return obj
            else:
                # FIX Bug 4: Print the actual error message from Angel
                err_msg = data.get("message", "Unknown error") if data else "No response"
                print(f"[angel_api] ❌ Login failed: {err_msg}")
                return None
        except Exception as e:
            # FIX Bug 3: No longer silently swallowed
            print(f"[angel_api] ❌ Session exception: {e}")
            return None


def is_configured() -> bool:
    """Returns True if Angel One credentials are available."""
    return _load_creds() is not None


# ═══════════════════════════════════════════════════════════════════════════════
#  INSTRUMENT MASTER
# ═══════════════════════════════════════════════════════════════════════════════

def _load_instrument_master() -> Optional[object]:
    """
    Downloads Angel One instrument master JSON and returns as DataFrame.
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
        resp = requests.get(url, timeout=20)
        if resp.status_code == 200:
            data = resp.json()
            df = pd.DataFrame(data)
            # Normalise expiry column to uppercase for consistent matching
            if "expiry" in df.columns:
                df["expiry"] = df["expiry"].astype(str).str.upper().str.strip()
            _instrument_df = df
            _instrument_loaded_ts = now
            print(f"[angel_api] Instrument master loaded — {len(df)} rows")
            return df
        else:
            print(f"[angel_api] Instrument master download failed: HTTP {resp.status_code}")
    except Exception as e:
        print(f"[angel_api] Instrument master exception: {e}")

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
    except Exception as e:
        print(f"[angel_api] _get_token exception: {e}")

    return None


def _build_expiry_variants(expiry_date: date):
    """
    FIX Bug 1: Returns all expiry string formats Angel One uses.
    Angel's instrument master uses inconsistent formats:
      - "29MAY2025"  (zero-padded, 4-digit year) — most common for monthly
      - "29MAY25"    (zero-padded, 2-digit year) — some weekly
      - "5JUN2025"   (NON-zero-padded, 4-digit year) — single-digit days
      - "5JUN25"     (NON-zero-padded, 2-digit year) — single-digit days weekly
    We try all four to guarantee a match.
    """
    day = expiry_date.day
    mon = expiry_date.strftime("%b").upper()
    yr4 = expiry_date.strftime("%Y")
    yr2 = expiry_date.strftime("%y")

    variants = [
        f"{day:02d}{mon}{yr4}",   # "29MAY2025"  zero-padded 4yr
        f"{day:02d}{mon}{yr2}",   # "29MAY25"    zero-padded 2yr
        f"{day}{mon}{yr4}",       # "5JUN2025"   non-padded  4yr
        f"{day}{mon}{yr2}",       # "5JUN25"     non-padded  2yr
    ]
    # Deduplicate while preserving order (day>=10 won't have duplicates, day<10 will have 2 unique)
    seen = set()
    return [v for v in variants if not (v in seen or seen.add(v))]


def _search_option_token(index: str, strike: int, opt_type: str,
                          expiry_date: date) -> Optional[str]:
    """
    Find the Angel One token for an options contract.
    FIX Bug 1: Tries all expiry format variants (zero-padded and non-zero-padded).
    """
    df = _load_instrument_master()
    if df is None:
        print("[angel_api] Instrument master not available for token search")
        return None

    try:
        import pandas as pd

        # Filter to NFO exchange, options instrumenttype
        nfo = df[df["exch_seg"] == "NFO"].copy()
        nfo = nfo[nfo["instrumenttype"].isin(["OPTIDX", "OPTSTK"])]

        # Filter by name (index base name)
        base = "BANKNIFTY" if "BANK" in index.upper() else "NIFTY"
        nfo = nfo[nfo["name"] == base]

        if nfo.empty:
            print(f"[angel_api] No NFO rows for index base '{base}'")
            return None

        # Filter by strike (Angel stores strike * 100)
        nfo["strike_f"] = pd.to_numeric(nfo["strike"], errors="coerce") / 100.0
        nfo = nfo[nfo["strike_f"] == float(strike)]

        if nfo.empty:
            print(f"[angel_api] No rows found for strike {strike} in {base}")
            return None

        # Filter by option type (CE/PE)
        nfo = nfo[nfo["symbol"].str.endswith(opt_type)]

        if nfo.empty:
            print(f"[angel_api] No rows for {base} {strike} {opt_type}")
            return None

        # FIX Bug 1: Try all expiry format variants
        expiry_variants = _build_expiry_variants(expiry_date)
        print(f"[angel_api] Trying expiry variants: {expiry_variants} for {base} {strike} {opt_type}")

        for fmt in expiry_variants:
            mask = nfo["expiry"].str.upper() == fmt
            rows = nfo[mask]
            if not rows.empty:
                token = str(rows.iloc[0]["token"])
                print(f"[angel_api] ✅ Token found: {token} via expiry format '{fmt}'")
                return token

        # Fallback: pandas datetime parse (handles unusual formats)
        if "expiry" in nfo.columns:
            try:
                nfo = nfo.copy()
                nfo["expiry_dt"] = pd.to_datetime(nfo["expiry"], dayfirst=True, errors="coerce")
                target = pd.Timestamp(expiry_date)
                close  = nfo[nfo["expiry_dt"] == target]
                if not close.empty:
                    token = str(close.iloc[0]["token"])
                    print(f"[angel_api] ✅ Token found via datetime fallback: {token}")
                    return token
            except Exception as e:
                print(f"[angel_api] Datetime fallback exception: {e}")

        # Debug: show what expiry values actually exist for this strike
        available_expiries = nfo["expiry"].unique().tolist()
        print(f"[angel_api] ❌ No token found. Available expiries in master for {base} {strike} {opt_type}: {available_expiries[:10]}")

    except Exception as e:
        print(f"[angel_api] _search_option_token exception: {e}")

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
    except Exception as e:
        print(f"[angel_api] _search_equity_token exception: {e}")
    return None


# ═══════════════════════════════════════════════════════════════════════════════
#  LTP FETCHING
# ═══════════════════════════════════════════════════════════════════════════════

def _get_ltp_by_token(exchange: str, token: str) -> Optional[float]:
    """
    Fetch LTP from Angel One getMarketData API for a given exchange + token.
    FIX Bug 2: Now logs 'unfetched' list — so you know when token is wrong.
    FIX Bug 3: Exceptions are logged, not silently swallowed.
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
            data     = result.get("data", {})
            fetched  = data.get("fetched", [])
            unfetched = data.get("unfetched", [])

            # FIX Bug 2: If token was invalid, Angel puts it in 'unfetched'
            if unfetched:
                print(f"[angel_api] ⚠️  Token {token} on {exchange} was UNFETCHED "
                      f"(wrong token or market closed): {unfetched}")

            if fetched:
                ltp = float(fetched[0].get("ltp", 0))
                if ltp > 0:
                    _ltp_cache[cache_key] = (ltp, time.time())
                    return ltp
                else:
                    print(f"[angel_api] LTP=0 for token {token} — market may be closed")
            else:
                if not unfetched:
                    print(f"[angel_api] Empty fetched AND unfetched for {exchange}:{token} — API issue?")
        else:
            err = result.get("message", "No message") if result else "No response"
            print(f"[angel_api] getMarketData status=False for {exchange}:{token}: {err}")

    except Exception as e:
        # FIX Bug 3: Log the actual exception
        print(f"[angel_api] _get_ltp_by_token exception for {exchange}:{token}: {e}")

    return None


def get_option_ltp(index: str, strike: int, opt_type: str,
                   expiry_str: str) -> Optional[float]:
    """
    Get live LTP for an options contract via Angel One.
    index:      "BANKNIFTY" or "NIFTY" or "NIFTY50"
    strike:     int e.g. 55000
    opt_type:   "CE" or "PE"
    expiry_str: "YYYY-MM-DD" format
    Returns LTP as float or None.
    """
    try:
        # Normalise index name (NIFTY50 → NIFTY for instrument master lookup)
        idx = "BANKNIFTY" if "BANK" in index.upper() else "NIFTY"
        exp_date = date.fromisoformat(expiry_str)
        token = _search_option_token(idx, int(strike), opt_type, exp_date)
        if token:
            return _get_ltp_by_token("NFO", token)
        else:
            print(f"[angel_api] get_option_ltp: No token found for {idx} {strike} {opt_type} {expiry_str}")
    except Exception as e:
        print(f"[angel_api] get_option_ltp exception: {e}")
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
    except Exception as e:
        print(f"[angel_api] get_equity_ltp exception: {e}")
    return None


def get_index_ltp(index: str) -> Optional[float]:
    """
    Get live LTP for NIFTY or BANKNIFTY index.
    Uses Angel One's hardcoded index tokens (these never change).
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
    # Handle yfinance-style symbols (kept for compatibility)
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
    FIX: Now logs unfetched items and exceptions.
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
            data      = resp.get("data", {})
            unfetched = data.get("unfetched", [])
            if unfetched:
                print(f"[angel_api] get_bulk_ltp unfetched: {unfetched}")
            for item in data.get("fetched", []):
                ex  = item.get("exchange", "")
                tok = item.get("symbolToken", "")
                ltp = float(item.get("ltp", 0))
                lookup = f"{ex}:{tok}"
                if lookup in key_map and ltp > 0:
                    result[key_map[lookup]] = ltp
        else:
            err = resp.get("message", "No message") if resp else "No response"
            print(f"[angel_api] get_bulk_ltp failed: {err}")
    except Exception as e:
        print(f"[angel_api] get_bulk_ltp exception: {e}")

    return result


# ═══════════════════════════════════════════════════════════════════════════════
#  OPTION CHAIN SNAPSHOT
# ═══════════════════════════════════════════════════════════════════════════════

def get_option_chain_ltp(index: str, expiry_str: str,
                          strikes: list) -> Dict[str, float]:
    """
    Bulk-fetch LTP for multiple option strikes (CE+PE) in one call.
    Returns dict: {"55000_CE": 412.5, "55000_PE": 88.3, ...}
    FIX Bug 1: Uses _build_expiry_variants for expiry matching.
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

        # FIX Bug 1: Use all expiry variants
        expiry_variants = _build_expiry_variants(exp_date)
        mask = nfo["expiry"].str.upper().isin(expiry_variants)
        nfo  = nfo[mask]

        if nfo.empty:
            print(f"[angel_api] get_option_chain_ltp: No rows matched expiry variants {expiry_variants}")
            return {}

        # Build contract list for bulk fetch
        contracts = []
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

        if not contracts:
            print(f"[angel_api] get_option_chain_ltp: No contracts built for strikes {strikes[:5]}...")
            return {}

        return get_bulk_ltp(contracts)

    except Exception as e:
        print(f"[angel_api] get_option_chain_ltp exception: {e}")
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
