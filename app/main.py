import os
from fastapi import FastAPI, Depends, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
import pandas as pd
import yfinance as yf
from typing import List

from .database import Base, engine, get_db
from .models import StockData

Base.metadata.create_all(bind=engine)

app = FastAPI()

# --- FRONTEND ---
@app.get("/")
def read_root():
    if os.path.exists("app/static/index.html"):
        return FileResponse("app/static/index.html")
    return {"message": "No index.html found."}

if os.path.exists("app/static"):
    app.mount("/static", StaticFiles(directory="app/static"), name="static")

# --- DATA FETCHING ---
def fetch_and_store_data(symbol: str, db: Session):
    print(f"Fetching 5 years of data for {symbol}...")
    try:
        df = yf.download(symbol, period="5y", interval="1d", progress=False, auto_adjust=True)
    except: return

    if df.empty: return

    if isinstance(df.columns, pd.MultiIndex):
        try: df.columns = df.columns.get_level_values(0)
        except: pass
    
    df.reset_index(inplace=True)
    
    existing_dates = {d[0] for d in db.query(StockData.timestamp).filter(StockData.symbol == symbol).all()}
    new_rows = []

    for _, row in df.iterrows():
        try:
            date_val = row['Date']
            if isinstance(date_val, pd.Series): date_val = date_val.iloc[0]
            ts = pd.to_datetime(date_val).to_pydatetime()
        except: continue
        
        if ts in existing_dates: continue

        def get_val(col):
            val = row.get(col, 0.0)
            if isinstance(val, pd.Series): return float(val.iloc[0])
            return float(val)

        new_rows.append(StockData(
            symbol=symbol, timestamp=ts,
            open=get_val('Open'), high=get_val('High'),
            low=get_val('Low'), close=get_val('Close'),
            volume=get_val('Volume')
        ))

    if new_rows:
        try:
            db.add_all(new_rows)
            db.commit()
        except: db.rollback()

# --- HELPER: Convert DB to DataFrame ---
def get_data_as_df(symbol, db):
    data = db.query(StockData).filter(StockData.symbol == symbol).order_by(StockData.timestamp).all()
    if not data:
        fetch_and_store_data(symbol, db)
        data = db.query(StockData).filter(StockData.symbol == symbol).order_by(StockData.timestamp).all()
    
    if not data: return pd.DataFrame()

    data_dicts = [{
        "symbol": d.symbol, "timestamp": d.timestamp, "close": d.close
    } for d in data]
    
    df = pd.DataFrame(data_dicts)
    df.sort_values('timestamp', inplace=True)
    return df

# --- DYNAMIC INDICATOR LOGIC ---
def calculate_dynamic(df, indicator_str):
    try:
        parts = indicator_str.split('_')
        name = parts[0]
        params = [float(p) for p in parts[1:]]
    except:
        return {"error": "Invalid format"}

    price = df['close'].iloc[-1]
    result = {"indicator": indicator_str.upper(), "price": price, "value": 0, "signal": "NEUTRAL", "details": ""}

    if name == "sma":
        period = int(params[0]) if params else 20
        sma = df['close'].rolling(window=period).mean()
        val = sma.iloc[-1]
        result["value"] = val
        result["signal"] = "BULLISH" if price > val else "BEARISH"

    elif name == "ema":
        period = int(params[0]) if params else 12
        ema = df['close'].ewm(span=period, adjust=False).mean()
        val = ema.iloc[-1]
        result["value"] = val
        result["signal"] = "BULLISH" if price > val else "BEARISH"

    elif name == "rsi":
        period = int(params[0]) if params else 14
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        val = rsi.iloc[-1]
        result["value"] = val
        if val < 30: result["signal"] = "OVERSOLD (BUY)"
        elif val > 70: result["signal"] = "OVERBOUGHT (SELL)"
        else: result["signal"] = "NEUTRAL"

    elif name == "bb":
        period = int(params[0]) if len(params) > 0 else 20
        std_dev = float(params[1]) if len(params) > 1 else 2.0
        sma = df['close'].rolling(window=period).mean()
        std = df['close'].rolling(window=period).std()
        upper = sma + (std * std_dev)
        lower = sma - (std * std_dev)
        val = sma.iloc[-1] 
        result["value"] = val
        result["details"] = f"Upper: {upper.iloc[-1]:.2f} | Lower: {lower.iloc[-1]:.2f}"
        if price > upper.iloc[-1]: result["signal"] = "OVERBOUGHT"
        elif price < lower.iloc[-1]: result["signal"] = "OVERSOLD"

    elif name == "macd":
        fast = int(params[0]) if len(params) > 0 else 12
        slow = int(params[1]) if len(params) > 1 else 26
        sig  = int(params[2]) if len(params) > 2 else 9
        ema_fast = df['close'].ewm(span=fast, adjust=False).mean()
        ema_slow = df['close'].ewm(span=slow, adjust=False).mean()
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=sig, adjust=False).mean()
        val = macd_line.iloc[-1]
        sig_val = signal_line.iloc[-1]
        result["value"] = val
        result["signal"] = "BULLISH" if val > sig_val else "BEARISH"
        result["details"] = f"Signal Line: {sig_val:.2f}"

    return result

# --- ROUTES ---

@app.get("/stats/strategy/backtest")
def backtest_strategy(symbol: str, db: Session = Depends(get_db)):
    df = get_data_as_df(symbol, db)
    if df.empty: return {"error": "No data"}
    
    df['sma_20'] = df['close'].rolling(window=20).mean()
    df['sma_50'] = df['close'].rolling(window=50).mean()
    
    trades = []
    position = None

    for i in range(len(df)):
        if pd.isna(df['sma_20'].iloc[i]) or pd.isna(df['sma_50'].iloc[i]): continue
        
        date = df['timestamp'].iloc[i]
        price = df['close'].iloc[i]
        sma20 = df['sma_20'].iloc[i]
        sma50 = df['sma_50'].iloc[i]
        
        signal = "BUY" if sma20 > sma50 else "SELL"

        if signal == "BUY" and position is None:
            position = {"date": date, "price": price}
        elif signal == "SELL" and position is not None:
            pnl = ((price - position['price']) / position['price']) * 100
            trades.append({
                "entry_date": position['date'].strftime("%Y-%m-%d"),
                "exit_date": date.strftime("%Y-%m-%d"),
                "entry_price": position['price'],
                "exit_price": price,
                "pnl_percent": round(pnl, 2)
            })
            position = None
            
    if not trades:
         return {"symbol": symbol, "total_count": 0, "net_return": 0, "recent_trades": [], "all_trades": []}

    net_ret = sum(t['pnl_percent'] for t in trades)
    
    # SEND BOTH: Last 5 for dashboard, and ALL for the modal
    return {
        "symbol": symbol, 
        "total_count": len(trades), 
        "net_return": round(net_ret, 2), 
        "recent_trades": trades[-5:], 
        "all_trades": trades 
    }

@app.get("/stats/{symbol}/{indicator_str}")
def get_indicator_data(symbol: str, indicator_str: str, db: Session = Depends(get_db)):
    df = get_data_as_df(symbol, db)
    if df.empty: raise HTTPException(status_code=404, detail="No data")
    return calculate_dynamic(df, indicator_str)