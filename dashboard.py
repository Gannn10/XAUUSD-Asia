import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime, timedelta

# ==========================================
# 1. PAGE CONFIGURATION & HEDGE FUND STYLING
# ==========================================
st.set_page_config(
    page_title="XAUUSD Quant Alpha",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Inject Custom CSS untuk Tampilan Profesional / Terminal Bloomberg
st.markdown("""
<style>
    /* Global Font & Background */
    html, body, [class*="css"] {
        font-family: 'Inter', 'Roboto', sans-serif;
    }
    
    /* Mengurangi padding atas agar lebih padat */
    .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
    }

    /* Styling Metric Cards ala Dashboard Finansial */
    div[data-testid="stMetricValue"] {
        font-size: 1.8rem;
        font-weight: 700;
        color: #E0E0E0;
    }
    div[data-testid="stMetricLabel"] {
        font-size: 0.9rem;
        font-weight: 600;
        color: #8892B0;
        text-transform: uppercase;
        letter-spacing: 1px;
    }
    div[data-testid="stMetricDelta"] {
        font-size: 1rem;
    }
    
    /* Container Box Styling */
    .st-emotion-cache-1y4p8pa {
        padding: 1.5rem;
        border-radius: 8px;
        background-color: #111B21; /* Dark navy/black */
        border: 1px solid #23303F;
        box-shadow: 0 4px 6px rgba(0,0,0,0.3);
    }

    /* Table Styling */
    .dataframe {
        font-size: 14px;
    }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 2. MOCK DATA GENERATOR (Bisa diganti dengan data real)
# ==========================================
@st.cache_data
def load_mock_data():
    # Generate mock price data untuk XAUUSD
    dates = pd.date_range(end=datetime.now(), periods=100, freq='15min')
    df = pd.DataFrame(index=dates)
    
    # Random walk for XAUUSD price around 2300
    np.random.seed(42)
    returns = np.random.normal(0, 0.001, 100)
    price_path = 2300 * np.exp(returns.cumsum())
    
    df['Open'] = price_path
    df['High'] = price_path * (1 + np.abs(np.random.normal(0, 0.0005, 100)))
    df['Low'] = price_path * (1 - np.abs(np.random.normal(0, 0.0005, 100)))
    df['Close'] = price_path * (1 + np.random.normal(0, 0.0002, 100))
    
    # Mock Trades
    trades = pd.DataFrame({
        'Time': dates[-5:],
        'Type': ['BUY', 'SELL', 'BUY', 'BUY', 'SELL'],
        'Entry': df['Close'].iloc[-5:].values - 1,
        'Exit': df['Close'].iloc[-5:].values + 1,
        'Profit (USD)': [45.2, -12.5, 89.0, 32.1, 110.5],
        'Status': ['CLOSED', 'CLOSED', 'CLOSED', 'CLOSED', 'OPEN']
    })
    
    return df, trades

df_price, df_trades = load_mock_data()

# ==========================================
# 3. SIDEBAR NAVIGATION & CONTROLS
# ==========================================
with st.sidebar:
    st.title("⚙️ Engine Control")
    st.markdown("---")
    
    st.subheader("Model Status")
    st.success("🟢 ML Agent (v3): Online")
    st.success("🟢 Regime Detector: Active")
    st.warning("🟡 Data Feed: 12ms ping")
    
    st.markdown("---")
    st.subheader("Parameters")
    risk_level = st.select_slider("Risk Mode", options=["Conservative", "Moderate", "Aggressive"], value="Moderate")
    trade_size = st.number_input("Base Lot Size", min_value=0.01, max_value=10.0, value=0.1, step=0.01)
    
    if st.button("RETRAIN MODEL NOW", type="primary", use_container_width=True):
        st.toast("Triggering auto_retrain.py...")
        st.snow()

# ==========================================
# 4. MAIN DASHBOARD AREA
# ==========================================
# Header
col_header1, col_header2 = st.columns([3, 1])
with col_header1:
    st.title("XAUUSD Scalping Engine Alpha")
    st.markdown("*Quantitative Strategy Dashboard & Monitoring*")
with col_header2:
    st.markdown(f"<div style='text-align: right; padding-top: 1.5rem; color: #8892B0;'>Last Update: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</div>", unsafe_allow_html=True)

st.markdown("---")

# Row 1: KPI Metrics
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("Total PnL (YTD)", "$ 12,450.00", "+2.4% today")
with col2:
    st.metric("Win Rate", "68.5%", "120 Trades")
with col3:
    st.metric("Sharpe Ratio", "2.14", "+0.05")
with col4:
    st.metric("Max Drawdown", "-4.2%", "Safe")

st.markdown("<br>", unsafe_allow_html=True)

# Row 2: Charts and Signals
col_chart, col_signal = st.columns([3, 1])

with col_chart:
    st.subheader("Price Action & Liquidity Zones")
    
    # Plotly Candlestick Chart (Dark Theme)
    fig = go.Figure(data=[go.Candlestick(x=df_price.index,
                    open=df_price['Open'],
                    high=df_price['High'],
                    low=df_price['Low'],
                    close=df_price['Close'],
                    name='XAUUSD')])
    
    # Customize layout for Hedge Fund look
    fig.update_layout(
        template='plotly_dark',
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        margin=dict(l=0, r=0, t=30, b=0),
        xaxis_rangeslider_visible=False,
        height=450,
        font=dict(color='#8892B0')
    )
    
    # Add mock FVG or Liquidity zones (SMC)
    fig.add_hrect(y0=df_price['Low'].min(), y1=df_price['Low'].min()+0.5, 
                  line_width=0, fillcolor="rgba(0, 255, 0, 0.1)", annotation_text="Buy Side Liquidity")
    fig.add_hrect(y0=df_price['High'].max()-0.5, y1=df_price['High'].max(), 
                  line_width=0, fillcolor="rgba(255, 0, 0, 0.1)", annotation_text="Sell Side Liquidity")

    st.plotly_chart(fig, use_container_width=True)

with col_signal:
    st.subheader("Alpha Engine")
    
    # Regime indicator
    st.markdown("##### Market Regime")
    st.info("📊 **VOLATILE TRENDING**")
    st.progress(0.85, text="Trend Strength")
    
    st.markdown("<hr style='margin:1rem 0;'>", unsafe_allow_html=True)
    
    # Latest Signal
    st.markdown("##### Active Signal")
    st.markdown("""
    <div style='background-color: #1E3A2F; padding: 15px; border-radius: 5px; border-left: 5px solid #00C853;'>
        <h3 style='color: #00C853; margin: 0;'>BUY XAUUSD</h3>
        <p style='margin: 5px 0 0 0; font-size: 14px;'>Entry: 2315.40</p>
        <p style='margin: 0; font-size: 14px;'>SL: 2310.00 | TP: 2325.00</p>
    </div>
    """, unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# Row 3: Trade Log
st.subheader("Recent Execution Log")

# Formatting Pandas dataframe for Streamlit
def color_profit(val):
    if isinstance(val, (int, float)):
        color = '#00C853' if val > 0 else '#FF3D00' if val < 0 else 'white'
        return f'color: {color}; font-weight: bold;'
    return ''

styled_trades = df_trades.style.map(color_profit, subset=['Profit (USD)'])
st.dataframe(styled_trades, use_container_width=True, hide_index=True)
