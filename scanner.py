import requests
import pandas as pd
from datetime import datetime
import plotly.graph_objects as go
import plotly.io as pio
from config import BINANCE_BASE_URL, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, INTERVAL, LOOKBACK

signal_history = []

def get_futures_usdt_symbols():
    try:
        res = requests.get(f"{BINANCE_BASE_URL}/fapi/v1/exchangeInfo").json()
        symbols = [s['symbol'] for s in res['symbols'] if s['contractType'] == "PERPETUAL" and s['quoteAsset'] == "USDT"]
        return symbols
    except Exception as e:
        print("Error fetching symbols:", e)
        return []

def get_klines(symbol, interval="15m", limit=100):
    try:
        url = f"{BINANCE_BASE_URL}/fapi/v1/klines?symbol={symbol}&interval={interval}&limit={limit}"
        data = requests.get(url).json()
        df = pd.DataFrame(data, columns=[
            'timestamp', 'open', 'high', 'low', 'close', 'volume',
            'close_time', 'quote_asset_volume', 'trades',
            'taker_base_vol', 'taker_quote_vol', 'ignore'
        ])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        for col in ['open', 'high', 'low', 'close', 'volume']:
            df[col] = df[col].astype(float)
        return df
    except Exception as e:
        print(f"Error fetching kline for {symbol}: {e}")
        return None

def calculate_indicators(df):
    df['MA7'] = df['close'].rolling(window=7).mean()
    df['MA25'] = df['close'].rolling(window=25).mean()
    df['MA99'] = df['close'].rolling(window=99).mean()

    # RSI
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))

    # MACD
    ema12 = df['close'].ewm(span=12, adjust=False).mean()
    ema26 = df['close'].ewm(span=26, adjust=False).mean()
    df['MACD'] = ema12 - ema26
    df['MACD_signal'] = df['MACD'].ewm(span=9, adjust=False).mean()

    # Volume
    df['vol_change'] = df['volume'].pct_change()

    return df

def detect_buy_signal(df):
    if len(df) < 100:
        return False

    latest = df.iloc[-1]
    prev = df.iloc[-2]

    # Conditions
    cond1 = prev['MA7'] < prev['MA25'] and latest['MA7'] > latest['MA25']  # MA7 cross MA25
    cond2 = latest['MA25'] > prev['MA25']  # MA25 rising
    cond3 = latest['RSI'] > 50 or (prev['MACD'] < prev['MACD_signal'] and latest['MACD'] > latest['MACD_signal'])  # RSI or MACD
    cond4 = latest['vol_change'] > 0  # Volume rising

    return all([cond1, cond2, cond3, cond4])

def send_telegram_alert(symbol, price):
    try:
        target1 = round(price * 1.025, 6)
        target2 = round(price * 1.05, 6)
        target3 = round(price * 1.075, 6)
        stop_loss = round(price * 0.95, 6)

        message = (
            f"🔥Binance MA Scanner BUY signal on *{symbol}*\n\n"
            f"Entry Price: {price}\n\n"
            f"🌟 Target 1: {target1} (+2.5%)\n"
            f"🌟 Target 2: {target2} (+5%)\n"
            f"🌟 Target 3: {target3} (+7.5%)\n\n"
            f"🔚 Stop Loss: {stop_loss} (−5%)"
        )

        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        data = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "Markdown"
        }
        requests.post(url, data=data)
    except Exception as e:
        print("Telegram error:", e)

def generate_plotly_chart(df, symbol):
    fig = go.Figure()

    fig.add_trace(go.Candlestick(
        x=df['timestamp'],
        open=df['open'],
        high=df['high'],
        low=df['low'],
        close=df['close'],
        name='Price'
    ))

    fig.add_trace(go.Scatter(x=df['timestamp'], y=df['MA7'], mode='lines', name='MA7', line=dict(color='blue')))
    fig.add_trace(go.Scatter(x=df['timestamp'], y=df['MA25'], mode='lines', name='MA25', line=dict(color='orange')))
    fig.add_trace(go.Scatter(x=df['timestamp'], y=df['MA99'], mode='lines', name='MA99', line=dict(color='green')))

    fig.update_layout(
        title=f"{symbol} MA + RSI + MACD",
        height=350,
        template='plotly_dark',
        margin=dict(l=20, r=20, t=30, b=20)
    )
    return pio.to_html(fig, full_html=False)

def run_scanner():
    symbols = get_futures_usdt_symbols()
    results = []

    for symbol in symbols:
        df = get_klines(symbol, interval="15m", limit=100)
        if df is None or df.empty:
            continue

        df = calculate_indicators(df)
        signal = "HOLD"
        if detect_buy_signal(df):
            signal = "BUY"
            price = df.iloc[-1]['close']
            send_telegram_alert(symbol, price)

        results.append({
            'symbol': symbol,
            'signal': signal,
            'chart': generate_plotly_chart(df, symbol)
        })

        signal_history.append({'time': datetime.utcnow(), 'symbol': symbol, 'signal': signal})

    return results

def get_signal_history(limit=100):
    return signal_history[-limit:]
