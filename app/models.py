from sqlalchemy import Column, Integer, String, Float, DateTime
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from .database import Base

# --- DATABASE TABLE ---
class StockData(Base):
    __tablename__ = "stock_data"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String, index=True)
    timestamp = Column(DateTime, index=True)
    open = Column(Float)
    high = Column(Float)
    low = Column(Float)
    close = Column(Float)
    volume = Column(Float)

# --- PYDANTIC SCHEMAS ---
class StockResponse(BaseModel):
    symbol: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    
    sma_20: Optional[float] = None
    sma_50: Optional[float] = None

    class Config:
        from_attributes = True