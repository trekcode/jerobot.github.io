import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime
import time
import requests

st.set_page_config(page_title="Gold Trading Bot", layout="wide")

# ============================================
# TELEGRAM NOTIFICATION CONFIGURATION
# ============================================
TELEGRAM_TOKEN = "8686418191:AAHtEBJ9Lyehb3geZS1WwWukmYZatqpAe-A"
TELEGRAM_CHAT_ID = "2057396237"  # Your chat ID

def send_telegram_message(message, parse_mode='HTML'):
    """Send message to Telegram"""
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {
            'chat_id': TELEGRAM_CHAT_ID,
            'text': message,
            'parse_mode': parse_mode
        }
        response = requests.post(url, json=payload, timeout=10)
        return response.status_code == 200
    except Exception as e:
        st.error(f"Telegram error: {e}")
        return False

def send_gold_signal(signal, price, confidence, stop_loss, take_profit, rsi, macd, trend):
    """Send formatted gold signal to Telegram"""
    
    if signal == "BUY":
        emoji = "🟢"
        action = "BUY"
        border = "🟢"
    elif signal == "SELL":
        emoji = "🔴"
        action = "SELL"
        border = "🔴"
    else:
        return
    
    message = f"""
<b>{emoji} GOLD {action} SIGNAL!</b>

<b>🥇 Instrument:</b> XAU/USD (Gold)
<b>💰 Price:</b> ${price:,.2f}
<b>🎯 Confidence:</b> {confidence}%
<b>📈 RSI:</b> {rsi:.1f}
<b>📊 MACD:</b> {macd}
<b>📉 Trend:</b> {trend}

<b>📋 Trade Plan (1-2 Hour Hold):</b>
• <b>Entry:</b> ${price:,.2f}
• <b>Stop Loss:</b> ${stop_loss:,.2f}
• <b>Take Profit:</b> ${take_profit:,.2f}

<b>⏰ Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

<i>⚠️ Educational purposes only - Trade at your own risk</i>
    """.strip()
    
    success = send_telegram_message(message)
    return success

# ============================================
# CUSTOM CSS FOR STYLING
# ============================================
st.markdown("""
<style>
.notification {
    position: fixed;
    top: 20px;
    right: 20px;
    z-index: 9999;
    padding: 15px 20px;
    border-radius: 10px;
    animation: slideIn 0.5s ease-out;
    box-shadow: 0 4px 12px rgba(0,0,0,0.3);
}
@keyframes slideIn {
    from {
        transform: translateX(100%);
        opacity: 0;
    }
    to {
        transform: translateX(0);
        opacity: 1;
    }
}
.buy-notification {
    background: linear-gradient(135deg, #1a472a 0%, #0e2a1a 100%);
    border-left: 5px solid #00ff00;
    color: white;
}
.sell-notification {
    background: linear-gradient(135deg, #471a1a 0%, #2a0e0e 100%);
    border-left: 5px solid #ff4444;
    color: white;
}
.gold-card {
    background: linear-gradient(135deg, #2c2c2c 0%, #1a1a1a 100%);
    border: 2px solid #ffaa00;
    border-radius: 15px;
    padding: 20px;
    margin: 10px 0;
}
.gold-price {
    font-size: 48px;
    font-weight: bold;
    color: #ffaa00;
}
</style>
""", unsafe_allow_html=True)

# ============================================
# APP TITLE
# ============================================
st.title("🥇 Gold Trading Bot - XAU/USD")
st.write("Real-time gold trading signals with Telegram notifications (Educational Only)")

# Initialize session state
if 'previous_signal' not in st.session_state:
    st.session_state.previous_signal = None
if 'previous_confidence' not in st.session_state:
    st.session_state.previous_confidence = 0
if 'telegram_sent' not in st.session_state:
    st.session_state.telegram_sent = set()
if 'auto_refresh' not in st.session_state:
    st.session_state.auto_refresh = False
if 'signal_history' not in st.session_state:
    st.session_state.signal_history = []

# ============================================
# SIDEBAR SETTINGS
# ============================================
with st.sidebar:
    st.header("⚙️ Settings")
    
    # Auto-refresh toggle
    st.session_state.auto_refresh = st.checkbox("🔄 Auto-refresh (every 60 seconds)", 
                                                 value=st.session_state.auto_refresh)
    
    st.markdown("---")
    
    # Telegram settings
    st.subheader("📱 Telegram Notifications")
    st.info(f"Bot: @{TELEGRAM_TOKEN.split(':')[0]}")
    st.caption(f"Chat ID: {TELEGRAM_CHAT_ID}")
    
    # Test Telegram button
    if st.button("📨 Send Test Message", use_container_width=True):
        test_msg = f"✅ <b>Gold Trading Bot is Online!</b>\n\n⏰ Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n🥇 Monitoring Gold (XAU/USD)\n🎯 Min Confidence: {min_confidence}%\n\n🔔 You will receive gold signals here!"
        if send_telegram_message(test_msg):
            st.success("✅ Test message sent! Check your Telegram!")
        else:
            st.error("❌ Failed to send. Check your token.")
    
    st.markdown("---")
    
    # Signal settings
    st.subheader("🔔 Signal Settings")
    notify_buy = st.checkbox("🔔 Notify on BUY signals", value=True)
    notify_sell = st.checkbox("🔔 Notify on SELL signals", value=True)
    min_confidence = st.slider("Minimum confidence for signals", 50, 90, 65)
    
    # Trading parameters
    st.subheader("📊 Trading Parameters")
    st.caption(f"Stop Loss: 1.5x ATR")
    st.caption(f"Take Profit: 2.5x ATR")
    st.caption(f"Expected Hold: 1-2 hours")
    
    st.markdown("---")
    
    # Manual refresh button
    if st.button("🔄 Refresh Now", use_container_width=True):
        st.rerun()

# ============================================
# FUNCTION TO ANALYZE GOLD
# ============================================
def analyze_gold():
    """Analyze Gold (XAU/USD) and generate signal"""
    try:
        # Fetch gold data - 1 hour timeframe
        gold = yf.Ticker("GC=F")
        df = gold.history(period='1wk', interval='1h')
        
        if len(df) < 30:
            return None
        
        # Current price and recent data
        current = df['Close'].iloc[-1]
        prev_close = df['Close'].iloc[-2]
        high_24h = df['High'].max()
        low_24h = df['Low'].min()
        
        # Moving Averages
        sma20 = df['Close'].rolling(20).mean().iloc[-1]
        sma50 = df['Close'].rolling(50).mean().iloc[-1] if len(df) >= 50 else sma20
        ema12 = df['Close'].ewm(span=12, adjust=False).mean().iloc[-1]
        ema26 = df['Close'].ewm(span=26, adjust=False).mean().iloc[-1]
        
        # RSI Calculation
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs)).iloc[-1]
        
        # MACD Calculation
        exp1 = df['Close'].ewm(span=12, adjust=False).mean()
        exp2 = df['Close'].ewm(span=26, adjust=False).mean()
        macd = exp1 - exp2
        macd_signal = macd.ewm(span=9, adjust=False).mean()
        macd_histogram = (macd - macd_signal).iloc[-1]
        macd_trend = "Bullish" if macd_histogram > 0 else "Bearish"
        
        # ATR for volatility
        high_low = df['High'] - df['Low']
        high_close = abs(df['High'] - df['Close'].shift())
        low_close = abs(df['Low'] - df['Close'].shift())
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        atr = tr.rolling(14).mean().iloc[-1]
        atr_percent = (atr / current) * 100
        
        # Bollinger Bands
        bb_middle = df['Close'].rolling(20).mean()
        bb_std = df['Close'].rolling(20).std()
        bb_upper = bb_middle + (bb_std * 2)
        bb_lower = bb_middle - (bb_std * 2)
        bb_position = (current - bb_lower.iloc[-1]) / (bb_upper.iloc[-1] - bb_lower.iloc[-1])
        
        # Signal scoring for Gold
        buy_score = 0
        sell_score = 0
        
        # Price vs SMA20
        if current > sma20:
            buy_score += 1
        else:
            sell_score += 1
        
        # SMA20 vs SMA50 (trend)
        if sma20 > sma50:
            buy_score += 1
        else:
            sell_score += 1
        
        # RSI signals
        if rsi < 30:
            buy_score += 2
        elif rsi > 70:
            sell_score += 2
        elif rsi < 45:
            buy_score += 1
        elif rsi > 55:
            sell_score += 1
        
        # MACD signals
        if macd_histogram > 0:
            buy_score += 1
        else:
            sell_score += 1
        
        # Bollinger Bands (mean reversion)
        if bb_position < 0.2:
            buy_score += 2
        elif bb_position > 0.8:
            sell_score += 2
        
        # Determine final signal
        if buy_score > sell_score and buy_score >= 3:
            signal = "BUY"
            signal_emoji = "🟢"
            confidence = min(90, 50 + (buy_score * 10))
            stop_loss = current - (atr * 1.5)
            take_profit = current + (atr * 2.5)
            trend = "Bullish" if current > sma50 else "Weak Bullish"
        elif sell_score > buy_score and sell_score >= 3:
            signal = "SELL"
            signal_emoji = "🔴"
            confidence = min(90, 50 + (sell_score * 10))
            stop_loss = current + (atr * 1.5)
            take_profit = current - (atr * 2.5)
            trend = "Bearish" if current < sma50 else "Weak Bearish"
        else:
            signal = "NEUTRAL"
            signal_emoji = "⚖️"
            confidence = 0
            stop_loss = None
            take_profit = None
            trend = "Sideways"
        
        # Price change
        price_change = ((current - prev_close) / prev_close) * 100
        
        # Risk/Reward
        risk_reward = None
        if signal != "NEUTRAL":
            risk = abs(current - stop_loss)
            reward = abs(take_profit - current)
            risk_reward = round(reward / risk, 2) if risk > 0 else 0
        
        return {
            'price': current,
            'price_change': price_change,
            'high_24h': high_24h,
            'low_24h': low_24h,
            'signal': signal,
            'signal_emoji': signal_emoji,
            'confidence': confidence,
            'rsi': rsi,
            'macd': macd_histogram,
            'macd_trend': macd_trend,
            'trend': trend,
            'atr': atr,
            'atr_percent': atr_percent,
            'bb_position': bb_position,
            'stop_loss': stop_loss,
            'take_profit': take_profit,
            'risk_reward': risk_reward,
            'sma20': sma20,
            'sma50': sma50,
            'buy_score': buy_score,
            'sell_score': sell_score,
            'timestamp': datetime.now()
        }
        
    except Exception as e:
        st.error(f"Error analyzing Gold: {e}")
        return None

# ============================================
# MAIN ANALYSIS
# ============================================
with st.spinner("Analyzing Gold market..."):
    gold_data = analyze_gold()

if gold_data:
    # ============================================
    # DISPLAY GOLD PRICE CARD
    # ============================================
    st.markdown(f"""
    <div class="gold-card">
        <div style="text-align: center;">
            <h2>🥇 Gold Spot Price (XAU/USD)</h2>
            <div class="gold-price">${gold_data['price']:,.2f}</div>
            <div style="font-size: 18px; color: {'#00ff00' if gold_data['price_change'] > 0 else '#ff4444'}">
                {gold_data['price_change']:+.2f}% (24h change)
            </div>
            <div style="margin-top: 10px;">
                <span style="color: #888;">24h High: ${gold_data['high_24h']:,.2f}</span> | 
                <span style="color: #888;">24h Low: ${gold_data['low_24h']:,.2f}</span>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # ============================================
    # CHECK FOR SIGNAL CHANGE
    # ============================================
    if gold_data['signal'] != 'NEUTRAL' and gold_data['confidence'] >= min_confidence:
        signal_key = f"{gold_data['signal']}_{gold_data['confidence']}_{int(gold_data['price'])}"
        
        if signal_key not in st.session_state.telegram_sent:
            if st.session_state.previous_signal != gold_data['signal']:
                # Send Telegram notification
                if gold_data['signal'] == 'BUY' and notify_buy:
                    send_gold_signal(
                        gold_data['signal'],
                        gold_data['price'],
                        gold_data['confidence'],
                        gold_data['stop_loss'],
                        gold_data['take_profit'],
                        gold_data['rsi'],
                        gold_data['macd_trend'],
                        gold_data['trend']
                    )
                    st.session_state.telegram_sent.add(signal_key)
                    # Add to history
                    st.session_state.signal_history.append({
                        'time': datetime.now(),
                        'signal': gold_data['signal'],
                        'price': gold_data['price'],
                        'confidence': gold_data['confidence']
                    })
                    
                elif gold_data['signal'] == 'SELL' and notify_sell:
                    send_gold_signal(
                        gold_data['signal'],
                        gold_data['price'],
                        gold_data['confidence'],
                        gold_data['stop_loss'],
                        gold_data['take_profit'],
                        gold_data['rsi'],
                        gold_data['macd_trend'],
                        gold_data['trend']
                    )
                    st.session_state.telegram_sent.add(signal_key)
                    # Add to history
                    st.session_state.signal_history.append({
                        'time': datetime.now(),
                        'signal': gold_data['signal'],
                        'price': gold_data['price'],
                        'confidence': gold_data['confidence']
                    })
    
    # Update previous signal
    st.session_state.previous_signal = gold_data['signal']
    st.session_state.previous_confidence = gold_data['confidence']
    
    # Clean old sent signals
    if len(st.session_state.telegram_sent) > 50:
        st.session_state.telegram_sent = set(list(st.session_state.telegram_sent)[-50:])
    
    # ============================================
    # DISPLAY TRADE SIGNAL CARD
    # ============================================
    st.markdown("## 🎯 Current Signal")
    
    if gold_data['signal'] != 'NEUTRAL' and gold_data['confidence'] >= min_confidence:
        if gold_data['signal'] == 'BUY':
            signal_color = "#1a472a"
            border_color = "#00ff00"
            bg_gradient = "linear-gradient(135deg, #1a472a 0%, #0e2a1a 100%)"
        else:
            signal_color = "#471a1a"
            border_color = "#ff4444"
            bg_gradient = "linear-gradient(135deg, #471a1a 0%, #2a0e0e 100%)"
        
        st.markdown(f"""
        <div style="background: {bg_gradient}; border-left: 5px solid {border_color}; padding: 20px; border-radius: 10px; margin: 10px 0;">
            <h2 style="margin: 0;">{gold_data['signal_emoji']} {gold_data['signal']} GOLD</h2>
            <p style="font-size: 24px; margin: 10px 0;">Confidence: {gold_data['confidence']}%</p>
        </div>
        """, unsafe_allow_html=True)
        
        # Trade Plan
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("🚀 Entry Price", f"${gold_data['price']:,.2f}")
        with col2:
            st.metric("🛑 Stop Loss", f"${gold_data['stop_loss']:,.2f}", 
                     delta=f"Risk: ${abs(gold_data['price'] - gold_data['stop_loss']):.2f}")
        with col3:
            st.metric("🎯 Take Profit", f"${gold_data['take_profit']:,.2f}",
                     delta=f"Reward: ${abs(gold_data['take_profit'] - gold_data['price']):.2f}")
        
        st.info(f"📊 Risk/Reward Ratio: 1:{gold_data['risk_reward']} | Expected Hold: 1-2 hours")
        
    else:
        st.info(f"⚖️ No trade signal at this time. Waiting for setup above {min_confidence}% confidence.")
    
    # ============================================
    # TECHNICAL INDICATORS
    # ============================================
    st.markdown("## 📊 Technical Indicators")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("RSI (14)", f"{gold_data['rsi']:.1f}",
                 delta="Oversold" if gold_data['rsi'] < 30 else ("Overbought" if gold_data['rsi'] > 70 else "Neutral"))
    
    with col2:
        st.metric("MACD", f"{gold_data['macd']:.4f}",
                 delta=gold_data['macd_trend'])
    
    with col3:
        st.metric("ATR Volatility", f"{gold_data['atr_percent']:.2f}%",
                 delta=f"${gold_data['atr']:.2f}")
    
    with col4:
        st.metric("Bollinger Position", f"{gold_data['bb_position']*100:.0f}%",
                 delta="Near Support" if gold_data['bb_position'] < 0.3 else ("Near Resistance" if gold_data['bb_position'] > 0.7 else "Middle"))
    
    # ============================================
    # MOVING AVERAGES
    # ============================================
    st.markdown("## 📈 Moving Averages")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.metric("SMA 20", f"${gold_data['sma20']:,.2f}",
                 delta=f"{((gold_data['price'] - gold_data['sma20']) / gold_data['sma20'] * 100):+.2f}% from price")
    
    with col2:
        st.metric("SMA 50", f"${gold_data['sma50']:,.2f}",
                 delta=f"{((gold_data['price'] - gold_data['sma50']) / gold_data['sma50'] * 100):+.2f}% from price")
    
    # ============================================
    # TREND ANALYSIS
    # ============================================
    st.markdown("## 📈 Trend Analysis")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Current Trend", gold_data['trend'])
    
    with col2:
        st.metric("Signal Score", f"Buy: {gold_data['buy_score']} | Sell: {gold_data['sell_score']}")
    
    with col3:
        st.metric("Market Condition", "High Volatility" if gold_data['atr_percent'] > 1.5 else "Normal Volatility")
    
    # ============================================
    # SIGNAL HISTORY
    # ============================================
    if st.session_state.signal_history:
        st.markdown("## 📜 Signal History")
        
        history_df = pd.DataFrame(st.session_state.signal_history[-10:])
        history_df['time'] = history_df['time'].dt.strftime('%Y-%m-%d %H:%M:%S')
        history_df = history_df.rename(columns={
            'time': 'Time',
            'signal': 'Signal',
            'price': 'Price',
            'confidence': 'Confidence'
        })
        
        st.dataframe(history_df, use_container_width=True, hide_index=True)
    
    # ============================================
    # TELEGRAM STATUS
    # ============================================
    with st.expander("📱 Telegram Status"):
        st.write(f"**Bot Token:** {TELEGRAM_TOKEN[:20]}...")
        st.write(f"**Chat ID:** {TELEGRAM_CHAT_ID}")
        st.write(f"**Signals Sent:** {len(st.session_state.telegram_sent)}")
        if st.session_state.signal_history:
            st.write("**Last Signal:**")
            last = st.session_state.signal_history[-1]
            st.write(f"• {last['signal']} at ${last['price']:,.2f} ({last['confidence']}%)")

# ============================================
# DISPLAY CURRENT TIME
# ============================================
st.markdown("---")
st.write(f"⏰ Last update: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
if st.session_state.auto_refresh:
    st.info("🔄 Auto-refresh enabled - Page updates every 60 seconds")

# ============================================
# AUTO-REFRESH LOGIC
# ============================================
if st.session_state.auto_refresh:
    time.sleep(60)
    st.rerun()

# ============================================
# FOOTER
# ============================================
st.markdown("---")
st.markdown("""
<div style='text-align: center; color: gray;'>
    <p>⚠️ <b>Educational purposes only</b> - Not financial advice</p>
    <p>🥇 Gold signals based on: RSI, MACD, Moving Averages, Bollinger Bands, and ATR</p>
    <p>📱 Telegram notifications sent to your phone when signals appear</p>
    <p>🔄 Enable auto-refresh in sidebar for live updates</p>
</div>
""", unsafe_allow_html=True)
