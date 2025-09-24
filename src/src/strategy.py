# src/strategy.py
"""
Strategy implementation: signal generation for Buy/Sell & exits.

Functions:
- prepare_indicators(df): compute EMAs, MACD, ATR, VWAP, vol_sma
- generate_signals(df, params): returns DataFrame with 'signal' column:
    1 = LONG entry signal (enter next bar open)
   -1 = SHORT entry signal
    0 = no entry
Also computes conditions used for exits (ema9_break, macd_flip).
"""

import pandas as pd
import numpy as np
from .utils import ema, macd, atr, vwap, in_ny_session_index

def prepare_indicators(df: pd.DataFrame, params: dict):
    df = df.copy()
    # EMAs
    df['ema9'] = ema(df['close'], params.get('ema9', 9))
    df['ema21'] = ema(df['close'], params.get('ema21', 21))
    df['ema60'] = ema(df['close'], params.get('ema60', 60))
    df['ema200'] = ema(df['close'], params.get('ema200', 200))
    # MACD
    df['macd_line'], df['macd_signal'], df['macd_hist'] = macd(df['close'],
                                                              params.get('macd_fast',12),
                                                              params.get('macd_slow',26),
                                                              params.get('macd_sig',9))
    # ATR
    df['atr'] = atr(df, params.get('atr_len', 14))
    # VWAP
    df['vwap'] = vwap(df)
    # Volume SMA
    df['vol_sma'] = df['volume'].rolling(params.get('vol_sma_len', 20), min_periods=1).mean()
    # session mask
    df['in_ny'] = in_ny_session_index(df.index,
                                      start=params.get('session_start', "08:30"),
                                      end=params.get('session_end', "16:00"),
                                      tz=params.get('tz', "America/New_York"))
    return df

def generate_signals(df_in: pd.DataFrame, params: dict = None) -> pd.DataFrame:
    if params is None:
        params = {}
    df = prepare_indicators(df_in, params)

    # HTF: compute 1H MACD / ema200 by resampling (if data is sub-hour)
    htf = params.get('htf', '1H')
    df_htf = df[['close']].resample(htf).last()
    df_htf['ema200_htf'] = df['close'].resample(htf).apply(lambda x: ema(x, params.get('ema200',200))[-1] if len(x)>0 else np.nan)
    # compute htf macd hist via resample and using same macd function
    macd_line_htf, macd_sig_htf, macd_hist_htf = macd(df['close'].resample(htf).last().ffill(),
                                                      params.get('macd_fast',12),
                                                      params.get('macd_slow',26),
                                                      params.get('macd_sig',9))
    df_htf['macd_hist_htf'] = macd_hist_htf
    # forward-fill htf values to original index
    df_htf_ff = df_htf.reindex(df.index, method='ffill')

    df['ema200_htf'] = df_htf_ff['ema200_htf']
    df['macd_hist_htf'] = df_htf_ff['macd_hist_htf']
    # optional ADX omitted for simplicity

    # Setup filters
    # HTF bullish / bearish
    df['htf_bull'] = (df['close'] > df['ema200_htf']) & (df['macd_hist_htf'] > 0)
    df['htf_bear'] = (df['close'] < df['ema200_htf']) & (df['macd_hist_htf'] < 0)

    # LTF stack
    df['ema_long_stack'] = (df['ema9'] > df['ema21']) & (df['ema21'] > df['ema60'])
    df['ema_short_stack'] = (df['ema9'] < df['ema21']) & (df['ema21'] < df['ema60'])

    # volume & vwap & macd rising/falling
    df['vol_ok'] = df['volume'] > df['vol_sma'] * params.get('vol_mult', 1.5)
    df['vwap_long'] = df['close'] > df['vwap']
    df['vwap_short'] = df['close'] < df['vwap']
    df['macd_rising'] = df['macd_hist'] > df['macd_hist'].shift(1)
    df['macd_falling'] = df['macd_hist'] < df['macd_hist'].shift(1)

    # Pullback: price inside EMA9-EMA21 band or close to EMA21 (within 1.5 ATR)
    df['pullback_to_ema'] = ((df['close'] <= df['ema9']) & (df['close'] >= df['ema21'])) | \
                            ( (df['close'] - df['ema21']).abs() <= 1.5 * df['atr'] )

    # Final entry signals
    df['long_setup'] = df['in_ny'] & df['htf_bull'] & df['ema_long_stack'] & df['vwap_long'] & df['vol_ok'] & df['macd_rising'] & df['pullback_to_ema']
    df['short_setup'] = df['in_ny'] & df['htf_bear'] & df['ema_short_stack'] & df['vwap_short'] & df['vol_ok'] & df['macd_falling'] & df['pullback_to_ema']

    # Signals: only allow 1 contract and prevent signals while position held (that is handled in backtest loop)
    df['signal'] = 0
    df.loc[df['long_setup'], 'signal'] = 1
    df.loc[df['short_setup'], 'signal'] = -1

    # For exits: mark EMA9 break and MACD flip
    df['ema9_break_long'] = df['close'] < df['ema9']  # break against long
    df['ema9_break_short'] = df['close'] > df['ema9'] # break against short
    df['macd_flip_long'] = df['macd_hist'] < 0
    df['macd_flip_short'] = df['macd_hist'] > 0

    return df
