"""
Gold Trading Bot - Scalping / Day Trading / Swing
Dedicated for XAU/USD with desktop notifications & compact mode
"""

import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timedelta
import time
import requests
import logging
from typing import Optional, Tuple, List
from dataclasses import dataclass
from enum import Enum

# Try to import desktop notification library
try:
    from plyer import notification
    DESKTOP_NOTIFY_AVAILABLE = True
except ImportError:
    DESKTOP_NOTIFY_AVAILABLE = False
    logging.warning("plyer not installed. Desktop notifications disabled. Install with: pip install plyer")

# ============================================
# CONFIGURATION
# ============================================

# Telegram for Gold Bot (unchanged)
GOLD_BOT_TOKEN = "8686418191:AAHtEBJ9Lyehb3geZS1WwWukmYZatqpAe-A"
GOLD_BOT_CHAT_ID = "2057396237"

# ============================================
# TRADING STYLES & PARAMETERS
# ============================================

class TradingStyle(Enum):
    SCALPING = "Scalping"
    DAY_TRADING = "Day Trading"
    SWING = "Swing"
    ALL = "Show All"

@dataclass
class StyleConfig:
    """Configuration parameters for a trading style"""
    name: str
    timeframes: Tuple[str, ...]          # e.g. ('1m', '5m', '15m')
    risk_per_trade: float                # % of account
    min_confidence: int
    max_trades_per_day: int
    hold_minutes: int
    rsi_buy_threshold: int
    rsi_sell_threshold: int
    volume_spike_threshold: float
    atr_multiplier_sl: float
    atr_multiplier_tp: float
    min_risk_reward: float
    account_balance: float = 100

# Configuration for each style
STYLE_CONFIGS = {
    TradingStyle.SCALPING: StyleConfig(
        name="Scalping",
        timeframes=('1m', '5m', '15m'),
        risk_per_trade=0.5,
        min_confidence=65,
        max_trades_per_day=10,
        hold_minutes=15,
        rsi_buy_threshold=30,
        rsi_sell_threshold=70,
        volume_spike_threshold=1.5,
        atr_multiplier_sl=1.0,
        atr_multiplier_tp=1.5,
        min_risk_reward=1.5,
        account_balance=100
    ),
    TradingStyle.DAY_TRADING: StyleConfig(
        name="Day Trading",
        timeframes=('5m', '15m', '1h'),
        risk_per_trade=1.0,
        min_confidence=70,
        max_trades_per_day=5,
        hold_minutes=120,
        rsi_buy_threshold=35,
        rsi_sell_threshold=65,
        volume_spike_threshold=1.3,
        atr_multiplier_sl=1.5,
        atr_multiplier_tp=2.5,
        min_risk_reward=2.0,
        account_balance=100
    ),
    TradingStyle.SWING: StyleConfig(
        name="Swing",
        timeframes=('15m', '1h', '4h'),
        risk_per_trade=2.0,
        min_confidence=75,
        max_trades_per_day=2,
        hold_minutes=1440,   # 1 day
        rsi_buy_threshold=25,
        rsi_sell_threshold=75,
        volume_spike_threshold=1.2,
        atr_multiplier_sl=2.0,
        atr_multiplier_tp=3.0,
        min_risk_reward=2.5,
        account_balance=100
    ),
}

# ============================================
# DATA CLASSES
# ============================================

class SignalType(Enum):
    BUY = "BUY"
    SELL = "SELL"
    NEUTRAL = "NEUTRAL"

@dataclass
class TradingSignal:
    """Unified trade signal for any style"""
    style: TradingStyle
    signal: SignalType
    entry: float
    stop_loss: float
    take_profit: float
    confidence: int
    rsi_fast: float      # fast timeframe RSI
    rsi_slow: float      # slower timeframe RSI
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
    handlers=[logging.FileHandler('gold_trading.log'), logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# ============================================
# TELEGRAM FUNCTIONS (unchanged, but updated to use TradingSignal)
# ============================================

def send_telegram_signal(signal: TradingSignal) -> bool:
    """Send trading signal to Telegram (updated from scalping version)"""
    
    if signal.signal == SignalType.BUY:
        emoji = "🟢"
        action = "BUY"
    else:
        emoji = "🔴"
        action = "SELL"
    
    # Style-specific emoji
    style_emoji = {
        TradingStyle.SCALPING: "⚡",
        TradingStyle.DAY_TRADING: "📈",
        TradingStyle.SWING: "🐢"
    }.get(signal.style, "")
    
    # Determine strength
    if signal.confidence >= 85:
        strength = "🔥 STRONG SIGNAL"
    elif signal.confidence >= 70:
        strength = "✅ GOOD OPPORTUNITY"
    else:
        strength = "📊 TRADE ALERT"
    
    message = f"""
{emoji}{style_emoji} <b>{signal.style.value} {action}</b>

<b>{strength}</b>
<b>Confidence:</b> {signal.confidence}%

<b>💰 Trade Levels:</b>
• Entry: ${signal.entry:.2f}
• Stop Loss: ${signal.stop_loss:.2f}
• Take Profit: ${signal.take_profit:.2f}
• Risk/Reward: 1:{signal.risk_reward:.1f}

<b>📊 Technicals:</b>
• RSI (fast): {signal.rsi_fast:.1f}
• RSI (slow): {signal.rsi_slow:.1f}
• Volume Ratio: {signal.volume_ratio:.1f}x

<b>📋 Position:</b>
• Lot Size: {signal.lot_size:.2f}
• Risk Amount: ${STYLE_CONFIGS[signal.style].account_balance * STYLE_CONFIGS[signal.style].risk_per_trade / 100:.2f}

<b>⏰ Timing:</b>
• Session: {signal.session}
• Expires: {signal.expiry.strftime('%H:%M')} UTC ({STYLE_CONFIGS[signal.style].hold_minutes} min)

<i>📌 Trade according to style: {signal.style.value}</i>
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
# DESKTOP NOTIFICATION
# ============================================

def send_desktop_notification(signal: TradingSignal):
    """Send a native desktop notification"""
    if not DESKTOP_NOTIFY_AVAILABLE:
        return
    
    title = f"{signal.style.value} {signal.signal.value} Signal"
    message = f"Gold ${signal.entry:.2f}\nSL: {signal.stop_loss:.2f}  TP: {signal.take_profit:.2f}\nConfidence: {signal.confidence}%"
    
    try:
        notification.notify(
            title=title,
            message=message,
            timeout=5
        )
    except Exception as e:
        logger.warning(f"Desktop notification failed: {e}")

# ============================================
# DATA FETCHING (multi timeframe)
# ============================================

def fetch_multi_timeframe_data(timeframes: List[str]) -> dict:
    """Fetch gold data for multiple timeframes"""
    data_dict = {}
    try:
        for tf in timeframes:
            ticker = yf.Ticker('GC=F')
            # yfinance interval mapping
            interval_map = {'1m': '1m', '5m': '5m', '15m': '15m', '1h': '1h', '4h': '1h'}  # 4h not directly available, use 1h and resample?
            if tf == '4h':
                df = ticker.history(period='5d', interval='1h')
                df = df.resample('4H').agg({
                    'Open': 'first',
                    'High': 'max',
                    'Low': 'min',
                    'Close': 'last',
                    'Volume': 'sum'
                }).dropna()
            else:
                df = ticker.history(period='2d', interval=interval_map.get(tf, '5m'))
            if len(df) >= 20:
                data_dict[tf] = df
        return data_dict if data_dict else None
    except Exception as e:
        logger.error(f"Data fetch error: {e}")
        return None

# ============================================
# INDICATOR CALCULATIONS (style-aware)
# ============================================

def calculate_indicators(df: pd.DataFrame, rsi_period: int = 7) -> dict:
    """Calculate common indicators for a given DataFrame"""
    try:
        current = df['Close'].iloc[-1]
        
        # EMAs
        ema_fast = df['Close'].ewm(span=5, adjust=False).mean().iloc[-1]
        ema_slow = df['Close'].ewm(span=10, adjust=False).mean().iloc[-1]
        
        # RSI
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(rsi_period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(rsi_period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs)).iloc[-1]
        
        # ATR
        high_low = df['High'] - df['Low']
        high_close = abs(df['High'] - df['Close'].shift())
        low_close = abs(df['Low'] - df['Close'].shift())
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        atr = tr.rolling(7).mean().iloc[-1]
        
        # Volume ratio
        vol_sma = df['Volume'].rolling(10).mean().iloc[-1]
        vol_ratio = df['Volume'].iloc[-1] / vol_sma if vol_sma > 0 else 1
        
        # Candle strength
        body = abs(df['Close'].iloc[-1] - df['Open'].iloc[-1])
        candle_range = df['High'].iloc[-1] - df['Low'].iloc[-1]
        candle_strength = body / candle_range if candle_range > 0 else 0
        
        return {
            'current': current,
            'ema_fast': ema_fast,
            'ema_slow': ema_slow,
            'rsi': rsi,
            'atr': atr,
            'volume_ratio': vol_ratio,
            'candle_strength': candle_strength
        }
    except Exception as e:
        logger.error(f"Indicator error: {e}")
        return None

# ============================================
# SIGNAL GENERATION PER STYLE
# ============================================

def generate_signal_for_style(style: TradingStyle, data_dict: dict) -> Optional[TradingSignal]:
    """Generate a signal for a given trading style using its own config and timeframes"""
    config = STYLE_CONFIGS[style]
    
    # Fetch required timeframes
    tf_fast, tf_slow, _ = config.timeframes
    if tf_fast not in data_dict or tf_slow not in data_dict:
        return None
    
    df_fast = data_dict[tf_fast]
    df_slow = data_dict[tf_slow]
    
    ind_fast = calculate_indicators(df_fast)
    ind_slow = calculate_indicators(df_slow)
    if not ind_fast or not ind_slow:
        return None
    
    current = ind_fast['current']
    
    # Scoring system
    buy_score = 0
    sell_score = 0
    
    # 1. EMA alignment
    if current > ind_fast['ema_fast'] > ind_fast['ema_slow']:
        buy_score += 2
    elif current < ind_fast['ema_fast'] < ind_fast['ema_slow']:
        sell_score += 2
    
    # 2. RSI thresholds
    if ind_fast['rsi'] < config.rsi_buy_threshold:
        buy_score += 3
    elif ind_fast['rsi'] > config.rsi_sell_threshold:
        sell_score += 3
    elif ind_fast['rsi'] < (config.rsi_buy_threshold + 10):
        buy_score += 1
    elif ind_fast['rsi'] > (config.rsi_sell_threshold - 10):
        sell_score += 1
    
    # 3. Volume spike
    if ind_fast['volume_ratio'] > config.volume_spike_threshold:
        if ind_fast['candle_strength'] > 0.6:
            if current > ind_fast['ema_fast']:
                buy_score += 2
            else:
                sell_score += 2
    
    # 4. Slower timeframe momentum
    if ind_slow['rsi'] < 50:
        buy_score += 1
    elif ind_slow['rsi'] > 50:
        sell_score += 1
    
    # 5. Candle strength
    if ind_fast['candle_strength'] > 0.7:
        if ind_fast['rsi'] < 50:
            buy_score += 1
        else:
            sell_score += 1
    
    total_score = buy_score + sell_score
    if total_score == 0:
        return None
    
    # Determine direction and confidence
    if buy_score > sell_score and buy_score >= 3:
        signal_type = SignalType.BUY
        confidence = min(95, 50 + int((buy_score / total_score) * 50))
        stop_loss = current - (ind_fast['atr'] * config.atr_multiplier_sl)
        take_profit = current + (ind_fast['atr'] * config.atr_multiplier_tp)
    elif sell_score > buy_score and sell_score >= 3:
        signal_type = SignalType.SELL
        confidence = min(95, 50 + int((sell_score / total_score) * 50))
        stop_loss = current + (ind_fast['atr'] * config.atr_multiplier_sl)
        take_profit = current - (ind_fast['atr'] * config.atr_multiplier_tp)
    else:
        return None
    
    if confidence < config.min_confidence:
        return None
    
    # Risk/Reward
    risk = abs(current - stop_loss)
    reward = abs(take_profit - current)
    rr = reward / risk if risk > 0 else 0
    if rr < config.min_risk_reward:
        return None
    
    # Lot size
    stop_pips = risk * 100
    risk_amount = config.account_balance * (config.risk_per_trade / 100)
    lot_size = risk_amount / (stop_pips * 0.1)
    lot_size = max(0.01, min(1.0, round(lot_size, 2)))
    
    # Session detection
    hour = datetime.utcnow().hour
    if 8 <= hour < 16:
        session = "London"
    elif 13 <= hour < 21:
        session = "New York"
    else:
        session = "Asian"
    
    return TradingSignal(
        style=style,
        signal=signal_type,
        entry=current,
        stop_loss=stop_loss,
        take_profit=take_profit,
        confidence=confidence,
        rsi_fast=ind_fast['rsi'],
        rsi_slow=ind_slow['rsi'],
        volume_ratio=ind_fast['volume_ratio'],
        session=session,
        risk_reward=rr,
        timestamp=datetime.now(),
        expiry=datetime.now() + timedelta(minutes=config.hold_minutes),
        lot_size=lot_size
    )

# ============================================
# TRADING BOT CLASS (supports multiple styles)
# ============================================

class GoldTradingBot:
    def __init__(self):
        self.signals_sent_today = {style: 0 for style in TradingStyle}
        self.last_signal_time = {style: None for style in TradingStyle}
        self.last_signal_key = {style: None for style in TradingStyle}
    
    def can_trade(self, style: TradingStyle) -> Tuple[bool, str]:
        config = STYLE_CONFIGS[style]
        if self.signals_sent_today[style] >= config.max_trades_per_day:
            return False, f"Max {config.max_trades_per_day} {style.value} trades per day"
        
        last = self.last_signal_time[style]
        if last:
            if (datetime.now() - last).total_seconds() < 60:
                return False, "Cooldown 1 min"
        return True, "OK"
    
    def analyze_style(self, style: TradingStyle) -> Optional[TradingSignal]:
        can, reason = self.can_trade(style)
        if not can:
            logger.info(f"{style.value} blocked: {reason}")
            return None
        
        config = STYLE_CONFIGS[style]
        timeframes = list(config.timeframes)
        data_dict = fetch_multi_timeframe_data(timeframes)
        if not data_dict:
            return None
        
        signal = generate_signal_for_style(style, data_dict)
        if not signal:
            return None
        
        # Duplicate check
        signal_key = f"{signal.style.value}_{signal.signal.value}_{signal.entry:.1f}"
        if signal_key == self.last_signal_key[style]:
            return None
        
        # Update state
        self.signals_sent_today[style] += 1
        self.last_signal_time[style] = datetime.now()
        self.last_signal_key[style] = signal_key
        
        return signal
    
    def analyze_all_styles(self) -> List[TradingSignal]:
        signals = []
        for style in [TradingStyle.SCALPING, TradingStyle.DAY_TRADING, TradingStyle.SWING]:
            s = self.analyze_style(style)
            if s:
                signals.append(s)
        return signals

# ============================================
# STREAMLIT UI
# ============================================

st.set_page_config(page_title="Gold Trading Bot", layout="wide")

# Compact mode CSS
def set_compact_mode():
    st.markdown("""
    <style>
        .main .block-container {
            padding-top: 1rem;
            padding-bottom: 0rem;
        }
        .stMetric {
            font-size: 0.8rem;
        }
        h1, h2, h3 {
            margin-top: 0rem;
            margin-bottom: 0.5rem;
        }
        .stButton button {
            padding: 0.2rem 0.5rem;
        }
        hr {
            margin: 0.5rem 0rem;
        }
    </style>
    """, unsafe_allow_html=True)

st.title("🥇 Gold Trading Bot")
st.write("Scalping | Day Trading | Swing — Signals + Desktop Notifications")

# Initialize bot
if 'bot' not in st.session_state:
    st.session_state.bot = GoldTradingBot()
    st.session_state.last_signals = []
    st.session_state.auto_enabled = False
    st.session_state.compact_mode = False

# Sidebar
with st.sidebar:
    st.header("⚙️ Settings")
    trading_style = st.selectbox("Trading Style", [s.value for s in TradingStyle], index=0)
    selected_style = TradingStyle(trading_style)
    
    st.session_state.compact_mode = st.checkbox("📱 Compact Mode (mini app view)", value=st.session_state.compact_mode)
    if st.session_state.compact_mode:
        set_compact_mode()
    
    st.divider()
    st.subheader("📊 Today's Signals")
    for style in [TradingStyle.SCALPING, TradingStyle.DAY_TRADING, TradingStyle.SWING]:
        sent = st.session_state.bot.signals_sent_today[style]
        max_t = STYLE_CONFIGS[style].max_trades_per_day
        st.metric(f"{style.value}", f"{sent} / {max_t}")
    
    st.divider()
    st.session_state.auto_enabled = st.checkbox("⚡ Auto-Scan (every 2 min)", value=st.session_state.auto_enabled)
    
    if st.button("🔍 Scan Now", use_container_width=True):
        st.rerun()

# Main panel action
do_scan = st.button("🚀 Generate Signal(s)", use_container_width=True) or st.session_state.auto_enabled

if do_scan:
    with st.spinner("Analyzing gold..."):
        if selected_style == TradingStyle.ALL:
            signals = st.session_state.bot.analyze_all_styles()
        else:
            sig = st.session_state.bot.analyze_style(selected_style)
            signals = [sig] if sig else []
        
        st.session_state.last_signals = signals
        
        for sig in signals:
            # Telegram and desktop notification
            send_telegram_signal(sig)
            send_desktop_notification(sig)
        
        if signals:
            st.success(f"✅ {len(signals)} signal(s) generated and sent!")
        else:
            st.info("⏳ No trading opportunity at this moment.")

# Display signals
st.markdown("## 🎯 Latest Signal(s)")

if st.session_state.last_signals:
    cols = st.columns(min(len(st.session_state.last_signals), 3))
    for idx, sig in enumerate(st.session_state.last_signals):
        with cols[idx % 3]:
            bg_color = "#1a472a" if sig.signal == SignalType.BUY else "#471a1a"
            border_color = "#ffff00" if sig.signal == SignalType.BUY else "#ffaa00"
            emoji = "🟢" if sig.signal == SignalType.BUY else "🔴"
            st.markdown(f"""
            <div style="background: {bg_color}; border-left: 4px solid {border_color}; padding: 10px; border-radius: 8px; margin-bottom: 10px;">
                <b>{emoji} {sig.style.value} {sig.signal.value}</b><br>
                Entry: ${sig.entry:.2f}<br>
                SL: ${sig.stop_loss:.2f}  TP: ${sig.take_profit:.2f}<br>
                Conf: {sig.confidence}%  R/R: 1:{sig.risk_reward:.1f}<br>
                Expires: {sig.expiry.strftime('%H:%M')}
            </div>
            """, unsafe_allow_html=True)
else:
    st.info("No signal yet. Click 'Scan Now' to start.")

# Auto-loop
if st.session_state.auto_enabled:
    st.markdown("---")
    st.info("🔄 Auto-scan active – checking every 120 seconds...")
    time.sleep(120)
    st.rerun()

st.markdown("---")
st.caption("⚠️ Educational only. Desktop notifications need 'plyer' installed.")