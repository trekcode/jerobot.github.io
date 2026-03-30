import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import requests
from datetime import datetime, timedelta
import time
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import warnings
warnings.filterwarnings('ignore')

# ============================================
# PAGE CONFIGURATION
# ============================================
st.set_page_config(
    page_title="Low Volatility Forex Bot",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================
# CONFIGURATION
# ============================================
TELEGRAM_TOKEN = st.secrets.get("TELEGRAM_TOKEN", "8773664334:AAE4fd4Wpyd2ZQkWBsjlPby7qSGKp00jGng")
CHAT_ID = st.secrets.get("CHAT_ID", "2057396237")

# Trading Parameters
MIN_CONFIDENCE = 65
TIMEFRAME = '1h'
LOOKBACK_DAYS = 7
RISK_PER_TRADE = 1.5
HOLD_TIME_HOURS = 2
ATR_MULTIPLIER = 1.2
PROFIT_MULTIPLIER = 1.8

# Low Volatility Pairs
LOW_VOLATILITY_PAIRS = {
    'EURCHF=X': '🇪🇺/🇨🇭 EUR/CHF',
    'GBPCHF=X': '🇬🇧/🇨🇭 GBP/CHF',
    'AUDNZD=X': '🇦🇺/🇳🇿 AUD/NZD',
    'EURGBP=X': '🇪🇺/🇬🇧 EUR/GBP',
    'USDCHF=X': '🇺🇸/🇨🇭 USD/CHF',
    'EURHUF=X': '🇪🇺/🇭🇺 EUR/HUF',
    'EURPLN=X': '🇪🇺/🇵🇱 EUR/PLN',
    'USDPLN=X': '🇺🇸/🇵🇱 USD/PLN',
    'EURCZK=X': '🇪🇺/🇨🇿 EUR/CZK',
    'USDCZK=X': '🇺🇸/🇨🇿 USD/CZK',
    'EURSEK=X': '🇪🇺/🇸🇪 EUR/SEK',
    'EURDKK=X': '🇪🇺/🇩🇰 EUR/DKK',
    'USDSEK=X': '🇺🇸/🇸🇪 USD/SEK',
    'USDDKK=X': '🇺🇸/🇩🇰 USD/DKK',
    'SGD=X': '🇸🇬 SGD/USD',
    'EURHKD=X': '🇪🇺/🇭🇰 EUR/HKD',
    'USDHKD=X': '🇺🇸/🇭🇰 USD/HKD',
    'EURTRY=X': '🇪🇺/🇹🇷 EUR/TRY',
    'USDMXN=X': '🇺🇸/🇲🇽 USD/MXN',
    'USDZAR=X': '🇺🇸/🇿🇦 USD/ZAR',
}
# ============================================

# Cache data to avoid excessive API calls
@st.cache_data(ttl=3600)
def fetch_pair_data(symbol, period=f'{LOOKBACK_DAYS}d', interval=TIMEFRAME):
    """Fetch forex data with caching"""
    try:
        ticker = yf.Ticker(symbol)
        df = ticker.history(period=period, interval=interval)
        return df
    except Exception as e:
        st.error(f"Error fetching {symbol}: {e}")
        return None

def calculate_indicators(df):
    """Calculate technical indicators"""
    if df is None or len(df) < 30:
        return None
    
    df = df.copy()
    
    # Moving Averages
    df['SMA_20'] = df['Close'].rolling(20).mean()
    df['SMA_50'] = df['Close'].rolling(50).mean()
    df['EMA_12'] = df['Close'].ewm(span=12, adjust=False).mean()
    df['EMA_26'] = df['Close'].ewm(span=26, adjust=False).mean()
    
    # RSI
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))
    
    # MACD
    exp1 = df['Close'].ewm(span=12, adjust=False).mean()
    exp2 = df['Close'].ewm(span=26, adjust=False).mean()
    df['MACD'] = exp1 - exp2
    df['MACD_Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
    df['MACD_Histogram'] = df['MACD'] - df['MACD_Signal']
    
    # Bollinger Bands
    df['BB_Middle'] = df['Close'].rolling(20).mean()
    bb_std = df['Close'].rolling(20).std()
    df['BB_Upper'] = df['BB_Middle'] + (bb_std * 2)
    df['BB_Lower'] = df['BB_Middle'] - (bb_std * 2)
    df['BB_Width'] = df['BB_Upper'] - df['BB_Lower']
    df['BB_Position'] = (df['Close'] - df['BB_Lower']) / df['BB_Width']
    
    # ATR
    high_low = df['High'] - df['Low']
    high_close = abs(df['High'] - df['Close'].shift())
    low_close = abs(df['Low'] - df['Close'].shift())
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    df['ATR'] = tr.rolling(14).mean()
    df['ATR_Percent'] = (df['ATR'] / df['Close']) * 100
    
    # ADX
    plus_dm = df['High'].diff()
    minus_dm = df['Low'].diff()
    plus_dm[plus_dm < 0] = 0
    minus_dm[minus_dm > 0] = 0
    atr = df['ATR']
    df['Plus_DI'] = 100 * (plus_dm.rolling(14).mean() / atr)
    df['Minus_DI'] = 100 * (abs(minus_dm).rolling(14).mean() / atr)
    df['ADX'] = 100 * (abs(df['Plus_DI'] - df['Minus_DI']) / (df['Plus_DI'] + df['Minus_DI'])).rolling(14).mean()
    
    return df

def generate_signal(df):
    """Generate trading signal"""
    if df is None or len(df) < 2:
        return None
    
    latest = df.iloc[-1]
    prev = df.iloc[-2]
    
    buy_score = 0
    sell_score = 0
    
    # RSI (Weight: 3)
    if latest['RSI'] < 30:
        buy_score += 3
    elif latest['RSI'] > 70:
        sell_score += 3
    elif latest['RSI'] < 40 and latest['RSI'] > prev['RSI']:
        buy_score += 1
    elif latest['RSI'] > 60 and latest['RSI'] < prev['RSI']:
        sell_score += 1
    
    # Bollinger Bands (Weight: 3)
    if latest['BB_Position'] < 0.2:
        buy_score += 3
    elif latest['BB_Position'] > 0.8:
        sell_score += 3
    elif latest['BB_Position'] < 0.3:
        buy_score += 1
    elif latest['BB_Position'] > 0.7:
        sell_score += 1
    
    # MACD (Weight: 2)
    if latest['MACD_Histogram'] > 0 and latest['MACD_Histogram'] > prev['MACD_Histogram']:
        buy_score += 2
    elif latest['MACD_Histogram'] < 0 and latest['MACD_Histogram'] < prev['MACD_Histogram']:
        sell_score += 2
    
    # ADX for range confirmation (Weight: 1)
    if latest['ADX'] < 25:
        buy_score += 1
        sell_score += 1
    
    total_score = buy_score + sell_score
    if total_score == 0:
        total_score = 1
    
    if buy_score > sell_score and buy_score >= 3:
        signal = "BUY"
        confidence = min(90, int((buy_score / total_score) * 100))
        signal_emoji = "🟢"
    elif sell_score > buy_score and sell_score >= 3:
        signal = "SELL"
        confidence = min(90, int((sell_score / total_score) * 100))
        signal_emoji = "🔴"
    else:
        signal = "NEUTRAL"
        confidence = 0
        signal_emoji = "⚪"
    
    # Calculate trade levels
    if signal != "NEUTRAL":
        entry = latest['Close']
        if signal == "BUY":
            stop_loss = entry - (latest['ATR'] * ATR_MULTIPLIER)
            take_profit = entry + (latest['ATR'] * PROFIT_MULTIPLIER)
        else:
            stop_loss = entry + (latest['ATR'] * ATR_MULTIPLIER)
            take_profit = entry - (latest['ATR'] * PROFIT_MULTIPLIER)
        
        risk_pips = abs(entry - stop_loss) * 10000
        reward_pips = abs(take_profit - entry) * 10000
        risk_reward = round(reward_pips / risk_pips, 2) if risk_pips > 0 else 0
    else:
        stop_loss = None
        take_profit = None
        risk_pips = 0
        reward_pips = 0
        risk_reward = 0
    
    return {
        'signal': signal,
        'signal_emoji': signal_emoji,
        'confidence': confidence,
        'entry': latest['Close'],
        'stop_loss': stop_loss,
        'take_profit': take_profit,
        'risk_pips': risk_pips,
        'reward_pips': reward_pips,
        'risk_reward': risk_reward,
        'rsi': latest['RSI'],
        'adx': latest['ADX'],
        'bb_position': latest['BB_Position'],
        'volatility': latest['ATR_Percent'],
        'trend': "Bullish" if latest['Close'] > latest['SMA_50'] else "Bearish"
    }

def send_telegram_notification(message):
    """Send notification to Telegram"""
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {
            'chat_id': CHAT_ID,
            'text': message,
            'parse_mode': 'HTML'
        }
        response = requests.post(url, json=payload, timeout=10)
        return response.ok
    except Exception as e:
        st.error(f"Telegram error: {e}")
        return False

def create_price_chart(df, pair_name, signal_data):
    """Create interactive price chart"""
    if df is None or len(df) < 20:
        return None
    
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, 
                        vertical_spacing=0.05, row_heights=[0.7, 0.3])
    
    # Candlestick chart
    fig.add_trace(go.Candlestick(
        x=df.index,
        open=df['Open'],
        high=df['High'],
        low=df['Low'],
        close=df['Close'],
        name='Price'
    ), row=1, col=1)
    
    # Add Bollinger Bands
    fig.add_trace(go.Scatter(
        x=df.index, y=df['BB_Upper'],
        name='BB Upper', line=dict(color='gray', dash='dash')
    ), row=1, col=1)
    
    fig.add_trace(go.Scatter(
        x=df.index, y=df['BB_Lower'],
        name='BB Lower', line=dict(color='gray', dash='dash'),
        fill='tonexty', fillcolor='rgba(128,128,128,0.1)'
    ), row=1, col=1)
    
    # Add SMA lines
    fig.add_trace(go.Scatter(
        x=df.index, y=df['SMA_20'],
        name='SMA 20', line=dict(color='blue', width=1)
    ), row=1, col=1)
    
    fig.add_trace(go.Scatter(
        x=df.index, y=df['SMA_50'],
        name='SMA 50', line=dict(color='orange', width=1)
    ), row=1, col=1)
    
    # RSI
    fig.add_trace(go.Scatter(
        x=df.index, y=df['RSI'],
        name='RSI', line=dict(color='purple')
    ), row=2, col=1)
    
    # Add RSI levels
    fig.add_hline(y=70, line_dash="dash", line_color="red", row=2, col=1)
    fig.add_hline(y=30, line_dash="dash", line_color="green", row=2, col=1)
    
    # Update layout
    fig.update_layout(
        title=f'{pair_name} - Price Chart',
        yaxis_title='Price',
        xaxis_title='Date',
        template='plotly_dark',
        height=600
    )
    
    fig.update_yaxes(title_text="RSI", row=2, col=1)
    
    return fig

def main():
    """Main Streamlit app"""
    st.title("📊 Low Volatility Forex Trading Bot")
    st.markdown("---")
    
    # Sidebar
    with st.sidebar:
        st.header("⚙️ Settings")
        
        st.subheader("📈 Trading Parameters")
        min_confidence = st.slider("Minimum Confidence", 50, 90, MIN_CONFIDENCE)
        risk_per_trade = st.slider("Risk per Trade (%)", 0.5, 3.0, RISK_PER_TRADE, 0.5)
        
        st.subheader("🔄 Update Options")
        auto_refresh = st.checkbox("Auto-refresh every 5 minutes", value=False)
        
        st.subheader("📱 Telegram Notifications")
        send_test = st.button("📨 Send Test Notification")
        
        if send_test:
            test_msg = "✅ Bot is running on Streamlit Cloud! You will receive trade signals automatically."
            if send_telegram_notification(test_msg):
                st.success("Test notification sent!")
            else:
                st.error("Failed to send notification")
        
        st.markdown("---")
        st.markdown("### 📊 Bot Status")
        st.markdown(f"✅ Active")
        st.markdown(f"📈 Analyzing: {len(LOW_VOLATILITY_PAIRS)} pairs")
        st.markdown(f"⏰ Last update: {datetime.now().strftime('%H:%M:%S')}")
    
    # Main content
    col1, col2, col3, col4 = st.columns(4)
    
    # Fetch and analyze all pairs
    with st.spinner("Analyzing markets..."):
        all_signals = []
        charts_data = {}
        
        progress_bar = st.progress(0)
        for idx, (symbol, name) in enumerate(LOW_VOLATILITY_PAIRS.items()):
            df = fetch_pair_data(symbol)
            if df is not None and len(df) > 0:
                df_with_indicators = calculate_indicators(df)
                if df_with_indicators is not None:
                    signal = generate_signal(df_with_indicators)
                    if signal:
                        signal['name'] = name
                        signal['symbol'] = symbol
                        signal['price'] = df_with_indicators['Close'].iloc[-1]
                        all_signals.append(signal)
                        charts_data[name] = df_with_indicators
            
            progress_bar.progress((idx + 1) / len(LOW_VOLATILITY_PAIRS))
        
        progress_bar.empty()
    
    # Display metrics
    active_signals = [s for s in all_signals if s['signal'] != 'NEUTRAL' and s['confidence'] >= min_confidence]
    
    with col1:
        st.metric("Total Pairs", len(all_signals))
    with col2:
        st.metric("Active Signals", len(active_signals))
    with col3:
        avg_conf = sum(s['confidence'] for s in active_signals) / len(active_signals) if active_signals else 0
        st.metric("Avg Confidence", f"{avg_conf:.0f}%")
    with col4:
        st.metric("Risk per Trade", f"{risk_per_trade}%")
    
    st.markdown("---")
    
    # Display trade signals
    if active_signals:
        st.subheader("🎯 ACTIVE TRADE SIGNALS")
        
        for signal in active_signals:
            with st.expander(f"{signal['signal_emoji']} {signal['name']} - {signal['signal']} (Confidence: {signal['confidence']}%)", expanded=True):
                col1, col2 = st.columns(2)
                
                with col1:
                    st.markdown(f"**💰 Current Price:** {signal['price']:.5f}")
                    st.markdown(f"**🎯 Signal:** {signal['signal']}")
                    st.markdown(f"**📊 Confidence:** {signal['confidence']}%")
                    st.markdown(f"**📈 RSI:** {signal['rsi']:.1f}")
                    st.markdown(f"**📉 ADX:** {signal['adx']:.1f}")
                
                with col2:
                    st.markdown(f"**🚀 Entry:** {signal['entry']:.5f}")
                    st.markdown(f"**🛑 Stop Loss:** {signal['stop_loss']:.5f} ({signal['risk_pips']:.1f} pips)")
                    st.markdown(f"**🎯 Take Profit:** {signal['take_profit']:.5f} ({signal['reward_pips']:.1f} pips)")
                    st.markdown(f"**📊 Risk/Reward:** 1:{signal['risk_reward']:.1f}")
                    st.markdown(f"**💰 Position Size:** {risk_per_trade / signal['risk_pips']:.2f} units per ${risk_per_trade} risk")
                
                # Send Telegram notification for new signals (only if auto-refresh)
                if auto_refresh and 'last_sent' not in st.session_state:
                    telegram_msg = f"""
🎯 <b>TRADE SIGNAL</b>

{signal['signal_emoji']} <b>{signal['name']}</b>
<b>Signal:</b> {signal['signal']}
<b>Confidence:</b> {signal['confidence']}%
<b>Price:</b> {signal['price']:.5f}

<b>📊 Trade Plan:</b>
Entry: {signal['entry']:.5f}
Stop Loss: {signal['stop_loss']:.5f}
Take Profit: {signal['take_profit']:.5f}
Risk/Reward: 1:{signal['risk_reward']:.1f}

<b>📈 Indicators:</b>
RSI: {signal['rsi']:.1f}
ADX: {signal['adx']:.1f}
Volatility: {signal['volatility']:.2f}%

⚠️ Educational purposes only
                    """
                    send_telegram_notification(telegram_msg)
                    st.session_state.last_sent = datetime.now()
                
                # Add chart
                if signal['name'] in charts_data:
                    st.plotly_chart(create_price_chart(charts_data[signal['name']], signal['name'], signal), use_container_width=True)
    
    else:
        st.info("No active trade signals at this time. Market is ranging or neutral.")
    
    # Display monitoring list
    st.subheader("📈 Market Monitoring")
    
    monitoring = [s for s in all_signals if s['signal'] == 'NEUTRAL' or s['confidence'] < min_confidence]
    
    if monitoring:
        cols = st.columns(4)
        for idx, signal in enumerate(monitoring[:8]):  # Show first 8
            with cols[idx % 4]:
                st.markdown(f"""
                <div style='padding: 10px; border: 1px solid #ddd; border-radius: 5px; margin: 5px;'>
                    <b>{signal['name']}</b><br>
                    Price: {signal['price']:.5f}<br>
                    RSI: {signal['rsi']:.1f}<br>
                    ADX: {signal['adx']:.1f}<br>
                    Status: ⏸️ Monitoring
                </div>
                """, unsafe_allow_html=True)
    
    # Auto-refresh logic
    if auto_refresh:
        st.markdown("---")
        st.info("🔄 Auto-refresh is enabled. Page will refresh every 5 minutes...")
        time.sleep(300)
        st.rerun()
    
    # Footer
    st.markdown("---")
    st.markdown("""
    <div style='text-align: center; color: gray;'>
        <p>⚠️ <b>Educational purposes only</b> - Not financial advice</p>
        <p>📊 Trading Strategy: Mean reversion on low volatility pairs</p>
        <p>⏱️ Expected Hold Time: 1-2 hours | 🎯 Risk per trade: 1-2%</p>
        <p>🔄 Data updates every hour | 📈 Technical indicators: RSI, MACD, Bollinger Bands, ADX</p>
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
