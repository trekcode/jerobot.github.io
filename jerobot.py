import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import requests
import time
import os

# ============================================
# LOW VOLATILITY PAIRS CONFIGURATION
# ============================================
TOKEN = ('8773664334:AAE4fd4Wpyd2ZQkWBsjlPby7qSGKp00jGng')
CHAT_ID = ('2057396237')

# Trading Parameters
MIN_CONFIDENCE = 65  # Minimum confidence for signals
TIMEFRAME = '1h'     # 1-hour candles for analysis
LOOKBACK_DAYS = 7    # Look back 7 days for trend analysis

# Risk Management for Low Volatility
RISK_PER_TRADE = 1.5  # 1.5% risk per trade
HOLD_TIME_HOURS = 2   # Expected hold time 1-2 hours
ATR_MULTIPLIER = 1.2  # Tighter stops for low volatility
PROFIT_MULTIPLIER = 1.8  # Conservative profit target
# ============================================

# Low Volatility Pairs (Excluding major volatile pairs)
LOW_VOLATILITY_PAIRS = {
    # Major Pairs with Lower Volatility
    'EURCHF=X': '🇪🇺/🇨🇭 EUR/CHF',      # Very stable, low volatility
    'GBPCHF=X': '🇬🇧/🇨🇭 GBP/CHF',      # Moderate volatility
    'AUDNZD=X': '🇦🇺/🇳🇿 AUD/NZD',      # Stable commodity pair
    'EURGBP=X': '🇪🇺/🇬🇧 EUR/GBP',      # Stable cross pair
    'USDCHF=X': '🇺🇸/🇨🇭 USD/CHF',      # Swiss safe haven
    
    # Exotic but Stable Pairs
    'EURHUF=X': '🇪🇺/🇭🇺 EUR/HUF',      # Central European
    'EURPLN=X': '🇪🇺/🇵🇱 EUR/PLN',      # Polish Zloty
    'USDPLN=X': '🇺🇸/🇵🇱 USD/PLN',      # USD vs Zloty
    'EURCZK=X': '🇪🇺/🇨🇿 EUR/CZK',      # Czech Koruna
    'USDCZK=X': '🇺🇸/🇨🇿 USD/CZK',      # USD vs Koruna
    
    # Scandinavian Pairs (Low Volatility)
    'EURSEK=X': '🇪🇺/🇸🇪 EUR/SEK',      # Swedish Krona
    'EURDKK=X': '🇪🇺/🇩🇰 EUR/DKK',      # Danish Krone (Pegged)
    'USDSEK=X': '🇺🇸/🇸🇪 USD/SEK',      # USD vs Krona
    'USDDKK=X': '🇺🇸/🇩🇰 USD/DKK',      # USD vs Krone
    
    # Asian Pairs (Stable)
    'SGD=X': '🇸🇬 SGD/USD',             # Singapore Dollar
    'EURHKD=X': '🇪🇺/🇭🇰 EUR/HKD',      # Euro vs Hong Kong
    'USDHKD=X': '🇺🇸/🇭🇰 USD/HKD',      # USD vs Hong Kong (Pegged)
    
    # Additional Stable Pairs
    'EURTRY=X': '🇪🇺/🇹🇷 EUR/TRY',      # Turkish Lira (Caution)
    'USDMXN=X': '🇺🇸/🇲🇽 USD/MXN',      # Mexican Peso
    'USDZAR=X': '🇺🇸/🇿🇦 USD/ZAR',      # South African Rand
}

def send_telegram_message(message):
    """Send message to Telegram"""
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {'chat_id': CHAT_ID, 'text': message, 'parse_mode': 'HTML'}
    try:
        response = requests.post(url, json=payload, timeout=30)
        return response.ok
    except Exception as e:
        print(f"Error: {e}")
        return False

def calculate_low_volatility_indicators(df):
    """Calculate indicators optimized for low volatility pairs"""
    if len(df) < 30:
        return None
    
    # Moving Averages (Longer periods for stability)
    df['SMA_20'] = df['Close'].rolling(20).mean()
    df['SMA_50'] = df['Close'].rolling(50).mean()
    df['EMA_12'] = df['Close'].ewm(span=12, adjust=False).mean()
    df['EMA_26'] = df['Close'].ewm(span=26, adjust=False).mean()
    
    # RSI (Standard period for low volatility)
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))
    
    # MACD with standard settings
    exp1 = df['Close'].ewm(span=12, adjust=False).mean()
    exp2 = df['Close'].ewm(span=26, adjust=False).mean()
    df['MACD'] = exp1 - exp2
    df['MACD_Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
    df['MACD_Histogram'] = df['MACD'] - df['MACD_Signal']
    
    # Bollinger Bands (Standard deviation for range-bound markets)
    df['BB_Middle'] = df['Close'].rolling(20).mean()
    bb_std = df['Close'].rolling(20).std()
    df['BB_Upper'] = df['BB_Middle'] + (bb_std * 2)
    df['BB_Lower'] = df['BB_Middle'] - (bb_std * 2)
    df['BB_Width'] = df['BB_Upper'] - df['BB_Lower']
    df['BB_Position'] = (df['Close'] - df['BB_Lower']) / df['BB_Width']
    
    # ATR for volatility measurement
    high_low = df['High'] - df['Low']
    high_close = abs(df['High'] - df['Close'].shift())
    low_close = abs(df['Low'] - df['Close'].shift())
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    df['ATR'] = tr.rolling(14).mean()
    df['ATR_Percent'] = (df['ATR'] / df['Close']) * 100
    
    # Average True Range for low volatility confirmation
    df['ATR_SMA'] = df['ATR'].rolling(20).mean()
    df['Volatility_Ratio'] = df['ATR'] / df['ATR_SMA']
    
    # Support and Resistance levels
    df['Resistance'] = df['High'].rolling(20).max()
    df['Support'] = df['Low'].rolling(20).min()
    df['Range'] = df['Resistance'] - df['Support']
    
    # ADX for trend strength (lower values indicate ranging markets)
    plus_dm = df['High'].diff()
    minus_dm = df['Low'].diff()
    plus_dm[plus_dm < 0] = 0
    minus_dm[minus_dm > 0] = 0
    atr = df['ATR']
    df['Plus_DI'] = 100 * (plus_dm.rolling(14).mean() / atr)
    df['Minus_DI'] = 100 * (abs(minus_dm).rolling(14).mean() / atr)
    df['ADX'] = 100 * (abs(df['Plus_DI'] - df['Minus_DI']) / (df['Plus_DI'] + df['Minus_DI'])).rolling(14).mean()
    
    return df

def calculate_range_trading_signal(df):
    """Generate signals for range-bound, low volatility markets"""
    latest = df.iloc[-1]
    prev = df.iloc[-2]
    
    buy_score = 0
    sell_score = 0
    
    # 1. RSI for Range Trading (Weight: 3)
    if latest['RSI'] < 30:
        buy_score += 3  # Oversold
    elif latest['RSI'] > 70:
        sell_score += 3  # Overbought
    elif latest['RSI'] < 40 and latest['RSI'] > prev['RSI']:
        buy_score += 1  # Coming from oversold
    elif latest['RSI'] > 60 and latest['RSI'] < prev['RSI']:
        sell_score += 1  # Coming from overbought
    
    # 2. Bollinger Bands for Mean Reversion (Weight: 3)
    if latest['BB_Position'] < 0.2:
        buy_score += 3  # Near lower band
    elif latest['BB_Position'] > 0.8:
        sell_score += 3  # Near upper band
    elif latest['BB_Position'] < 0.3:
        buy_score += 1
    elif latest['BB_Position'] > 0.7:
        sell_score += 1
    
    # 3. Support & Resistance (Weight: 2)
    if latest['Close'] <= latest['Support'] * 1.005:
        buy_score += 2  # Near support
    elif latest['Close'] >= latest['Resistance'] * 0.995:
        sell_score += 2  # Near resistance
    
    # 4. MACD Momentum (Weight: 2)
    if latest['MACD_Histogram'] > 0 and latest['MACD_Histogram'] > prev['MACD_Histogram']:
        buy_score += 2
    elif latest['MACD_Histogram'] < 0 and latest['MACD_Histogram'] < prev['MACD_Histogram']:
        sell_score += 2
    
    # 5. Volatility Confirmation (Weight: 2)
    if latest['Volatility_Ratio'] < 1.2:  # Low volatility condition
        if latest['Close'] > latest['BB_Middle']:
            buy_score += 1
        else:
            sell_score += 1
    
    # 6. ADX for Range Confirmation (Weight: 1)
    if latest['ADX'] < 25:  # Ranging market
        buy_score += 1
        sell_score += 1
    
    # 7. Moving Average for Trend Filter (Weight: 1)
    if latest['Close'] > latest['SMA_20'] and latest['RSI'] < 50:
        buy_score += 1
    elif latest['Close'] < latest['SMA_20'] and latest['RSI'] > 50:
        sell_score += 1
    
    # Determine signal
    total_score = buy_score + sell_score
    if total_score == 0:
        total_score = 1
    
    # Lower threshold for low volatility pairs
    if buy_score > sell_score and buy_score >= 3:
        signal = "BUY"
        confidence = min(90, int((buy_score / total_score) * 100))
        signal_emoji = "🟢📊"
    elif sell_score > buy_score and sell_score >= 3:
        signal = "SELL"
        confidence = min(90, int((sell_score / total_score) * 100))
        signal_emoji = "🔴📊"
    else:
        signal = "NO SIGNAL"
        confidence = 0
        signal_emoji = "⏸️"
    
    # Calculate trade levels
    if signal != "NO SIGNAL":
        entry_price = latest['Close']
        
        if signal == "BUY":
            stop_loss = entry_price - (latest['ATR'] * ATR_MULTIPLIER)
            take_profit = entry_price + (latest['ATR'] * PROFIT_MULTIPLIER)
            risk_pips = abs(entry_price - stop_loss) * 10000
            reward_pips = abs(take_profit - entry_price) * 10000
        else:
            stop_loss = entry_price + (latest['ATR'] * ATR_MULTIPLIER)
            take_profit = entry_price - (latest['ATR'] * PROFIT_MULTIPLIER)
            risk_pips = abs(entry_price - stop_loss) * 10000
            reward_pips = abs(take_profit - entry_price) * 10000
        
        risk_reward = round(reward_pips / risk_pips, 2)
    else:
        stop_loss = None
        take_profit = None
        risk_reward = 0
        risk_pips = 0
        reward_pips = 0
    
    return {
        'signal': signal,
        'signal_emoji': signal_emoji,
        'confidence': confidence,
        'buy_score': buy_score,
        'sell_score': sell_score,
        'entry': latest['Close'],
        'stop_loss': stop_loss,
        'take_profit': take_profit,
        'risk_pips': risk_pips,
        'reward_pips': reward_pips,
        'risk_reward': risk_reward,
        'rsi': latest['RSI'],
        'bb_position': latest['BB_Position'],
        'bb_width': latest['BB_Width'],
        'adx': latest['ADX'],
        'volatility_ratio': latest['Volatility_Ratio'],
        'atr_percent': latest['ATR_Percent'],
        'trend': "Bullish" if latest['Close'] > latest['SMA_50'] else "Bearish",
        'range_status': "Ranging" if latest['ADX'] < 25 else "Trending"
    }

def analyze_low_volatility_pair(symbol, name):
    """Analyze a low volatility pair"""
    try:
        # Fetch 1-hour data
        ticker = yf.Ticker(symbol)
        df = ticker.history(period=f'{LOOKBACK_DAYS}d', interval=TIMEFRAME)
        
        if len(df) < 50:
            return None
        
        df = calculate_low_volatility_indicators(df)
        if df is None:
            return None
        
        signal_data = calculate_range_trading_signal(df)
        
        # Get recent price action
        latest = df.iloc[-1]
        prev_5 = df.iloc[-5:]
        
        # Calculate average range
        avg_range = prev_5['High'].max() - prev_5['Low'].min()
        daily_volatility = (latest['ATR'] / latest['Close']) * 100
        
        return {
            'name': name,
            'symbol': symbol,
            'price': latest['Close'],
            'signal': signal_data,
            'daily_volatility': daily_volatility,
            'avg_range': avg_range,
            'timestamp': latest.name,
            'volume': latest['Volume'],
            'high_24h': df['High'].max(),
            'low_24h': df['Low'].min()
        }
        
    except Exception as e:
        print(f"Error analyzing {name}: {e}")
        return None

def get_all_low_volatility_pairs():
    """Analyze all low volatility pairs"""
    results = []
    
    for symbol, name in LOW_VOLATILITY_PAIRS.items():
        print(f"Analyzing {name}...")
        analysis = analyze_low_volatility_pair(symbol, name)
        if analysis:
            results.append(analysis)
        time.sleep(0.5)  # Rate limiting
    
    # Sort by confidence and signal strength
    results.sort(key=lambda x: (
        x['signal']['confidence'] if x['signal']['signal'] != 'NO SIGNAL' else 0
    ), reverse=True)
    
    return results

def format_low_volatility_message(results):
    """Format message for low volatility pairs"""
    now = datetime.now()
    
    lines = [
        "📊" * 40,
        "<b>🎯 LOW VOLATILITY PAIRS SIGNALS</b>",
        f"⏰ {now.strftime('%Y-%m-%d %H:%M:%S')} UTC",
        f"📈 Timeframe: {TIMEFRAME} candles",
        f"⏱️ Expected Hold: {HOLD_TIME_HOURS} hours",
        f"📉 Volatility Filter: Low volatility only",
        "📊" * 40,
        ""
    ]
    
    # Separate signals
    active_signals = [r for r in results if r['signal']['signal'] != 'NO SIGNAL' and r['signal']['confidence'] >= MIN_CONFIDENCE]
    monitoring = [r for r in results if r['signal']['signal'] == 'NO SIGNAL' or r['signal']['confidence'] < MIN_CONFIDENCE]
    
    if active_signals:
        lines.append("🎯 <b>TRADE SIGNALS</b>")
        lines.append("-" * 35)
        
        for r in active_signals:
            s = r['signal']
            
            lines.append(f"\n{s['signal_emoji']} <b>{r['name']}</b>")
            lines.append(f"   💰 Price: {r['price']:.5f}")
            lines.append(f"   🎯 Signal: <b>{s['signal']}</b> (Confidence: {s['confidence']}%)")
            lines.append(f"   📊 RSI: {s['rsi']:.1f}")
            lines.append(f"   📈 Trend: {s['trend']} | Range Status: {s['range_status']}")
            lines.append(f"   📉 ADX: {s['adx']:.1f} ({'Ranging' if s['adx'] < 25 else 'Trending'})")
            lines.append(f"   📊 Bollinger Position: {s['bb_position']*100:.0f}%")
            lines.append(f"   📈 Daily Volatility: {r['daily_volatility']:.2f}%")
            
            lines.append(f"\n   <b>🎯 TRADE PLAN (1-2 Hour Hold):</b>")
            lines.append(f"   🚀 Entry: {s['entry']:.5f}")
            lines.append(f"   🛑 Stop Loss: {s['stop_loss']:.5f} ({s['risk_pips']:.1f} pips)")
            lines.append(f"   🎯 Take Profit: {s['take_profit']:.5f} ({s['reward_pips']:.1f} pips)")
            lines.append(f"   📊 Risk/Reward: 1:{s['risk_reward']:.1f}")
            
            # Position sizing suggestion
            position_size = RISK_PER_TRADE / s['risk_pips'] if s['risk_pips'] > 0 else 0
            lines.append(f"   💰 Suggested Size: {position_size:.2f} units per ${RISK_PER_TRADE} risk")
            
            # Market context
            lines.append(f"\n   📊 <b>Market Context:</b>")
            lines.append(f"   • 24h Range: {r['low_24h']:.5f} - {r['high_24h']:.5f}")
            lines.append(f"   • Avg Range: {r['avg_range']:.5f}")
            lines.append(f"   • Volume: {r['volume']:.0f}")
            
            lines.append("")
    
    if monitoring:
        lines.append("\n📈 <b>MARKETS MONITORING</b>")
        lines.append("-" * 35)
        
        for r in monitoring[:5]:  # Show top 5 monitoring pairs
            s = r['signal']
            status = "🔍 Monitoring"
            if s['adx'] < 25:
                status = "📊 Ranging - Good for mean reversion"
            else:
                status = "📈 Trending - Wait for pullback"
            
            lines.append(f"\n⏸️ <b>{r['name']}</b>")
            lines.append(f"   Price: {r['price']:.5f} | RSI: {s['rsi']:.1f}")
            lines.append(f"   ADX: {s['adx']:.1f} | Volatility: {r['daily_volatility']:.2f}%")
            lines.append(f"   Status: {status}")
    
    # Trading strategy reminder
    lines.append("\n" + "📊" * 40)
    lines.append("<b>📝 LOW VOLATILITY TRADING STRATEGY:</b>")
    lines.append("• Enter at support/resistance levels")
    lines.append("• Target 1-2 hour holds")
    lines.append("• Use tighter stops (1.2x ATR)")
    lines.append("• Focus on mean reversion")
    lines.append("• Avoid major news events")
    lines.append("📊" * 40)
    lines.append("⚠️ <i>Educational purposes only - Low risk strategy</i>")
    lines.append(f"🔄 Next update in {HOLD_TIME_HOURS} hours")
    
    return "\n".join(lines)

def get_next_update_time():
    """Calculate next update time (1-2 hours)"""
    now = datetime.now()
    
    # Add random minutes between 60-120 minutes
    update_minutes = 60 + (now.minute % 60)  # Varies between 60-120 minutes
    next_update = now + timedelta(minutes=update_minutes)
    
    return next_update

def main():
    """Main bot loop for low volatility pairs"""
    print("=" * 60)
    print("🎯 LOW VOLATILITY PAIRS BOT STARTED")
    print(f"📊 Analyzing {len(LOW_VOLATILITY_PAIRS)} stable pairs")
    print(f"📈 Timeframe: {TIMEFRAME}")
    print(f"⏱️ Expected Hold Time: {HOLD_TIME_HOURS} hours")
    print(f"🎯 Min Confidence: {MIN_CONFIDENCE}%")
    print("=" * 60)
    print("\n📋 Low Volatility Pairs Included:")
    for name in list(LOW_VOLATILITY_PAIRS.values())[:10]:
        print(f"   • {name}")
    print(f"   ... and {len(LOW_VOLATILITY_PAIRS) - 10} more")
    print("=" * 60)
    
    # Send startup message
    startup_msg = (
        "🎯 <b>Low Volatility Pairs Bot Online</b>\n\n"
        f"📊 Monitoring {len(LOW_VOLATILITY_PAIRS)} stable pairs\n"
        f"📈 Timeframe: {TIMEFRAME} candles\n"
        f"⏱️ Expected Hold: {HOLD_TIME_HOURS} hours\n"
        f"📉 Strategy: Mean reversion, support/resistance\n"
        f"🎯 Min Confidence: {MIN_CONFIDENCE}%\n"
        f"💰 Risk per trade: {RISK_PER_TRADE}%\n\n"
        f"✅ Bot is active - First analysis incoming..."
    )
    send_telegram_message(startup_msg)
    
    # Main loop
    while True:
        try:
            print(f"\n[{datetime.now()}] Analyzing low volatility pairs...")
            
            # Analyze all pairs
            results = get_all_low_volatility_pairs()
            
            if results:
                message = format_low_volatility_message(results)
                send_telegram_message(message)
                
                active_signals = len([r for r in results if r['signal']['signal'] != 'NO SIGNAL'])
                print(f"✓ Analysis complete - {active_signals} trade signals found")
                print(f"  Total pairs analyzed: {len(results)}")
            else:
                print("✗ No data received")
                send_telegram_message("⚠️ Bot error: Could not fetch market data.")
            
            # Calculate next update (1-2 hours)
            next_update = get_next_update_time()
            wait_seconds = (next_update - datetime.now()).total_seconds()
            
            if wait_seconds < 60:
                wait_seconds = 3600  # Default to 1 hour
            
            print(f"\n📅 Next update: {next_update.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"⏳ Waiting {wait_seconds/60:.0f} minutes...")
            print("=" * 60)
            
            time.sleep(wait_seconds)
            
        except KeyboardInterrupt:
            print("\n🛑 Bot stopped by user")
            send_telegram_message("🛑 Low volatility bot stopped")
            break
        except Exception as e:
            print(f"Error in main loop: {e}")
            send_telegram_message(f"⚠️ Bot error: {str(e)[:100]}")
            time.sleep(300)  # Wait 5 minutes on error

if __name__ == "__main__":
    main()