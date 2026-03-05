"""
portfolio_shared.py
===================
Shared utilities imported by both portfolio_returns_engine.py (main app)
and pages/06_Strategy_Backtest.py.

This module contains NO top-level Streamlit calls so it is safe to import
from any Streamlit page without triggering set_page_config or data loading
side-effects.
"""

import streamlit as st
import pandas as pd
import numpy as np
import gdown
from pathlib import Path
from scipy import stats as sp_stats
import warnings

warnings.filterwarnings("ignore")

# ─────────────────────────────────────────────────────────────────────────────
# Data constants
# ─────────────────────────────────────────────────────────────────────────────

DATA_PATH = Path("/tmp/price_data.parquet")
FILE_ID = "1pMQ817V05j4RK0vqJcVkBMmOBK5zRrug"
GDRIVE_URL = f"https://drive.google.com/uc?id={FILE_ID}"

# Include PRICEBID and PRICEASK so the optimizer engine can use actual
# bid/ask execution prices rather than falling back to PRICECLOSE.
_REQUIRED_COLS = [
    "TRADINGITEMID", "TICKERSYMBOL", "PRICEDATE",
    "PRICECLOSE", "PRICEMID", "PRICEBID", "PRICEASK",
    "TRADINGITEMSTATUSID",
]


# ─────────────────────────────────────────────────────────────────────────────
# Data loading
# ─────────────────────────────────────────────────────────────────────────────

@st.cache_data(show_spinner=True)
def ensure_data():
    """Download price data from Google Drive if not already cached on disk."""
    if not DATA_PATH.exists():
        out = gdown.download(GDRIVE_URL, str(DATA_PATH), quiet=False, fuzzy=True)
        if out is None or not DATA_PATH.exists():
            st.error("Google Drive download failed (permissions/quota/bad link).")
            st.stop()


def prepare_price_data(df: pd.DataFrame, price_field: str = "PRICECLOSE") -> pd.DataFrame:
    """
    Clean raw price data for use by all engine functions.

    Filters to active trading items only (status 1 = active, 15 = suspended-but-valid).
    Status 15 is kept because suspended instruments may still have valid historical
    prices needed for backtesting. All other statuses (delisted, errored, etc.) are
    excluded to avoid stale or unreliable price data.

    The sort by (ticker, date) is critical: get_ticker_prices relies on iloc[0] and
    iloc[-1] to find the first/last price in a date range, which only works correctly
    on sorted data. This function runs once at app startup via @st.cache_data.
    """
    df = df.copy()
    df["PRICEDATE"] = pd.to_datetime(df["PRICEDATE"], errors="coerce")
    df = df.dropna(subset=["PRICEDATE"])
    if "TRADINGITEMSTATUSID" in df.columns:
        df = df[df["TRADINGITEMSTATUSID"].isin([1, 15])].copy()
    if price_field not in df.columns:
        raise ValueError(f"Price field '{price_field}' not found in dataset.")
    df[price_field] = pd.to_numeric(df[price_field], errors="coerce")
    df = df.dropna(subset=[price_field])
    df["TICKERSYMBOL"] = df["TICKERSYMBOL"].astype(str).str.strip().str.upper()
    df = df.sort_values(["TICKERSYMBOL", "PRICEDATE"]).reset_index(drop=True)
    return df


@st.cache_data(show_spinner=True)
def load_data():
    ensure_data()
    if not DATA_PATH.exists():
        st.error(f"Dataset not found: {DATA_PATH}")
        st.stop()
    # Sanity check: a valid parquet file should be >10MB. Smaller means
    # the download was likely interrupted or the file is corrupt.
    if DATA_PATH.stat().st_size < 10 * 1024 * 1024:
        st.error("Downloaded file looks too small (likely corrupt). Reboot app to retry.")
        st.stop()
    try:
        df = pd.read_parquet(DATA_PATH, columns=_REQUIRED_COLS)
    except Exception:
        # PRICEBID/PRICEASK may not exist in this dataset version — fall back without them
        fallback_cols = [c for c in _REQUIRED_COLS if c not in ("PRICEBID", "PRICEASK")]
        try:
            df = pd.read_parquet(DATA_PATH, columns=fallback_cols)
        except Exception as e:
            st.error(f"Failed to read parquet: {e}")
            st.stop()
    df = prepare_price_data(df, price_field="PRICECLOSE")
    return df


# ─────────────────────────────────────────────────────────────────────────────
# Performance metrics
# ─────────────────────────────────────────────────────────────────────────────

def compute_strategy_metrics(daily_values, initial_capital, benchmark_values=None):
    """
    Compute performance metrics from a daily portfolio value series.

    V4 extends the original {total_return, cagr, vol, sharpe, max_dd} with:
    - Skewness: negative skew = fatter left tail = more downside risk
    - Kurtosis (excess/Fisher): >0 means heavier tails than normal distribution
    - Avg Drawdown: mean of all daily drawdowns (not just max)
    - Tracking Error: annualized std of active returns vs benchmark
    - Information Ratio: annualized active return / tracking error

    All annualization uses 252 trading days. Sharpe uses Rf=0 (simplification
    appropriate for relative strategy comparison).
    """
    n = len(daily_values)
    if n < 2:
        return {
            "total_return": 0.0, "cagr": 0.0, "annualized_vol": 0.0,
            "sharpe": 0.0, "max_drawdown": 0.0,
            "skewness": 0.0, "kurtosis": 0.0, "avg_drawdown": 0.0,
            "tracking_error": 0.0, "information_ratio": 0.0,
        }
    final = daily_values[-1]
    total_return = final / initial_capital - 1

    years = n / 252.0
    if years > 0 and final > 0 and initial_capital > 0:
        cagr = (final / initial_capital) ** (1 / years) - 1
    else:
        cagr = 0.0

    daily_rets = np.diff(daily_values) / daily_values[:-1]
    ann_vol = np.std(daily_rets, ddof=1) * np.sqrt(252) if len(daily_rets) > 1 else 0.0
    sharpe = (cagr / ann_vol) if ann_vol > 0 else 0.0

    running_max = np.maximum.accumulate(daily_values)
    drawdowns = (daily_values - running_max) / running_max
    max_dd = float(np.min(drawdowns))

    skewness = float(sp_stats.skew(daily_rets)) if len(daily_rets) > 2 else 0.0
    kurtosis = float(sp_stats.kurtosis(daily_rets, fisher=True)) if len(daily_rets) > 3 else 0.0
    avg_drawdown = float(np.mean(drawdowns))

    tracking_error = 0.0
    information_ratio = 0.0
    if benchmark_values is not None and len(benchmark_values) == n:
        bm_rets = np.diff(benchmark_values) / benchmark_values[:-1]
        active_rets = daily_rets - bm_rets
        tracking_error = float(np.std(active_rets, ddof=1) * np.sqrt(252)) if len(active_rets) > 1 else 0.0
        if tracking_error > 1e-12:
            ann_active_mean = float(np.mean(active_rets) * 252)
            information_ratio = ann_active_mean / tracking_error

    return {
        "total_return": round(total_return, 6),
        "cagr": round(cagr, 6),
        "annualized_vol": round(ann_vol, 6),
        "sharpe": round(sharpe, 4),
        "max_drawdown": round(max_dd, 6),
        "skewness": round(skewness, 4),
        "kurtosis": round(kurtosis, 4),
        "avg_drawdown": round(avg_drawdown, 6),
        "tracking_error": round(tracking_error, 6),
        "information_ratio": round(information_ratio, 4),
    }
