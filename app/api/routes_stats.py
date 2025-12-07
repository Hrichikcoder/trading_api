from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from ..db import get_db
from ..services import fetch_ohlcv, calculate_indicator
import pandas as pd

router = APIRouter(prefix="/stats", tags=["stats"])

@router.get("/supported_indicators")
def get_supported_indicators():
    return {
        "supported_indicators": ["ema", "sma", "rsi", "macd", "bb", "stoch", "atr", "obv"],
        "usage_examples": [
            "/stats/BTC-USD/rsi?period=14",
            "/stats/AAPL/bb", 
            "/stats/EURUSD=X/ema?period=50"
        ]
    }

@router.get("/strategy/backtest")
def backtest_strategy(
    symbol: str = "BTC-USD", 
    short_period: int = 12, 
    long_period: int = 26, 
    tf: str = "1d",
    db: Session = Depends(get_db)
):
    print(f"Backtesting {symbol} on {tf}...")
    
    symbol = symbol.upper()
    
    df = fetch_ohlcv(symbol, tf, db)
    if df is None:
        raise HTTPException(status_code=404, detail=f"Data not found for {symbol}")

    df.ta.ema(length=short_period, append=True)
    df.ta.ema(length=long_period, append=True)
    
    short_col = f"EMA_{short_period}"
    long_col = f"EMA_{long_period}"
    
    if short_col not in df.columns or long_col not in df.columns:
         raise HTTPException(status_code=500, detail="Indicator calculation failed.")

    trades = []
    position = None 
    entry_price = 0
    entry_date = None
    
    for i in range(long_period, len(df)):
        s = df[short_col].iloc[i]
        l = df[long_col].iloc[i]
        prev_s = df[short_col].iloc[i-1]
        prev_l = df[long_col].iloc[i-1]
        price = df['close'].iloc[i]
        date = df.index[i]

        if prev_s < prev_l and s > l and position is None:
            position = 'LONG'
            entry_price = price
            entry_date = date
            
        elif prev_s > prev_l and s < l and position == 'LONG':
            pnl_percent = ((price - entry_price) / entry_price) * 100
            trades.append({
                "entry_date": str(entry_date).split(" ")[0], 
                "exit_date": str(date).split(" ")[0],
                "entry_price": round(entry_price, 2),
                "exit_price": round(price, 2),
                "pnl_percent": round(pnl_percent, 2)
            })
            position = None 

    return {
        "symbol": symbol,
        "strategy": "ema_crossover",
        "net_return_percent": round(sum(t['pnl_percent'] for t in trades), 2),
        "total_trades": len(trades),
        "trades": trades 
    }

@router.get("/{symbol}/{indicator}")
def get_stats(
    symbol: str, 
    indicator: str, 
    tf: str = Query("1d"), 
    period: int = Query(14),
    db: Session = Depends(get_db)
):
    symbol = symbol.upper()
    
    df = fetch_ohlcv(symbol, tf, db)
    if df is None or df.empty:
        raise HTTPException(status_code=404, detail=f"No data found for {symbol}")

    algo = indicator.split("_")[0]
    processed_df, col_name = calculate_indicator(df, algo, period=period)
    
    if processed_df is None:
        raise HTTPException(status_code=400, detail=f"Calculation failed for {indicator}")

    raw_values = processed_df[col_name].fillna(0).tolist()
    
    if algo == "obv":
        clean_values = [int(v) for v in raw_values]
    else:
        clean_values = [round(float(v), 2) for v in raw_values]

    signals = ["NEUTRAL"] * len(clean_values)
    if algo == "rsi":
        signals = ["SELL" if v > 70 else "BUY" if v < 30 else "NEUTRAL" for v in clean_values]
    elif algo == "stoch":
         signals = ["SELL" if v > 80 else "BUY" if v < 20 else "NEUTRAL" for v in clean_values]

    limit = 100
    
    return {
        "symbol": symbol,
        "indicator": indicator,
        "parameters": {"period": period},
        "count": limit,
        "values": clean_values[-limit:], 
        "buy_sell_signals": signals[-limit:],
        "timestamps": [str(t).split(" ")[0] for t in processed_df.index[-limit:]]
    }