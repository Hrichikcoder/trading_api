# 📈 AlgoTrading API & Quantitative Analytics Dashboard

## 🚀 Project Mission
This project establishes a robust, high-performance RESTful API service tailored for **quantitative financial analysis** and **algorithmic trading simulation**.

Unlike simple data fetchers, this system acts as a **full-stack financial engine** that:
* **Ingests** raw market data from Yahoo Finance.
* **Cleans & Normalizes** time-series data for consistency.
* **Computes** complex technical indicators in real-time.
* **Backtests** trading strategies (EMA Crossover) against historical data.
* **Visualizes** performance in a Bloomberg-style interactive dashboard.
* **Generates** professional PDF reports for strategy evaluation.

**Backend:** FastAPI (Python)  
**Frontend:** Vanilla JS + Bootstrap 5 (Dark/Light Mode)

---

## 🏗️ Technical Architecture

### 1. Backend Engine: FastAPI
* **Asynchronous Execution:** Utilizes `async`/`await` for non-blocking external API calls to Yahoo Finance.
* **Auto-Documentation:** Generates interactive Swagger UI documentation via Pydantic schemas.
* **Type Safety:** Enforces strict data validation across all endpoints.

### 2. Data Processing: Pandas & Pandas-TA
* **Vectorized Operations:** Leverages `pandas` for high-speed time-series manipulation.
* **Technical Analysis:** Integrates `pandas-ta` to compute indicators (RSI, MACD, Bollinger Bands) over thousands of data points in milliseconds.
* **Dynamic Resolution:** Implements custom logic to handle variable column names from calculation libraries, preventing runtime errors.

### 3. Persistence Layer: SQLite & SQLAlchemy
Implements a **"Fetch-First, Store-Later"** caching strategy:
1.  **Check Local DB:** Queries internal `ohlcv.db` first to minimize latency.
2.  **Fetch External:** If missing, pulls fresh data from Yahoo Finance.
3.  **Normalize & Store:** cleans data (timezone removal, column standardization) and commits to SQLite.

### 4. Frontend Dashboard
* **Zero-Dependency:** Built with pure Vanilla JavaScript to demonstrate core DOM manipulation concepts.
* **Responsive UI:** Uses Bootstrap 5 grid system with a custom CSS variable engine for **Dark/Light Mode**.
* **Print Engine:** Integrated CSS `@media print` queries to unroll scrollable data tables and generate clean, high-resolution PDF reports directly from the browser.

---

## ⚡ Key Features

### 📡 Automated Data Ingestion
* **Source:** Yahoo Finance (`yfinance`).
* **Normalization Pipeline:**
    * Renames columns to standard lowercase (`open`, `high`, `low`, `close`, `volume`).
    * Strips timezone offsets for database compatibility.
    * Handles `NaN` values to ensure calculation stability.

### 📊 Dynamic Indicator Engine
Supports on-the-fly calculation of:
* **Trend:** SMA, EMA, MACD.
* **Momentum:** RSI, Stochastic Oscillator.
* **Volatility:** Bollinger Bands, ATR.
* **Volume:** On-Balance Volume (OBV).

### 🧪 Strategy Backtester (EMA Crossover)
A logic engine that simulates trading over historical data:
* **Signal Detection:** Identifies "Golden Cross" and "Death Cross" events.
* **Trade Logging:** Records entry/exit prices, dates, and PnL for every trade.
* **Metrics:** Calculates **Net Return (%)**, **Win Rate**, **Profit Factor**, and **Total Trades**.

### 🖥️ Interactive Dashboard
* **Live Signal Checker:** Query any global ticker (Stocks, Crypto, Forex) for real-time signals.
* **Trade Log:** Scrollable, detailed history of all backtested trades.
* **PDF Export:** One-click generation of strategy performance reports.

---

## 🛠️ Engineering Challenges & Solutions

### Challenge 1: Dynamic Column Names
**The Problem:** The `pandas-ta` library dynamically names output columns based on parameters (e.g., `ATRr_14` vs `ATR_14`), causing `KeyError` crashes when parameters changed.
**The Solution:** Implemented a dynamic resolution logic that detects newly added columns regardless of their name.

```python
# Logic Snippet from services.py
initial_cols = len(df.columns)
# ... perform calculation ...
if len(df.columns) > initial_cols:
    target_col = df.columns[-1] # Dynamically grab the new column