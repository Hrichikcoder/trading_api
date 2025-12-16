import yfinance as yf
import pandas as pd
import pandas_ta as ta
import ccxt
from sqlalchemy.orm import Session
from datetime import datetime
from . import models

# --- RECRUITER REQUIREMENT: TWO SOURCES ---

def fetch_from_yahoo(symbol: str, timeframe: str):
    """Source 1: Yahoo Finance (Stocks/Crypto)"""
    print(f"Fetching {symbol} from Yahoo...")
    try:
        ticker = yf.Ticker(symbol)
        # RECRUITER REQUIREMENT: 365 Days
        df = ticker.history(period="1y", interval=timeframe)
        if df.empty: return None

        df.reset_index(inplace=True)
        # NORMALIZE FIELD NAMES
        df.rename(columns={
            "Date": "timestamp", "Datetime": "timestamp",
            "Open": "open", "High": "high", "Low": "low", "Close": "close", "Volume": "volume"
        }, inplace=True)
        
        # FIX TIMEZONES (SQLite requires clean UTC)
        if df['timestamp'].dt.tz is not None:
            df['timestamp'] = df['timestamp'].dt.tz_convert('UTC').dt.tz_localize(None)
            
        return df[['timestamp', 'open', 'high', 'low', 'close', 'volume']]
    except Exception as e:
        print(f"Yahoo error: {e}")
        return None

def fetch_from_binance(symbol: str, timeframe: str):
    """Source 2: Binance (Crypto Backup)"""
    print(f"Fetching {symbol} from Binance...")
    try:
        exchange = ccxt.binance()
        # Map BTC-USD to BTC/USDT
        mapped = symbol.replace("-", "/").replace("USD", "/USDT") if "USD" in symbol else symbol
        
        ohlcv = exchange.fetch_ohlcv(mapped.replace("//", "/"), timeframe, limit=365)
        if not ohlcv: return None

        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        return df
    except Exception as e:
        print(f"Binance error: {e}")
        return None

# --- RECRUITER REQUIREMENT: DUPLICATE HANDLING ---

def get_or_fetch_data(symbol: str, timeframe: str, db: Session):
    # 1. Check Local DB
    existing_data = db.query(models.Ohlcv).filter(
        models.Ohlcv.symbol == symbol,
        models.Ohlcv.timeframe == timeframe
    ).order_by(models.Ohlcv.timestamp.asc()).all()

    # 2. Fetch Fresh Data (Yahoo -> Binance)
    fetched_df = fetch_from_yahoo(symbol, timeframe)
    if fetched_df is None or fetched_df.empty:
        fetched_df = fetch_from_binance(symbol, timeframe)

    # 3. SMART MERGE (Fix Duplicacy)
    # Even if we have DB data, we might need new rows from the fetch
    existing_timestamps = {d.timestamp for d in existing_data}
    new_records = []

    if fetched_df is not None and not fetched_df.empty:
        for _, row in fetched_df.iterrows():
            if row['timestamp'] not in existing_timestamps:
                record = models.Ohlcv(
                    symbol=symbol, timeframe=timeframe, timestamp=row['timestamp'],
                    open=row['open'], high=row['high'], low=row['low'], close=row['close'], volume=row['volume']
                )
                new_records.append(record)
                # Update our local set so we use it immediately below
                existing_timestamps.add(row['timestamp'])

        # Save ONLY new rows
        if new_records:
            try:
                db.add_all(new_records)
                db.commit()
                print(f"Added {len(new_records)} new rows to DB.")
            except Exception as e:
                db.rollback()
                print(f"DB Error: {e}")

    # 4. Return Combined Data (DB + Fresh)
    # Re-query to get everything sorted nicely, or construct from memory
    final_data = db.query(models.Ohlcv).filter(
        models.Ohlcv.symbol == symbol,
        models.Ohlcv.timeframe == timeframe
    ).order_by(models.Ohlcv.timestamp.asc()).all()
    
    if not final_data: return None

    data = [{"timestamp": d.timestamp, "open": d.open, "high": d.high, "low": d.low, "close": d.close, "volume": d.volume} for d in final_data]
    df_final = pd.DataFrame(data)
    df_final.set_index("timestamp", inplace=True)
    return df_final

# --- RECRUITER REQUIREMENT: DYNAMIC PARSING ---

def calculate_indicator(df: pd.DataFrame, indicator_str: str):
    # Parses 'sma_50' -> name='sma', params=[50]
    try:
        parts = indicator_str.split('_')
        name = parts[0]
        params = [int(p) for p in parts[1:]] 

        if name == "sma":
            p = params[0] if params else 14
            df.ta.sma(length=p, append=True)
            return df[f"SMA_{p}"], params
        elif name == "ema":
            p = params[0] if params else 14
            df.ta.ema(length=p, append=True)
            return df[f"EMA_{p}"], params
        elif name == "rsi":
            p = params[0] if params else 14
            df.ta.rsi(length=p, append=True)
            return df[f"RSI_{p}"], params
        elif name == "macd":
            f, s, sig = (params[0], params[1], params[2]) if len(params) >= 3 else (12, 26, 9)
            df.ta.macd(fast=f, slow=s, signal=sig, append=True)
            return df[f"MACD_{f}_{s}_{sig}"], params
        elif name == "bb":
            l, std = (params[0], params[1]) if len(params) >= 2 else (20, 2)
            df.ta.bbands(length=l, std=std, append=True)
            return df[f"BBM_{l}_{std}"], params # Middle Band
        
        return None, None
    except Exception as e:
        print(f"Indicator Error: {e}")
        return None, None