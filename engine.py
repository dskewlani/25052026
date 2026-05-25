"""
engine.py — ProTrader Terminal v4 — Enhanced Analysis Engine
=============================================================
FIXES in v4:
  ✅ Corrected STT (delivery 0.1% both sides, intraday 0.025% sell only)
  ✅ Delivery uses 3y/1d + weekly confirmation (2y/1wk)
  ✅ EMA200 requires sufficient candle history
  ✅ Delivery min conviction raised to 70%
  ✅ Fundamentals actually fetched and used in scanner
  ✅ Half-Kelly cap: f = max(0, f) * 0.5
  ✅ SuperTrend scored in signal engine
  ✅ MACD zero-line cross filter added
  ✅ Delivery targets: 8%/12%/18%, SL 5% hard stop
  ✅ Tiered position sizing by signal strength
  ✅ Max workers reduced to 20 (yfinance throttle limit)
  ✅ Cache TTL: 15s intraday, 300s delivery/EOD

NEW in v4:
  ✅ Relative Strength vs Nifty (RS Rating) — #1 delivery filter
  ✅ Weekly trend confirmation for delivery trades
  ✅ 52-Week high breakout detector with volume confirmation
  ✅ Weinstein Stage Analysis (Stage 1–4 via 30W MA)
  ✅ Accumulation/Distribution Line (smarter than OBV alone)
  ✅ Gap-up / gap-down detection on earnings-style moves
  ✅ Earnings risk flag (< 7 days to earnings)
  ✅ Rate of Change (ROC-10) for momentum acceleration
  ✅ Stochastic RSI indicator
  ✅ VWAP + VWAP bands (±1σ, ±2σ) for intraday
  ✅ RSI thresholds adjusted for delivery (40–55 ideal entry)
  ✅ Composite stock ranking score
  ✅ Sector mapping and sector RS tagging
  ✅ Institutional accumulation proxy signal
  ✅ Options: IV Percentile computation
  ✅ Options SL: 35% for weekly, 45% for monthly
  ✅ Option strategy builder: Bull Call Spread, Bear Put Spread, Iron Condor, Straddle
"""

import numpy as np
import pandas as pd
import yfinance as yf
import math
import time
import concurrent.futures
import warnings
from datetime import datetime, date, timedelta
warnings.filterwarnings("ignore")

# ─── NSE/BSE Universe ─────────────────────────────────────────────────────────
NSE_SYMBOLS = [
    "RELIANCE.NS","TCS.NS","INFY.NS","HDFCBANK.NS","ICICIBANK.NS","SBIN.NS",
    "BAJFINANCE.NS","WIPRO.NS","AXISBANK.NS","KOTAKBANK.NS","LT.NS","HCLTECH.NS",
    "ASIANPAINT.NS","MARUTI.NS","TITAN.NS","SUNPHARMA.NS","BHARTIARTL.NS",
    "NESTLEIND.NS","ULTRACEMCO.NS","POWERGRID.NS","NTPC.NS","ONGC.NS","BPCL.NS",
    "COALINDIA.NS","IOC.NS","GAIL.NS","ADANIENT.NS","ADANIPORTS.NS","ADANIGREEN.NS","ADANIPOWER.BO","HFCL.NS","SCODATUBES.NS","IONEXCHANG.NS",
    "TATAMOTORS.NS","TATASTEEL.NS","TATACONSUM.NS","CIPLA.NS","DIVISLAB.NS",
    "DRREDDY.NS","APOLLOHOSP.NS","HINDALCO.NS","JSWSTEEL.NS","TECHM.NS",
    "HDFCLIFE.NS","SBILIFE.NS","BAJAJFINSV.NS","EICHERMOT.NS","HEROMOTOCO.NS",
    "BRITANNIA.NS","PIDILITIND.NS","DABUR.NS","MARICO.NS","COLPAL.NS",
    "HAVELLS.NS","VOLTAS.NS","BERGEPAINT.NS","GODREJCP.NS","GRASIM.NS",
    "INDUSINDBK.NS","BANDHANBNK.NS","FEDERALBNK.NS","IDFCFIRSTB.NS","PNB.NS",
    "BANKBARODA.NS","CANBK.NS","UNIONBANK.NS","SAIL.NS","NMDC.NS",
    "RECLTD.NS","PFC.NS","IRFC.NS","NHPC.NS","SJVN.NS",
    "ZOMATO.NS","NYKAA.NS","PAYTM.NS","IRCTC.NS","HAPPSTMNDS.NS",
    "PERSISTENT.NS","COFORGE.NS","MPHASIS.NS","LTIM.NS","OFSS.NS",
    "KPITTECH.NS","TATAELXSI.NS","DIXON.NS","AMBER.NS","CROMPTON.NS",
    "PAGEIND.NS","TRENT.NS","DMART.NS","ABFRL.NS","INDIGO.NS",
    "CONCOR.NS","HDFCAMC.NS","ASTRAL.NS","POLYCAB.NS","CUMMINSIND.NS",
    "BHEL.NS","ABB.NS","SIEMENS.NS","AMBUJACEM.NS","ACC.NS","SHREECEM.NS",
    "MUTHOOTFIN.NS","CHOLAFIN.NS","SHRIRAMFIN.NS","AUROPHARMA.NS",
    "TORNTPHARM.NS","LUPIN.NS","BIOCON.NS","ALKEM.NS","GLENMARK.NS",
    "ZYDUSLIFE.NS","APOLLOTYRE.NS","MRF.NS","BALKRISIND.NS","EXIDEIND.NS",
    "MOTHERSON.NS","BOSCHLTD.NS","MCDOWELL-N.NS","UBL.NS","GOLDBEES.NS","SILVERBEES.NS"
    "JUBLFOOD.NS","WESTLIFE.NS","DEVYANI.NS","NAUKRI.NS",
    "DEEPAKNTR.NS","LALPATHLAB.NS","METROPOLIS.NS",
    "HAVELLS.NS","POLYCAB.NS","DIXON.NS","AMBER.NS",
    "RVNL.NS","RAILTEL.NS","IRCON.NS","BEL.NS","HAL.NS",
    "VEDL.NS","HINDCOPPER.NS","NATIONALUM.NS",
    "SUPREMEIND.NS","ASTRAL.NS","FINOLEX.NS",
]

BSE_SYMBOLS = [
    "SENSEX.BO","RELIANCE.BO","TCS.BO","INFY.BO","HDFCBANK.BO",
    "ICICIBANK.BO","SBIN.BO","BAJFINANCE.BO","WIPRO.BO","LT.BO",
    "AXISBANK.BO","KOTAKBANK.BO","MARUTI.BO","SUNPHARMA.BO","TATAMOTORS.BO",
    "TATASTEEL.BO","BHARTIARTL.BO","ASIANPAINT.BO","TITAN.BO","HCLTECH.BO",
]

INDEX_SYMBOLS = {
    "NIFTY50":    "^NSEI",
    "BANKNIFTY":  "^NSEBANK",
    "NIFTYIT":    "^CNXIT",
    "NIFTYMID":   "^NSMIDCP",
    "SENSEX":     "^BSESN",
    "VIX":        "^INDIAVIX",
    "NIFTYPHARMA":"^CNXPHARMA",
    "NIFTYAUTO":  "^CNXAUTO",
    "NIFTYFMCG":  "^CNXFMCG",
    "NIFTYMETAL":  "^CNXMETAL",
}

FUTURES_SYMBOLS = [
    "RELIANCE.NS","TCS.NS","INFY.NS","HDFCBANK.NS","ICICIBANK.NS",
    "SBIN.NS","BAJFINANCE.NS","NIFTY_FUT","BANKNIFTY_FUT",
    "TATAMOTORS.NS","TATASTEEL.NS","AXISBANK.NS","WIPRO.NS","LT.NS",
    "KOTAKBANK.NS","ASIANPAINT.NS","MARUTI.NS","SUNPHARMA.NS",
    "BHARTIARTL.NS","HCLTECH.NS","ADANIENT.NS","ADANIPORTS.NS",
    "JSWSTEEL.NS","HINDALCO.NS","ONGC.NS","NTPC.NS","POWERGRID.NS",
]

# ─── Sector Mapping ───────────────────────────────────────────────────────────
SECTOR_MAP = {
    "HDFCBANK.NS":"Banking","ICICIBANK.NS":"Banking","SBIN.NS":"Banking",
    "AXISBANK.NS":"Banking","KOTAKBANK.NS":"Banking","INDUSINDBK.NS":"Banking",
    "BANDHANBNK.NS":"Banking","FEDERALBNK.NS":"Banking","PNB.NS":"Banking",
    "BANKBARODA.NS":"Banking","IDFCFIRSTB.NS":"Banking",
    "BAJFINANCE.NS":"NBFC","BAJAJFINSV.NS":"NBFC","CHOLAFIN.NS":"NBFC",
    "MUTHOOTFIN.NS":"NBFC","SHRIRAMFIN.NS":"NBFC","HDFCAMC.NS":"NBFC",
    "HDFCLIFE.NS":"Insurance","SBILIFE.NS":"Insurance",
    "TCS.NS":"IT","INFY.NS":"IT","WIPRO.NS":"IT","HCLTECH.NS":"IT",
    "TECHM.NS":"IT","PERSISTENT.NS":"IT","COFORGE.NS":"IT","MPHASIS.NS":"IT",
    "LTIM.NS":"IT","OFSS.NS":"IT","KPITTECH.NS":"IT","TATAELXSI.NS":"IT",
    "RELIANCE.NS":"Energy","ONGC.NS":"Energy","BPCL.NS":"Energy",
    "IOC.NS":"Energy","GAIL.NS":"Energy","PETRONET.NS":"Energy",
    "NTPC.NS":"Power","POWERGRID.NS":"Power","TATAPOWER.NS":"Power",
    "ADANIGREEN.NS":"Power","IREDA.NS":"Power","NHPC.NS":"Power",
    "SUNPHARMA.NS":"Pharma","CIPLA.NS":"Pharma","DRREDDY.NS":"Pharma",
    "DIVISLAB.NS":"Pharma","LUPIN.NS":"Pharma","AUROPHARMA.NS":"Pharma",
    "BIOCON.NS":"Pharma","TORNTPHARM.NS":"Pharma","ALKEM.NS":"Pharma",
    "MARUTI.NS":"Auto","TATAMOTORS.NS":"Auto","EICHERMOT.NS":"Auto",
    "HEROMOTOCO.NS":"Auto","BAJAJFINSV.NS":"Auto","MOTHERSON.NS":"Auto",
    "LT.NS":"Capital Goods","SIEMENS.NS":"Capital Goods","ABB.NS":"Capital Goods",
    "BHEL.NS":"Capital Goods","BEL.NS":"Defence","HAL.NS":"Defence",
    "TATASTEEL.NS":"Metals","JSWSTEEL.NS":"Metals","HINDALCO.NS":"Metals",
    "VEDL.NS":"Metals","SAIL.NS":"Metals","NMDC.NS":"Metals",
    "ASIANPAINT.NS":"FMCG","BRITANNIA.NS":"FMCG","NESTLEIND.NS":"FMCG",
    "DABUR.NS":"FMCG","MARICO.NS":"FMCG","COLPAL.NS":"FMCG",
    "GODREJCP.NS":"FMCG","TITAN.NS":"Consumer","TRENT.NS":"Retail",
    "DMART.NS":"Retail","ZOMATO.NS":"Consumer Tech","NAUKRI.NS":"Consumer Tech",
    "ADANIENT.NS":"Conglomerate","ADANIPORTS.NS":"Infrastructure",
    "APOLLOHOSP.NS":"Healthcare","LALPATHLAB.NS":"Healthcare",
    "ULTRACEMCO.NS":"Cement","AMBUJACEM.NS":"Cement","SHREECEM.NS":"Cement",
}

SECTOR_ETFS = {
    "Banking":    "^NSEBANK",
    "IT":         "^CNXIT",
    "Pharma":     "^CNXPHARMA",
    "Auto":       "^CNXAUTO",
    "FMCG":       "^CNXFMCG",
    "Metals":     "^CNXMETAL",
    "Energy":     "^NSEI",
    "Power":      "^NSEI",
    "Capital Goods":"^NSEI",
}

# ─── Helpers ──────────────────────────────────────────────────────────────────
def _sf(val, default=0.0):
    try:
        v = float(val.iloc[-1]) if isinstance(val, pd.Series) else float(val)
        return v if np.isfinite(v) else default
    except Exception:
        return default

# ─── Data Fetching with Smart Cache TTL ───────────────────────────────────────
_price_cache = {}

def get_ohlcv(symbol, period="3mo", interval="1d"):
    cache_key = f"{symbol}_{period}_{interval}"
    cached = _price_cache.get(cache_key)
    # Intraday: 15s TTL; EOD/delivery: 300s TTL
    ttl = 15 if interval in ("1m","5m","15m","30m","1h") else 300
    if cached and (time.time() - cached["ts"]) < ttl:
        return cached["df"]
    try:
        df = yf.Ticker(symbol).history(period=period, interval=interval)
        if not df.empty:
            df.index = pd.to_datetime(df.index)
            _price_cache[cache_key] = {"df": df, "ts": time.time()}
            return df
    except Exception:
        pass
    return None

def get_live_price(symbol):
    """
    Fetch live equity/index price.
    Priority:
      1. Angel One SmartAPI (real exchange LTP, most accurate)
      2. yfinance history (1m candle)
      3. yfinance fast_info
    Returns float or None.
    """
    # ── 1. Angel One (real LTP from exchange) ────────────────────────────────
    try:
        import angel_api as _angel
        if _angel.is_configured():
            # Try as index first (NIFTY, BANKNIFTY, SENSEX, VIX)
            lp = _angel.get_index_ltp(symbol)
            if lp and np.isfinite(lp) and lp > 0:
                return lp
            # Try as equity
            lp = _angel.get_equity_ltp(symbol)
            if lp and np.isfinite(lp) and lp > 0:
                return lp
    except Exception:
        pass

    # ── 2. yfinance history ───────────────────────────────────────────────────
    try:
        t = yf.Ticker(symbol)
        h = t.history(period="1d", interval="1m")
        if h is not None and not h.empty:
            lp = float(h["Close"].iloc[-1])
            if np.isfinite(lp) and lp > 0:
                return lp
    except Exception:
        pass

    # ── 3. yfinance fast_info ─────────────────────────────────────────────────
    try:
        lp = yf.Ticker(symbol).fast_info.last_price
        return float(lp) if lp and np.isfinite(float(lp)) and float(lp) > 0 else None
    except Exception:
        return None


# ─── NSE Option Chain Cache ───────────────────────────────────────────────────
# Caches full option chain per index to avoid repeated API calls
_nse_chain_cache: dict = {}   # { index_name: (chain_dict, timestamp) }
_NSE_CHAIN_TTL   = 12         # seconds — matches auto-refresh interval

# NSE session cache (session with cookies, valid for several minutes)
_nse_session_cache: dict = {}   # { "session": requests.Session, "ts": float }
_NSE_SESSION_TTL = 300          # refresh session every 5 minutes

# Spot price cache for BS fallback
_spot_cache: dict = {}
_SPOT_CACHE_TTL  = 10


def _get_nse_session():
    """
    Returns a requests.Session pre-warmed with NSE cookies.
    NSE requires visiting the homepage first to get cookies, then API calls work.
    Session is cached and reused for up to 5 minutes.
    """
    import requests as _req
    import time as _t

    cached = _nse_session_cache.get("session")
    cached_ts = _nse_session_cache.get("ts", 0)
    if cached and (_t.time() - cached_ts) < _NSE_SESSION_TTL:
        return cached

    session = _req.Session()
    session.headers.update({
        "User-Agent":      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                           "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept":          "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection":      "keep-alive",
        "DNT":             "1",
        "Upgrade-Insecure-Requests": "1",
    })
    try:
        # Warm up session — visit NSE homepage to get cookies
        session.get("https://www.nseindia.com", timeout=10)
        # Also visit option chain page to get additional cookies
        session.get("https://www.nseindia.com/option-chain", timeout=10)
    except Exception:
        pass

    _nse_session_cache["session"] = session
    _nse_session_cache["ts"] = _t.time()
    return session


def _fetch_nse_option_chain_direct(index_name: str) -> dict:
    """
    Fetch live NSE option chain via NSE India's official API.
    Uses a warmed session with cookies — returns actual market LTP.
    Returns dict: { "STRIKE_EXPIRY_TYPE": lastPrice } e.g. {"24000_29-May-2025_CE": 144.5}
    """
    import time as _t

    sym = "BANKNIFTY" if "BANK" in index_name.upper() else "NIFTY"
    url = f"https://www.nseindia.com/api/option-chain-indices?symbol={sym}"

    session = _get_nse_session()
    api_headers = {
        "Accept":          "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Referer":         "https://www.nseindia.com/option-chain",
        "X-Requested-With": "XMLHttpRequest",
    }

    try:
        resp = session.get(url, headers=api_headers, timeout=10)
        if resp.status_code != 200:
            # Session expired — force refresh and retry once
            _nse_session_cache.clear()
            session = _get_nse_session()
            resp = session.get(url, headers=api_headers, timeout=10)

        if resp.status_code != 200:
            return {}

        data    = resp.json()
        records = data.get("records", {})
        rows    = records.get("data", [])
        result  = {}
        for row in rows:
            strike = row.get("strikePrice")
            expiry = row.get("expiryDate", "")   # "29-May-2025" format from NSE
            for ot in ("CE", "PE"):
                leg = row.get(ot, {})
                ltp = leg.get("lastPrice", 0)
                if strike and ltp and float(ltp) > 0:
                    key = f"{int(strike)}_{expiry}_{ot}"
                    result[key] = float(ltp)
        return result
    except Exception:
        return {}


def _fetch_nse_option_chain_nsepython(index_name: str) -> dict:
    """
    Fallback: fetch via nsepython library.
    Returns dict: { "STRIKE_EXPIRY_TYPE": lastPrice }
    """
    try:
        from nsepython import nse_optionchain_scrapper
        sym  = "BANKNIFTY" if "BANK" in index_name.upper() else "NIFTY"
        data = nse_optionchain_scrapper(sym)
        if not data:
            return {}
        records = data.get("records", {})
        rows    = records.get("data", [])
        result  = {}
        for row in rows:
            strike = row.get("strikePrice")
            expiry = row.get("expiryDate", "")
            for ot in ("CE", "PE"):
                leg = row.get(ot, {})
                ltp = leg.get("lastPrice", 0)
                if strike and ltp and float(ltp) > 0:
                    key = f"{int(strike)}_{expiry}_{ot}"
                    result[key] = float(ltp)
        return result
    except Exception:
        return {}


def _fetch_nse_option_chain(index_name: str) -> dict:
    """
    Master fetcher: tries direct NSE API first (most accurate, real LTP),
    falls back to nsepython library if direct API fails.
    Returns dict: { "STRIKE_EXPIRY_TYPE": lastPrice } e.g. {"24000_29-May-2025_CE": 144.5}
    Returns empty dict on complete failure.
    """
    # Strategy 1: Direct NSE API (most accurate — actual exchange data)
    result = _fetch_nse_option_chain_direct(index_name)
    if result:
        return result

    # Strategy 2: nsepython library fallback
    result = _fetch_nse_option_chain_nsepython(index_name)
    if result:
        return result

    return {}


def _get_nse_chain_cached(index_name: str) -> dict:
    """Returns cached NSE option chain, refreshing if older than TTL."""
    import time as _t
    now = _t.time()
    cached = _nse_chain_cache.get(index_name)
    if cached and (now - cached[1]) < _NSE_CHAIN_TTL:
        return cached[0]
    chain = _fetch_nse_option_chain(index_name)
    if chain:                                     # only cache non-empty results
        _nse_chain_cache[index_name] = (chain, now)
    return chain


def get_spot_cached(index_name: str):
    """Live NIFTY/BANKNIFTY spot with TTL cache."""
    import time as _t
    sym   = "^NSEBANK" if "BANK" in index_name.upper() else "^NSEI"
    now   = _t.time()
    cached = _spot_cache.get(sym)
    if cached and (now - cached[1]) < _SPOT_CACHE_TTL:
        return cached[0]
    price = get_live_price(sym)
    if price:
        _spot_cache[sym] = (price, now)
    return price


def get_option_live_price(index_name: str, strike: float, opt_type: str,
                          expiry_str: str, entry_price: float):
    """
    Returns (price, source) tuple:
      price  — live option CMP as float (or None)
      source — "ANGEL_LIVE" | "NSE_LIVE" | "YFINANCE" | "BS_THEORETICAL" | "STALE"

    Priority:
      1. Angel One SmartAPI  — real exchange LTP (most accurate, free)
      2. NSE Direct API      — real LTP from NSE website
      3. yfinance option ticker
      4. Black-Scholes       — theoretical only, last resort
      5. entry_price         — stale fallback
    """
    # ── 1. Angel One SmartAPI (real exchange LTP) ─────────────────────────────
    try:
        import angel_api as _angel
        if _angel.is_configured():
            ltp = _angel.get_option_ltp(
                index_name, int(strike), opt_type, expiry_str
            )
            if ltp and float(ltp) > 0:
                return float(ltp), "ANGEL_LIVE"
    except Exception:
        pass

    # ── 2. NSE Live (Direct API + nsepython fallback) ─────────────────────────
    try:
        from datetime import datetime as _dt
        chain = _get_nse_chain_cached(index_name)
        if chain:
            # Try multiple expiry date formats NSE might use
            try:
                exp_dt   = _dt.strptime(expiry_str, "%Y-%m-%d")
                exp_nse1 = exp_dt.strftime("%d-%b-%Y")   # 29-May-2025
                exp_nse2 = exp_dt.strftime("%d %b %Y")   # 29 May 2025
                exp_nse3 = exp_dt.strftime("%d-%b-%y")   # 29-May-25
            except Exception:
                exp_nse1 = exp_nse2 = exp_nse3 = expiry_str

            strike_int = int(strike)
            for exp_fmt in (exp_nse1, exp_nse2, exp_nse3):
                key = f"{strike_int}_{exp_fmt}_{opt_type}"
                if key in chain:
                    return chain[key], "NSE_LIVE"

            # Fuzzy match: find nearest expiry in chain for this strike+type
            prefix     = f"{strike_int}_"
            suffix     = f"_{opt_type}"
            candidates = [k for k in chain if k.startswith(prefix) and k.endswith(suffix)]
            if candidates:
                try:
                    target_dt = _dt.strptime(expiry_str, "%Y-%m-%d")
                    best_key  = None
                    best_diff = float("inf")
                    for c in candidates:
                        parts = c.split("_")
                        if len(parts) >= 3:
                            exp_part = "_".join(parts[1:-1])
                            for fmt in ("%d-%b-%Y", "%d %b %Y", "%d-%b-%y"):
                                try:
                                    cd   = _dt.strptime(exp_part, fmt)
                                    diff = abs((cd - target_dt).days)
                                    if diff < best_diff:
                                        best_diff = diff
                                        best_key  = c
                                    break
                                except Exception:
                                    continue
                    if best_key and best_diff <= 7:   # within 7 days = same expiry week
                        return chain[best_key], "NSE_LIVE"
                except Exception:
                    pass
    except Exception:
        pass

    # ── 2. yfinance option ticker ─────────────────────────────────────────────
    try:
        from datetime import datetime as _dt2
        exp_dt2  = _dt2.strptime(expiry_str, "%Y-%m-%d")
        exp_str2 = exp_dt2.strftime("%d%b%y").upper()     # 29MAY25
        sym      = f"{index_name.upper()}{exp_str2}{int(strike)}{opt_type}.NS"
        t        = yf.Ticker(sym)
        h        = t.history(period="1d", interval="1m")
        if h is not None and not h.empty:
            lp = float(h["Close"].iloc[-1])
            if np.isfinite(lp) and lp > 0:
                return lp, "YFINANCE"
        lp = t.fast_info.last_price
        if lp and np.isfinite(float(lp)) and float(lp) > 0:
            return float(lp), "YFINANCE"
    except Exception:
        pass

    # ── 3. Black-Scholes with live spot (THEORETICAL — not market price) ──────
    try:
        from datetime import date as _date
        spot = get_spot_cached(index_name)
        if spot:
            dte   = max(1, (_date.fromisoformat(expiry_str) - _date.today()).days)
            T     = dte / 365.0
            r     = 0.065
            iv    = 0.22 if "BANK" in index_name.upper() else 0.18
            price = bs_greeks(spot, float(strike), T, r, iv, opt_type).get("price", 0)
            if price and float(price) > 0:
                return float(price), "BS_THEORETICAL"
    except Exception:
        pass

    # ── 4. Stale entry price ──────────────────────────────────────────────────
    return entry_price, "STALE"


def get_fundamentals(symbol):
    try:
        info = yf.Ticker(symbol).info
        return {
            "name":        info.get("longName", symbol),
            "sector":      info.get("sector", "N/A"),
            "industry":    info.get("industry", "N/A"),
            "pe":          info.get("trailingPE"),
            "pb":          info.get("priceToBook"),
            "roe":         info.get("returnOnEquity"),
            "de":          info.get("debtToEquity"),
            "eps":         info.get("trailingEps"),
            "beta":        info.get("beta"),
            "mktcap":      info.get("marketCap"),
            "52h":         info.get("fiftyTwoWeekHigh"),
            "52l":         info.get("fiftyTwoWeekLow"),
            "avg_vol":     info.get("averageVolume"),
            "div_yield":   info.get("dividendYield"),
            "earnings_ts": info.get("earningsTimestamp"),
            "fwd_pe":      info.get("forwardPE"),
            "peg":         info.get("pegRatio"),
            "revenue_gr":  info.get("revenueGrowth"),
            "earn_gr":     info.get("earningsGrowth"),
        }
    except Exception:
        return {}

# ─── NEW: Relative Strength vs Nifty ─────────────────────────────────────────
_nifty_cache = {}

def get_nifty_return(period_days=65):
    """Return Nifty % change over last ~period_days trading days."""
    cache_key = f"nifty_{period_days}"
    cached = _nifty_cache.get(cache_key)
    if cached and (time.time() - cached["ts"]) < 3600:
        return cached["val"]
    try:
        df = get_ohlcv("^NSEI", "1y", "1d")
        if df is not None and len(df) >= period_days:
            c = df["Close"].astype(float)
            ret = (c.iloc[-1] - c.iloc[-period_days]) / c.iloc[-period_days] * 100
            _nifty_cache[cache_key] = {"val": float(ret), "ts": time.time()}
            return float(ret)
    except Exception:
        pass
    return 0.0

def compute_rs_rating(df_stock, period_days=65):
    """
    Relative Strength Rating vs Nifty50.
    RS > 1.0 = outperforming Nifty = GOOD for delivery
    RS > 1.3 = strong outperformer = EXCELLENT entry candidate
    """
    try:
        if df_stock is None or len(df_stock) < period_days:
            return None
        c = df_stock["Close"].astype(float)
        stock_ret = (c.iloc[-1] - c.iloc[-period_days]) / c.iloc[-period_days] * 100
        nifty_ret = get_nifty_return(period_days)
        if nifty_ret == 0:
            return None
        # RS ratio — above 1.0 means stock beats Nifty
        rs = (1 + stock_ret / 100) / (1 + nifty_ret / 100)
        return round(rs, 3)
    except Exception:
        return None

# ─── NEW: Weinstein Stage Analysis ───────────────────────────────────────────
def weinstein_stage(df_weekly):
    """
    Determine Weinstein Stage (1–4) using weekly data.
    Stage 2 = Uptrend = BUY zone.
    Requires weekly OHLCV with ~52+ candles.
    """
    try:
        if df_weekly is None or len(df_weekly) < 30:
            return None, "Insufficient weekly data"
        c = df_weekly["Close"].astype(float)
        v = df_weekly["Volume"].astype(float) if "Volume" in df_weekly.columns else pd.Series(np.ones(len(c)))
        ma30 = c.rolling(30).mean()
        last_close = c.iloc[-1]
        last_ma30  = ma30.iloc[-1]
        # Slope of 30W MA
        slope = (ma30.iloc[-1] - ma30.iloc[-5]) / ma30.iloc[-5] * 100 if ma30.iloc[-5] > 0 else 0
        # Volume trend (last 10W avg vs prior 20W avg)
        vol_recent = v.iloc[-10:].mean()
        vol_prior  = v.iloc[-30:-10].mean() if len(v) >= 30 else v.mean()
        vol_expanding = vol_recent > vol_prior

        if last_close > last_ma30 and slope > 0.5:
            stage = 2
            desc  = "Stage 2 — Uptrend ✅ (BUY zone)"
        elif last_close > last_ma30 and slope <= 0.5:
            stage = 3
            desc  = "Stage 3 — Topping ⚠️ (avoid new positions)"
        elif last_close < last_ma30 and slope < -0.5:
            stage = 4
            desc  = "Stage 4 — Downtrend 🔴 (do not touch)"
        else:
            stage = 1
            desc  = "Stage 1 — Basing 🔵 (wait for breakout)"
        return stage, desc
    except Exception:
        return None, "Stage analysis failed"

# ─── NEW: Accumulation/Distribution Line ─────────────────────────────────────
def compute_ad_line(df):
    """
    Accumulation/Distribution Line.
    Rising A/D on rising price = institutional buying confirmed.
    """
    try:
        h = df["High"].astype(float)
        l = df["Low"].astype(float)
        c = df["Close"].astype(float)
        v = df["Volume"].astype(float) if "Volume" in df.columns else pd.Series(np.ones(len(c)))
        clv = ((c - l) - (h - c)) / (h - l + 0.001)
        ad  = (clv * v).cumsum()
        # Trend: last 5 vs prior 5
        if len(ad) >= 10:
            ad_trend = (ad.iloc[-1] - ad.iloc[-6]) / (abs(ad.iloc[-6]) + 1)
        else:
            ad_trend = 0.0
        return float(ad.iloc[-1]), float(ad_trend)
    except Exception:
        return 0.0, 0.0

# ─── NEW: Gap Detection ───────────────────────────────────────────────────────
def detect_gap(df):
    """
    Detect gap-up or gap-down vs previous close.
    Gap-up > 2% on high volume = high-probability delivery setup.
    """
    try:
        if df is None or len(df) < 2:
            return None, 0.0
        o  = df["Open"].astype(float)
        c  = df["Close"].astype(float)
        v  = df["Volume"].astype(float) if "Volume" in df.columns else pd.Series(np.ones(len(c)))
        prev_close = c.iloc[-2]
        today_open = o.iloc[-1]
        gap_pct = (today_open - prev_close) / prev_close * 100
        vma20 = v.rolling(20).mean().iloc[-1]
        vr    = v.iloc[-1] / vma20 if vma20 > 0 else 1.0
        if gap_pct >= 2.0 and vr >= 1.5:
            return "GAP_UP", round(gap_pct, 2)
        elif gap_pct <= -2.0 and vr >= 1.5:
            return "GAP_DOWN", round(gap_pct, 2)
        return None, round(gap_pct, 2)
    except Exception:
        return None, 0.0

# ─── NEW: Earnings Risk Check ─────────────────────────────────────────────────
def earnings_risk(fund):
    """Check if earnings are within 7 days — flag as RISKY for delivery."""
    try:
        ets = fund.get("earnings_ts")
        if not ets:
            return False, None
        earnings_dt = datetime.fromtimestamp(ets).date()
        days_to_earnings = (earnings_dt - date.today()).days
        if 0 <= days_to_earnings <= 7:
            return True, days_to_earnings
        return False, days_to_earnings
    except Exception:
        return False, None

# ─── NEW: 52-Week High Breakout ───────────────────────────────────────────────
def check_52w_breakout(df, fund=None):
    """
    Returns True + volume ratio if price breaks above 52W high with volume > 1.8x.
    This is the #1 delivery BUY signal in Indian markets.
    """
    try:
        if df is None or len(df) < 252:
            # Fall back to fund data
            if fund:
                high52 = fund.get("52h")
                c = df["Close"].astype(float).iloc[-1] if df is not None else None
                if high52 and c and c >= float(high52) * 0.99:
                    return True, 1.0
            return False, 0.0
        c = df["Close"].astype(float)
        v = df["Volume"].astype(float) if "Volume" in df.columns else pd.Series(np.ones(len(c)))
        high_52w = c.iloc[-252:-1].max()
        last_c = c.iloc[-1]
        vma20 = v.rolling(20).mean().iloc[-1]
        vr = v.iloc[-1] / vma20 if vma20 > 0 else 1.0
        if last_c >= high_52w * 0.99 and vr >= 1.8:
            return True, round(vr, 2)
        return False, round(vr, 2)
    except Exception:
        return False, 0.0

# ─── NEW: VWAP + Bands ────────────────────────────────────────────────────────
def compute_vwap(df):
    """VWAP and ±1σ, ±2σ bands for intraday use."""
    try:
        if df is None or len(df) < 5:
            return None
        tp = (df["High"].astype(float) + df["Low"].astype(float) + df["Close"].astype(float)) / 3
        v  = df["Volume"].astype(float) if "Volume" in df.columns else pd.Series(np.ones(len(tp)))
        vwap = (tp * v).cumsum() / v.cumsum()
        std  = tp.rolling(min(20, len(tp))).std()
        return {
            "vwap":   float(vwap.iloc[-1]),
            "vwap_u1": float(vwap.iloc[-1] + std.iloc[-1]),
            "vwap_u2": float(vwap.iloc[-1] + 2 * std.iloc[-1]),
            "vwap_l1": float(vwap.iloc[-1] - std.iloc[-1]),
            "vwap_l2": float(vwap.iloc[-1] - 2 * std.iloc[-1]),
        }
    except Exception:
        return None

# ─── NEW: Rate of Change ──────────────────────────────────────────────────────
def compute_roc(c, period=10):
    """Rate of Change — measures price acceleration."""
    try:
        if len(c) < period + 1:
            return 0.0
        roc = (c.iloc[-1] - c.iloc[-(period+1)]) / c.iloc[-(period+1)] * 100
        return round(float(roc), 3)
    except Exception:
        return 0.0

# ─── NEW: Stochastic RSI ──────────────────────────────────────────────────────
def compute_stoch_rsi(rsi_series, period=14):
    """Stochastic RSI — better than plain RSI for overbought/oversold."""
    try:
        if rsi_series is None or len(rsi_series) < period:
            return 50.0, 50.0
        rsi_min = rsi_series.rolling(period).min()
        rsi_max = rsi_series.rolling(period).max()
        stoch_k = 100 * (rsi_series - rsi_min) / (rsi_max - rsi_min + 0.001)
        stoch_d = stoch_k.rolling(3).mean()
        return float(stoch_k.iloc[-1]), float(stoch_d.iloc[-1])
    except Exception:
        return 50.0, 50.0

# ─── NEW: IV Percentile ───────────────────────────────────────────────────────
def compute_iv_percentile(vix, lookback_high=30, lookback_low=11):
    """
    Approximate IV Percentile from VIX.
    IVP > 50 = IV elevated (sell premium)
    IVP < 25 = IV cheap (buy options)
    """
    try:
        ivp = (vix - lookback_low) / (lookback_high - lookback_low) * 100
        return max(0, min(100, round(ivp, 1)))
    except Exception:
        return 50.0

# ─── Indicator Engine ─────────────────────────────────────────────────────────
def compute_indicators(df, for_delivery=False):
    """
    Compute all technical indicators.
    for_delivery=True uses longer EMA periods and skips intraday-only metrics.
    """
    if df is None or len(df) < 20:
        return {}
    try:
        c = df["Close"].astype(float)
        h = df["High"].astype(float)
        l = df["Low"].astype(float)
        v = df["Volume"].astype(float) if "Volume" in df.columns else pd.Series(np.ones(len(c)), index=c.index)

        # RSI
        d     = c.diff()
        g_    = d.clip(lower=0).ewm(span=14, adjust=False).mean()
        ls_   = (-d.clip(upper=0)).ewm(span=14, adjust=False).mean()
        rsi   = 100 - 100 / (1 + g_ / ls_.replace(0, np.nan))

        # Stochastic RSI
        srsi_k, srsi_d = compute_stoch_rsi(rsi)

        # MACD
        e12   = c.ewm(span=12, adjust=False).mean()
        e26   = c.ewm(span=26, adjust=False).mean()
        macd  = e12 - e26
        msig  = macd.ewm(span=9, adjust=False).mean()
        mhist = macd - msig

        # Bollinger Bands
        s20   = c.rolling(20).mean()
        sd20  = c.rolling(20).std()
        bbu   = s20 + 2*sd20
        bbl   = s20 - 2*sd20
        bbpct = (c - bbl) / (bbu - bbl + 0.001)

        # ATR
        tr    = pd.concat([h-l,(h-c.shift()).abs(),(l-c.shift()).abs()],axis=1).max(axis=1)
        atr   = tr.rolling(14).mean()

        # EMAs
        e5    = c.ewm(span=5,   adjust=False).mean()
        e9    = c.ewm(span=9,   adjust=False).mean()
        e13   = c.ewm(span=13,  adjust=False).mean()
        e21   = c.ewm(span=21,  adjust=False).mean()
        e50   = c.ewm(span=50,  adjust=False).mean()
        # EMA200: only trust if we have 250+ candles
        e200_val = float(c.ewm(span=200, adjust=False).mean().iloc[-1]) if len(c) >= 250 else 0.0

        # Stochastic
        l14   = l.rolling(14).min()
        h14   = h.rolling(14).max()
        sk    = 100*(c-l14)/(h14-l14+0.001)
        sd_k  = sk.rolling(3).mean()

        # ADX
        pdm   = (h.diff()).clip(lower=0)
        ndm   = (-l.diff()).clip(lower=0)
        pdi   = 100*pdm.ewm(span=14).mean()/atr.replace(0,np.nan)
        ndi   = 100*ndm.ewm(span=14).mean()/atr.replace(0,np.nan)
        dx    = 100*(pdi-ndi).abs()/(pdi+ndi+0.001)
        adx   = dx.ewm(span=14).mean()

        # Williams %R
        wr    = -100*(h14-c)/(h14-l14+0.001)

        # CCI
        tp    = (h+l+c)/3
        cci   = (tp - tp.rolling(20).mean())/(0.015*tp.rolling(20).std()+0.001)

        # Volume analysis
        vma20 = v.rolling(20).mean().replace(0, np.nan)
        vratio= v/vma20
        obv   = (np.sign(c.diff())*v).cumsum()

        # Accumulation/Distribution
        ad_val, ad_trend = compute_ad_line(df)

        # Pivot / S&R
        pivot = (h.iloc[-1]+l.iloc[-1]+c.iloc[-1])/3
        r1    = 2*pivot - l.iloc[-1]
        s1    = 2*pivot - h.iloc[-1]
        r2    = pivot + (h.iloc[-1]-l.iloc[-1])
        s2    = pivot - (h.iloc[-1]-l.iloc[-1])
        r3    = h.iloc[-1] + 2*(pivot-l.iloc[-1])
        s3    = l.iloc[-1] - 2*(h.iloc[-1]-pivot)

        # Momentum
        m5    = float((c.iloc[-1]-c.iloc[-5])/c.iloc[-5]*100)  if len(c)>=5  else 0
        m20   = float((c.iloc[-1]-c.iloc[-20])/c.iloc[-20]*100) if len(c)>=20 else 0
        m60   = float((c.iloc[-1]-c.iloc[-60])/c.iloc[-60]*100) if len(c)>=60 else 0

        # Rate of Change
        roc10 = compute_roc(c, 10)
        roc20 = compute_roc(c, 20)

        # Squeeze Momentum (TTM style)
        kc_u  = s20 + 1.5*atr
        kc_l  = s20 - 1.5*atr
        squeeze = (bbl > kc_l) & (bbu < kc_u)

        # Day change
        prev  = c.shift(1)
        day_chg = ((c-prev)/prev.replace(0,np.nan))*100

        # SuperTrend (properly scored now)
        hl2   = (h+l)/2
        mult  = 3.0
        st_up = hl2 - mult*atr
        st_dn = hl2 + mult*atr
        # SuperTrend direction: close above st_up = uptrend
        st_bullish = float(c.iloc[-1]) > float(st_up.iloc[-1])
        st_bearish = float(c.iloc[-1]) < float(st_dn.iloc[-1])

        # VWAP (useful for intraday; included for all)
        vwap_data = compute_vwap(df) or {}

        # Gap detection
        gap_type, gap_pct = detect_gap(df)

        return {
            "rsi": _sf(rsi), "rsi_s": rsi,
            "srsi_k": srsi_k, "srsi_d": srsi_d,
            "macd": _sf(macd), "macd_sig": _sf(msig), "macd_hist": _sf(mhist),
            "macd_s": macd, "msig_s": msig,
            "macd_above_zero": float(macd.iloc[-1]) > 0,
            "bb_pct": _sf(bbpct), "bb_u": _sf(bbu), "bb_l": _sf(bbl), "bb_mid": _sf(s20),
            "atr": _sf(atr),
            "e5": _sf(e5), "e9": _sf(e9), "e13": _sf(e13),
            "e21": _sf(e21), "e50": _sf(e50), "e200": e200_val,
            "sk": _sf(sk), "sd": _sf(sd_k),
            "adx": _sf(adx), "pdi": _sf(pdi), "ndi": _sf(ndi),
            "wr": _sf(wr), "cci": _sf(cci),
            "vr": _sf(vratio), "obv": _sf(obv),
            "ad_line": ad_val, "ad_trend": ad_trend,
            "pivot": pivot, "r1": r1, "r2": r2, "r3": r3,
            "s1": s1, "s2": s2, "s3": s3,
            "m5": m5, "m20": m20, "m60": m60,
            "roc10": roc10, "roc20": roc20,
            "squeeze": bool(squeeze.iloc[-1]),
            "close": _sf(c), "high": _sf(h), "low": _sf(l), "open": _sf(df["Open"].astype(float)),
            "volume": _sf(v), "avg_vol_20": _sf(vma20),
            "day_chg": _sf(day_chg),
            "st_up": _sf(st_up), "st_dn": _sf(st_dn),
            "st_bullish": st_bullish, "st_bearish": st_bearish,
            "vwap": vwap_data.get("vwap", 0),
            "vwap_u1": vwap_data.get("vwap_u1", 0),
            "vwap_l1": vwap_data.get("vwap_l1", 0),
            "vwap_u2": vwap_data.get("vwap_u2", 0),
            "vwap_l2": vwap_data.get("vwap_l2", 0),
            "gap_type": gap_type, "gap_pct": gap_pct,
        }
    except Exception as e:
        return {}

# ─── Candlestick Patterns ─────────────────────────────────────────────────────
def detect_patterns(df):
    if df is None or len(df) < 4:
        return []
    patterns = []
    try:
        o = df["Open"].astype(float)
        h = df["High"].astype(float)
        l = df["Low"].astype(float)
        c = df["Close"].astype(float)
        o1,o2,o3 = o.iloc[-3],o.iloc[-2],o.iloc[-1]
        h1,h2,h3 = h.iloc[-3],h.iloc[-2],h.iloc[-1]
        l1,l2,l3 = l.iloc[-3],l.iloc[-2],l.iloc[-1]
        c1,c2,c3 = c.iloc[-3],c.iloc[-2],c.iloc[-1]
        b3 = abs(c3-o3); r3 = h3-l3 if h3!=l3 else 0.001
        b2 = abs(c2-o2); r2 = h2-l2 if h2!=l2 else 0.001
        lw3 = min(o3,c3)-l3; uw3 = h3-max(o3,c3)

        if b3/r3 < 0.1:                                               patterns.append(("Doji","NEUTRAL"))
        if lw3>2*b3 and uw3<b3 and c2<o2:                             patterns.append(("Hammer","BUY"))
        if uw3>2*b3 and lw3<b3 and c2>o2:                             patterns.append(("Shooting Star","SELL"))
        if c2<o2 and c3>o3 and o3<c2 and c3>o2:                       patterns.append(("Bullish Engulfing","BUY"))
        if c2>o2 and c3<o3 and o3>c2 and c3<o2:                       patterns.append(("Bearish Engulfing","SELL"))
        if c1<o1 and b2<r2*0.3 and c3>o3 and c3>(o1+c1)/2:            patterns.append(("Morning Star","BUY"))
        if c1>o1 and b2<r2*0.3 and c3<o3 and c3<(o1+c1)/2:            patterns.append(("Evening Star","SELL"))
        if c3>o3 and b3>b2*2 and lw3<b3*0.3 and uw3<b3*0.3:          patterns.append(("Marubozu Bull","BUY"))
        if c3<o3 and b3>b2*2 and lw3<b3*0.3 and uw3<b3*0.3:          patterns.append(("Marubozu Bear","SELL"))
        if lw3>2*b3 and c3>o3:                                         patterns.append(("Dragonfly Doji","BUY"))
        if uw3>2*b3 and c3<o3:                                         patterns.append(("Gravestone Doji","SELL"))
        if c1>o1 and c2>o2 and c3>o3 and c3>c2>c1:                    patterns.append(("Three White Soldiers","BUY"))
        if c1<o1 and c2<o2 and c3<o3 and c3<c2<c1:                    patterns.append(("Three Black Crows","SELL"))
    except Exception:
        pass
    return patterns

# ─── RSI Divergence ───────────────────────────────────────────────────────────
def detect_divergence(df, ind):
    if df is None or len(df)<15 or not ind:
        return None
    try:
        c   = df["Close"].astype(float).values[-20:]
        rsi = ind.get("rsi_s")
        if rsi is None or len(rsi)<20:
            return None
        rsi = rsi.values[-20:]
        lows  = [i for i in range(1,len(c)-1) if c[i]<c[i-1] and c[i]<c[i+1]]
        highs = [i for i in range(1,len(c)-1) if c[i]>c[i-1] and c[i]>c[i+1]]
        if len(lows)>=2:
            i1,i2 = lows[-2],lows[-1]
            if c[i2]<c[i1] and rsi[i2]>rsi[i1] and rsi[i1]<50:
                return ("BULLISH_DIV","BUY","RSI bullish divergence — higher low while price makes lower low")
        if len(highs)>=2:
            i1,i2 = highs[-2],highs[-1]
            if c[i2]>c[i1] and rsi[i2]<rsi[i1] and rsi[i1]>50:
                return ("BEARISH_DIV","SELL","RSI bearish divergence — lower high while price makes higher high")
    except Exception:
        pass
    return None

# ─── Volume Spike Detection ───────────────────────────────────────────────────
def volume_spike(ind):
    vr = ind.get("vr", 1.0) if ind else 1.0
    if vr >= 3.0:   return "EXTREME", vr
    elif vr >= 2.0: return "HIGH", vr
    elif vr >= 1.5: return "ABOVE_AVG", vr
    return "NORMAL", vr

# ─── Institutional Accumulation Proxy ────────────────────────────────────────
def institutional_accumulation(ind):
    """
    Proxy for FII/DII buying:
    Price rising + OBV rising + A/D positive + volume > 1.5x avg on up days.
    """
    try:
        m5  = ind.get("m5", 0)
        vr  = ind.get("vr", 1.0)
        ad  = ind.get("ad_trend", 0)
        day = ind.get("day_chg", 0)
        # Price up, volume above avg, A/D line rising
        if m5 > 1 and vr > 1.5 and ad > 0 and day > 0:
            return True
    except Exception:
        pass
    return False

# ─── Master Signal Scorer ─────────────────────────────────────────────────────
def score_signal(ind, fund, df, market_mood="NEUTRAL", vix=15.0, mode="INTRADAY",
                 df_weekly=None, rs_rating=None):
    """
    Comprehensive signal scorer v4.
    Returns (recommendation, strength, buy_score, sell_score, reasoning)
    """
    if not ind:
        return "NEUTRAL", 0, 0, 0, ["No data"]

    buy = 0; sell = 0; reasons = []

    def g(k, d=0.0):
        v = ind.get(k, d)
        try: return float(v) if np.isfinite(float(v)) else d
        except: return d

    rsi   = g("rsi", 50)
    macd  = g("macd"); msig  = g("macd_sig"); mhist = g("macd_hist")
    macd_above_zero = ind.get("macd_above_zero", False)
    bb    = g("bb_pct", 0.5)
    sk    = g("sk", 50);  sd    = g("sd", 50)
    srsi_k= g("srsi_k", 50); srsi_d = g("srsi_d", 50)
    adx   = g("adx", 20); pdi   = g("pdi"); ndi   = g("ndi")
    wr    = g("wr", -50); cci   = g("cci")
    vr    = g("vr", 1.0)
    close = g("close"); e9=g("e9"); e13=g("e13"); e21=g("e21"); e50=g("e50"); e200=g("e200")
    m5    = g("m5"); m20 = g("m20"); m60 = g("m60")
    roc10 = g("roc10"); roc20 = g("roc20")
    atr   = g("atr"); squeeze = ind.get("squeeze", False)
    s1=g("s1"); s2=g("s2"); r1=g("r1"); r2=g("r2")
    st_bullish = ind.get("st_bullish", False)
    st_bearish = ind.get("st_bearish", False)
    gap_type   = ind.get("gap_type")
    gap_pct    = g("gap_pct")
    ad_trend   = g("ad_trend")

    # ── Market Mood ───────────────────────────────────────────────────────────
    if market_mood == "BEARISH":
        sell += 2; reasons.append("🔴 Market BEARISH → SELL +2")
    elif market_mood == "BULLISH":
        buy  += 1; reasons.append("🟢 Market BULLISH → BUY +1")
    if vix > 22:
        sell += 1; reasons.append(f"⚠️ VIX={vix:.1f} elevated → caution")
    elif vix < 13:
        buy  += 1; reasons.append(f"🟢 VIX={vix:.1f} low → favourable")

    # ── RSI — mode-adjusted thresholds ───────────────────────────────────────
    if mode == "DELIVERY":
        # For delivery: ideal RSI entry is 40–55 after pullback in uptrend
        if 40 <= rsi <= 55:
            buy += 3; reasons.append(f"RSI={rsi:.1f} ideal delivery entry zone (40–55) → BUY +3")
        elif rsi < 35:
            reasons.append(f"RSI={rsi:.1f} oversold — possible falling knife for delivery ⚠️")
        elif rsi > 70:
            sell += 2; reasons.append(f"RSI={rsi:.1f} overbought → SELL +2 (avoid delivery buy)")
        elif rsi > 60:
            sell += 1; reasons.append(f"RSI={rsi:.1f} elevated → SELL +1")
    else:
        # Intraday thresholds
        if rsi < 25:   buy  += 4; reasons.append(f"RSI={rsi:.1f} DEEPLY oversold → BUY +4")
        elif rsi < 35: buy  += 3; reasons.append(f"RSI={rsi:.1f} oversold → BUY +3")
        elif rsi < 45: buy  += 1; reasons.append(f"RSI={rsi:.1f} mild oversold → BUY +1")
        elif rsi > 80: sell += 4; reasons.append(f"RSI={rsi:.1f} DEEPLY overbought → SELL +4")
        elif rsi > 70: sell += 3; reasons.append(f"RSI={rsi:.1f} overbought → SELL +3")
        elif rsi > 60: sell += 1; reasons.append(f"RSI={rsi:.1f} elevated → SELL +1")
        else:          reasons.append(f"RSI={rsi:.1f} neutral")

    # ── Stochastic RSI ────────────────────────────────────────────────────────
    if srsi_k < 20 and srsi_k > srsi_d:
        buy  += 2; reasons.append(f"StochRSI K={srsi_k:.0f} oversold+crossing up → BUY +2")
    elif srsi_k > 80 and srsi_k < srsi_d:
        sell += 2; reasons.append(f"StochRSI K={srsi_k:.0f} overbought+crossing dn → SELL +2")

    # ── MACD with zero-line filter ────────────────────────────────────────────
    if macd > msig and mhist > 0:
        if macd_above_zero:
            buy += 3; reasons.append(f"MACD bullish crossover ABOVE zero line → BUY +3 (strong)")
        else:
            buy += 1; reasons.append(f"MACD bullish crossover below zero line → BUY +1 (weak)")
    elif macd < msig and mhist < 0:
        sell += 2; reasons.append(f"MACD bearish crossover → SELL +2")
    if mhist > 0 and ind.get("macd_s") is not None:
        ms = ind["macd_s"]
        if len(ms)>=2 and float(ms.iloc[-1])>float(ms.iloc[-2]):
            buy += 1; reasons.append("MACD histogram expanding → BUY +1")

    # ── SuperTrend — now actually scored ─────────────────────────────────────
    if st_bullish:
        buy += 3; reasons.append(f"SuperTrend(10,3) bullish → BUY +3")
    elif st_bearish:
        sell += 3; reasons.append(f"SuperTrend(10,3) bearish → SELL +3")

    # ── Bollinger Bands ───────────────────────────────────────────────────────
    if bb < 0.05:   buy  += 3; reasons.append(f"Price at lower BB ({bb:.2f}) → BUY +3")
    elif bb < 0.15: buy  += 2; reasons.append(f"Price near lower BB → BUY +2")
    elif bb > 0.95: sell += 3; reasons.append(f"Price at upper BB ({bb:.2f}) → SELL +3")
    elif bb > 0.85: sell += 2; reasons.append(f"Price near upper BB → SELL +2")

    # ── EMA Stack ─────────────────────────────────────────────────────────────
    if close>0 and e9>0 and e13>0 and e21>0 and e50>0:
        if close > e9 > e13 > e21 > e50:
            buy  += 4; reasons.append("Perfect bull EMA stack: price>9>13>21>50 → BUY +4")
        elif close < e9 < e13 < e21 < e50:
            sell += 4; reasons.append("Perfect bear EMA stack: price<9<13<21<50 → SELL +4")
        elif close > e21 > e50:
            buy  += 2; reasons.append("Price above EMA21 & 50 → BUY +2")
        elif close < e21 < e50:
            sell += 2; reasons.append("Price below EMA21 & 50 → SELL +2")
        if e200 > 0 and len(df) >= 250:
            if close > e200: buy  += 1; reasons.append("Price above EMA200 (macro uptrend) → BUY +1")
            else:            sell += 1; reasons.append("Price below EMA200 (macro downtrend) → SELL +1")

    # ── ADX — hard filter for intraday ────────────────────────────────────────
    if adx > 30:
        if pdi > ndi: buy  += 3; reasons.append(f"ADX={adx:.0f} STRONG uptrend → BUY +3")
        else:         sell += 3; reasons.append(f"ADX={adx:.0f} STRONG downtrend → SELL +3")
    elif adx > 20:
        if pdi > ndi: buy  += 1; reasons.append(f"ADX={adx:.0f} moderate uptrend → BUY +1")
        else:         sell += 1; reasons.append(f"ADX={adx:.0f} moderate downtrend → SELL +1")

    # ── Stochastic ────────────────────────────────────────────────────────────
    if sk < 20 and sk > sd:
        buy  += 2; reasons.append(f"Stoch K={sk:.0f} oversold+crossing up → BUY +2")
    elif sk < 15:
        buy  += 1; reasons.append(f"Stoch K={sk:.0f} deep oversold → BUY +1")
    elif sk > 80 and sk < sd:
        sell += 2; reasons.append(f"Stoch K={sk:.0f} overbought+crossing dn → SELL +2")
    elif sk > 85:
        sell += 1; reasons.append(f"Stoch K={sk:.0f} deep overbought → SELL +1")

    # ── Williams %R ───────────────────────────────────────────────────────────
    if wr < -85:   buy  += 2; reasons.append(f"Williams R={wr:.0f} deeply oversold → BUY +2")
    elif wr < -70: buy  += 1; reasons.append(f"Williams R={wr:.0f} oversold → BUY +1")
    elif wr > -10: sell += 2; reasons.append(f"Williams R={wr:.0f} overbought → SELL +2")
    elif wr > -20: sell += 1; reasons.append(f"Williams R={wr:.0f} elevated → SELL +1")

    # ── CCI ───────────────────────────────────────────────────────────────────
    if cci < -150: buy  += 2; reasons.append(f"CCI={cci:.0f} extreme oversold → BUY +2")
    elif cci < -100: buy+= 1; reasons.append(f"CCI={cci:.0f} oversold → BUY +1")
    elif cci > 150: sell+= 2; reasons.append(f"CCI={cci:.0f} extreme overbought → SELL +2")
    elif cci > 100: sell+= 1; reasons.append(f"CCI={cci:.0f} overbought → SELL +1")

    # ── Volume ────────────────────────────────────────────────────────────────
    vs, vr_val = volume_spike(ind)
    if vs in ("EXTREME","HIGH") and buy > sell:
        buy  += 2; reasons.append(f"Volume spike {vr_val:.1f}x confirms bullish → BUY +2")
    elif vs in ("EXTREME","HIGH") and sell > buy:
        sell += 2; reasons.append(f"Volume spike {vr_val:.1f}x confirms bearish → SELL +2")
    elif vs == "ABOVE_AVG":
        if buy > sell:   buy  += 1; reasons.append(f"Above-avg vol {vr_val:.1f}x → BUY +1")
        elif sell > buy: sell += 1; reasons.append(f"Above-avg vol {vr_val:.1f}x → SELL +1")

    # ── Accumulation/Distribution ──────────────────────────────────────────────
    if ad_trend > 0.05:
        buy += 2; reasons.append(f"A/D line rising (+{ad_trend:.2f}) — institutional accumulation → BUY +2")
    elif ad_trend < -0.05:
        sell += 2; reasons.append(f"A/D line falling ({ad_trend:.2f}) — distribution → SELL +2")

    # ── Squeeze Momentum ──────────────────────────────────────────────────────
    if squeeze:
        reasons.append("⚡ TTM Squeeze firing — big move imminent!")
        if buy > sell: buy += 2
        else:          sell += 2

    # ── Rate of Change (Acceleration) ────────────────────────────────────────
    if roc10 > 3:   buy  += 2; reasons.append(f"ROC10={roc10:.1f}% accelerating upward → BUY +2")
    elif roc10 > 1: buy  += 1; reasons.append(f"ROC10={roc10:.1f}% positive → BUY +1")
    elif roc10 < -3: sell += 2; reasons.append(f"ROC10={roc10:.1f}% accelerating down → SELL +2")
    elif roc10 < -1: sell += 1; reasons.append(f"ROC10={roc10:.1f}% negative → SELL +1")

    # ── Momentum ──────────────────────────────────────────────────────────────
    if m5 > 3:    buy  += 2; reasons.append(f"5D momentum +{m5:.1f}% → BUY +2")
    elif m5 > 1:  buy  += 1; reasons.append(f"5D momentum +{m5:.1f}% → BUY +1")
    elif m5 < -3: sell += 2; reasons.append(f"5D momentum {m5:.1f}% → SELL +2")
    elif m5 < -1: sell += 1; reasons.append(f"5D momentum {m5:.1f}% → SELL +1")
    if m20 > 10:  buy  += 1; reasons.append(f"20D momentum +{m20:.1f}% → BUY +1")
    elif m20 < -10: sell += 1; reasons.append(f"20D momentum {m20:.1f}% → SELL +1")

    # ── S/R Proximity ─────────────────────────────────────────────────────────
    if close > 0 and s1 > 0:
        if abs(close-s1)/close < 0.005: buy  += 2; reasons.append(f"Price at Support S1 ₹{s1:.2f} → BUY +2")
        if abs(close-s2)/close < 0.005: buy  += 3; reasons.append(f"Price at Strong Support S2 ₹{s2:.2f} → BUY +3")
        if abs(close-r1)/close < 0.005: sell += 2; reasons.append(f"Price at Resistance R1 ₹{r1:.2f} → SELL +2")
        if abs(close-r2)/close < 0.005: sell += 3; reasons.append(f"Price at Strong Resistance R2 ₹{r2:.2f} → SELL +3")

    # ── Candlestick Patterns ──────────────────────────────────────────────────
    if df is not None:
        for pname, psig in detect_patterns(df):
            if psig == "BUY":    buy  += 2; reasons.append(f"🕯️ {pname} → BUY +2")
            elif psig == "SELL": sell += 2; reasons.append(f"🕯️ {pname} → SELL +2")
            else: reasons.append(f"🕯️ {pname} (Neutral)")

    # ── RSI Divergence ────────────────────────────────────────────────────────
    div = detect_divergence(df, ind)
    if div:
        _, dsig, dmsg = div
        if dsig == "BUY":  buy  += 3; reasons.append(f"📐 {dmsg} → BUY +3")
        else:              sell += 3; reasons.append(f"📐 {dmsg} → SELL +3")

    # ── Gap Detection ─────────────────────────────────────────────────────────
    if gap_type == "GAP_UP":
        buy += 3; reasons.append(f"🚀 Gap-up {gap_pct:.1f}% with volume → BUY +3 (high-prob delivery setup)")
    elif gap_type == "GAP_DOWN":
        sell += 3; reasons.append(f"⬇️ Gap-down {gap_pct:.1f}% with volume → SELL +3")

    # ── Institutional Accumulation ────────────────────────────────────────────
    if institutional_accumulation(ind):
        buy += 2; reasons.append("🏦 Institutional accumulation proxy: price+vol+A/D all rising → BUY +2")

    # ── DELIVERY-SPECIFIC SIGNALS ──────────────────────────────────────────────
    if mode == "DELIVERY":

        # Relative Strength vs Nifty
        if rs_rating is not None:
            if rs_rating >= 1.3:
                buy += 4; reasons.append(f"⭐ RS Rating={rs_rating:.2f} — STRONG outperformer vs Nifty → BUY +4")
            elif rs_rating >= 1.1:
                buy += 2; reasons.append(f"RS Rating={rs_rating:.2f} — outperforming Nifty → BUY +2")
            elif rs_rating < 0.9:
                sell += 2; reasons.append(f"RS Rating={rs_rating:.2f} — underperforming Nifty → SELL +2 (avoid delivery)")
            else:
                reasons.append(f"RS Rating={rs_rating:.2f} — neutral vs Nifty")

        # Weekly trend confirmation
        if df_weekly is not None:
            w_ind = compute_indicators(df_weekly)
            if w_ind:
                w_close = w_ind.get("close", 0)
                w_e21   = w_ind.get("e21", 0)
                w_e50   = w_ind.get("e50", 0)
                if w_close > w_e21 > w_e50:
                    buy += 3; reasons.append("📊 Weekly: price>EMA21>EMA50 — weekly uptrend confirmed → BUY +3")
                elif w_close < w_e21 < w_e50:
                    sell += 3; reasons.append("📊 Weekly: price<EMA21<EMA50 — weekly downtrend ⚠️ → SELL +3")
                else:
                    reasons.append("📊 Weekly trend: mixed — no strong confirmation")

        # Weinstein Stage
        if df_weekly is not None:
            stage, stage_desc = weinstein_stage(df_weekly)
            if stage == 2:
                buy += 4; reasons.append(f"📈 Weinstein {stage_desc} → BUY +4")
            elif stage == 4:
                sell += 4; reasons.append(f"📉 Weinstein {stage_desc} → SELL +4 (do not touch)")
            elif stage == 3:
                sell += 2; reasons.append(f"⚠️ Weinstein {stage_desc} → SELL +2")
            elif stage == 1:
                reasons.append(f"⏳ Weinstein {stage_desc} — wait for breakout")

        # 52W Breakout
        is_breakout, brk_vr = check_52w_breakout(df, fund)
        if is_breakout:
            buy += 5; reasons.append(f"🔥 52-Week HIGH breakout! Vol {brk_vr:.1f}x → BUY +5 (CANSLIM signal)")

        # Earnings Risk
        if fund:
            ern_risk, dte_earn = earnings_risk(fund)
            if ern_risk:
                reasons.append(f"⚠️ EARNINGS RISK: {dte_earn} days to earnings — position sizing risk elevated")
                sell += 1

    # ── Fundamentals ──────────────────────────────────────────────────────────
    if fund:
        pe   = fund.get("pe")
        pb   = fund.get("pb")
        roe  = fund.get("roe")
        h52  = fund.get("52h")
        l52  = fund.get("52l")
        if pe:
            try:
                pe = float(pe)
                if np.isfinite(pe) and pe > 0:
                    if pe < 15:   buy  += 1; reasons.append(f"Low P/E {pe:.1f} — cheap → BUY +1")
                    elif pe < 25: buy  += 0; reasons.append(f"P/E {pe:.1f} — fair value")
                    elif pe > 60: sell += 1; reasons.append(f"High P/E {pe:.1f} — stretched → SELL +1")
            except: pass
        if roe:
            try:
                roe_pct = float(roe)*100
                if roe_pct > 20: buy += 1; reasons.append(f"ROE={roe_pct:.1f}% — high quality business → BUY +1")
            except: pass
        if h52 and l52 and close > 0:
            try:
                rng = float(h52)-float(l52)
                if rng > 0:
                    pos52 = (close-float(l52))/rng
                    if pos52 < 0.15: buy  += 2; reasons.append(f"Near 52W low ({pos52*100:.0f}%) → BUY +2")
                    elif pos52 > 0.90 and mode != "DELIVERY":
                        sell += 1; reasons.append(f"Near 52W high ({pos52*100:.0f}%) → caution")
            except: pass

    # ── Final Classification ───────────────────────────────────────────────────
    total    = max(buy+sell, 1)
    if buy > sell:
        net_str  = min(98, int(buy/total*100))
        if buy >= 18: rec = "STRONG BUY"
        elif buy >= 10: rec = "BUY"
        else:          rec = "WEAK BUY"
    elif sell > buy:
        net_str  = min(98, int(sell/total*100))
        if sell >= 18: rec = "STRONG SELL"
        elif sell >= 10: rec = "SELL"
        else:           rec = "WEAK SELL"
    else:
        rec = "NEUTRAL"; net_str = 50

    # Mode-specific adjustments
    if mode == "INTRADAY" and adx < 18:
        rec = "NEUTRAL"; reasons.append("ADX<18 — no clear trend, skip intraday")
    if mode == "DELIVERY" and net_str < 70:
        rec = "NEUTRAL"; reasons.append("Insufficient conviction for delivery (need ≥70%)")
    if mode == "INTRADAY" and vr < 1.2 and buy > sell:
        reasons.append("⚠️ Volume below avg — intraday signal less reliable (VR < 1.2)")

    return rec, net_str, buy, sell, reasons

# ─── Trade Cost Calculators — FIXED ──────────────────────────────────────────
def equity_cost(price, qty, side="BUY", delivery=False):
    """
    FIXED STT:
    - Delivery BUY:   STT = 0.1% on buy value
    - Delivery SELL:  STT = 0.1% on sell value
    - Intraday SELL:  STT = 0.025% on sell value only
    - Intraday BUY:   STT = 0 (no STT on intraday buy)
    """
    tv    = price * qty
    brok  = 0 if delivery else min(20.0, tv * 0.0003)
    if delivery:
        stt = tv * 0.001          # 0.1% both sides for delivery
    else:
        stt = tv * 0.00025 if side == "SELL" else 0   # intraday: 0.025% sell only
    exch  = tv * 0.0000345
    sebi  = tv * 0.000001
    gst   = (brok + exch + sebi) * 0.18
    stamp = tv * 0.00015 if side == "BUY" else 0
    return round(brok + stt + exch + sebi + gst + stamp, 2)

def options_cost(prem, lots, lot_sz, side="BUY", expiry_type="weekly"):
    """
    STT on options at expiry is on intrinsic value, not premium.
    For intraday/before-expiry: STT on sell side only on premium.
    """
    tv   = prem * lots * lot_sz
    brok = min(40.0, tv * 0.0003)
    # STT: only on sell side; at expiry on intrinsic but we use premium as proxy
    stt  = tv * 0.0005 if side == "SELL" else 0
    exch = tv * 0.0000495
    sebi = tv * 0.000001
    gst  = (brok + exch + sebi) * 0.18
    stamp= tv * 0.00003 if side == "BUY" else 0
    return round(brok + stt + exch + sebi + gst + stamp, 2)

def futures_cost(price, lots, lot_sz, side="BUY"):
    tv   = price * lots * lot_sz
    brok = min(40.0, tv * 0.0003)
    stt  = tv * 0.0001
    exch = tv * 0.000019
    sebi = tv * 0.000001
    gst  = (brok + exch + sebi) * 0.18
    stamp= tv * 0.00002 if side == "BUY" else 0
    return round(brok + stt + exch + sebi + gst + stamp, 2)

# ─── Kelly Position Sizing — FIXED with Half-Kelly cap ───────────────────────
def kelly_size(capital, win_rate, rr_ratio, strength):
    """
    FIXED: Half-Kelly cap prevents negative fractions destroying account.
    f = max(0, kelly_fraction) * 0.5  ← Half-Kelly for safety
    Tiered sizing by signal strength.
    """
    try:
        f = win_rate - (1 - win_rate) / max(rr_ratio, 0.1)
        f = max(0, f) * 0.5          # FIXED: Half-Kelly, no negative sizing
        f = min(0.20, f)             # Never risk > 20% per trade
        s = 0.4 + (strength / 100) * 0.6
        return round(capital * f * s, 2)
    except Exception:
        return round(capital * 0.03, 2)

def tiered_position_size(capital, strength, base_risk=15000):
    """
    Tiered sizing by signal strength (as recommended in analysis).
    STRONG BUY (>80%): 2x = ₹30,000
    BUY (65–80%):      1x = ₹15,000
    WEAK BUY (55–65%): 0.5x = ₹7,500
    """
    if strength >= 80:
        multiplier = 2.0
        tier = "STRONG (2x)"
    elif strength >= 65:
        multiplier = 1.0
        tier = "STANDARD (1x)"
    else:
        multiplier = 0.5
        tier = "REDUCED (0.5x)"
    pos_size = min(base_risk * multiplier, capital * 0.20)
    return round(pos_size, 2), tier

# ─── Black-Scholes Greeks ─────────────────────────────────────────────────────
def _ncdf(x):
    return 0.5*(1+math.erf(x/math.sqrt(2)))

def bs_greeks(S, K, T, r, sigma, opt_type="CE"):
    try:
        if T<=0 or sigma<=0 or S<=0 or K<=0:
            return dict(price=0,delta=0,gamma=0,theta=0,vega=0,iv=sigma)
        d1 = (math.log(S/K)+(r+0.5*sigma**2)*T)/(sigma*math.sqrt(T))
        d2 = d1 - sigma*math.sqrt(T)
        nd1= math.exp(-d1**2/2)/math.sqrt(2*math.pi)
        if opt_type=="CE":
            price = S*_ncdf(d1) - K*math.exp(-r*T)*_ncdf(d2)
            delta = _ncdf(d1)
            theta = (-(S*sigma*nd1)/(2*math.sqrt(T)) - r*K*math.exp(-r*T)*_ncdf(d2))/365
        else:
            price = K*math.exp(-r*T)*_ncdf(-d2) - S*_ncdf(-d1)
            delta = _ncdf(d1)-1
            theta = (-(S*sigma*nd1)/(2*math.sqrt(T)) + r*K*math.exp(-r*T)*_ncdf(-d2))/365
        gamma = nd1/(S*sigma*math.sqrt(T))
        vega  = S*math.sqrt(T)*nd1*0.01
        return dict(price=round(max(price,0),2),delta=round(delta,4),
                    gamma=round(gamma,6),theta=round(theta,2),
                    vega=round(vega,2),iv=round(sigma*100,1))
    except:
        return dict(price=0,delta=0,gamma=0,theta=0,vega=0,iv=0)

# ─── NEW: Option Strategy Builder ────────────────────────────────────────────
def build_strategy(strategy_name, spot, vix, expiry_date, index_name="NIFTY"):
    """
    Pre-built option strategies with net Greeks, breakeven, max profit/loss.
    Strategies: Bull Call Spread, Bear Put Spread, Iron Condor, Straddle, Strangle
    """
    tick = 100 if index_name == "BANKNIFTY" else 50
    lot  = 15  if index_name == "BANKNIFTY" else 25
    atm  = round(spot/tick)*tick
    dte  = max(1, (expiry_date - datetime.now().date()).days)
    T    = dte/365; r = 0.065
    iv   = max(0.08, vix/100)

    def greeks(K, otype): return bs_greeks(spot, K, T, r, iv, otype)

    strategies = {}

    if strategy_name == "Bull Call Spread":
        buy_k  = atm; sell_k = atm + 2*tick
        ce_buy = greeks(buy_k, "CE")
        ce_sel = greeks(sell_k, "CE")
        net_debit = round((ce_buy["price"] - ce_sel["price"]) * lot, 2)
        max_profit = round((sell_k - buy_k - ce_buy["price"] + ce_sel["price"]) * lot, 2)
        be = round(buy_k + ce_buy["price"] - ce_sel["price"], 2)
        strategies = {
            "name": "Bull Call Spread", "bias": "BULLISH",
            "legs": [
                {"action":"BUY","type":"CE","strike":buy_k,"price":ce_buy["price"],"delta":ce_buy["delta"]},
                {"action":"SELL","type":"CE","strike":sell_k,"price":ce_sel["price"],"delta":ce_sel["delta"]},
            ],
            "net_debit": net_debit, "max_profit": max_profit, "max_loss": net_debit,
            "breakeven": be, "dte": dte, "lot": lot,
            "net_delta": round((ce_buy["delta"] + ce_sel["delta"])*lot, 3),
        }

    elif strategy_name == "Bear Put Spread":
        buy_k  = atm; sell_k = atm - 2*tick
        pe_buy = greeks(buy_k, "PE")
        pe_sel = greeks(sell_k, "PE")
        net_debit = round((pe_buy["price"] - pe_sel["price"]) * lot, 2)
        max_profit = round((buy_k - sell_k - pe_buy["price"] + pe_sel["price"]) * lot, 2)
        be = round(buy_k - pe_buy["price"] + pe_sel["price"], 2)
        strategies = {
            "name": "Bear Put Spread", "bias": "BEARISH",
            "legs": [
                {"action":"BUY","type":"PE","strike":buy_k,"price":pe_buy["price"],"delta":pe_buy["delta"]},
                {"action":"SELL","type":"PE","strike":sell_k,"price":pe_sel["price"],"delta":pe_sel["delta"]},
            ],
            "net_debit": net_debit, "max_profit": max_profit, "max_loss": net_debit,
            "breakeven": be, "dte": dte, "lot": lot,
            "net_delta": round((pe_buy["delta"] + pe_sel["delta"])*lot, 3),
        }

    elif strategy_name == "Iron Condor":
        ce_sell_k = atm + 2*tick; ce_buy_k = atm + 4*tick
        pe_sell_k = atm - 2*tick; pe_buy_k = atm - 4*tick
        cs = greeks(ce_sell_k,"CE"); cb = greeks(ce_buy_k,"CE")
        ps = greeks(pe_sell_k,"PE"); pb = greeks(pe_buy_k,"PE")
        net_credit = round((cs["price"] - cb["price"] + ps["price"] - pb["price"]) * lot, 2)
        max_loss   = round((2*tick - cs["price"] + cb["price"] - ps["price"] + pb["price"]) * lot, 2)
        strategies = {
            "name": "Iron Condor", "bias": "NEUTRAL",
            "legs": [
                {"action":"SELL","type":"CE","strike":ce_sell_k,"price":cs["price"],"delta":cs["delta"]},
                {"action":"BUY","type":"CE","strike":ce_buy_k,"price":cb["price"],"delta":cb["delta"]},
                {"action":"SELL","type":"PE","strike":pe_sell_k,"price":ps["price"],"delta":ps["delta"]},
                {"action":"BUY","type":"PE","strike":pe_buy_k,"price":pb["price"],"delta":pb["delta"]},
            ],
            "net_credit": net_credit, "max_profit": net_credit, "max_loss": max_loss,
            "breakeven_upper": round(ce_sell_k + (net_credit/lot), 2),
            "breakeven_lower": round(pe_sell_k - (net_credit/lot), 2),
            "dte": dte, "lot": lot,
            "net_delta": round((cs["delta"]+cb["delta"]+ps["delta"]+pb["delta"])*lot, 3),
        }

    elif strategy_name == "Straddle":
        ce = greeks(atm, "CE"); pe = greeks(atm, "PE")
        net_debit = round((ce["price"] + pe["price"]) * lot, 2)
        be_up = round(atm + ce["price"] + pe["price"], 2)
        be_dn = round(atm - ce["price"] - pe["price"], 2)
        strategies = {
            "name": "Straddle", "bias": "VOLATILE",
            "legs": [
                {"action":"BUY","type":"CE","strike":atm,"price":ce["price"],"delta":ce["delta"]},
                {"action":"BUY","type":"PE","strike":atm,"price":pe["price"],"delta":pe["delta"]},
            ],
            "net_debit": net_debit, "max_profit": "Unlimited", "max_loss": net_debit,
            "breakeven_upper": be_up, "breakeven_lower": be_dn,
            "dte": dte, "lot": lot,
            "net_delta": round((ce["delta"] + pe["delta"]) * lot, 3),
        }

    elif strategy_name == "Strangle":
        ce_k = atm + tick; pe_k = atm - tick
        ce   = greeks(ce_k, "CE"); pe = greeks(pe_k, "PE")
        net_debit = round((ce["price"] + pe["price"]) * lot, 2)
        be_up = round(ce_k + ce["price"] + pe["price"], 2)
        be_dn = round(pe_k - ce["price"] - pe["price"], 2)
        strategies = {
            "name": "Strangle", "bias": "VOLATILE",
            "legs": [
                {"action":"BUY","type":"CE","strike":ce_k,"price":ce["price"],"delta":ce["delta"]},
                {"action":"BUY","type":"PE","strike":pe_k,"price":pe["price"],"delta":pe["delta"]},
            ],
            "net_debit": net_debit, "max_profit": "Unlimited", "max_loss": net_debit,
            "breakeven_upper": be_up, "breakeven_lower": be_dn,
            "dte": dte, "lot": lot,
            "net_delta": round((ce["delta"] + pe["delta"]) * lot, 3),
        }

    return strategies

# ─── Option Chain Builder — FIXED SL ─────────────────────────────────────────
def build_chain(index_name, spot, expiry_date, vix, n_strikes=12):
    tick  = 100 if index_name=="BANKNIFTY" else 50
    lot   = 15  if index_name=="BANKNIFTY" else 25
    atm   = round(spot/tick)*tick
    dte   = max(1,(expiry_date-datetime.now().date()).days)
    T     = dte/365; r = 0.065
    iv    = max(0.08, vix/100*(1+0.05*math.sqrt(dte/365)))

    # FIXED SL: 35% for weekly (≤7 DTE), 45% for monthly
    sl_pct = 0.35 if dte <= 7 else 0.45

    # IV Percentile
    iv_percentile = compute_iv_percentile(vix)

    strikes = [atm+(i-n_strikes)*tick for i in range(2*n_strikes+1)]

    # Underlying data for signal
    sym = "^NSEBANK" if index_name=="BANKNIFTY" else "^NSEI"
    df  = get_ohlcv(sym, "1mo","1d")
    ind_u = compute_indicators(df)

    chain = []
    for K in strikes:
        ce = bs_greeks(spot,K,T,r,iv,"CE")
        pe = bs_greeks(spot,K,T,r,iv,"PE")
        ce_sig = _option_signal(spot,K,atm,ind_u,df,"CE",ce["delta"],dte,vix,iv_percentile)
        pe_sig = _option_signal(spot,K,atm,ind_u,df,"PE",pe["delta"],dte,vix,iv_percentile)
        typ = "ATM" if K==atm else ("ITM-CE/OTM-PE" if K<atm else "OTM-CE/ITM-PE")
        chain.append({
            "strike":K,"type":typ,"is_atm":K==atm,"lot":lot,"dte":dte,"iv":ce["iv"],
            "iv_percentile": iv_percentile,
            "ce_price":ce["price"],"ce_delta":ce["delta"],"ce_gamma":ce["gamma"],
            "ce_theta":ce["theta"],"ce_vega":ce["vega"],
            "ce_sl":round(ce["price"]*sl_pct,2),          # FIXED: dynamic SL
            "ce_t1":round(ce["price"]*1.30,2),"ce_t2":round(ce["price"]*1.60,2),
            "ce_t3":round(ce["price"]*2.00,2),"ce_signal":ce_sig,
            "pe_price":pe["price"],"pe_delta":pe["delta"],"pe_gamma":pe["gamma"],
            "pe_theta":pe["theta"],"pe_vega":pe["vega"],
            "pe_sl":round(pe["price"]*sl_pct,2),          # FIXED: dynamic SL
            "pe_t1":round(pe["price"]*1.30,2),"pe_t2":round(pe["price"]*1.60,2),
            "pe_t3":round(pe["price"]*2.00,2),"pe_signal":pe_sig,
        })
    return chain

def _option_signal(spot,K,atm,ind_u,df_u,otype,delta,dte,vix,iv_percentile=50):
    """Enhanced option signal with IV Percentile and PCR proxy."""
    score=0; reasons=[]
    if ind_u:
        rsi=ind_u.get("rsi",50); m5=ind_u.get("m5",0)
        e13=ind_u.get("e13",0); e21=ind_u.get("e21",0); close=ind_u.get("close",0)
        st_bullish = ind_u.get("st_bullish", False)
        st_bearish = ind_u.get("st_bearish", False)
        macd_above = ind_u.get("macd_above_zero", False)
        bull = close>e13>e21 if (close and e13 and e21) else False
        bear = close<e13<e21 if (close and e13 and e21) else False
        if otype=="CE":
            if bull:       score+=3; reasons.append("Underlying bullish EMA stack → +3")
            if st_bullish: score+=2; reasons.append("SuperTrend bullish → +2")
            if bear:       score-=2; reasons.append("Underlying bearish → -2")
            if rsi<40:     score+=1; reasons.append(f"RSI {rsi:.0f} oversold → +1")
            if m5>1.5:     score+=2; reasons.append(f"5D momentum +{m5:.1f}% → +2")
            if macd_above: score+=1; reasons.append("MACD above zero → +1")
        else:
            if bear:       score+=3; reasons.append("Underlying bearish EMA stack → +3")
            if st_bearish: score+=2; reasons.append("SuperTrend bearish → +2")
            if bull:       score-=2; reasons.append("Underlying bullish → -2")
            if rsi>60:     score+=1; reasons.append(f"RSI {rsi:.0f} elevated → +1")
            if m5<-1.5:    score+=2; reasons.append(f"5D momentum {m5:.1f}% → +2")
            if not macd_above: score+=1; reasons.append("MACD below zero → +1")

    # IV Percentile filter
    if iv_percentile > 70:
        # High IV — better to sell premium
        if otype in ("CE","PE"):
            score -= 1; reasons.append(f"IVP={iv_percentile:.0f}% — expensive options, buying risky → -1")
    elif iv_percentile < 25:
        score += 2; reasons.append(f"IVP={iv_percentile:.0f}% — cheap options, good to buy → +2")

    # Delta sweet spot
    ad = abs(delta)
    if 0.35<=ad<=0.65:  score+=2; reasons.append(f"|Δ|={ad:.2f} optimal → +2")
    elif 0.20<=ad<0.35: score+=1; reasons.append(f"|Δ|={ad:.2f} tradeable OTM → +1")
    elif ad<0.15:       score-=2; reasons.append(f"|Δ|={ad:.2f} too far OTM → -2")

    # DTE
    if dte<=2:   score-=3; reasons.append("⚠️ ≤2 DTE — theta burn extreme → -3")
    elif dte<=5: score-=1; reasons.append(f"{dte}D to expiry — theta elevated → -1")
    else:        score+=1; reasons.append(f"{dte}D expiry — time value adequate → +1")

    # VIX
    if vix>20:  score+=1; reasons.append(f"VIX {vix:.1f} high — use momentum plays → +1")
    elif vix<13: score+=1; reasons.append(f"VIX {vix:.1f} low — cheap options → +1")

    # Strike position
    pct = (K-spot)/spot*100 if otype=="CE" else (spot-K)/spot*100
    if 0<=pct<=0.5:   score+=2; reasons.append("Near-ATM best liquidity → +2")
    elif 0.5<pct<=1.5: score+=1; reasons.append("Slightly OTM good R/R → +1")
    elif pct>3:       score-=2; reasons.append("Far OTM — low prob → -2")

    if score>=7:    sig="STRONG BUY"; str_=min(95,60+score*3)
    elif score>=4:  sig="BUY";        str_=min(80,50+score*5)
    elif score<=-3: sig="AVOID";      str_=max(10,50+score*5)
    else:           sig="NEUTRAL";    str_=45
    return {"signal":sig,"score":score,"strength":str_,"reasons":reasons}

# ─── Composite Ranking Score ──────────────────────────────────────────────────
def compute_rank_score(result, rs_rating=None, stage=None):
    """
    Composite rank score for sorting delivery candidates.
    Higher = better opportunity.
    """
    score = 0
    score += result.get("strength", 0) * 0.4          # Signal conviction
    if rs_rating:
        score += min(rs_rating * 20, 40)               # RS Rating (max 40pts)
    if stage == 2:
        score += 20                                     # Weinstein Stage 2 bonus
    score += min(result.get("vr", 1) * 5, 15)          # Volume confirmation
    score += min(result.get("adx", 0) * 0.3, 10)       # Trend strength
    return round(score, 2)

# ─── Parallel Scanner — FIXED ─────────────────────────────────────────────────
def scan_parallel(symbols, mode="INTRADAY", market_mood="NEUTRAL", vix=15.0,
                  max_workers=20, min_strength=55, use_fundamentals=False):
    """
    FIXED:
    - max_workers=20 (yfinance throttles above this)
    - Fundamentals actually fetched when use_fundamentals=True
    - Delivery uses 3y/1d daily + 2y/1wk weekly data
    - Delivery targets: 8%/12%/18%, hard SL 5%
    - Tiered position sizing
    - RS Rating computed for all delivery scans
    - Composite ranking
    """
    results = []

    def _scan_one(sym):
        try:
            if mode == "DELIVERY":
                # Use 3y daily for enough EMA200 candles
                df       = get_ohlcv(sym, "3y", "1d")
                df_weekly= get_ohlcv(sym, "2y", "1wk")
            else:
                df        = get_ohlcv(sym, "1mo", "1d")
                df_weekly = None

            ind = compute_indicators(df, for_delivery=(mode=="DELIVERY"))
            if not ind:
                return None

            # Fetch fundamentals when enabled (FIXED: actually called now)
            fund = {}
            if use_fundamentals or mode == "DELIVERY":
                try:
                    fund = get_fundamentals(sym)
                except Exception:
                    fund = {}

            # Compute RS Rating for delivery
            rs_rating = None
            if mode == "DELIVERY" and df is not None:
                rs_rating = compute_rs_rating(df, period_days=65)

            rec, strength, bs, ss, reasons = score_signal(
                ind, fund, df, market_mood, vix, mode,
                df_weekly=df_weekly, rs_rating=rs_rating
            )

            if rec == "NEUTRAL" and strength < min_strength:
                return None

            price = ind.get("close", 0)
            atr   = ind.get("atr", price * 0.02)

            # FIXED: Delivery targets & SL
            if mode == "DELIVERY":
                if rec in ("BUY","STRONG BUY","WEAK BUY"):
                    target_1 = round(price * 1.08, 2)   # 8% target
                    target_2 = round(price * 1.12, 2)   # 12% target
                    target_3 = round(price * 1.18, 2)   # 18% target
                    sl       = round(price * 0.95, 2)   # 5% hard SL
                    target   = target_2
                elif rec in ("SELL","STRONG SELL","WEAK SELL"):
                    target_1 = round(price * 0.92, 2)
                    target_2 = round(price * 0.88, 2)
                    target_3 = round(price * 0.82, 2)
                    sl       = round(price * 1.05, 2)
                    target   = target_2
                else:
                    target = price; sl = price
                    target_1 = target_2 = target_3 = price
            else:
                # Intraday targets (ATR-based)
                if rec in ("BUY","STRONG BUY","WEAK BUY"):
                    target = round(price * (1 + 0.015 * (bs/5)), 2)
                    sl     = round(price - 1.5 * atr, 2)
                elif rec in ("SELL","STRONG SELL","WEAK SELL"):
                    target = round(price * (1 - 0.015 * (ss/5)), 2)
                    sl     = round(price + 1.5 * atr, 2)
                else:
                    target = price; sl = price
                target_1 = target_2 = target_3 = target

            rr = abs(target-price)/max(abs(price-sl), 0.01)

            # Patterns & divergence
            patterns = detect_patterns(df)
            div      = detect_divergence(df, ind)

            # Weinstein stage
            stage, stage_desc = weinstein_stage(df_weekly) if df_weekly is not None else (None, "N/A")

            # Rank score
            rank_score = compute_rank_score(
                {"strength": strength, "vr": ind.get("vr",1), "adx": ind.get("adx",0)},
                rs_rating=rs_rating, stage=stage
            )

            # Earnings risk
            earn_risk, earn_dte = earnings_risk(fund) if fund else (False, None)

            # Sector
            sector = SECTOR_MAP.get(sym, fund.get("sector","Unknown") if fund else "Unknown")

            # Position sizing
            pos_size, pos_tier = tiered_position_size(500000, strength)

            return {
                "symbol":sym,"rec":rec,"strength":strength,
                "buy_score":bs,"sell_score":ss,
                "price":price,"target":target,"sl":sl,"rr":round(rr,2),
                "target_1":target_1,"target_2":target_2,"target_3":target_3,
                "atr":atr,"day_chg":ind.get("day_chg",0),
                "m5":ind.get("m5",0),"m20":ind.get("m20",0),
                "vr":ind.get("vr",1),"adx":ind.get("adx",0),
                "rsi":ind.get("rsi",50),"macd":ind.get("macd",0),
                "roc10":ind.get("roc10",0),
                "indicators":ind,"reasons":reasons,
                "patterns":[(p[0],p[1]) for p in patterns],
                "divergence":div,
                "s1":ind.get("s1",0),"r1":ind.get("r1",0),
                "rs_rating":rs_rating,
                "stage":stage,"stage_desc":stage_desc,
                "rank_score":rank_score,
                "earn_risk":earn_risk,"earn_dte":earn_dte,
                "sector":sector,
                "pos_size":pos_size,"pos_tier":pos_tier,
                "fundamentals":fund if fund else {},
                "gap_type":ind.get("gap_type"),"gap_pct":ind.get("gap_pct",0),
                "ad_trend":ind.get("ad_trend",0),
                "vwap":ind.get("vwap",0),
                "st_bullish":ind.get("st_bullish",False),
            }
        except Exception:
            return None

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as ex:
        for r in ex.map(_scan_one, symbols):
            if r and r["strength"] >= min_strength:
                results.append(r)

    # Sort by rank_score for delivery, else by rec+strength for intraday
    if mode == "DELIVERY":
        results.sort(key=lambda x: -x["rank_score"])
    else:
        results.sort(key=lambda x: (0 if "BUY" in x["rec"] else 1, -x["strength"]))

    return results
