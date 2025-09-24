# src/utils.py
import pandas as pd
import numpy as np

def ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False).mean()

def macd(series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    fast_ema = ema(series, fast)
    slow_ema = ema(series, slow)
    macd_line = fast_ema - slow_ema
    macd_signal = ema(macd_line, signal)
    macd_hist = macd_line - macd_signal
    return macd_line, macd_signal, macd_hist

def atr(df: pd.DataFrame, length: int = 14) -> pd.Series:
    # expects df with high, low, close
    high, low, close = df['high'], df['low'], df['close']
    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.rolling(length, min_periods=1).mean()

def vwap(df: pd.DataFrame) -> pd.Series:
    # intrabar cumulative VWAP approximate per dataframe (resets not implemented)
    # For per-bar VWAP use typical price * volume / cumulative volume over session — here we implement per-row VWAP over entire df which is acceptable for signal filters
    tp = (df['high'] + df['low'] + df['close']) / 3
    cum_vp = (tp * df['volume']).cumsum()
    cum_vol = df['volume'].cumsum()
    return (cum_vp / cum_vol).fillna(method='ffill')

def in_ny_session_index(index: pd.DatetimeIndex, start="08:30", end="16:00", tz="America/New_York"):
    # Returns boolean mask for NY session on a timezone-aware index
    # If index naive, assume UTC then convert
    if index.tz is None:
        idx = index.tz_localize('UTC').tz_convert(tz)
    else:
        idx = index.tz_convert(tz)
    times = idx.time
    start_t = pd.to_datetime(start).time()
    end_t = pd.to_datetime(end).time()
    mask = [(t >= start_t) and (t <= end_t) for t in times]
    return np.array(mask)
