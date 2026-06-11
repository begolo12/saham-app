"""
Backtesting engine for trading signal recommendations.

Evaluates signal accuracy, simulates trades, and calculates performance
metrics (win rate, avg return, Sharpe ratio, max drawdown).
Updates signal weights based on performance.
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Tuple

import numpy as np
import pandas as pd

from analysis import (
    generate_technical_signal, generate_fundamental_signal, combine_signals,
    detect_market_regime, calc_atr, calc_vwap,
)
from stock_data import get_stock_history, get_stock_info
from services.db import (
    _now_iso, _record_backtest_result, _get_signal_weights,
    _upsert_signal_weights, _get_backtest_history, _db_conn,
)

logger = logging.getLogger('saham-api')


class BacktestEngine:
    """Engine for backtesting trading signal recommendations."""

    def __init__(self, initial_capital: float = 10_000_000):
        self.initial_capital = initial_capital

    # ── Public API ──

    def run_backtest(self, symbol: str, start_date: str, end_date: str) -> Dict[str, Any]:
        """Simulate trading signal recommendations for a date range.

        Steps:
          1. Fetch historical data for the full range.
          2. Split into training periods (generate signals) and evaluation
             periods (check forward price).
          3. Record each simulated trade.
          4. Return aggregated performance.
        """
        full_symbol = symbol if symbol.endswith('.JK') else symbol + '.JK'
        df = get_stock_history(full_symbol, period='1y')
        if df.empty or len(df) < 50:
            return self._empty_result(symbol, 'Insufficient data')

        # Filter to date range
        try:
            start_dt = datetime.fromisoformat(start_date)
            end_dt = datetime.fromisoformat(end_date)
        except ValueError:
            return self._empty_result(symbol, 'Invalid date format')

        df = df[(df.index >= start_dt) & (df.index <= end_dt)]
        if len(df) < 30:
            return self._empty_result(symbol, 'Not enough data in range')

        trades = self._simulate_trades(symbol, df)
        if not trades:
            return self._empty_result(symbol, 'No trades generated')

        return self._aggregate_results(symbol, trades, start_date, end_date)

    def run_batch_backtest(self, symbols: List[str], days: int = 365) -> List[Dict[str, Any]]:
        """Run backtest for multiple symbols over the last N days."""
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=days)
        results = []
        for sym in symbols:
            try:
                result = self.run_backtest(sym, start_date.isoformat()[:10], end_date.isoformat()[:10])
                results.append(result)
            except Exception as exc:
                logger.warning('Backtest failed for %s: %s', sym, exc)
                results.append({'symbol': sym, 'error': str(exc)})
        return results

    def evaluate_signal_accuracy(self, symbol: str) -> Dict[str, Any]:
        """Evaluate past signal_recommendations for a symbol.

        Reads from signal_recommendations table, calculates win rate,
        average return, Sharpe ratio, and max drawdown.
        Updates signal_weights table with adjusted weights.
        """
        try:
            with _db_conn() as conn:
                rows = conn.execute(
                    '''SELECT recommendation, strength, price, return_pct, outcome, is_correct
                       FROM signal_recommendations
                       WHERE symbol = ? AND evaluated_at IS NOT NULL
                       ORDER BY created_at ASC''',
                    (symbol,),
                ).fetchall()
        except Exception:
            return self._empty_result(symbol, 'DB error')

        if not rows:
            return self._empty_result(symbol, 'No evaluated signals')

        trades = []
        for r in rows:
            trades.append({
                'signal': r['recommendation'],
                'strength': float(r['strength'] or 50),
                'entry_price': float(r['price'] or 0),
                'return_pct': float(r['return_pct'] or 0),
                'outcome': r['outcome'] or 'unknown',
                'is_correct': bool(r['is_correct']),
            })

        result = self._calc_accuracy(trades)
        result['symbol'] = symbol
        result['total_trades'] = len(trades)

        # Update weights based on performance
        self._adjust_weights_from_performance(symbol, result)

        # Record to backtest table
        record = dict(result)
        record['start_date'] = ''
        record['end_date'] = ''
        _record_backtest_result(symbol, record)

        return result

    # ── Internal helpers ──

    def _simulate_trades(self, symbol: str, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """Walk-forward simulation: generate signals on a rolling window."""
        trades = []
        min_window = 60  # need at least this many days for indicator computation
        step = 5  # re-evaluate every 5 trading days
        horizon = 7  # check price 7 trading days later

        if len(df) < min_window + horizon:
            return trades

        for i in range(min_window, len(df) - horizon, step):
            window = df.iloc[:i]
            lookahead = df.iloc[i:i + horizon]

            if lookahead.empty:
                continue

            # Generate signals on the window
            entry_price = float(window['close'].iloc[-1])
            info = get_stock_info(symbol if symbol.endswith('.JK') else symbol + '.JK')

            tech_signal = generate_technical_signal(window)
            fund_signal = generate_fundamental_signal(info or {})

            overall = combine_signals(
                tech_signal, fund_signal,
                df=window, entry_price=entry_price,
            )

            signal_type = overall['signal']
            if signal_type == 'NEUTRAL':
                continue  # skip neutral — no trade signal

            # Check forward price
            future_price = float(lookahead['close'].iloc[-1])
            return_pct = round(((future_price - entry_price) / entry_price) * 100, 2)

            if signal_type == 'BUY':
                is_correct = return_pct > 0
            elif signal_type == 'SELL':
                is_correct = return_pct < 0
            else:
                is_correct = abs(return_pct) <= 3

            trades.append({
                'signal': signal_type,
                'strength': overall['strength'],
                'entry_price': entry_price,
                'exit_price': future_price,
                'return_pct': return_pct,
                'regime': overall.get('market_regime', 'unknown'),
                'is_correct': is_correct,
                'outcome': 'win' if is_correct else 'loss',
            })

        return trades

    def _calc_accuracy(self, trades: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate performance metrics from a list of trades."""
        if not trades:
            return {'win_rate': 0, 'avg_return': 0, 'sharpe_ratio': 0, 'max_drawdown': 0, 'total_trades': 0}

        total = len(trades)
        wins = sum(1 for t in trades if t.get('is_correct'))
        win_rate = round(wins / total * 100, 2) if total > 0 else 0

        returns = [t['return_pct'] for t in trades]
        avg_return = round(np.mean(returns), 2) if returns else 0

        # Sharpe ratio (annualized, using daily returns as proxy)
        if len(returns) > 1:
            std = np.std(returns, ddof=1)
            sharpe_ratio = round((np.mean(returns) / std) * np.sqrt(252 / 5) if std > 0 else 0, 4)
        else:
            sharpe_ratio = 0.0

        # Max drawdown
        cumulative = np.cumsum(returns) if returns else np.array([0])
        peak = np.maximum.accumulate(cumulative)
        drawdowns = peak - cumulative
        max_drawdown = round(float(np.max(drawdowns)), 2) if len(drawdowns) > 0 else 0.0

        return {
            'win_rate': win_rate,
            'avg_return': avg_return,
            'sharpe_ratio': sharpe_ratio,
            'max_drawdown': max_drawdown,
            'total_trades': total,
        }

    def _aggregate_results(self, symbol: str, trades: List[Dict[str, Any]],
                           start_date: str, end_date: str) -> Dict[str, Any]:
        """Aggregate simulated trades into a final result dict and record to DB."""
        accuracy = self._calc_accuracy(trades)

        # Pick representative first trade for details
        first = trades[0] if trades else {}

        result = {
            'symbol': symbol,
            'signal_type': first.get('signal', ''),
            'entry_price': first.get('entry_price'),
            'exit_price': first.get('exit_price'),
            'return_pct': accuracy['avg_return'],
            'signal_strength': first.get('strength'),
            'regime': first.get('regime', 'unknown'),
            'outcome': 'win' if accuracy['win_rate'] >= 50 else 'loss',
            'is_correct': 1 if accuracy['win_rate'] >= 50 else 0,
            'win_rate': accuracy['win_rate'],
            'avg_return': accuracy['avg_return'],
            'sharpe_ratio': accuracy['sharpe_ratio'],
            'max_drawdown': accuracy['max_drawdown'],
            'total_trades': accuracy['total_trades'],
            'start_date': start_date,
            'end_date': end_date,
        }

        _record_backtest_result(symbol, result)

        # Update signal weights based on backtest win rate
        if accuracy['total_trades'] >= 3:
            self._adjust_weights_from_performance(symbol, result)

        return result

    def _adjust_weights_from_performance(self, symbol: str, result: Dict[str, Any]):
        """Update signal_weights table based on backtest/evaluation results.

        If win_rate < 40%: decrease TA weight by 0.05, increase fund by 0.05
        If win_rate > 70%: boost TA weight by 0.05
        """
        win_rate = result.get('win_rate', 50)
        if win_rate <= 0:
            return

        current = _get_signal_weights(symbol)
        if win_rate < 40:
            current['ta_weight'] = max(0.05, current['ta_weight'] - 0.05)
            current['fund_weight'] = min(0.6, current['fund_weight'] + 0.05)
        elif win_rate > 70:
            current['ta_weight'] = min(0.6, current['ta_weight'] + 0.05)
            current['fund_weight'] = max(0.05, current['fund_weight'] - 0.05)

        _upsert_signal_weights(symbol, current)

    @staticmethod
    def _empty_result(symbol: str, reason: str) -> Dict[str, Any]:
        return {
            'symbol': symbol,
            'error': reason,
            'win_rate': 0,
            'avg_return': 0,
            'sharpe_ratio': 0,
            'max_drawdown': 0,
            'total_trades': 0,
        }
