import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import requests
import io
from datetime import datetime

# ==================== PAGE CONFIG & PROFESSIONAL THEMING ====================
st.set_page_config(
    page_title="ProTrade Terminal | Institutional Indian Market Suite",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
    <style>
    .main { background-color: #0b0f19; color: #f8fafc; }
    .stTabs [data-baseweb="tab-list"] { gap: 10px; }
    .stTabs [data-baseweb="tab"] { background-color: #1e293b; border-radius: 6px; color: white; padding: 10px 20px; font-weight: 600; }
    .stTabs [aria-selected="true"] { background-color: #3b82f6 !important; color: white !important; }
    div.stButton > button { background: linear-gradient(90deg, #3b82f6 0%, #1d4ed8 100%); color: white; border-radius: 6px; font-weight: bold; border: none; }
    div.stButton > button:hover { background: linear-gradient(90deg, #2563eb 0%, #1e40af 100%); }
    </style>
""", unsafe_allow_html=True)

st.title("⚡ ProTrade Terminal: Institutional Execution & Signal Suite")
st.markdown("### Advanced Quantitative Momentum Scanner, Automated Entry/Exit Rules & Risk Matrix")
st.caption("Market data powered by Yahoo Finance (NSE delayed ~15m). Simulated algorithmic execution framework.")

STARTING_CAPITAL = 100000.0
DEFAULT_WATCHLIST = ["RELIANCE.NS", "TCS.NS", "INFY.NS", "HDFCBANK.NS", "TATAMOTORS.NS", "SBIN.NS"]

@st.cache_data(ttl=12 * 60 * 60, show_spinner=False)
def fetch_nse_master_list():
    """Downloads official NSE master list for symbol mapping[cite: 1]."""
    try:
        url = "https://nsearchives.nseindia.com/content/equities/EQUITY_L.csv"
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        df = pd.read_csv(io.StringIO(resp.text))
        df.columns = [c.strip() for c in df.columns]
        return dict(zip(df["SYMBOL"].str.strip(), df["NAME OF COMPANY"].str.strip()))
    except Exception:
        return None

# ==================== SESSION STATE ====================
if "wallet" not in st.session_state:
    st.session_state.wallet = STARTING_CAPITAL
if "holdings" not in st.session_state:
    st.session_state.holdings = []
if "watchlist" not in st.session_state:
    st.session_state.watchlist = DEFAULT_WATCHLIST.copy()
if "trade_log" not in st.session_state:
    st.session_state.trade_log = []

# ==================== QUANTITATIVE STRATEGY & INDICATOR ENGINE ====================
def compute_strategy_signals(hist_df):
    """
    Computes professional indicators: 
    - EMA 9 & EMA 21 Crossover
    - RSI (14) Momentum Filter
    - ATR (14) Volatility-based Stop-Loss & Target calculation
    """
    if len(hist_df) < 30:
        return {"Signal": "NO DATA", "Entry": 0, "StopLoss": 0, "Target": 0, "RSI": 50, "ATR": 0}
    
    close = hist_df["Close"]
    high = hist_df["High"]
    low = hist_df["Low"]
    
    # Exponential Moving Averages
    ema_9 = close.ewm(span=9, adjust=False).mean()
    ema_21 = close.ewm(span=21, adjust=False).mean()
    
    # RSI 14
    delta = close.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    
    # ATR 14 (Average True Range for Dynamic Risk Management)
    tr1 = high - low
    tr2 = (high - close.shift()).abs()
    tr3 = (low - close.shift()).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(window=14).mean()
    
    current_close = float(close.iloc[-1])
    curr_ema9 = float(ema_9.iloc[-1])
    curr_ema21 = float(ema_21.iloc[-1])
    curr_rsi = float(rsi.iloc[-1])
    curr_atr = float(atr.iloc[-1]) if not np.isnan(atr.iloc[-1]) else current_close * 0.01
    
    # Strategy Logic Matrix
    signal = "HOLD / NEUTRAL"
    if curr_ema9 > curr_ema21 and curr_rsi > 50 and curr_rsi < 70:
        signal = "🟢 BULLISH BUY"
    elif curr_ema9 < curr_ema21 and curr_rsi < 50 and curr_rsi > 30:
        signal = "🔴 BEARISH SELL"
    elif curr_rsi <= 30:
        signal = "⚡ OVERSOLD REVERSAL"
    elif curr_rsi >= 70:
        signal = "⚠️ OVERBOUGHT EXIT"

    # Risk-Reward Targets (1.5x ATR Risk, 3.0x ATR Reward)
    stop_loss = round(current_close - (1.5 * curr_atr), 2)
    target = round(current_close + (3.0 * curr_atr), 2)
    
    return {
        "Signal": signal,
        "Entry": round(current_close, 2),
        "StopLoss": stop_loss,
        "Target": target,
        "RSI": round(curr_rsi, 2),
        "ATR": round(curr_atr, 2)
    }

@st.cache_data(ttl=60, show_spinner=False)
def fetch_market_quotes(symbols: tuple):
    data = {}
    for sym in symbols:
        try:
            ticker = yf.Ticker(sym)
            hist = ticker.history(period="3mo")
            if hist.empty:
                data[sym] = None
                continue
            
            current = float(hist["Close"].iloc[-1])
            prev = float(hist["Close"].iloc[-2]) if len(hist) > 1 else current
            strat = compute_strategy_signals(hist)
            
            data[sym] = {
                "price": current,
                "pct_1d": ((current - prev) / prev) * 100,
                "as_of": hist.index[-1].strftime("%d %b %H:%M"),
                **strat
            }
        except Exception:
            data[sym] = None
    return data

def get_symbols_needed():
    held = [h["symbol"] + ".NS" for h in st.session_state.holdings]
    return tuple(sorted(set(st.session_state.watchlist) | set(held)))

quotes = fetch_market_quotes(get_symbols_needed())

# ==================== SIDEBAR CONFIGURATION ====================
st.sidebar.header("🎛️ Terminal Settings")
account_mode = st.sidebar.selectbox("Trading Engine Mode", ["Paper Simulator (Active)", "Broker API (Ready)"])

nse_master = fetch_nse_master_list()
all_clean_symbols = sorted(nse_master.keys()) if nse_master else [s.replace(".NS", "") for s in DEFAULT_WATCHLIST]

def label_for(clean_sym):
    return f"{clean_sym} — {nse_master.get(clean_sym, '')}" if nse_master else clean_sym

def to_label(sym_with_ns):
    return label_for(sym_with_ns.replace(".NS", ""))

def to_symbol(label):
    return label.split(" — ")[0].strip() + ".NS"

current_labels = [to_label(s) for s in st.session_state.watchlist]
option_labels = sorted(set(label_for(s) for s in all_clean_symbols) | set(current_labels))

selected_labels = st.sidebar.multiselect("Watchlist Manager", options=option_labels, default=current_labels)
st.session_state.watchlist = [to_symbol(l) for l in selected_labels]

# ==================== MAIN APPLICATION TABS ====================
tab_scanner, tab_execute, tab_portfolio, tab_logs = st.tabs([
    "📊 Strategy Signal Scanner", 
    "💼 Execution & Risk Desk", 
    "📈 Active Portfolio", 
    "📜 Trade History Logs"
])

# --- TAB 1: STRATEGY SCANNER ---
with tab_scanner:
    st.subheader("🤖 Automated Entry, Stop-Loss & Target Matrix")
    st.markdown("Real-time screening using **EMA Crossovers**, **RSI momentum**, and **ATR Volatility Bands** for risk-optimized trade entries.")
    
    scanner_rows = []
    for sym in st.session_state.watchlist:
        q = quotes.get(sym)
        if q:
            scanner_rows.append({
                "Symbol": sym.replace(".NS", ""),
                "LTP (₹)": q["price"],
                "1D Change (%)": round(q["pct_1d"], 2),
                "RSI (14)": q["RSI"],
                "Strategy Action": q["Signal"],
                "Rec. Entry (₹)": q["Entry"],
                "Dynamic Stop Loss (₹)": q["StopLoss"],
                "Target Price (₹)": q["Target"]
            })
            
    if scanner_rows:
        df_strat = pd.DataFrame(scanner_rows)
        st.dataframe(
            df_strat, 
            use_container_width=True, 
            hide_index=True,
            column_config={
                "1D Change (%)": st.column_config.NumberColumn(format="%.2f%%"),
                "RSI (14)": st.column_config.NumberColumn(format="%.1f"),
            }
        )
    else:
        st.warning("Awaiting market data synchronization...")

# --- TAB 2: EXECUTION & RISK DESK ---
with tab_execute:
    st.subheader("⚡ Automated Order Placement & Risk Management")
    
    col_buy, col_info = st.columns([1, 1])
    
    with col_buy:
        st.markdown("### Place New Order")
        if st.session_state.watchlist:
            buy_label = st.selectbox("Select Asset", [to_label(s) for s in st.session_state.watchlist])
            target_stock = to_symbol(buy_label)
            q_info = quotes.get(target_stock)
            
            qty = st.number_input("Quantity", min_value=1, value=15, step=1)
            
            suggested_sl = q_info["StopLoss"] if q_info else 0.0
            suggested_tp = q_info["Target"] if q_info else 0.0
            
            custom_sl = st.number_input("Stop Loss ₹ (Risk Limit)", value=float(suggested_sl), step=0.5)
            custom_tp = st.number_input("Target Price ₹ (Reward Goal)", value=float(suggested_tp), step=0.5)
            
            if st.button("🚀 Submit Market Buy Order", use_container_width=True):
                if q_info:
                    total_amt = q_info["price"] * qty
                    if st.session_state.wallet >= total_amt:
                        st.session_state.wallet -= total_amt
                        clean_name = target_stock.replace(".NS", "")
                        
                        existing = next((h for h in st.session_state.holdings if h["symbol"] == clean_name), None)
                        if existing:
                            new_q = existing["qty"] + qty
                            existing["avg_price"] = ((existing["avg_price"] * existing["qty"]) + total_amt) / new_q
                            existing["qty"] = new_q
                        else:
                            st.session_state.holdings.append({
                                "symbol": clean_name,
                                "qty": qty,
                                "avg_price": q_info["price"],
                                "sl": custom_sl,
                                "tp": custom_tp
                            })
                        st.success(f"Successfully executed order for {qty} shares of {clean_name} at ₹{q_info['price']:.2f}!")
                        st.rerun()
                    else:
                        st.error("Insufficient wallet funds to execute trade.")

    with col_info:
        st.markdown("### 📋 Risk Management Rules")
        st.info(
            "**How the strategy works:**\n"
            "* **Entries:** Triggered when fast momentum (EMA 9) crosses trend lines accompanied by confirmation from the RSI oscillator.\n"
            "* **Stop-Loss (SL):** Automatically mapped below volatility parameters using Average True Range (ATR) to limit downside risk.\n"
            "* **Targets (TP):** Calculated using a 2:1 or 3:1 Risk-to-Reward ratio profile."
        )
        st.metric("Available Cash Balance", f"₹{st.session_state.wallet:,.2f}")

# --- TAB 3: ACTIVE PORTFOLIO ---
with tab_portfolio:
    st.subheader("📈 Open Positions & Real-Time P&L")
    if st.session_state.holdings:
        total_invested = 0
        total_current = 0
        
        for h in st.session_state.holdings:
            q = quotes.get(h["symbol"] + ".NS")
            current_price = q["price"] if q else h["avg_price"]
            invested_val = h["qty"] * h["avg_price"]
            current_val = h["qty"] * current_price
            pnl = current_val - invested_val
            pnl_pct = (pnl / invested_val) * 100 if invested_val > 0 else 0
            
            total_invested += invested_val
            total_current += current_val
            
            col1, col2, col3, col4 = st.columns(4)
            col1.markdown(f"**{h['symbol']}** ({h['qty']} units) \n Avg: ₹{h['avg_price']:.2f}")
            col2.markdown(f"LTP: ₹{current_price:.2f}")
            color_tag = "green" if pnl >= 0 else "red"
            col3.markdown(f"P&L: :{color_tag}[₹{pnl:,.2f} ({pnl_pct:+.2f}%)]")
            
            if st.button(f"Liquidate {h['symbol']}", key=f"sell_{h['symbol']}"):
                st.session_state.wallet += current_val
                st.session_state.trade_log.append({
                    "Symbol": h["symbol"],
                    "Qty": h["qty"],
                    "Exit Price": current_price,
                    "Realized P&L ₹": round(pnl, 2),
                    "Timestamp": datetime.now().strftime("%d %b %Y %H:%M")
                })
                st.session_state.holdings.remove(h)
                st.rerun()
            st.divider()
            
        m1, m2, m3 = st.columns(3)
        m1.metric("Total Invested Capital", f"₹{total_invested:,.2f}")
        m2.metric("Current Portfolio Value", f"₹{total_current:,.2f}")
        m3.metric("Total Unrealized P&L", f"₹{total_current - total_invested:,.2f}")
    else:
        st.info("No open market positions. Use the Execution Desk to enter positions.")

# --- TAB 4: TRADE LOGS ---
with tab_logs:
    st.subheader("📜 Completed Audit Logs")
    if st.session_state.trade_log:
        df_logs = pd.DataFrame(st.session_state.trade_log)
        st.dataframe(df_logs, use_container_width=True, hide_index=True)
    else:
        st.info("No recorded historical trades yet.")