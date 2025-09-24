# src/backtest.py
"""
Simple bar-by-bar backtest engine using the strategy signals in strategy.py.

Usage:
    python -m src.backtest --data path/to/gold.csv

CSV must contain: datetime, open, high, low, close, volume
datetime should be ISO parseable. Index will be set to datetime and must be increasing.
"""

import argparse
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import os
from datetime import datetime, timezone
from .strategy import generate_signals

CONTRACT_TICK_VALUE = 10.0  # default approximation: $10 per tick (adjust to your data symbol)
CONTRACT_POINT_VALUE = 100.0  # not used; placeholder

def run_backtest(df: pd.DataFrame, params: dict):
    df = generate_signals(df, params)
    initial_equity = params.get('initial_equity', 100000.0)
    equity = initial_equity
    daily_start = df.index[0].date()
    daily_pnl = 0.0
    max_daily_drawdown_pct = params.get('daily_loss_limit_pct', 0.15)  # 15%
    position = None  # dict: {'side','entry_price','stop','tp','entry_index'}
    trades = []

    for i in range(1, len(df)):
        row = df.iloc[i]
        prev = df.iloc[i-1]

        # reset daily pnl when date changes
        if row.name.date() != daily_start:
            daily_start = row.name.date()
            daily_pnl = 0.0

        # enforce daily loss limit: if exceeded, skip new entries
        if daily_pnl <= -max_daily_drawdown_pct * equity:
            # do not open new trades today
            can_open = False
        else:
            can_open = True

        # CLOSES: Check existing position for TP/SL or exit signals or session close
        if position is not None:
            side = position['side']
            # check stop
            if side == 'LONG':
                # stop hit?
                if row['low'] <= position['stop']:
                    exit_price = position['stop']
                    pnl = (exit_price - position['entry_price']) * position['qty'] * CONTRACT_TICK_VALUE
                    reason = 'stop'
                    trades.append({**position, 'exit_price': exit_price, 'exit_time': row.name, 'pnl': pnl, 'reason': reason})
                    equity += pnl
                    daily_pnl += pnl
                    position = None
                    continue  # move to next bar
                # tp hit?
                if row['high'] >= position['tp']:
                    exit_price = position['tp']
                    pnl = (exit_price - position['entry_price']) * position['qty'] * CONTRACT_TICK_VALUE
                    reason = 'tp'
                    trades.append({**position, 'exit_price': exit_price, 'exit_time': row.name, 'pnl': pnl, 'reason': reason})
                    equity += pnl
                    daily_pnl += pnl
                    position = None
                    continue

                # technical exits (EMA9 break or MACD flip)
                if row['ema9_break_long'] or row['macd_flip_long']:
                    exit_price = row['close']
                    pnl = (exit_price - position['entry_price']) * position['qty'] * CONTRACT_TICK_VALUE
                    reason = 'technical_exit'
                    trades.append({**position, 'exit_price': exit_price, 'exit_time': row.name, 'pnl': pnl, 'reason': reason})
                    equity += pnl
                    daily_pnl += pnl
                    position = None
                    continue

                # session close (if near end of session) -> strategy uses session mask; we can force-close when in_ny becomes False next bar
                if not row['in_ny'] and prev['in_ny']:
                    exit_price = row['close']
                    pnl = (exit_price - position['entry_price']) * position['qty'] * CONTRACT_TICK_VALUE
                    reason = 'session_close'
                    trades.append({**position, 'exit_price': exit_price, 'exit_time': row.name, 'pnl': pnl, 'reason': reason})
                    equity += pnl
                    daily_pnl += pnl
                    position = None
                    continue

            else:  # SHORT
                if row['high'] >= position['stop']:
                    exit_price = position['stop']
                    pnl = (position['entry_price'] - exit_price) * position['qty'] * CONTRACT_TICK_VALUE
                    reason = 'stop'
                    trades.append({**position, 'exit_price': exit_price, 'exit_time': row.name, 'pnl': pnl, 'reason': reason})
                    equity += pnl
                    daily_pnl += pnl
                    position = None
                    continue
                if row['low'] <= position['tp']:
                    exit_price = position['tp']
                    pnl = (position['entry_price'] - exit_price) * position['qty'] * CONTRACT_TICK_VALUE
                    reason = 'tp'
                    trades.append({**position, 'exit_price': exit_price, 'exit_time': row.name, 'pnl': pnl, 'reason': reason})
                    equity += pnl
                    daily_pnl += pnl
                    position = None
                    continue
                if row['ema9_break_short'] or row['macd_flip_short']:
                    exit_price = row['close']
                    pnl = (position['entry_price'] - exit_price) * position['qty'] * CONTRACT_TICK_VALUE
                    reason = 'technical_exit'
                    trades.append({**position, 'exit_price': exit_price, 'exit_time': row.name, 'pnl': pnl, 'reason': reason})
                    equity += pnl
                    daily_pnl += pnl
                    position = None
                    continue
                if not row['in_ny'] and prev['in_ny']:
                    exit_price = row['close']
                    pnl = (position['entry_price'] - exit_price) * position['qty'] * CONTRACT_TICK_VALUE
                    reason = 'session_close'
                    trades.append({**position, 'exit_price': exit_price, 'exit_time': row.name, 'pnl': pnl, 'reason': reason})
                    equity += pnl
                    daily_pnl += pnl
                    position = None
                    continue

        # ENTRIES: only open new if no position and can_open
        if position is None and can_open:
            sig = row['signal']
            if sig == 1:
                # open LONG at next bar open (simulate by using current bar open)
                entry_price = row['open']
                stop = entry_price - params.get('atr_mult', 1.2) * row['atr']
                tp = entry_price + 3 * (entry_price - stop)
                position = {'side': 'LONG', 'entry_price': entry_price, 'stop': stop, 'tp': tp, 'qty': 1, 'entry_time': row.name}
                # no immediate pnl change
            elif sig == -1:
                entry_price = row['open']
                stop = entry_price + params.get('atr_mult', 1.2) * row['atr']
                tp = entry_price - 3 * (stop - entry_price)
                position = {'side': 'SHORT', 'entry_price': entry_price, 'stop': stop, 'tp': tp, 'qty': 1, 'entry_time': row.name}
            # else no entry

    # End loop - if still position open, close at last close
    if position is not None:
        exit_price = df.iloc[-1]['close']
        if position['side'] == 'LONG':
            pnl = (exit_price - position['entry_price']) * position['qty'] * CONTRACT_TICK_VALUE
        else:
            pnl = (position['entry_price'] - exit_price) * position['qty'] * CONTRACT_TICK_VALUE
        trades.append({**position, 'exit_price': exit_price, 'exit_time': df.index[-1], 'pnl': pnl, 'reason': 'end_of_data'})
        equity += pnl

    trades_df = pd.DataFrame(trades)
    # compute summary metrics
    total_pnl = trades_df['pnl'].sum() if not trades_df.empty else 0.0
    wins = trades_df[trades_df['pnl'] > 0]
    losses = trades_df[trades_df['pnl'] <= 0]
    win_rate = len(wins) / len(trades_df) if len(trades_df) > 0 else np.nan
    profit_factor = wins['pnl'].sum() / (-losses['pnl'].sum()) if len(losses) > 0 else np.nan
    max_drawdown = None  # quick placeholder; a more thorough calc can be added

    print("Backtest summary")
    print("----------------")
    print("Initial equity:", initial_equity)
    print("Final equity:", equity)
    print("Net P&L:", equity - initial_equity)
    print("Trades:", len(trades_df))
    print("Win rate:", win_rate)
    print("Profit factor:", profit_factor)

    # save trades
    out_dir = params.get('out_dir', 'data/results')
    os.makedirs(out_dir, exist_ok=True)
    trades_df.to_csv(os.path.join(out_dir, 'trades.csv'), index=False)

    # equity curve plot (cumulative PnL over trades)
    if not trades_df.empty:
        trades_df['cum_pnl'] = trades_df['pnl'].cumsum()
        plt.figure(figsize=(10,5))
        plt.plot(trades_df['entry_time'], trades_df['cum_pnl'])
        plt.xlabel('Trade time')
        plt.ylabel('Cumulative P&L')
        plt.title('Equity curve (per-trade cumulative PnL)')
        plt.grid(True)
        plt.tight_layout()
        plt.savefig(os.path.join(out_dir, 'equity_curve.png'))
        print("Saved trades and equity curve to", out_dir)

    return trades_df

def load_data(path):
    df = pd.read_csv(path, parse_dates=['datetime'])
    df = df.set_index('datetime').sort_index()
    # ensure numeric columns
    for c in ['open','high','low','close','volume']:
        df[c] = pd.to_numeric(df[c], errors='coerce')
    # forward fill small gaps
    df = df.dropna(subset=['open','high','low','close'])
    return df

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--data', type=str, required=True, help='path to OHLCV CSV (datetime,open,high,low,close,volume)')
    parser.add_argument('--out', type=str, default='data/results', help='output directory')
    args = parser.parse_args()

    df = load_data(args.data)
    params = {
        'ema9':9, 'ema21':21, 'ema60':60, 'ema200':200,
        'macd_fast':12, 'macd_slow':26, 'macd_sig':9,
        'atr_len':14, 'atr_mult':1.2,
        'vol_sma_len':20, 'vol_mult':1.5,
        'session_start': "08:30", 'session_end': "16:00", 'tz': "America/New_York",
        'htf': '1H',
        'initial_equity': 100000.0,
        'daily_loss_limit_pct': 0.15,
        'out_dir': args.out
    }
    trades = run_backtest(df, params)
    print("Done.")

if __name__ == '__main__':
    main()
