"""
通用回测引擎

与具体策略解耦：通过策略实例（BaseStrategy）的 generate_signal() 生成信号，
引擎负责成交撮合、持仓状态机、按当前价格估值（mark-to-market）、指标统计。

任何注册到 registry 的策略都自动支持回测，无需额外代码。
"""

import logging
from collections import defaultdict
from datetime import datetime
from itertools import groupby

import numpy as np
import pandas as pd

from apps.market.models import KLine
from apps.account.models import SystemConfig
from apps.strategy.registry import registry
from core.exceptions import StrategyError

logger = logging.getLogger(__name__)


class BacktestEngine:
    """通用回测引擎"""

    def __init__(self, strategy_config, user=None,
                 fee_rate: float = 0.001, slippage: float = 0.001,
                 lookback: int = 300):
        self.config = strategy_config
        self.user = user
        self.fee_rate = fee_rate
        self.slippage = slippage
        self.lookback = lookback  # 单次传入策略的最大K线数
        self.strategy_impl = None

    # ---------- 主入口 ----------
    def run(self, start_date: datetime, end_date: datetime) -> dict:
        """执行回测，返回指标字典（由调用方持久化到 BacktestResult）"""
        # 加载策略实现
        impl_cls = registry.get(self.config.strategy_type)
        if impl_cls is None:
            raise StrategyError(f'未注册的策略类型: {self.config.strategy_type}')
        self.strategy_impl = impl_cls(self.config)

        env = SystemConfig.get_config(user=self.user).active_environment
        all_klines = list(
            KLine.objects.select_related('instrument').filter(
                environment=env,
                instrument__inst_id__in=self.config.symbols,
                bar=self.config.bar,
                timestamp__gte=start_date,
                timestamp__lte=end_date,
            ).order_by('timestamp')
        )
        if not all_klines:
            raise StrategyError('回测区间内无K线数据')

        # 构建 DataFrame 缓存 {symbol: DataFrame}
        df_cache = self._build_df_cache(all_klines)

        capital = float(self.config.initial_capital)
        initial_capital = capital
        equity_curve = [(start_date, capital)]
        trades_log = []
        positions = {}  # sym -> {'side', 'price', 'amount', 'fee'}
        latest_close = {}

        grouped = groupby(all_klines, key=lambda k: k.timestamp)

        for timestamp, klines_group in grouped:
            for kline in klines_group:
                sym = kline.instrument.inst_id
                latest_close[sym] = float(kline.close)
                df = df_cache.get(sym)
                if df is None or df.empty:
                    continue

                # 当前时间点前的数据切片（因子/指标窗口）
                window = df.loc[:timestamp].iloc[-self.lookback:]
                if len(window) < self.strategy_impl.MIN_BARS:
                    continue

                # 调用策略信号函数（回测不检查冷却，不依赖外部状态）
                sig = self.strategy_impl.generate_signal(
                    window, sym, position=positions.get(sym),
                    context={'check_cooling': False, 'user': self.user,
                             'custom_factors': self._custom_factors()},
                )
                action = self._resolve_action(sig.signal, positions.get(sym))
                if action is None:
                    continue

                base_price = float(kline.close)
                if action in ('open_long', 'close_short'):
                    price = base_price * (1 + self.slippage)
                else:
                    price = base_price * (1 - self.slippage)

                if action in ('open_long', 'open_short'):
                    amount = capital * float(self.config.order_size_pct)
                    fee = amount * self.fee_rate
                    if amount + fee > capital:
                        continue
                    capital -= (amount + fee)
                    positions[sym] = {
                        'side': 'long' if action == 'open_long' else 'short',
                        'price': price, 'amount': amount, 'fee': fee,
                    }
                    trades_log.append({
                        'timestamp': timestamp, 'symbol': sym,
                        'action': 'buy' if action == 'open_long' else 'sell',
                        'price': price, 'amount': amount, 'fee': fee,
                        'capital': capital,
                    })
                else:
                    entry = positions[sym]
                    if action == 'close_long':
                        proceeds = entry['amount'] * (price / entry['price'])
                        fee = proceeds * self.fee_rate
                        pnl = proceeds - entry['amount'] - fee - entry['fee']
                        capital += (proceeds - fee)
                    else:  # close_short
                        cost = entry['amount'] * (price / entry['price'])
                        fee = cost * self.fee_rate
                        pnl = entry['amount'] - cost - fee - entry['fee']
                        capital += (2 * entry['amount'] - cost - fee)
                    positions.pop(sym, None)
                    trades_log.append({
                        'timestamp': timestamp, 'symbol': sym,
                        'action': 'buy' if action == 'close_short' else 'sell',
                        'price': price, 'pnl': pnl, 'fee': fee,
                        'capital': capital,
                    })

            equity_curve.append((timestamp, self._mark_to_market(capital, positions, latest_close)))

        # 回测结束：未平仓持仓按最后价格强制结算
        for sym, pos in list(positions.items()):
            self._force_close(sym, pos, df_cache, end_date, trades_log, capital)

        # 计算指标
        metrics = self._compute_metrics(
            initial_capital, capital, equity_curve, trades_log,
            start_date, end_date, self.fee_rate, self.slippage,
        )
        metrics['equity_curve'] = [
            (ts.isoformat(), float(v)) for ts, v in equity_curve
        ]
        metrics['trade_detail'] = [
            {**t,
             'timestamp': t['timestamp'].isoformat()
             if hasattr(t['timestamp'], 'isoformat') else str(t['timestamp'])}
            for t in trades_log
        ]
        return metrics

    # ---------- 内部工具 ----------
    @staticmethod
    def _build_df_cache(all_klines) -> dict:
        symbol_rows = defaultdict(list)
        for k in all_klines:
            symbol_rows[k.instrument.inst_id].append({
                'timestamp': k.timestamp,
                'open': float(k.open), 'high': float(k.high),
                'low': float(k.low), 'close': float(k.close),
                'volume': float(k.vol),
            })
        cache = {}
        for sym, rows in symbol_rows.items():
            cache[sym] = pd.DataFrame(rows).set_index('timestamp')
        return cache

    def _custom_factors(self) -> list:
        """用户的自定义因子列表"""
        from apps.strategy.models import FactorDefinition
        if self.config.strategy_type != 'factor_composite':
            return []
        return [
            {'name': f.name, 'formula': f.formula}
            for f in FactorDefinition.objects.filter(
                is_active=True, is_custom=True, user=self.config.user
            ) if f.formula
        ]

    @staticmethod
    def _resolve_action(signal: str, position) -> str:
        """信号 -> 交易动作（方向由策略 filter_by_direction 保证，平仓不受限）"""
        cur_side = position['side'] if position else None
        if signal == 'buy':
            if cur_side == 'short':
                return 'close_short'
            if cur_side is None:
                return 'open_long'
        elif signal == 'sell':
            if cur_side == 'long':
                return 'close_long'
            if cur_side is None:
                return 'open_short'
        elif signal == 'close_long' and cur_side == 'long':
            return 'close_long'
        elif signal == 'close_short' and cur_side == 'short':
            return 'close_short'
        return None

    @staticmethod
    def _mark_to_market(cash, pos_map, latest_close) -> float:
        """总权益 = 现金 + 持仓按当前价格估值"""
        equity = cash
        for sym, pos in pos_map.items():
            cur = latest_close.get(sym, pos['price'])
            if pos['side'] == 'long':
                equity += pos['amount'] * (cur / pos['price'])
            else:
                equity += pos['amount'] * (2 - cur / pos['price'])
        return equity

    def _force_close(self, sym, pos, df_cache, end_date, trades_log, capital):
        """回测结束时强制平仓（按最后价格结算）"""
        sym_df = df_cache.get(sym)
        if sym_df is not None and not sym_df.empty:
            last_close = float(sym_df.iloc[-1]['close'])
        else:
            last_close = pos['price']
        price = last_close * (1 - self.slippage) if pos['side'] == 'long' \
            else last_close * (1 + self.slippage)
        if pos['side'] == 'long':
            proceeds = pos['amount'] * (price / pos['price'])
            fee = proceeds * self.fee_rate
            pnl = proceeds - pos['amount'] - fee - pos['fee']
            capital[0] += (proceeds - fee)  # 通过 list 引用修改外部变量
        else:
            cost = pos['amount'] * (price / pos['price'])
            fee = cost * self.fee_rate
            pnl = pos['amount'] - cost - fee - pos['fee']
            capital[0] += (2 * pos['amount'] - cost - fee)
        trades_log.append({
            'timestamp': end_date, 'symbol': sym,
            'action': 'buy' if pos['side'] == 'short' else 'sell',
            'price': price, 'pnl': pnl, 'fee': fee,
            'capital': capital[0], 'forced': True,
        })

    @staticmethod
    def _compute_metrics(initial_capital, final_capital, equity_curve, trades_log,
                         start_date, end_date, fee_rate, slippage) -> dict:
        """计算回测核心指标"""
        total_return = (final_capital - initial_capital) / initial_capital if initial_capital > 0 else 0
        days = max((end_date - start_date).days, 1)
        annual_return = (1 + total_return) ** (365 / days) - 1 if days > 0 else 0

        equity_values = [v for _, v in equity_curve]
        peak = equity_values[0]
        max_dd = 0
        for v in equity_values:
            if v > peak:
                peak = v
            dd = (peak - v) / peak if peak > 0 else 0
            max_dd = max(max_dd, dd)

        close_trades = [t for t in trades_log if t.get('pnl') is not None]
        total_trades = len(close_trades)
        profit_trades = sum(1 for t in close_trades if t['pnl'] > 0)
        loss_trades = sum(1 for t in close_trades if t['pnl'] <= 0)
        win_rate = profit_trades / len(close_trades) if close_trades else 0

        profits = [t['pnl'] for t in close_trades if t['pnl'] > 0]
        losses = [abs(t['pnl']) for t in close_trades if t['pnl'] <= 0]
        avg_profit = float(np.mean(profits)) if profits else 0
        avg_loss = float(np.mean(losses)) if losses else 0
        profit_factor = sum(profits) / sum(losses) if losses and sum(losses) > 0 else 0

        returns = []
        prev = initial_capital
        for _, v in equity_curve[1:]:
            if prev > 0:
                returns.append((v - prev) / prev)
            prev = v
        if returns and np.std(returns) > 0:
            sharpe = float(np.mean(returns) / np.std(returns) * np.sqrt(365))
        else:
            sharpe = 0

        return {
            'initial_capital': initial_capital,
            'final_capital': final_capital,
            'total_return': total_return,
            'annual_return': annual_return,
            'sharpe_ratio': sharpe,
            'max_drawdown': max_dd,
            'win_rate': win_rate,
            'total_trades': total_trades,
            'profit_trades': profit_trades,
            'loss_trades': loss_trades,
            'avg_profit': avg_profit,
            'avg_loss': avg_loss,
            'profit_factor': profit_factor,
            'fee_rate': fee_rate,
            'slippage': slippage,
        }
