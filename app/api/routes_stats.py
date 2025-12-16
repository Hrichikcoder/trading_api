from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from ..db import get_db
from .. import services
import math

router = APIRouter(prefix="/stats", tags=["Stats"])

# --- 1. STATIC ROUTES (MUST BE FIRST) ---

@router.get("/supported_indicators")
def get_supported_indicators():
    return {
        "trend": ["sma_period", "ema_period", "macd_fast_slow_signal"],
        "momentum": ["rsi_period", "stoch_k_d_smooth"],
        "volatility": ["bb_period_std", "atr_period"],
        "volume": ["obv"]
    }

@router.get("/strategy/backtest")
def run_backtest(
    symbol: str, 
    short_period: int = 12, 
    long_period: int = 26, 
    db: Session = Depends(get_db)
):
    # 1. Fetch Data
    df = services.get_or_fetch_data(symbol, "1d", db)
    if df is None:
        raise HTTPException(status_code=404, detail="Data not found")

    # 2. Calculate Indicators
    df.ta.ema(length=short_period, append=True)
    df.ta.ema(length=long_period, append=True)
    
    short_col = f"EMA_{short_period}"
    long_col = f"EMA_{long_period}"

    trades = []
    position = None
    entry_price = 0
    entry_date = None

    # 3. Run Strategy Logic
    for i in range(1, len(df)):
        current_short = df[short_col].iloc[i]
        current_long = df[long_col].iloc[i]
        prev_short = df[short_col].iloc[i-1]
        prev_long = df[long_col].iloc[i-1]
        
        price = df['close'].iloc[i]
        timestamp = df.index[i]

        # Golden Cross (BUY)
        if prev_short < prev_long and current_short > current_long and position is None:
            position = 'LONG'
            entry_price = price
            entry_date = timestamp

        # Death Cross (SELL)
        elif prev_short > prev_long and current_short < current_long and position == 'LONG':
            position = None
            exit_price = price
            pnl = ((exit_price - entry_price) / entry_price) * 100
            
            trades.append({
                "entry_date": str(entry_date).split()[0],
                "exit_date": str(timestamp).split()[0],
                "entry_price": round(entry_price, 2),
                "exit_price": round(exit_price, 2),
                "pnl_percent": round(pnl, 2)
            })

    # 4. Calculate Stats
    total_trades = len(trades)
    wins = len([t for t in trades if t['pnl_percent'] > 0])
    win_rate = (wins / total_trades * 100) if total_trades > 0 else 0
    net_return = sum([t['pnl_percent'] for t in trades])

    return {
        "symbol": symbol,
        "strategy": "ema_crossover",
        "net_return_percent": round(net_return, 2),
        "win_rate": round(win_rate, 2),
        "total_trades": total_trades,
        "trades": trades
    }

# --- 2. DYNAMIC ROUTES (MUST BE LAST) ---
# This catches everything else, so it must be at the bottom.

@router.get("/{symbol}/{indicator}")
def get_indicator_stats(
    symbol: str, 
    indicator: str, 
    tf: str = Query("1d", description="Timeframe"),
    db: Session = Depends(get_db)
):
    # 1. Fetch Data
    df = services.get_or_fetch_data(symbol, tf, db)
    if df is None:
        raise HTTPException(status_code=404, detail="Data not found")

    # 2. Calculate Indicator
    series, params = services.calculate_indicator(df, indicator.lower())
    if series is None:
        raise HTTPException(status_code=400, detail="Calculation failed")

    # 3. Format Values
    values = [v if not math.isnan(v) else None for v in series.tolist()]
    timestamps = df.index.astype(str).tolist()

    # 4. Generate Signals
    signals = []
    base_name = indicator.split('_')[0]
    
    for v in values:
        sig = "NEUTRAL"
        if v is not None:
            if base_name == "rsi":
                if v > 70: sig = "SELL"
                elif v < 30: sig = "BUY"
        signals.append(sig)

    return {
        "symbol": symbol,
        "indicator": indicator,
        "parameters": params,
        "values": values,
        "buy_sell_signals": signals,
        "timestamps": timestamps
    }