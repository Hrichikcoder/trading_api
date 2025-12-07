# app/services.py
import yfinance as yf
import pandas as pd
import pandas_ta as ta
from sqlalchemy.orm import Session
from . import models

def fetch_ohlcv(symbol: str, timeframe: str, db: Session):
    existing_data = db.query(models.Ohlcv).filter(
        models.Ohlcv.symbol == symbol,
        models.Ohlcv.timeframe == timeframe
    ).order_by(models.Ohlcv.timestamp.asc()).all()

    if existing_data:
        data = [{"timestamp": d.timestamp, "open": d.open, "high": d.high, "low": d.low, "close": d.close, "volume": d.volume} for d in existing_data]
        df = pd.DataFrame(data)
        df.set_index("timestamp", inplace=True)
        return df

    print(f"Fetching {symbol} from Yahoo...")
    try:
        ticker = yf.Ticker(symbol)
        df = ticker.history(period="2y", interval=timeframe)
    except Exception as e:
        print(f"Yahoo fetch error: {e}")
        return None
    
    if df.empty:
        return None

    df.reset_index(inplace=True)
    df.rename(columns={"Date": "timestamp", "Datetime": "timestamp", "Open": "open", "High": "high", "Low": "low", "Close": "close", "Volume": "volume"}, inplace=True)
    
    if df['timestamp'].dt.tz is not None:
        df['timestamp'] = df['timestamp'].dt.tz_convert(None)

    db_records = []
    for _, row in df.iterrows():
        exists = db.query(models.Ohlcv).filter_by(symbol=symbol, timeframe=timeframe, timestamp=row["timestamp"]).first()
        if not exists:
            db_records.append(models.Ohlcv(symbol=symbol, timeframe=timeframe, timestamp=row["timestamp"], open=row["open"], high=row["high"], low=row["low"], close=row["close"], volume=row["volume"]))
    
    if db_records:
        db.add_all(db_records)
        db.commit()

    df.set_index("timestamp", inplace=True)
    return df

def calculate_indicator(df: pd.DataFrame, indicator_name: str, **kwargs):
    temp_df = df.copy()
    initial_cols = len(temp_df.columns)

    try:
        if indicator_name == "ema":
            temp_df.ta.ema(length=kwargs.get('period', 14), append=True)
        elif indicator_name == "sma":
            temp_df.ta.sma(length=kwargs.get('period', 50), append=True)
        elif indicator_name == "rsi":
            temp_df.ta.rsi(length=kwargs.get('period', 14), append=True)
        elif indicator_name == "macd":
            temp_df.ta.macd(fast=12, slow=26, signal=9, append=True)
        elif indicator_name == "bb":
            temp_df.ta.bbands(length=kwargs.get('period', 20), std=2, append=True)
        elif indicator_name == "stoch":
            temp_df.ta.stoch(k=14, d=3, smooth_k=3, append=True)
        elif indicator_name == "atr":
            temp_df.ta.atr(length=kwargs.get('period', 14), append=True)
        elif indicator_name == "obv":
            temp_df.ta.obv(append=True)
            
    except Exception as e:
        print(f"Calculation Error: {e}")
        return None, None

    if len(temp_df.columns) > initial_cols:
        if indicator_name == "bb":
            col_name = [c for c in temp_df.columns if "BBM" in c or "MB" in c][0]
        elif indicator_name == "macd":
            col_name = [c for c in temp_df.columns if c.startswith("MACD") and not c.startswith("MACDs") and not c.startswith("MACDh")][0]
        elif indicator_name == "stoch":
            col_name = [c for c in temp_df.columns if "STOCHk" in c][0]
        else:
            col_name = temp_df.columns[-1]
            
        return temp_df, col_name
    
    return None, None