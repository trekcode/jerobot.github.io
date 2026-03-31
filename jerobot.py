"""
Gold Scalping Bot - Dedicated for XAU/USD
Optimized for quick entries/exits with tight stops
"""

import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timedelta
import time
import requests
import logging
from typing import Optional, Tuple
from dataclasses import dataclass
from enum import Enum

# ============================================
# CONFIGURATION
# ============================================

# Telegram for Gold Bot
GOLD_BOT_TOKEN = "8686418191:AAHtEBJ9Lyehb3geZS1WwWukmYZatqpAe-A"
GOLD_BOT_CHAT_ID = "2057396237"

# Scalping Parameters
SCALP_ACCOUNT_BALANCE = 100  # $100 account
SCALP_RISK_PER_TRADE = 0.5  # 0.5% risk per scalp (lower for scalping)
MIN_SCALP_CONFIDENCE = 65
MAX_SCALP_TRADES_PER_DAY = 10
SCALP_HOLD_MINUTES = 15  # Max hold time in minutes

# Scalping Indicators
RSI_SCALP_BUY = 30  # Lower threshold for scalp buys
RSI_SCALP_SELL = 70  # Higher threshold for scalp sells
VOLUME_SPIKE_THRESHOLD = 1.5  # 150% of average volume
ATR_MULTIPLIER_SL = 1.0  # Tighter stop for scalping
ATR_MULTIPLIER_TP = 1.5  # Tighter target for scalping

# Session Times (UTC) - Best for Gold
GOLD_SESSIONS = {
    'London': (8, 16),
    'New York': (13, 21),
    'Asian': (23, 8)
}

# ============================================
# DATA CLASSES
# ============================================

class ScalpSignalType(Enum):
    BUY = "BUY"
    SELL = "SELL"
    NEUTRAL = "NEUTRAL"

@dataclass
class ScalpSignal:
    """Scalping trade signal"""
    signal: ScalpSignalType
    entry: float
    stop_loss: float
    take_profit: float
    confidence: int
    rsi_1m: float
    rsi_5m: float
    volume_ratio: float
    session: str
    risk_reward: float
    timestamp: datetime
    expiry: datetime
    lot_size: float

# ============================================
# LOGGING
# ============================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler('gold_scalp.log'), logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# ============================================
# TELEGRAM FUNCTIONS
# ============================================

def send_gold_signal(signal: ScalpSignal) -> bool:
    """Send gold scalping signal to Telegram"""
    
    if signal.signal == ScalpSignalType.BUY:
        emoji = "🟢⚡"
        action = "BUY"
        direction = "▲"
    else:
        emoji = "🔴⚡"
        action = "SELL"
        direction = "▼"
    
    # Determine strength
    if signal.confidence >= 80:
        strength = "🔥 STRONG SCALP"
    elif signal.confidence >= 70:
        strength = "⚡ SCALP OPPORTUNITY"
    else:
        strength = "📊 SCALP ALERT"
    
    message = f"""
{emoji} <b>GOLD SCALP {action}</b>

<b>{strength}</b>
<b>Confidence:</b> {signal.confidence}%

<b>💰 Trade Levels:</b>
• Entry: ${signal.entry:.2f}
• Stop Loss: ${signal.stop_loss:.2f}
• Take Profit: ${signal.take_profit:.2f}
• Risk/Reward: 1:{signal.risk_reward:.1f}

<b>📊 Technicals:</b>
• RSI (1m): {signal.rsi_1m:.1f}
• RSI (5m): {signal.rsi_5m:.1f}
• Volume Ratio: {signal.volume_ratio:.1f}x

<b>📋 Position:</b>
• Lot Size: {signal.lot_size:.2f}
• Risk Amount: ${SCALP_ACCOUNT_BALANCE * SCALP_RISK_PER_TRADE / 100:.2f}

<b>⏰ Timing:</b>
• Session: {signal.session}
• Expires: {signal.expiry.strftime('%H:%M')} UTC ({SCALP_HOLD_MINUTES} min)

<i>⚡ Scalping Tip: Quick entry/exit within 5-15 minutes</i>
<i>⚠️ High risk - Use tight stops!</i>
"""
    
    try:
        url = f"https://api.telegram.org/bot{GOLD_BOT_TOKEN}/sendMessage"
        payload = {
            'chat_id': GOLD_BOT_CHAT_ID,
            'text': message,
            'parse_mode': 'HTML',
            'disable_web_page_preview': True
        }
        response = requests.post(url, json=payload, timeout=10)
        return response.status_code == 200
    except Exception as e:
        logger.error(f"Telegram error: {e}")
        return False

# ============================================
# GOLD SCALPING ANALYSIS
# ============================================

def fetch_gold_data() -> Optional[Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]]:
    """Fetch gold data for multiple timeframes"""
    try:
        df_1m = yf.Ticker('GC=F').history(period='1d', interval='1m')
        df_5m = yf.Ticker('GC=F').history(period='1d', interval='5m')
        df_15m = yf.Ticker('GC=F').history(period='1d', interval='15m')
        
        if len(df_1m) < 20:
            return None
        
        return df_1m, df_5m, df_15m
        
    except Exception as e:
        logger.error(f"Gold data fetch error: {e}")
        return None

def calculate_scalp_indicators(df_1m: pd.DataFrame, df_5m: pd.DataFrame) -> dict:
    """Calculate scalping indicators"""
    try:
        # Current price
        current = df_1m['Close'].iloc[-1]
        
        # 1-minute EMAs
        ema_5 = df_1m['Close'].ewm(span=5, adjust=False).mean().iloc[-1]
        ema_10 = df_1m['Close'].ewm(span=10, adjust=False).mean().iloc[-1]
        
        # 1-minute RSI (7 period for scalping)
        delta = df_1m['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(7).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(7).mean()
        rs = gain / loss
        rsi_1m = 100 - (100 / (1 + rs)).iloc[-1]
        
        # 1-minute ATR
        high_low = df_1m['High'] - df_1m['Low']
        high_close = abs(df_1m['High'] - df_1m['Close'].shift())
        low_close = abs(df_1m['Low'] - df_1m['Close'].shift())
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        atr_1m = tr.rolling(7).mean().iloc[-1]
        
        # Volume ratio
        volume_sma = df_1m['Volume'].rolling(10).mean().iloc[-1]
        current_volume = df_1m['Volume'].iloc[-1]
        volume_ratio = current_volume / volume_sma if volume_sma > 0 else 1
        
        # 5-minute RSI
        if len(df_5m) > 5:
            delta_5m = df_5m['Close'].diff()
            gain_5m = (delta_5m.where(delta_5m > 0, 0)).rolling(7).mean()
            loss_5m = (-delta_5m.where(delta_5m < 0, 0)).rolling(7).mean()
            rs_5m = gain_5m / loss_5m
            rsi_5m = 100 - (100 / (1 + rs_5m)).iloc[-1]
        else:
            rsi_5m = 50
        
        # Candlestick patterns
        body = abs(df_1m['Close'].iloc[-1] - df_1m['Open'].iloc[-1])
        range_ = df_1m['High'].iloc[-1] - df_1m['Low'].iloc[-1]
        candle_strength = body / range_ if range_ > 0 else 0
        
        return {
            'current': current,
            'ema_5': ema_5,
            'ema_10': ema_10,
            'rsi_1m': rsi_1m,
            'rsi_5m': rsi_5m,
            'atr': atr_1m,
            'volume_ratio': volume_ratio,
            'candle_strength': candle_strength
        }
        
    except Exception as e:
        logger.error(f"Indicator calculation error: {e}")
        return None

def generate_scalp_signal(indicators: dict) -> Optional[ScalpSignal]:
    """Generate scalping signal based on indicators"""
    try:
        buy_score = 0
        sell_score = 0
        
        current = indicators['current']
        
        # 1. EMA alignment
        if current > indicators['ema_5'] > indicators['ema_10']:
            buy_score += 2
        elif current < indicators['ema_5'] < indicators['ema_10']:
            sell_score += 2
        
        # 2. RSI thresholds (tighter for scalping)
        if indicators['rsi_1m'] < RSI_SCALP_BUY:
            buy_score += 3
        elif indicators['rsi_1m'] > RSI_SCALP_SELL:
            sell_score += 3
        elif indicators['rsi_1m'] < 40:
            buy_score += 1
        elif indicators['rsi_1m'] > 60:
            sell_score += 1
        
        # 3. Volume confirmation
        if indicators['volume_ratio'] > VOLUME_SPIKE_THRESHOLD:
            if indicators['candle_strength'] > 0.6:
                if current > indicators['ema_5']:
                    buy_score += 2
                else:
                    sell_score += 2
        
        # 4. 5-minute momentum
        if indicators['rsi_5m'] < 40:
            buy_score += 1
        elif indicators['rsi_5m'] > 60:
            sell_score += 1
        
        # 5. Candle strength
        if indicators['candle_strength'] > 0.7:
            if indicators['rsi_1m'] < 50:
                buy_score += 1
            else:
                sell_score += 1
        
        # Determine signal
        total_score = buy_score + sell_score
        if total_score == 0:
            return None
        
        if buy_score > sell_score and buy_score >= 3:
            signal = ScalpSignalType.BUY
            confidence = min(90, 50 + int((buy_score / total_score) * 50))
            
            # Tight scalping levels
            stop_loss = current - (indicators['atr'] * ATR_MULTIPLIER_SL)
            take_profit = current + (indicators['atr'] * ATR_MULTIPLIER_TP)
            
        elif sell_score > buy_score and sell_score >= 3:
            signal = ScalpSignalType.SELL
            confidence = min(90, 50 + int((sell_score / total_score) * 50))
            
            stop_loss = current + (indicators['atr'] * ATR_MULTIPLIER_SL)
            take_profit = current - (indicators['atr'] * ATR_MULTIPLIER_TP)
        else:
            return None
        
        # Check confidence
        if confidence < MIN_SCALP_CONFIDENCE:
            return None
        
        # Calculate risk/reward
        risk = abs(current - stop_loss)
        reward = abs(take_profit - current)
        risk_reward = reward / risk if risk > 0 else 0
        
        if risk_reward < 1.5:
            return None
        
        # Calculate lot size for scalping
        stop_pips = risk * 100  # Convert to pips
        risk_amount = SCALP_ACCOUNT_BALANCE * (SCALP_RISK_PER_TRADE / 100)
        lot_size = risk_amount / (stop_pips * 0.1)  # $0.1 per pip for gold
        lot_size = max(0.01, min(1.0, round(lot_size, 2)))
        
        # Get current session
        current_hour = datetime.utcnow().hour
        if 8 <= current_hour < 16:
            session = "London"
        elif 13 <= current_hour < 21:
            session = "New York"
        else:
            session = "Asian"
        
        return ScalpSignal(
            signal=signal,
            entry=current,
            stop_loss=stop_loss,
            take_profit=take_profit,
            confidence=confidence,
            rsi_1m=indicators['rsi_1m'],
            rsi_5m=indicators['rsi_5m'],
            volume_ratio=indicators['volume_ratio'],
            session=session,
            risk_reward=risk_reward,
            timestamp=datetime.now(),
            expiry=datetime.now() + timedelta(minutes=SCALP_HOLD_MINUTES),
            lot_size=lot_size
        )
        
    except Exception as e:
        logger.error(f"Signal generation error: {e}")
        return None

# ============================================
# SCALPING BOT CLASS
# ============================================

class GoldScalpingBot:
    """Dedicated gold scalping bot"""
    
    def __init__(self):
        self.signals_sent_today = 0
        self.last_signal_time = None
        self.last_signal_key = None
        
    def can_scalp(self) -> bool:
        """Check if we can scalp"""
        if self.signals_sent_today >= MAX_SCALP_TRADES_PER_DAY:
            return False, f"Max {MAX_SCALP_TRADES_PER_DAY} scalp trades per day"
        
        if self.last_signal_time:
            time_diff = (datetime.now() - self.last_signal_time).total_seconds()
            if time_diff < 60:  # 1 minute cooldown
                return False, "Too frequent (1 min cooldown)"
        
        return True, "OK"
    
    def analyze(self) -> Optional[ScalpSignal]:
        """Run gold scalping analysis"""
        
        # Check if we can scalp
        can_scalp, reason = self.can_scalp()
        if not can_scalp:
            logger.info(f"Scalping blocked: {reason}")
            return None
        
        # Fetch data
        data = fetch_gold_data()
        if not data:
            return None
        
        df_1m, df_5m, df_15m = data
        
        # Calculate indicators
        indicators = calculate_scalp_indicators(df_1m, df_5m)
        if not indicators:
            return None
        
        # Generate signal
        signal = generate_scalp_signal(indicators)
        if not signal:
            return None
        
        # Prevent duplicate signals
        signal_key = f"{signal.signal.value}_{signal.entry:.1f}"
        if signal_key == self.last_signal_key:
            return None
        
        # Update state
        self.signals_sent_today += 1
        self.last_signal_time = datetime.now()
        self.last_signal_key = signal_key
        
        return signal

# ============================================
# STREAMLIT UI
# ============================================

st.set_page_config(page_title="Gold Scalping Bot", layout="wide")

st.title("🥇 Gold Scalping Bot")
st.write("Dedicated scalping signals for XAU/USD | Tight stops | Quick entries")

# Initialize bot
if 'scalp_bot' not in st.session_state:
    st.session_state.scalp_bot = GoldScalpingBot()
    st.session_state.last_scalp_signal = None
    st.session_state.auto_scalp = False

# Sidebar
with st.sidebar:
    st.header("⚡ Scalping Settings")
    
    st.subheader("💰 Risk Management")
    st.metric("Account Balance", f"${SCALP_ACCOUNT_BALANCE}")
    st.metric("Risk per Trade", f"{SCALP_RISK_PER_TRADE}%")
    st.metric("Max Trades/Day", MAX_SCALP_TRADES_PER_DAY)
    
    st.subheader("🎯 Signal Filters")
    st.metric("Min Confidence", f"{MIN_SCALP_CONFIDENCE}%")
    st.metric("Min R/R", "1:1.5")
    st.metric("Hold Time", f"{SCALP_HOLD_MINUTES} min")
    
    st.subheader("📊 Today's Stats")
    st.metric("Signals Sent", st.session_state.scalp_bot.signals_sent_today)
    st.metric("Remaining", MAX_SCALP_TRADES_PER_DAY - st.session_state.scalp_bot.signals_sent_today)
    
    # Auto-scalp toggle
    st.session_state.auto_scalp = st.checkbox("⚡ Auto-Scalp (every 2 min)", value=False)
    
    # Manual button
    if st.button("🔍 Check Gold NOW", use_container_width=True):
        st.rerun()

# Manual or auto analysis
should_analyze = st.button("🚀 Generate Scalp Signal", use_container_width=True) or st.session_state.auto_scalp

if should_analyze:
    with st.spinner("Analyzing gold for scalp opportunities..."):
        signal = st.session_state.scalp_bot.analyze()
        st.session_state.last_scalp_signal = signal
        
        if signal:
            # Send to Telegram
            success = send_gold_signal(signal)
            if success:
                st.success(f"✅ {signal.signal.value} SCALP SIGNAL SENT!")
            else:
                st.error("Failed to send Telegram notification")
        else:
            st.info("⚖️ No scalp signal at this time")

# Display last signal
st.markdown("## 🎯 LAST SCALP SIGNAL")

if st.session_state.last_scalp_signal:
    s = st.session_state.last_scalp_signal
    
    if s.signal == ScalpSignalType.BUY:
        color = "#1a472a"
        border = "#ffff00"
        emoji = "🟢⚡"
    else:
        color = "#471a1a"
        border = "#ffaa00"
        emoji = "🔴⚡"
    
    st.markdown(f"""
    <div style="background: {color}; border-left: 5px solid {border}; padding: 20px; border-radius: 10px;">
        <h2>{emoji} {s.signal.value} GOLD SCALP</h2>
        <table style="width: 100%;">
            <tr>
                <td><b>💰 Entry:</b></td><td>${s.entry:.2f}</td>
                <td><b>🎯 Confidence:</b></td><td>{s.confidence}%</td>
            </tr>
            <tr>
                <td><b>🛑 Stop Loss:</b></td><td>${s.stop_loss:.2f}</td>
                <td><b>🎯 Take Profit:</b></td><td>${s.take_profit:.2f}</td>
            </tr>
            <tr>
                <td><b>📊 RSI (1m):</b></td><td>{s.rsi_1m:.1f}</td>
                <td><b>📊 RSI (5m):</b></td><td>{s.rsi_5m:.1f}</td>
            </tr>
            <tr>
                <td><b>📈 Volume:</b></td><td>{s.volume_ratio:.1f}x avg</td>
                <td><b>📊 Risk/Reward:</b></td><td>1:{s.risk_reward:.1f}</td>
            </tr>
            <tr>
                <td><b>💼 Lot Size:</b></td><td>{s.lot_size:.2f}</td>
                <td><b>⏰ Expires:</b></td><td>{s.expiry.strftime('%H:%M:%S')} UTC</td>
            </tr>
        </table>
    </div>
    """, unsafe_allow_html=True)
else:
    st.info("No scalp signal generated yet. Click 'Generate Scalp Signal' to start.")

# Auto-scalp logic
if st.session_state.auto_scalp:
    st.markdown("---")
    st.info("⚡ Auto-scalp enabled - Checking every 2 minutes...")
    time.sleep(120)
    st.rerun()

# Footer
st.markdown("---")
st.markdown("""
<div style='text-align: center; color: gray;'>
    <p>⚠️ <b>Educational purposes only</b> - High risk strategy!</p>
    <p>⚡ Scalping requires fast execution and tight risk management</p>
    <p>📊 Signals based on: 1m/5m RSI, Volume spikes, EMA crossovers</p>
</div>
""", unsafe_allow_html=True)
