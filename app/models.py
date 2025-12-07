# app/models.py
from sqlalchemy import Column, Integer, String, Float, DateTime, UniqueConstraint
from .db import Base


class Ohlcv(Base):
    __tablename__ = "ohlcv"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String, index=True)
    timeframe = Column(String, index=True)  # e.g. "1d", "1h"
    timestamp = Column(DateTime, index=True)

    open = Column(Float)
    high = Column(Float)
    low = Column(Float)
    close = Column(Float)
    volume = Column(Float)

    __table_args__ = (
        UniqueConstraint("symbol", "timeframe", "timestamp", name="uix_symbol_tf_ts"),
    )
