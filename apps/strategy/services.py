"""
策略引擎服务层
提供信号生成、策略执行、回测等核心功能
"""

import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import ta
from django.db import transaction


from django.utils import timezone

from apps.market.models import Instrument
from apps.market.services import MarketDataService
from apps.strategy.models import StrategyConfig, SignalRecord, BacktestResult
from apps.strategy.factors import FactorEngine, FactorResult
from core.okx_client import get_okx_client
from core.risk_manager import RiskManager, PositionInfo
from core.exceptions import StrategyError


logger = logging.getLogger(__name__)


class StrategyService:
    """策略服务"""

    # ========== 信号生成 ==========
    @staticmethod
    def generate_signals(strategy: StrategyConfig) -> List[SignalRecord]:
        """为策略的所有标的生成交易信号"""
        if strategy.strategy_type == 'trend_follow':
            return StrategyService._generate_trend_signals(strategy)
        return StrategyService._generate_factor_signals(strategy)

    @staticmethod
    def _generate_factor_signals(strategy: StrategyConfig) -> List[SignalRecord]:
        """基于因子综合评分生成信号"""
        signals = []

        for symbol in strategy.symbols:
            try:
                market_service = MarketDataService()
                market_service.fetch_klines(inst_id=symbol, bar=strategy.bar, limit=200)
                df = market_service.get_klines_df(inst_id=symbol, bar=strategy.bar, limit=200)

                if df.empty:
                    logger.warning(f'{symbol} 无K线数据，跳过信号生成')
                    continue

                engine = FactorEngine(df)
                engine.calculate_all(strategy.factors)
                composite_score, composite_signal = engine.get_composite_score()

                current_price = float(df['close'].iloc[-1])
                final_signal = StrategyService._filter_by_direction(composite_signal, strategy.direction)

                details = {
                    name: {'value': r.value, 'score': round(r.score, 4), 'signal': r.signal}
                    for name, r in engine._results.items()
                }

                signal = SignalRecord.objects.create(
                    strategy=strategy,
                    inst_id=symbol,
                    signal=final_signal,
                    pos_side=StrategyService._infer_pos_side(final_signal),
                    td_mode=strategy.td_mode,
                    leverage=strategy.leverage,
                    score=Decimal(str(round(composite_score, 4))),
                    factors_detail=details,
                    price=Decimal(str(round(current_price, 4))),
                    reason=f'综合评分: {composite_score:.2f}, 成分: {composite_signal}',
                )
                signals.append(signal)

            except Exception as e:
                logger.error(f'{symbol} 因子信号生成异常: {e}')

        logger.info(f'策略 [{strategy.name}] 生成 {len(signals)} 个因子信号')
        return signals

    @staticmethod
    def _generate_trend_signals(strategy: StrategyConfig) -> List[SignalRecord]:
        """基于趋势跟踪生成分钟级买卖信号"""
        signals = []
        client = get_okx_client()

        # 获取当前持仓以判断是开仓还是平仓
        positions = {}
        try:
            pos_resp = client.get_positions(inst_type=strategy.inst_type)
            if pos_resp.get('code') == '0':
                positions = {p['instId']: p for p in pos_resp.get('data', []) if float(p.get('pos', 0)) != 0}
        except Exception as e:
            logger.warning(f'获取持仓失败: {e}')

        for symbol in strategy.symbols:
            try:
                market_service = MarketDataService()
                market_service.fetch_klines(inst_id=symbol, bar=strategy.bar, limit=200)
                df = market_service.get_klines_df(inst_id=symbol, bar=strategy.bar, limit=200)

                if len(df) < 50:
                    logger.warning(f'{symbol} K线数据不足，跳过')
                    continue

                signal_type, score, reason = StrategyService._trend_decision(
                    df, strategy.direction, symbol, positions
                )

                if signal_type == 'hold':
                    continue

                current_price = float(df['close'].iloc[-1])
                pos_side = StrategyService._infer_pos_side(signal_type)

                signal = SignalRecord.objects.create(
                    strategy=strategy,
                    inst_id=symbol,
                    signal=signal_type,
                    pos_side=pos_side,
                    td_mode=strategy.td_mode,
                    leverage=strategy.leverage,
                    score=Decimal(str(round(score, 4))),
                    factors_detail={
                        'ema_fast': round(float(df['close'].ewm(span=12, adjust=False).mean().iloc[-1]), 4),
                        'ema_slow': round(float(df['close'].ewm(span=26, adjust=False).mean().iloc[-1]), 4),
                        'close': round(current_price, 4),
                    },
                    price=Decimal(str(round(current_price, 4))),
                    reason=reason,
                )
                signals.append(signal)

            except Exception as e:
                logger.error(f'{symbol} 趋势信号生成异常: {e}')

        logger.info(f'策略 [{strategy.name}] 生成 {len(signals)} 个趋势信号')
        return signals

    @staticmethod
    def _trend_decision(df, direction: str, symbol: str, positions: Dict) -> Tuple[str, float, str]:
        """趋势判断：返回 (signal, score, reason)"""
        close = df['close']
        ema_fast = close.ewm(span=12, adjust=False).mean()
        ema_slow = close.ewm(span=26, adjust=False).mean()
        adx = ta.trend.ADXIndicator(df['high'], df['low'], df['close'], window=14).adx()

        last_close = float(close.iloc[-1])
        prev_fast = float(ema_fast.iloc[-2])
        prev_slow = float(ema_slow.iloc[-2])
        curr_fast = float(ema_fast.iloc[-1])
        curr_slow = float(ema_slow.iloc[-1])
        adx_value = float(adx.iloc[-1]) if not pd.isna(adx.iloc[-1]) else 0

        # 判断当前持仓
        current_pos = positions.get(symbol, {})
        current_pos_side = current_pos.get('posSide', '')
        current_pos_qty = abs(float(current_pos.get('pos', 0)))

        score = min(adx_value / 50, 1.0) if adx_value > 20 else 0.3
        trend_strong = adx_value >= 25

        # 金叉 / 死叉
        golden_cross = prev_fast <= prev_slow and curr_fast > curr_slow
        death_cross = prev_fast >= prev_slow and curr_fast < curr_slow
        above_ma = curr_fast > curr_slow and last_close > curr_fast
        below_ma = curr_fast < curr_slow and last_close < curr_fast

        # 平多：死叉 或 跌破慢线
        if current_pos_side == 'long' and current_pos_qty > 0:
            if death_cross or (last_close < curr_slow):
                return 'close_long', 0.7, f'趋势反转/跌破均线，ADX={adx_value:.1f}'
            return 'hold', 0, '持有多仓'

        # 平空：金叉 或 突破慢线
        if current_pos_side == 'short' and current_pos_qty > 0:
            if golden_cross or (last_close > curr_slow):
                return 'close_short', 0.7, f'趋势反转/突破均线，ADX={adx_value:.1f}'
            return 'hold', 0, '持有空仓'

        # 开多
        if direction in ('long', 'both') and (golden_cross or (above_ma and trend_strong)):
            reason = f'EMA金叉且趋势强劲，ADX={adx_value:.1f}' if golden_cross else f'均线多头排列，ADX={adx_value:.1f}'
            return 'buy', score, reason

        # 开空
        if direction in ('short', 'both') and (death_cross or (below_ma and trend_strong)):
            reason = f'EMA死叉且趋势强劲，ADX={adx_value:.1f}' if death_cross else f'均线空头排列，ADX={adx_value:.1f}'
            return 'sell', score, reason

        return 'hold', 0, f'无明确趋势，ADX={adx_value:.1f}'

    @staticmethod
    def _infer_pos_side(signal: str) -> str:
        """根据信号推断持仓方向"""
        if signal in ('buy', 'close_short'):
            return 'long'
        if signal in ('sell', 'close_long'):
            return 'short'
        return 'net'


    @staticmethod
    def _filter_by_direction(signal: str, direction: str) -> str:
        """根据策略方向过滤信号"""
        if direction == 'long':
            return signal if signal in ('buy', 'close_short') else 'hold'
        elif direction == 'short':
            return signal if signal in ('sell', 'close_long') else 'hold'
        elif direction == 'both':
            return signal
        return signal

    # ========== 信号执行 ==========
    @staticmethod
    def execute_signal(signal: SignalRecord) -> Optional[Dict]:
        """执行单个交易信号（支持合约杠杆）"""
        if signal.is_executed:
            logger.warning(f'信号 #{signal.id} 已执行，跳过')
            return None

        client = get_okx_client()
        strategy = signal.strategy
        td_mode = signal.td_mode or strategy.td_mode or 'cash'
        leverage = float(signal.leverage or strategy.leverage or 1)

        # 合约模式下设置杠杆
        if td_mode in ('cross', 'isolated'):
            try:
                client.set_leverage(
                    lever=str(int(leverage)),
                    mgn_mode=td_mode,
                    inst_id=signal.inst_id,
                )
            except Exception as e:
                logger.warning(f'设置杠杆失败（可能已设置）: {e}')

        # 获取账户余额
        balance = client.get_account_balance()
        if balance['code'] != '0':
            raise StrategyError(f'获取余额失败: {balance.get("msg")}')

        details = balance.get('data', [])[0].get('details', [])
        usdt_detail = next((d for d in details if d['ccy'] == 'USDT'), None)
        available_usd = float(usdt_detail.get('availBal', 0)) if usdt_detail else 0

        # 合约模式下按杠杆放大名义价值
        order_value = available_usd * float(strategy.order_size_pct) * leverage
        order_value = min(order_value, available_usd * leverage)

        if order_value <= 0:
            logger.warning(f'可用余额不足: {available_usd}')
            return None

        current_price = float(signal.price) if signal.price else 0
        if current_price <= 0:
            ticker = client.get_ticker(signal.inst_id)
            if ticker['code'] == '0' and ticker['data']:
                current_price = float(ticker['data'][0]['last'])

        sz = str(round(order_value / current_price, 6)) if current_price > 0 else '0'

        side, pos_side = StrategyService._signal_to_order_params(signal.signal)
        if not side:
            logger.info(f'信号 #{signal.id} 为 hold，无需下单')
            return None

        try:
            result = client.place_order(
                inst_id=signal.inst_id,
                td_mode=td_mode,
                side=side,
                pos_side=pos_side,
                ord_type='market',
                sz=sz,
            )

            if result['code'] == '0':
                signal.is_executed = True
                signal.save(update_fields=['is_executed'])
                logger.info(f'信号 #{signal.id} 执行成功: {signal.inst_id} {signal.signal} td_mode={td_mode} leverage={leverage}')
                return result

        except Exception as e:
            logger.error(f'执行信号 #{signal.id} 失败: {e}')
            raise StrategyError(f'Order failed: {e}') from e

        return None

    @staticmethod
    def _signal_to_order_params(signal: str) -> Tuple[Optional[str], Optional[str]]:
        """信号转下单参数 (side, pos_side)"""
        mapping = {
            'buy': ('buy', 'long'),
            'sell': ('sell', 'short'),
            'close_long': ('sell', 'long'),
            'close_short': ('buy', 'short'),
        }
        return mapping.get(signal, (None, None))


    # ========== 回测 ==========
    @staticmethod
    def run_backtest(strategy: StrategyConfig,
                     start_date: datetime, end_date: datetime) -> BacktestResult:
        """简单回测引擎（基于历史K线）"""
        from apps.market.models import KLine
        import numpy as np

        # 获取所有标的的历史K线
        all_klines = KLine.objects.filter(
            instrument__inst_id__in=strategy.symbols,
            bar=strategy.bar,
            timestamp__gte=start_date,
            timestamp__lte=end_date,
        ).order_by('timestamp')

        if not all_klines.exists():
            raise StrategyError('回测区间内无K线数据')

        capital = float(strategy.initial_capital)
        initial_capital = capital
        equity_curve = [(start_date, capital)]
        trades_log = []

        # 按时间分组
        from itertools import groupby
        grouped = groupby(all_klines, key=lambda k: k.timestamp)

        for timestamp, klines_group in grouped:
            # 每根K线评估一次信号
            for kline in klines_group:
                sym = kline.instrument.inst_id
                # 获取该时间点前的K线数据用于因子计算
                df = MarketDataService.get_klines_df(
                    inst_id=sym, bar=strategy.bar, limit=200
                )
                if df.empty:
                    continue

                # 过滤到当前时间之前
                df = df[df.index <= timestamp]
                if len(df) < 50:
                    continue

                engine = FactorEngine(df)
                engine.calculate_all(strategy.factors)
                score, sig = engine.get_composite_score()
                sig = StrategyService._filter_by_direction(sig, strategy.direction)

                price = float(kline.close)
                trade_pct = float(strategy.order_size_pct)

                if sig == 'buy':
                    amount = capital * trade_pct
                    qty = amount / price
                    capital -= amount
                    trades_log.append({
                        'timestamp': timestamp, 'symbol': sym,
                        'action': 'buy', 'price': price, 'amount': amount,
                        'capital': capital,
                    })

                elif sig == 'sell':
                    # 清算持仓
                    for t in list(trades_log):
                        if t['symbol'] == sym and t['action'] == 'buy':
                            proceeds = t['amount'] * (price / t['price'])
                            pnl = proceeds - t['amount']
                            capital += proceeds
                            trades_log.remove(t)
                            trades_log.append({
                                'timestamp': timestamp, 'symbol': sym,
                                'action': 'sell', 'price': price,
                                'pnl': pnl, 'capital': capital,
                            })
                            break

            equity_curve.append((timestamp, capital))

        # 计算回测指标
        final_capital = capital
        total_return = (final_capital - initial_capital) / initial_capital if initial_capital > 0 else 0

        # 交易日数
        days = max((end_date - start_date).days, 1)
        annual_return = (1 + total_return) ** (365 / days) - 1 if days > 0 else 0

        # 最大回撤
        equity_values = [v for _, v in equity_curve]
        peak = equity_values[0]
        max_dd = 0
        for v in equity_values:
            if v > peak:
                peak = v
            dd = (peak - v) / peak if peak > 0 else 0
            max_dd = max(max_dd, dd)

        # 统计交易结果
        buy_trades = [t for t in trades_log if t.get('action') == 'buy']
        sell_trades = [t for t in trades_log if t.get('pnl') is not None]
        total_trades = len(buy_trades) + len(sell_trades)
        profit_trades = sum(1 for t in sell_trades if t['pnl'] > 0)
        loss_trades = sum(1 for t in sell_trades if t['pnl'] <= 0)

        win_rate = profit_trades / len(sell_trades) if sell_trades else 0
        profits = [t['pnl'] for t in sell_trades if t['pnl'] > 0]
        losses = [abs(t['pnl']) for t in sell_trades if t['pnl'] <= 0]

        avg_profit = np.mean(profits) if profits else 0
        avg_loss = np.mean(losses) if losses else 0
        profit_factor = sum(profits) / sum(losses) if losses and sum(losses) > 0 else 0

        # 夏普比率
        returns = []
        prev = initial_capital
        for _, v in equity_curve[1:]:
            if prev > 0:
                returns.append((v - prev) / prev)
            prev = v
        sharpe = (np.mean(returns) / np.std(returns) * np.sqrt(365)) if returns else 0

        result = BacktestResult.objects.create(
            strategy=strategy,
            start_date=start_date,
            end_date=end_date,
            initial_capital=Decimal(str(initial_capital)),
            final_capital=Decimal(str(final_capital)),
            total_return=Decimal(str(total_return)),
            annual_return=Decimal(str(annual_return)),
            sharpe_ratio=Decimal(str(round(float(sharpe), 4))),
            max_drawdown=Decimal(str(max_dd)),
            win_rate=Decimal(str(win_rate)),
            total_trades=total_trades,
            profit_trades=profit_trades,
            loss_trades=loss_trades,
            avg_profit=Decimal(str(round(float(avg_profit), 4))),
            avg_loss=Decimal(str(round(float(avg_loss), 4))),
            profit_factor=Decimal(str(round(float(profit_factor), 4))),
            equity_curve=[(ts.isoformat(), float(v)) for ts, v in equity_curve],
        )
        logger.info(f'回测完成: 总收益 {total_return:.2%}, 夏普 {sharpe:.2f}, 最大回撤 {max_dd:.2%}')
        return result
