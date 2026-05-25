"""
ui.py — ProTrader Terminal v4 UI
Exact Upstox color schema from screenshots:
  - Background: #F7F8FA (page), #FFFFFF (cards)
  - Primary CTA purple: #5B2ECC  (deep Upstox violet)
  - Hover purple: #4F1DB5
  - Nav dark purple: #2D1066
  - Green (profit): #00B386
  - Red (loss):     #F45B69
  - Text: #1A1A2E  /  #4A4A6A  /  #7A7A9A
Fonts: Plus Jakarta Sans (UI) + JetBrains Mono (data)
"""

TERMINAL_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:ital,wght@0,300;0,400;0,500;0,600;0,700;0,800;1,400&family=JetBrains+Mono:wght@300;400;500;600&display=swap');

:root {
    /* ═══ Upstox Exact Brand Purple ═══ */
    --p:        #5B2ECC;
    --p2:       #4F1DB5;
    --p3:       #7B3FE4;
    --p4:       #9B66EE;
    --p-light:  #EDE8FD;
    --p-pale:   #F5F0FF;
    --p-bg:     rgba(91,46,204,0.06);
    --p-border: rgba(91,46,204,0.22);
    --p-glow:   rgba(91,46,204,0.28);
    --p-nav:    #2D1066;

    /* ═══ Surfaces ═══ */
    --bg:      #F7F8FA;
    --bg2:     #FFFFFF;
    --bg3:     #EEEEF5;
    --surface: #FFFFFF;
    --card:    #FFFFFF;

    /* ═══ Borders ═══ */
    --border:  #E4E4EE;
    --border2: #CCCCE0;

    /* ═══ Shadows ═══ */
    --sh-xs: 0 1px 3px rgba(0,0,0,0.05);
    --sh-sm: 0 2px 8px rgba(0,0,0,0.07);
    --sh-md: 0 4px 16px rgba(0,0,0,0.09);
    --sh-p:  0 4px 18px rgba(91,46,204,0.22);

    /* ═══ Semantic ═══ */
    --green:        #00B386;
    --green2:       #008F6C;
    --green-bg:     #E6F7F3;
    --green-border: rgba(0,179,134,0.3);
    --red:          #F45B69;
    --red2:         #D94255;
    --red-bg:       #FEF0F1;
    --red-border:   rgba(244,91,105,0.3);
    --gold:         #F59E0B;
    --gold2:        #D97706;
    --gold-bg:      #FEF3C7;
    --gold-border:  rgba(245,158,11,0.3);
    --blue:         #3B82F6;
    --blue-bg:      #EFF6FF;
    --teal:         #0891B2;
    --teal-bg:      #E0F7FA;
    --orange:       #F97316;

    /* ═══ Text ═══ */
    --tx:    #1A1A2E;
    --tx2:   #4A4A6A;
    --tx3:   #7A7A9A;
    --muted: #AAAABB;
    --white: #FFFFFF;

    /* ═══ Fonts ═══ */
    --f-ui:   'Plus Jakarta Sans', sans-serif;
    --f-mono: 'JetBrains Mono', monospace;
}

/* ══ BASE ══ */
html, body, [class*="css"] {
    font-family: var(--f-ui) !important;
    background:  var(--bg)  !important;
    color:       var(--tx)  !important;
    font-size: 14px;
}
.stApp { background: var(--bg) !important; }
* { box-sizing: border-box; }

::-webkit-scrollbar       { width:5px; height:5px; }
::-webkit-scrollbar-track { background:var(--bg3); }
::-webkit-scrollbar-thumb { background:var(--border2); border-radius:4px; }
::-webkit-scrollbar-thumb:hover { background:var(--p4); }

/* ══ TERMINAL HEADER ══ */
.terminal-header {
    background: var(--white);
    border-bottom: 1px solid var(--border);
    padding: 14px 28px 12px;
    position: relative;
    box-shadow: var(--sh-xs);
}
.terminal-header::after {
    content:'';
    position:absolute;
    bottom:0; left:0; right:0;
    height:3px;
    background: linear-gradient(90deg, var(--p), var(--p3), #B99FFF);
}
.terminal-title {
    font-family: var(--f-ui);
    font-size: 1.45rem;
    font-weight: 800;
    color: var(--tx);
    line-height: 1.2;
    letter-spacing: -0.4px;
}
.terminal-title span { color: var(--p); }
.terminal-sub {
    font-family: var(--f-mono);
    font-size: 0.6rem;
    color: var(--muted);
    letter-spacing: 2px;
    text-transform: uppercase;
    margin-top: 3px;
}
.terminal-dot {
    display: inline-block;
    width: 7px; height: 7px;
    border-radius: 50%;
    background: var(--green);
    box-shadow: 0 0 6px rgba(0,179,134,0.55);
    animation: pdot 2s ease-in-out infinite;
    margin-right: 6px;
    vertical-align: middle;
}
@keyframes pdot {
    0%,100% { opacity:1; }
    50%      { opacity:0.4; }
}

/* ══ TICKER TAPE ══ */
.ticker-outer {
    overflow: hidden;
    background: var(--white);
    border-bottom: 1px solid var(--border);
    padding: 6px 0;
}
.ticker-inner {
    display:flex; gap:52px;
    animation: scrolll 55s linear infinite;
    white-space:nowrap;
}
@keyframes scrolll {
    0%   { transform:translateX(0); }
    100% { transform:translateX(-50%); }
}
.t-item { font-family:var(--f-mono); font-size:0.68rem; color:var(--tx3); display:inline-flex; gap:7px; align-items:center; }
.t-name { color:var(--tx2); font-weight:600; }
.t-up   { color:var(--green); font-weight:500; }
.t-dn   { color:var(--red);   font-weight:500; }
.t-flat { color:var(--gold);  font-weight:500; }

/* ══ INDEX CARDS ══ */
.idx-card {
    background: var(--white);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 16px 18px;
    position: relative;
    overflow: hidden;
    box-shadow: var(--sh-sm);
    transition: box-shadow .2s, border-color .2s;
}
.idx-card:hover { box-shadow:var(--sh-md); border-color:var(--p-border); }
.idx-card::before {
    content:''; position:absolute; top:0; left:0; right:0; height:3px;
}
.idx-card.bn::before { background:linear-gradient(90deg,var(--p),var(--p3)); }
.idx-card.nf::before { background:linear-gradient(90deg,#3B82F6,#06B6D4); }
.idx-card.vx::before { background:linear-gradient(90deg,var(--red),var(--orange)); }
.idx-card.sx::before { background:linear-gradient(90deg,var(--gold),var(--orange)); }
.idx-card.it::before { background:linear-gradient(90deg,var(--teal),var(--blue)); }
.idx-label { font-size:.6rem; color:var(--muted); text-transform:uppercase; letter-spacing:1.8px; margin-bottom:6px; font-weight:700; }
.idx-price { font-family:var(--f-mono); font-size:1.4rem; font-weight:600; color:var(--tx); line-height:1.1; letter-spacing:-0.5px; }
.idx-chg   { font-family:var(--f-mono); font-size:.7rem; margin-top:4px; }
.up   { color:var(--green) !important; }
.dn   { color:var(--red)   !important; }
.flat { color:var(--gold)  !important; }

/* ══ METRIC CARDS ══ */
.m-card {
    background: var(--white);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 16px 18px;
    text-align: center;
    box-shadow: var(--sh-sm);
    transition: box-shadow .2s, border-color .2s;
}
.m-card:hover { box-shadow:var(--sh-md); border-color:var(--p-border); }
.m-val { font-family:var(--f-mono); font-size:1.3rem; font-weight:600; color:var(--tx); }
.m-lbl { font-size:.6rem; color:var(--muted); text-transform:uppercase; letter-spacing:1.5px; margin-top:4px; font-weight:700; }

/* ══ SIGNAL BADGES ══ */
.sig { display:inline-block; padding:4px 12px; border-radius:6px; font-family:var(--f-mono); font-size:.68rem; font-weight:600; letter-spacing:.3px; }
.sig-sbuy  { background:#D4F6EC; color:#007A5A; border:1px solid rgba(0,179,134,.4); }
.sig-buy   { background:var(--green-bg); color:var(--green2); border:1px solid var(--green-border); }
.sig-wbuy  { background:var(--teal-bg);  color:var(--teal);   border:1px solid rgba(8,145,178,.3); }
.sig-ssell { background:#FDDBDF; color:var(--red2); border:1px solid rgba(244,91,105,.45); }
.sig-sell  { background:var(--red-bg);   color:var(--red2);   border:1px solid var(--red-border); }
.sig-wsell { background:#FFF4ED;          color:var(--orange); border:1px solid rgba(249,115,22,.3); }
.sig-neut  { background:var(--gold-bg);  color:var(--gold2);  border:1px solid var(--gold-border); }

/* ══ SECTION TITLE ══ */
.sec-ttl {
    font-family:var(--f-ui); font-size:.68rem; font-weight:800; letter-spacing:2px;
    color:var(--p); text-transform:uppercase;
    border-bottom:1px solid var(--border);
    padding-bottom:10px; margin-bottom:16px; margin-top:8px;
}

/* ══ TRADE CARDS ══ */
.tc { background:var(--white); border:1px solid var(--border); border-radius:12px; padding:16px 18px; margin-bottom:8px; box-shadow:var(--sh-sm); transition:box-shadow .2s; }
.tc:hover { box-shadow:var(--sh-md); }
.tc.win  { border-left:3px solid var(--green); }
.tc.loss { border-left:3px solid var(--red); }
.tc.open { border-left:3px solid var(--p); }
.tc-head { font-family:var(--f-ui); font-weight:700; font-size:.95rem; color:var(--tx); }
.tc-meta { font-family:var(--f-mono); font-size:.67rem; color:var(--tx3); margin-top:3px; }

/* ══ PROFIT BOOK ══ */
.pb { background:var(--green-bg); border:1px solid var(--green-border); border-radius:8px; padding:9px 14px; margin:4px 0; display:flex; justify-content:space-between; align-items:center; }
.pb-pct { font-family:var(--f-mono); font-size:.78rem; color:var(--green); font-weight:600; }
.pb-pr  { font-family:var(--f-mono); font-size:.82rem; color:var(--tx); font-weight:500; }
.pb-lbl { font-size:.67rem; color:var(--tx3); }

/* ══ GREEK BOXES ══ */
.gk { background:var(--bg); border:1px solid var(--border); border-radius:10px; padding:12px 14px; text-align:center; transition:border-color .2s, box-shadow .2s; }
.gk:hover { border-color:var(--p-border); box-shadow:var(--sh-sm); }
.gk-v { font-family:var(--f-mono); font-size:.95rem; font-weight:600; color:var(--tx); }
.gk-l { font-size:.58rem; color:var(--muted); text-transform:uppercase; letter-spacing:1.2px; margin-top:3px; font-weight:700; }

/* ══ S/R LEVELS ══ */
.lvl { border-radius:8px; padding:9px 14px; font-family:var(--f-mono); font-size:.82rem; text-align:center; font-weight:600; }
.lvl-r  { background:var(--red-bg);   border:1px solid var(--red-border);   color:var(--red2); }
.lvl-s  { background:var(--green-bg); border:1px solid var(--green-border); color:var(--green2); }
.lvl-e  { background:var(--p-pale);   border:1px solid var(--p-border);     color:var(--p); }
.lvl-tg { background:var(--teal-bg);  border:1px solid rgba(8,145,178,.3);  color:var(--teal); }

/* ══ STRENGTH BAR ══ */
.sb-wrap { background:var(--bg3); border-radius:4px; height:5px; overflow:hidden; margin-top:5px; }
.sb-fill { height:5px; border-radius:4px; transition:width .5s ease; }

/* ══ ALERT BOXES ══ */
.info-b    { background:var(--p-pale);   border:1px solid var(--p-border);         border-radius:10px; padding:12px 16px; font-size:.82rem; color:var(--p2);    margin:6px 0; }
.warn-b    { background:var(--gold-bg);  border:1px solid var(--gold-border);       border-radius:10px; padding:12px 16px; font-size:.82rem; color:var(--gold2); margin:6px 0; }
.success-b { background:var(--green-bg); border:1px solid var(--green-border);      border-radius:10px; padding:12px 16px; font-size:.82rem; color:var(--green2);margin:6px 0; }
.danger-b  { background:var(--red-bg);   border:1px solid var(--red-border);        border-radius:10px; padding:12px 16px; font-size:.82rem; color:var(--red2);  margin:6px 0; }

/* ══ CHIPS ══ */
.ce-chip  { background:var(--blue-bg); border:1px solid rgba(59,130,246,.3); color:#2563EB;     border-radius:6px; padding:3px 10px; font-size:.68rem; font-family:var(--f-mono); font-weight:600; }
.pe-chip  { background:var(--red-bg);  border:1px solid var(--red-border);   color:var(--red2); border-radius:6px; padding:3px 10px; font-size:.68rem; font-family:var(--f-mono); font-weight:600; }
.atm-chip { background:var(--gold-bg); border:1px solid var(--gold-border);  color:var(--gold2);border-radius:6px; padding:3px 10px; font-size:.68rem; font-family:var(--f-mono); font-weight:600; }
.fut-chip { background:var(--p-pale);  border:1px solid var(--p-border);     color:var(--p);    border-radius:6px; padding:3px 10px; font-size:.68rem; font-family:var(--f-mono); font-weight:600; }

/* ══ UTILITIES ══ */
.purple-color { color:var(--p)     !important; }
.green-color  { color:var(--green) !important; }
.red-color    { color:var(--red)   !important; }
.gold-color   { color:var(--gold)  !important; }
.muted-color  { color:var(--muted) !important; }
.white-color  { color:var(--white) !important; }
.ce-color     { color:#2563EB !important; }
.pe-color     { color:var(--red2) !important; }
.itm-ce       { background:var(--blue-bg); }
.itm-pe       { background:var(--red-bg); }
.pnl-pos  { color:var(--green); font-family:var(--f-mono); font-weight:600; }
.pnl-neg  { color:var(--red);   font-family:var(--f-mono); font-weight:600; }
.pnl-zero { color:var(--gold);  font-family:var(--f-mono); font-weight:600; }

/* ══ BUTTONS  (Upstox deep-purple pill CTA) ══ */
.stButton > button {
    background: var(--p) !important;
    color: var(--white) !important;
    font-family: var(--f-ui) !important;
    font-weight: 700 !important;
    font-size: .85rem !important;
    letter-spacing: .2px !important;
    border: none !important;
    border-radius: 8px !important;
    padding: 9px 22px !important;
    transition: background .18s, box-shadow .18s !important;
    box-shadow: 0 2px 8px var(--p-glow) !important;
}
.stButton > button:hover  { background:var(--p2) !important; box-shadow:var(--sh-p) !important; }
.stButton > button:active { background:var(--p3) !important; }

/* ══ TABS ══ */
.stTabs [data-baseweb="tab-list"] { background:var(--white) !important; border-bottom:1px solid var(--border) !important; gap:2px !important; }
.stTabs [data-baseweb="tab"] { font-family:var(--f-ui) !important; font-size:.82rem !important; font-weight:600 !important; color:var(--tx3) !important; padding:10px 18px !important; background:transparent !important; }
.stTabs [aria-selected="true"] { color:var(--p) !important; border-bottom:2px solid var(--p) !important; background:var(--p-pale) !important; border-radius:6px 6px 0 0 !important; }

/* ══ DATAFRAME ══ */
.stDataFrame { border:1px solid var(--border) !important; border-radius:12px !important; overflow:hidden !important; box-shadow:var(--sh-sm) !important; }
.stDataFrame thead th { background:var(--bg) !important; color:var(--tx3) !important; font-family:var(--f-ui) !important; font-size:.67rem !important; text-transform:uppercase !important; letter-spacing:1px !important; font-weight:700 !important; border-bottom:1px solid var(--border) !important; }
.stDataFrame tbody td { font-family:var(--f-mono) !important; font-size:.78rem !important; color:var(--tx) !important; border-bottom:1px solid var(--border) !important; background:var(--white) !important; }
.stDataFrame tbody tr:hover td { background:var(--p-pale) !important; }

/* ══ SIDEBAR ══ */
[data-testid="stSidebar"] { background:var(--white) !important; border-right:1px solid var(--border) !important; box-shadow:var(--sh-sm) !important; }
[data-testid="stSidebar"] label { color:var(--tx2) !important; font-family:var(--f-ui) !important; font-size:.8rem !important; font-weight:600 !important; }
[data-testid="stSidebar"] .stSelectbox > div > div { background:var(--bg) !important; border-color:var(--border) !important; color:var(--tx) !important; border-radius:8px !important; }

/* ══ INPUTS ══ */
.stSelectbox > div > div,
.stTextInput > div > div > input,
.stNumberInput > div > div > input {
    background:var(--white) !important; border:1px solid var(--border) !important;
    border-radius:8px !important; color:var(--tx) !important;
    font-family:var(--f-ui) !important; font-size:.85rem !important; box-shadow:var(--sh-xs) !important;
}
.stSelectbox > div > div:focus-within,
.stTextInput > div > div > input:focus,
.stNumberInput > div > div > input:focus {
    border-color:var(--p) !important;
    box-shadow:0 0 0 3px var(--p-bg) !important; outline:none !important;
}
.stCheckbox label, .stRadio label { color:var(--tx2) !important; font-family:var(--f-ui) !important; font-size:.82rem !important; font-weight:500 !important; }
.stProgress > div > div { background:var(--p) !important; border-radius:4px !important; }

/* ══ EXPANDER ══ */
.streamlit-expanderHeader { background:var(--white) !important; border:1px solid var(--border) !important; border-radius:10px !important; font-family:var(--f-ui) !important; font-size:.82rem !important; color:var(--tx) !important; font-weight:600 !important; box-shadow:var(--sh-xs) !important; }
.streamlit-expanderHeader:hover { border-color:var(--p-border) !important; }
.streamlit-expanderContent { background:var(--white) !important; border:1px solid var(--border) !important; border-top:none !important; border-radius:0 0 10px 10px !important; }

/* ══ OPTION CHAIN TABLE ══ */
.oc-hdr {
    display:grid;
    grid-template-columns:1.5fr .8fr .7fr .6fr 1fr 1.2fr 1fr .6fr .7fr .8fr 1.5fr;
    padding:10px 14px; background:var(--bg);
    border:1px solid var(--border); border-radius:12px 12px 0 0;
    font-size:.6rem; text-transform:uppercase; letter-spacing:1.5px;
    color:var(--muted); gap:4px; font-family:var(--f-ui); font-weight:700;
}
.oc-row {
    display:grid;
    grid-template-columns:1.5fr .8fr .7fr .6fr 1fr 1.2fr 1fr .6fr .7fr .8fr 1.5fr;
    padding:8px 14px; border:1px solid var(--border); border-top:none;
    font-size:.77rem; gap:4px; align-items:center; transition:background .12s;
    font-family:var(--f-mono); background:var(--white);
}
.oc-row:hover       { background:var(--p-pale) !important; }
.oc-row:last-child  { border-radius:0 0 12px 12px; }
.oc-atm { background:var(--gold-bg) !important; border-left:3px solid var(--gold) !important; border-right:3px solid var(--gold) !important; }

/* ══ JOURNAL ROW ══ */
.jrnl-row { background:var(--white); border:1px solid var(--border); border-radius:10px; padding:10px 16px; margin:4px 0; display:flex; justify-content:space-between; align-items:center; gap:10px; flex-wrap:wrap; box-shadow:var(--sh-xs); transition:box-shadow .15s, border-color .15s; }
.jrnl-row:hover { box-shadow:var(--sh-sm); border-color:var(--p-border); }

/* ══ PILL TAG ══ */
.pill       { display:inline-block; background:var(--p-pale);   border:1px solid var(--p-border);        color:var(--p);      border-radius:20px; padding:3px 11px; font-size:.67rem; font-family:var(--f-ui); font-weight:700; }
.pill-green { background:var(--green-bg); border-color:var(--green-border); color:var(--green2); }
.pill-red   { background:var(--red-bg);   border-color:var(--red-border);   color:var(--red2); }
.pill-gold  { background:var(--gold-bg);  border-color:var(--gold-border);  color:var(--gold2); }

/* ══ RANK BADGE ══ */
.rank-badge { display:inline-flex; align-items:center; justify-content:center; width:26px; height:26px; background:var(--p-pale); border:1px solid var(--p-border); border-radius:50%; font-family:var(--f-mono); font-size:.7rem; font-weight:600; color:var(--p); }

/* ══ DIVIDERS ══ */
.divider        { height:1px; background:var(--border); margin:12px 0; }
.divider-purple { height:1px; background:linear-gradient(90deg,transparent,var(--p-border),transparent); margin:14px 0; }

/* ══ HIGHLIGHT BOX ══ */
.hl-box { background:var(--p-pale); border:1px solid var(--p-border); border-radius:12px; padding:16px 20px; text-align:center; box-shadow:var(--sh-sm); }
.hl-val { font-family:var(--f-mono); font-size:1.45rem; font-weight:600; color:var(--p); }
.hl-lbl { font-size:.6rem; color:var(--muted); text-transform:uppercase; letter-spacing:1.5px; margin-top:4px; font-weight:700; }

/* ══ SCROLLABLE TABLE ══ */
.scroll-table { max-height:420px; overflow-y:auto; border-radius:12px; border:1px solid var(--border); box-shadow:var(--sh-sm); }
.scroll-table::-webkit-scrollbar       { width:4px; }
.scroll-table::-webkit-scrollbar-thumb { background:var(--border2); border-radius:4px; }
</style>
"""

# ─── Helper Rendering Functions ───────────────────────────────────────────────

def sig_badge(rec):
    cls = {
        "STRONG BUY":  "sig-sbuy",
        "BUY":         "sig-buy",
        "WEAK BUY":    "sig-wbuy",
        "STRONG SELL": "sig-ssell",
        "SELL":        "sig-sell",
        "WEAK SELL":   "sig-wsell",
        "NEUTRAL":     "sig-neut",
        "AVOID":       "sig-ssell",
    }.get(rec, "sig-neut")
    return f'<span class="sig {cls}">{rec}</span>'

def strength_bar(pct, color=None):
    if color is None:
        if pct >= 75:   color = "var(--green)"
        elif pct >= 55: color = "var(--p)"
        else:           color = "var(--gold)"
    return (f'<div class="sb-wrap">'
            f'<div class="sb-fill" style="width:{pct}%;background:{color};"></div>'
            f'</div>')

def pnl_fmt(val):
    if val > 0:   return f'<span class="pnl-pos">▲ ₹{val:,.2f}</span>'
    elif val < 0: return f'<span class="pnl-neg">▼ ₹{abs(val):,.2f}</span>'
    return f'<span class="pnl-zero">₹0.00</span>'

def ticker_item(name, price, pct):
    cls   = "t-up" if pct >= 0 else "t-dn"
    arrow = "▲" if pct >= 0 else "▼"
    return (f'<span class="t-item">'
            f'<span class="t-name">{name}</span>'
            f'<span class="{cls}">{price:,.2f} {arrow}{abs(pct):.2f}%</span>'
            f'</span>')

def metric_card(val, lbl, color="var(--p)"):
    return (f'<div class="m-card">'
            f'<div class="m-val" style="color:{color};">{val}</div>'
            f'<div class="m-lbl">{lbl}</div>'
            f'</div>')

def level_box(label, val, css_class):
    return (f'<div class="lvl {css_class}">'
            f'<div style="font-size:.58rem;opacity:.6;margin-bottom:2px;">{label}</div>'
            f'₹{val:,.2f}'
            f'</div>')

def profit_book_row(pct, price, label, profit_abs):
    return (f'<div class="pb">'
            f'<span class="pb-pct">+{pct}%</span>'
            f'<span class="pb-pr">₹{price:.2f}</span>'
            f'<span class="pb-lbl">{label}</span>'
            f'<span style="font-family:var(--f-mono);font-size:.78rem;'
            f'color:var(--teal);font-weight:600;">+₹{profit_abs:.0f}</span>'
            f'</div>')

def greek_box(val, label, color="var(--tx)"):
    return (f'<div class="gk">'
            f'<div class="gk-v" style="color:{color}">{val}</div>'
            f'<div class="gk-l">{label}</div>'
            f'</div>')

def pill(text, variant="purple"):
    cls = {
        "purple": "pill",
        "green":  "pill pill-green",
        "red":    "pill pill-red",
        "gold":   "pill pill-gold",
    }.get(variant, "pill")
    return f'<span class="{cls}">{text}</span>'

def rank_badge(n):
    return f'<span class="rank-badge">#{n}</span>'

def hl_box(val, lbl, color="var(--p)"):
    return (f'<div class="hl-box">'
            f'<div class="hl-val" style="color:{color};">{val}</div>'
            f'<div class="hl-lbl">{lbl}</div>'
            f'</div>')
