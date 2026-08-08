"""
策略分析功能：蒙特卡洛 / Walk-forward / 参数优化 / 组合回测 / 对比 / 指标分析等。
与策略注册机制解耦，全部通过通用回测引擎执行。
"""

import logging
from typing import Dict, List

import numpy as np
import pandas as pd
import ta

from apps.strategy.backtest_engine import BacktestEngine
from core.exceptions import StrategyError

logger = logging.getLogger(__name__)


def run_backtest_for(strategy, start_date, end_date, user=None,
                     fee_rate=0.001, slippage=0.001):
    """统一入口：通过通用回测引擎运行任意策略回测"""
    engine = BacktestEngine(strategy, user=user, fee_rate=fee_rate, slippage=slippage)
    return engine.run(start_date=start_date, end_date=end_date)


def run_monte_carlo(equity_curve: List, n_simulations: int = 1000) -> Dict:
    """基于回测权益曲线做蒙特卡洛模拟，估计最大回撤/收益分布"""
    equity = [float(v) for _, v in (equity_curve or [])]
    if len(equity) < 2:
        return {'error': '权益曲线太短，无法模拟'}

    returns = np.diff(equity) / np.array(equity[:-1])
    returns = returns[~np.isnan(returns) & ~np.isinf(returns)]
    if len(returns) < 2:
        return {'error': '收益率样本不足'}

    n = len(returns)
    max_drawdowns = []
    final_returns = []
    rng = np.random.default_rng(42)

    for _ in range(n_simulations):
        sampled = rng.choice(returns, size=n, replace=True)
        sim_equity = np.cumprod(1 + sampled) * equity[0]
        peak = np.maximum.accumulate(sim_equity)
        dd = (sim_equity - peak) / peak
        max_drawdowns.append(float(np.min(dd)))
        final_returns.append(float(sim_equity[-1] / equity[0] - 1))

    def _percentile(arr, p):
        arr_sorted = sorted(arr)
        idx = min(int(len(arr_sorted) * p), len(arr_sorted) - 1)
        return arr_sorted[idx]

    return {
        'n_simulations': n_simulations,
        'max_drawdown': {
            'median': round(_percentile(max_drawdowns, 0.5), 6),
            'p95': round(_percentile(max_drawdowns, 0.95), 6),
            'p99': round(_percentile(max_drawdowns, 0.99), 6),
        },
        'total_return': {
            'median': round(_percentile(final_returns, 0.5), 6),
            'p5': round(_percentile(final_returns, 0.05), 6),
            'p95': round(_percentile(final_returns, 0.95), 6),
        },
        'max_drawdowns_sample': [round(x, 4) for x in max_drawdowns[:200]],
    }


def run_walk_forward(strategy, start_date, end_date, window_days=14, user=None) -> Dict:
    """Walk-forward 分析：滚动窗口回测，评估参数稳定性"""
    from datetime import timedelta

    results = []
    total_days = (end_date - start_date).days
    if total_days < window_days * 2:
        return {'error': f'回测区间需至少 {window_days * 2} 天'}

    cur = start_date
    idx = 0
    while cur + timedelta(days=window_days) <= end_date:
        win_start = cur
        win_end = min(cur + timedelta(days=window_days), end_date)
        try:
            bt = run_backtest_for(strategy, start_date=win_start, end_date=win_end, user=user)
            results.append({
                'window': idx,
                'start': win_start.date().isoformat(),
                'end': win_end.date().isoformat(),
                'total_return': float(bt['total_return']),
                'sharpe_ratio': float(bt['sharpe_ratio'] or 0),
                'max_drawdown': float(bt['max_drawdown']),
                'total_trades': bt['total_trades'],
            })
        except Exception as e:
            results.append({
                'window': idx, 'error': str(e),
                'start': win_start.date().isoformat(),
                'end': win_end.date().isoformat(),
            })
        cur = win_end
        idx += 1

    if not results:
        return {'error': '无有效的窗口回测结果'}

    valid = [r for r in results if 'error' not in r]
    avg_return = sum(r['total_return'] for r in valid) / len(valid) if valid else 0
    avg_sharpe = sum(r['sharpe_ratio'] for r in valid) / len(valid) if valid else 0
    return {
        'windows': results,
        'avg_total_return': round(avg_return, 6),
        'avg_sharpe_ratio': round(avg_sharpe, 4),
        'positive_windows': len([r for r in valid if r['total_return'] > 0]),
        'total_windows': len(valid),
    }


def optimize_params(strategy, start_date, end_date, param_grid: Dict, user=None) -> List[Dict]:
    """网格搜索策略参数，返回按目标指标排序的结果列表"""
    base_params = dict(strategy.params or {})
    keys = list(param_grid.keys())
    results = []

    def _gen(prefix: dict, idx: int):
        if idx >= len(keys):
            yield dict(prefix)
            return
        key = keys[idx]
        for val in param_grid[key]:
            prefix2 = dict(prefix)
            prefix2[key] = val
            yield from _gen(prefix2, idx + 1)

    for combo in _gen({}, 0):
        strategy.params = {**base_params, **combo}
        try:
            bt = run_backtest_for(strategy, start_date=start_date, end_date=end_date, user=user)
            results.append({
                'params': combo,
                'total_return': float(bt['total_return']),
                'sharpe_ratio': float(bt['sharpe_ratio'] or 0),
                'max_drawdown': float(bt['max_drawdown']),
                'win_rate': float(bt['win_rate']),
                'total_trades': bt['total_trades'],
            })
        except Exception as e:
            logger.warning(f'参数组合 {combo} 回测失败: {e}')
        finally:
            strategy.params = base_params

    results.sort(key=lambda r: (r['sharpe_ratio'], r['total_return']), reverse=True)
    return results[:50]


def optimize_factor_weights(strategy, start_date, end_date, user=None, iterations=10) -> Dict:
    """基于回测结果自动优化因子权重（随机爬山）"""
    import random

    factors = list(strategy.factors or [])
    if len(factors) < 2:
        return {'error': '至少需要2个因子才能优化权重'}

    def _score(weights) -> float:
        strategy.factor_weights = weights
        try:
            bt = run_backtest_for(strategy, start_date=start_date, end_date=end_date, user=user)
            return float(bt['sharpe_ratio'] or 0) * 10 + float(bt['total_return']) * 2
        except Exception:
            return float('-inf')
        finally:
            strategy.factor_weights = None

    best_weights = {f: 1.0 / len(factors) for f in factors}
    best_score = _score(best_weights)

    for i in range(iterations):
        candidate = {f: best_weights[f] + random.uniform(-0.2, 0.2) for f in factors}
        candidate = {f: max(v, 0.05) for f, v in candidate.items()}
        total = sum(candidate.values())
        candidate = {f: v / total for f, v in candidate.items()}
        s = _score(candidate)
        if s > best_score:
            best_score = s
            best_weights = candidate

    strategy.factor_weights = best_weights
    strategy.save(update_fields=['factor_weights'])

    return {
        'weights': {k: round(v, 4) for k, v in best_weights.items()},
        'score': round(best_score, 4),
    }


def run_multi_symbol_backtest(strategy, start_date, end_date, user=None,
                              fee_rate=0.001, slippage=0.001) -> Dict:
    """对策略的每个标的单独回测，返回各品种独立表现 + 汇总"""
    symbols = list(strategy.symbols or [])
    if not symbols:
        raise StrategyError('策略未配置标的')

    original_symbols = strategy.symbols
    per_symbol = []
    try:
        for sym in symbols:
            strategy.symbols = [sym]
            try:
                bt = run_backtest_for(strategy, start_date=start_date, end_date=end_date,
                                      user=user, fee_rate=fee_rate, slippage=slippage)
                per_symbol.append({
                    'symbol': sym,
                    'total_return': float(bt['total_return']),
                    'annual_return': float(bt['annual_return'] or 0),
                    'sharpe_ratio': float(bt['sharpe_ratio'] or 0),
                    'max_drawdown': float(bt['max_drawdown']),
                    'win_rate': float(bt['win_rate']),
                    'total_trades': bt['total_trades'],
                    'profit_factor': float(bt['profit_factor'] or 0),
                    'equity_curve': bt['equity_curve'],
                })
            except Exception as e:
                per_symbol.append({'symbol': sym, 'error': str(e)})
    finally:
        strategy.symbols = original_symbols

    valid = [r for r in per_symbol if 'error' not in r]
    avg_return = sum(r['total_return'] for r in valid) / len(valid) if valid else 0
    return {
        'strategy_id': strategy.id,
        'name': strategy.name,
        'symbols': per_symbol,
        'avg_total_return': round(avg_return, 6),
        'positive_symbols': len([r for r in valid if r['total_return'] > 0]),
        'total_symbols': len(valid),
    }


def run_portfolio_backtest(portfolio, start_date, end_date, user=None) -> Dict:
    """组合回测：按权重分配资金给各策略独立回测，聚合权益曲线"""
    from apps.strategy.models import StrategyConfig

    items = portfolio.strategies or []
    if not items:
        raise StrategyError('组合内无策略')

    total_weight = sum(float(i.get('weight', 0)) for i in items)
    if total_weight <= 0:
        raise StrategyError('组合权重总和需大于0')

    initial_capital = float(portfolio.initial_capital)
    curves = []
    for item in items:
        strategy = StrategyConfig.objects.filter(id=item.get('strategy_id'), user=user).first()
        if not strategy:
            continue
        weight = float(item.get('weight', 0)) / total_weight
        try:
            bt = run_backtest_for(strategy, start_date=start_date, end_date=end_date, user=user)
            curves.append({
                'strategy_id': strategy.id,
                'name': strategy.name,
                'weight': weight,
                'equity_curve': bt['equity_curve'],
                'total_return': float(bt['total_return']),
                'sharpe_ratio': float(bt['sharpe_ratio'] or 0),
                'max_drawdown': float(bt['max_drawdown']),
            })
        except Exception as e:
            logger.warning(f'组合成员 {strategy.name} 回测失败: {e}')

    if not curves:
        raise StrategyError('组合回测无有效结果')

    time_map = {}
    for c in curves:
        capital_per = initial_capital * c['weight']
        for ts, val in c['equity_curve']:
            time_map.setdefault(ts, 0)
            time_map[ts] += capital_per * (val / initial_capital if initial_capital else 1)

    timestamps = sorted(time_map.keys())
    agg_curve = [(ts, time_map[ts]) for ts in timestamps]

    final_capital = agg_curve[-1][1] if agg_curve else initial_capital
    total_return = (final_capital - initial_capital) / initial_capital if initial_capital else 0

    return {
        'portfolio_id': portfolio.id,
        'name': portfolio.name,
        'initial_capital': initial_capital,
        'final_capital': round(final_capital, 4),
        'total_return': round(total_return, 6),
        'equity_curve': agg_curve,
        'members': curves,
    }


def compare_strategies(strategy_ids: List[int], start_date, end_date, user=None) -> List[Dict]:
    """多策略回测结果对比"""
    from apps.strategy.models import StrategyConfig

    results = []
    strategies = StrategyConfig.objects.filter(id__in=strategy_ids, user=user)
    for strategy in strategies:
        try:
            bt = run_backtest_for(strategy, start_date=start_date, end_date=end_date, user=user)
            results.append({
                'strategy_id': strategy.id,
                'name': strategy.name,
                'strategy_type': strategy.strategy_type,
                'symbols': strategy.symbols,
                'total_return': float(bt['total_return']),
                'annual_return': float(bt['annual_return'] or 0),
                'sharpe_ratio': float(bt['sharpe_ratio'] or 0),
                'max_drawdown': float(bt['max_drawdown']),
                'win_rate': float(bt['win_rate']),
                'total_trades': bt['total_trades'],
                'profit_factor': float(bt['profit_factor'] or 0),
                'equity_curve': bt['equity_curve'],
            })
        except Exception as e:
            results.append({
                'strategy_id': strategy.id,
                'name': strategy.name,
                'error': str(e),
            })
    return results


# ========== 指标分析（因子IC/相关性/市场状态等） ==========

def correlation_matrix(symbols: List[str], bar: str = '1D', limit: int = 200, user=None) -> Dict:
    """计算多品种收益率相关性矩阵"""
    from apps.market.models import KLine
    from apps.account.models import SystemConfig

    env = SystemConfig.get_config(user=user).active_environment
    closes = {}
    for sym in symbols:
        rows = list(
            KLine.objects.filter(instrument__inst_id=sym, bar=bar, environment=env)
            .order_by('-timestamp')[:limit]
        )
        if len(rows) < 20:
            continue
        closes[sym] = pd.Series(
            [float(r.close) for r in rows], index=[r.timestamp for r in rows]
        ).sort_index()

    if len(closes) < 2:
        return {'error': '至少需要2个有足够数据的品种'}

    df = pd.DataFrame(closes).dropna(how='all')
    returns = df.pct_change().dropna()
    corr = returns.corr().round(4)

    return {
        'symbols': list(corr.index),
        'matrix': corr.values.tolist(),
        'sample_size': len(returns),
    }


def factor_ic_analysis(strategy, bar: str = '1D', lookback: int = 100, user=None) -> Dict:
    """因子 IC（信息系数）分析：因子值与未来收益的秩相关"""
    from scipy import stats
    from apps.market.models import KLine
    from apps.account.models import SystemConfig
    from apps.strategy.factors import FactorEngine

    env = SystemConfig.get_config(user=user).active_environment
    symbols = list(strategy.symbols or [])[:3]
    if not symbols:
        return {'error': '策略未配置标的'}

    results = {}
    for sym in symbols:
        rows = list(
            KLine.objects.filter(instrument__inst_id=sym, bar=bar, environment=env)
            .order_by('-timestamp')[:lookback + 60]
        )
        if len(rows) < 60:
            continue
        rows.sort(key=lambda r: r.timestamp)
        df = pd.DataFrame([{
            'timestamp': r.timestamp,
            'open': float(r.open), 'high': float(r.high),
            'low': float(r.low), 'close': float(r.close),
            'volume': float(r.vol),
        } for r in rows])
        engine = FactorEngine(df)
        factor_names = list(strategy.factors or [])
        engine.calculate_all(factor_names)
        future_ret = df['close'].shift(-5) / df['close'] - 1
        per_factor = {}
        for name in factor_names:
            if name in getattr(engine, '_custom_formulas', {}):
                continue
            vals = []
            for i in range(30, len(df)):
                sub = df.iloc[:i + 1]
                try:
                    sub_engine = FactorEngine(sub)
                    sub_engine.calculate_all([name])
                    vals.append(sub_engine._results[name].value)
                except Exception:
                    vals.append(np.nan)
            if len(vals) < 20:
                continue
            vals_arr = np.array(vals[-len(future_ret.dropna()):])
            fwd = future_ret.values[-len(vals_arr):]
            mask = ~(np.isnan(vals_arr) | np.isnan(fwd))
            if mask.sum() < 10:
                continue
            ic, _ = stats.spearmanr(vals_arr[mask], fwd[mask])
            per_factor[name] = {'ic': round(float(ic), 4), 'samples': int(mask.sum())}
        results[sym] = per_factor

    return {'symbols': list(results.keys()), 'factors': results}


def market_state(inst_id: str, bar: str = '1D', lookback: int = 60, user=None) -> Dict:
    """市场状态分类：趋势/震荡/高波动"""
    from apps.market.services import MarketDataService

    df = MarketDataService.get_klines_df(inst_id=inst_id, bar=bar, limit=lookback, user=user)
    if df is None or len(df) < 30:
        return {'error': '数据不足'}

    try:
        adx = float(ta.trend.ADXIndicator(
            df['high'], df['low'], df['close'], window=14
        ).adx().iloc[-1])
        adx = adx if not pd.isna(adx) else 0
    except Exception:
        adx = 0

    try:
        atr = float(ta.volatility.AverageTrueRange(
            df['high'], df['low'], df['close'], window=14
        ).average_true_range().iloc[-1])
        atr_ratio = atr / float(df['close'].iloc[-1]) if atr and not pd.isna(atr) else 0
    except Exception:
        atr_ratio = 0

    if adx > 30 and atr_ratio > 0.03:
        state = 'high_trend'
    elif adx > 25:
        state = 'trend'
    elif atr_ratio > 0.03:
        state = 'high_volatility'
    else:
        state = 'range'

    state_labels = {
        'high_trend': '高波动趋势', 'trend': '趋势行情',
        'high_volatility': '高波动震荡', 'range': '震荡行情',
    }
    return {
        'inst_id': inst_id,
        'bar': bar,
        'state': state,
        'state_label': state_labels[state],
        'adx': round(adx, 2),
        'atr_ratio': round(atr_ratio, 5),
        'suggest': {
            'trend': '顺势策略', 'high_trend': '趋势跟踪，控制仓位',
            'high_volatility': '波动套利/观望', 'range': '高抛低吸/区间策略',
        }.get(state),
    }
