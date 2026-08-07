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

    # ========== 自定义因子 ==========
    @staticmethod
    def _get_custom_factors(strategy: StrategyConfig, user=None) -> List[Dict]:
        """获取用户的启用的自定义因子列表"""
        from apps.strategy.models import FactorDefinition
        qs = FactorDefinition.objects.filter(
            is_active=True, is_custom=True, user=strategy.user
        )
        if not qs.exists():
            return []
        return [
            {'name': f.name, 'formula': f.formula}
            for f in qs if f.formula
        ]

    # ========== 信号生成 ==========
    @staticmethod
    def _calculate_atr(df, atr_len=14):
        """计算 ATR（真实波幅均值），返回与 df 等长的 Series"""
        high = df['high'].astype(float)
        low = df['low'].astype(float)
        close = df['close'].astype(float)
        prev_close = close.shift(1)
        tr1 = high - low
        tr2 = (high - prev_close).abs()
        tr3 = (low - prev_close).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(window=atr_len, min_periods=atr_len).mean()
        return atr

    @staticmethod
    def generate_signals(strategy: StrategyConfig, user=None) -> List[SignalRecord]:
        """为策略的所有标的生成交易信号"""
        if strategy.strategy_type == 'trend_follow':
            return StrategyService._generate_trend_signals(strategy, user=user)
        if strategy.strategy_type == 'volume_breakout':
            return StrategyService._generate_volume_breakout_signals(strategy, user=user)
        return StrategyService._generate_factor_signals(strategy, user=user)

    # ========== 放量跟随策略参数 ==========
    DEFAULT_VOLUME_PARAMS = {
        'vol_ma_len': 20,          # 成交量均线周期
        'vol_ratio': 1.8,          # 放量倍数阈值
        'trend_ma_len': 60,        # 趋势均线(震荡过滤)周期
        'atr_len': 14,             # ATR 周期
        'min_atr_factor': 0.0015,  # 最小波动阈值(占价格比例)
        'cooling_min': 3,          # 同方向信号冷却(分钟)
        'stop_loss_mul': 1.2,      # 止损 = 1.2 × entry_atr
        'tp_mode': 'fixed',        # fixed=固定盈亏比 / trailing=移动止盈
        'tp_ratio': 1.5,           # 固定止盈盈亏比
        'trailing_trigger': 0.5,   # 盈利达 0.5×止损距离 启动移动止盈
        'trailing_factor': 0.8,    # 追踪幅度 = 0.8 × entry_atr
        'enhanced_no_single_pulse': False,  # 增强1：拒绝单根脉冲K
        'risk_per_trade': 0.01,    # 单笔风险比例(账户0.5%~1%)
        'daily_max_stop': 3,       # 单日连续止损次数上限
    }

    @staticmethod
    def _vb_param(strategy, key, default=None):
        """读取放量跟随策略参数，策略 params 优先，其次默认表"""
        val = (strategy.params or {}).get(key, StrategyService.DEFAULT_VOLUME_PARAMS.get(key, default))
        if val is None:
            return default
        return val

    @staticmethod
    def _generate_factor_signals(strategy: StrategyConfig, user=None) -> List[SignalRecord]:
        """基于因子综合评分生成信号"""
        signals = []

        for symbol in strategy.symbols:
            try:
                MarketDataService.fetch_klines(inst_id=symbol, bar=strategy.bar, limit=200, user=user)
                df = MarketDataService.get_klines_df(inst_id=symbol, bar=strategy.bar, limit=200, user=user)

                if df.empty:
                    logger.warning(f'{symbol} 无K线数据，跳过信号生成')
                    continue

                engine = FactorEngine(df)
                # 计算策略因子 + 用户自定义因子
                factor_list = list(strategy.factors or [])
                custom_factors = StrategyService._get_custom_factors(strategy, user=user)
                for cf in custom_factors:
                    engine.set_custom_formula(cf['name'], cf['formula'])
                    factor_list.append(cf['name'])
                engine.calculate_all(factor_list)
                weights = (strategy.factor_weights or {}) if strategy.factor_weights else None
                composite_score, composite_signal = engine.get_composite_score(weights=weights)

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
    def _generate_trend_signals(strategy: StrategyConfig, user=None) -> List[SignalRecord]:
        """基于趋势跟踪生成分钟级买卖信号"""
        signals = []
        client = get_okx_client(user=user)

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
                MarketDataService.fetch_klines(inst_id=symbol, bar=strategy.bar, limit=200, user=user)
                df = MarketDataService.get_klines_df(inst_id=symbol, bar=strategy.bar, limit=200, user=user)

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

    # ========== 放量跟随策略信号 ==========
    @staticmethod
    def _generate_volume_breakout_signals(strategy: StrategyConfig, user=None) -> List[SignalRecord]:
        """放量跟随策略：放量上涨做多 / 放量下跌做空 + 趋势过滤 + ATR过滤 + 冷却 + 强制反向平仓

        适用 ETH/USDT 1min，现货/合约均可。
        """
        from django.db.models import Sum
        from apps.strategy.models import TrackedPosition
        from datetime import timedelta

        signals = []
        client = get_okx_client(user=user)

        vol_ma_len = int(StrategyService._vb_param(strategy, 'vol_ma_len', 20))
        vol_ratio = float(StrategyService._vb_param(strategy, 'vol_ratio', 1.8))
        trend_ma_len = int(StrategyService._vb_param(strategy, 'trend_ma_len', 60))
        atr_len = int(StrategyService._vb_param(strategy, 'atr_len', 14))
        min_atr_factor = float(StrategyService._vb_param(strategy, 'min_atr_factor', 0.0015))
        cooling_min = int(StrategyService._vb_param(strategy, 'cooling_min', 3))
        stop_loss_mul = float(StrategyService._vb_param(strategy, 'stop_loss_mul', 1.2))
        tp_mode = StrategyService._vb_param(strategy, 'tp_mode', 'fixed')
        tp_ratio = float(StrategyService._vb_param(strategy, 'tp_ratio', 1.5))
        enhanced1 = bool(StrategyService._vb_param(strategy, 'enhanced_no_single_pulse', False))
        daily_max_stop = int(StrategyService._vb_param(strategy, 'daily_max_stop', 3))

        # 当前 OKX 持仓（判断多/空方向）
        positions = {}
        try:
            pos_resp = client.get_positions(inst_type=strategy.inst_type)
            if pos_resp.get('code') == '0':
                for p in pos_resp.get('data', []):
                    if float(p.get('pos', 0)) != 0:
                        positions[p['instId']] = p
        except Exception as e:
            logger.warning(f'获取持仓失败: {e}')

        # 当日止损停止：策略级当日累计止损次数达上限则当日不再开仓
        today = timezone.now().date()
        stop_sum = TrackedPosition.objects.filter(
            strategy=strategy, daily_stop_date=today
        ).aggregate(total=Sum('daily_stop_count'))['total'] or 0
        stop_halted = stop_sum >= daily_max_stop

        kline_limit = max(vol_ma_len, trend_ma_len) + atr_len + 10

        for symbol in strategy.symbols:
            try:
                MarketDataService.fetch_klines(inst_id=symbol, bar=strategy.bar, limit=kline_limit, user=user)
                df = MarketDataService.get_klines_df(inst_id=symbol, bar=strategy.bar, limit=kline_limit, user=user)
                if len(df) < trend_ma_len + atr_len:
                    logger.warning(f'{symbol} K线不足，跳过')
                    continue

                close = df['close'].astype(float)
                high = df['high'].astype(float)
                low = df['low'].astype(float)
                vol = df['volume'].astype(float)
                op = df['open'].astype(float)

                vol_ma = vol.rolling(vol_ma_len).mean()
                ma_trend = close.rolling(trend_ma_len).mean()
                atr_series = StrategyService._calculate_atr(df, atr_len)

                cur_vol = float(vol.iloc[-1])
                cur_vol_ma = float(vol_ma.iloc[-1])
                prev_vol = float(vol.iloc[-2])
                cur_atr = float(atr_series.iloc[-1]) if not pd.isna(atr_series.iloc[-1]) else 0.0
                cur_close = float(close.iloc[-1])
                prev_close = float(close.iloc[-2])
                cur_open = float(op.iloc[-1])
                cur_ma = float(ma_trend.iloc[-1])

                # 放量条件
                is_burst = cur_vol_ma > 0 and cur_vol > cur_vol_ma * vol_ratio

                # 增强条件1：前一根成交量 ≥ VOL_MA × 1.2
                prev_burst_ok = True
                if enhanced1:
                    prev_burst_ok = prev_vol >= cur_vol_ma * 1.2

                # K线方向：阳线+收盘创新高 / 阴线+收盘创新低
                is_bull_k = (cur_close > cur_open) and (cur_close > prev_close)
                is_bear_k = (cur_close < cur_open) and (cur_close < prev_close)

                bull_signal = is_burst and is_bull_k and prev_burst_ok
                bear_signal = is_burst and is_bear_k and prev_burst_ok

                # ATR 过滤（震荡屏蔽）
                atr_ok = cur_atr > 0 and cur_atr > min_atr_factor * cur_close

                # 趋势方向过滤（顺着 MA60 大方向）
                above_ma = cur_close > cur_ma
                below_ma = cur_close < cur_ma

                # 当前持仓方向（OKX）
                cur_pos = positions.get(symbol, {})
                pos_side = cur_pos.get('posSide', '')
                has_long = pos_side == 'long' and float(cur_pos.get('pos', 0)) != 0
                has_short = pos_side == 'short' and float(cur_pos.get('pos', 0)) != 0

                # 冷却：距上次同向开仓信号≥cooling_min分钟
                last_buy = SignalRecord.objects.filter(
                    strategy=strategy, inst_id=symbol, signal='buy'
                ).order_by('-created_at').first()
                last_sell = SignalRecord.objects.filter(
                    strategy=strategy, inst_id=symbol, signal='sell'
                ).order_by('-created_at').first()
                cooling_long_ok = (last_buy is None or
                                   (timezone.now() - last_buy.created_at) >= timedelta(minutes=cooling_min))
                cooling_short_ok = (last_sell is None or
                                    (timezone.now() - last_sell.created_at) >= timedelta(minutes=cooling_min))

                # 决策
                signal_type = 'hold'
                reason = ''
                if has_long:
                    if bear_signal:
                        signal_type = 'close_long'
                        reason = '持有多仓 + 触发标准空头放量信号 -> 强制平多(主力出逃)'
                    else:
                        reason = '持有多仓，等待出场'
                elif has_short:
                    if bull_signal:
                        signal_type = 'close_short'
                        reason = '持有空仓 + 触发标准多头放量信号 -> 强制平空(主力出逃)'
                    else:
                        reason = '持有空仓，等待出场'
                else:
                    if stop_halted:
                        reason = f'当日止损已达上限({daily_max_stop}笔)，停止开仓'
                    elif bull_signal and above_ma and atr_ok and cooling_long_ok:
                        signal_type = 'buy'
                        reason = f'放量上涨+顺势(价>MA{trend_ma_len})+ATR过滤+冷却OK'
                    elif bear_signal and below_ma and atr_ok and cooling_short_ok:
                        signal_type = 'sell'
                        reason = f'放量下跌+顺势(价<MA{trend_ma_len})+ATR过滤+冷却OK'
                    else:
                        bits = []
                        if not (bull_signal or bear_signal):
                            bits.append('无放量同向K')
                        if not atr_ok:
                            bits.append('ATR过小/震荡屏蔽')
                        if not (above_ma or below_ma):
                            bits.append('价格缠绕MA')
                        reason = ';'.join(bits) or '条件不满足'

                if signal_type == 'hold':
                    continue

                # 计算入场止损/止盈价
                stop_loss_price = take_profit_price = None
                if signal_type in ('buy', 'sell'):
                    if signal_type == 'buy':
                        sl = cur_close - stop_loss_mul * cur_atr
                        tp = (cur_close + tp_ratio * (cur_close - sl)) if tp_mode == 'fixed' else None
                    else:
                        sl = cur_close + stop_loss_mul * cur_atr
                        tp = (cur_close - tp_ratio * (sl - cur_close)) if tp_mode == 'fixed' else None
                    stop_loss_price = round(sl, 8)
                    take_profit_price = round(tp, 8) if tp else None

                sig = SignalRecord.objects.create(
                    strategy=strategy,
                    inst_id=symbol,
                    signal=signal_type,
                    pos_side=StrategyService._infer_pos_side(signal_type),
                    td_mode=strategy.td_mode,
                    leverage=strategy.leverage,
                    score=Decimal('0.8'),
                    factors_detail={
                        'vol': round(cur_vol, 2),
                        'vol_ma': round(cur_vol_ma, 2),
                        'close': round(cur_close, 4),
                        'ma': round(cur_ma, 4),
                        'atr': round(cur_atr, 8),
                        'bull_signal': bull_signal,
                        'bear_signal': bear_signal,
                        'atr_ok': atr_ok,
                        'above_ma': above_ma,
                    },
                    price=Decimal(str(round(cur_close, 8))),
                    reason=reason,
                    stop_loss_price=Decimal(str(stop_loss_price)) if stop_loss_price else None,
                    take_profit_price=Decimal(str(take_profit_price)) if take_profit_price else None,
                    entry_atr=Decimal(str(round(cur_atr, 8))) if cur_atr else None,
                    tp_mode=tp_mode,
                )
                signals.append(sig)

            except Exception as e:
                logger.error(f'{symbol} 放量跟随信号生成异常: {e}')

        logger.info(f'策略 [{strategy.name}] 生成 {len(signals)} 个放量跟随信号')
        return signals

    # ========== 信号执行 ==========
    @staticmethod
    def execute_signal(signal: SignalRecord, user=None) -> Optional[Dict]:
        """执行单个交易信号（支持合约杠杆）"""
        if signal.is_executed:
            logger.warning(f'信号 #{signal.id} 已执行，跳过')
            return None

        client = get_okx_client(user=user)
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

        current_price = float(signal.price) if signal.price else 0
        if current_price <= 0:
            ticker = client.get_ticker(signal.inst_id)
            if ticker['code'] == '0' and ticker['data']:
                current_price = float(ticker['data'][0]['last'])

        # 仓位大小
        if (strategy.strategy_type == 'volume_breakout'
                and signal.signal in ('buy', 'sell') and signal.stop_loss_price is not None):
            # 风险公式：仓位 = 账户资金 × 风险比例 ÷ (入场价与止损价价差)
            risk_pct = float(StrategyService._vb_param(strategy, 'risk_per_trade', 0.01))
            sl_price = float(signal.stop_loss_price)
            sl_dist = abs(current_price - sl_price)
            if sl_dist <= 0:
                logger.warning(f'信号 #{signal.id} 止损距离为0，跳过')
                return None
            risk_amount = available_usd * risk_pct
            order_value = risk_amount / sl_dist * current_price  # 名义价值
            # 合约保证金保护：名义价值不超过 可用×杠杆
            if td_mode != 'cash':
                order_value = min(order_value, available_usd * leverage * current_price)
        else:
            order_value = available_usd * float(strategy.order_size_pct) * leverage
            order_value = min(order_value, available_usd * leverage)

        if order_value <= 0:
            logger.warning(f'可用余额不足: {available_usd}')
            return None

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
                # 放量跟随：维护持仓跟踪
                StrategyService._sync_tracked_position_after_exec(signal, strategy, td_mode)
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

    # ========== 持仓跟踪与监控（放量跟随出场管理） ==========
    @staticmethod
    def _sync_tracked_position_after_exec(signal: SignalRecord, strategy: StrategyConfig, td_mode: str):
        """信号执行成功后，维护持仓跟踪状态"""
        if strategy.strategy_type != 'volume_breakout':
            return
        from apps.strategy.models import TrackedPosition
        if signal.signal in ('buy', 'sell'):
            side = 'long' if signal.signal == 'buy' else 'short'
            TrackedPosition.objects.update_or_create(
                strategy=strategy, inst_id=signal.inst_id,
                defaults={
                    'side': side,
                    'entry_price': signal.price or Decimal('0'),
                    'entry_atr': signal.entry_atr or Decimal('0'),
                    'stop_loss_price': signal.stop_loss_price or Decimal('0'),
                    'take_profit_price': signal.take_profit_price,
                    'tp_mode': signal.tp_mode or 'fixed',
                    'highest_price': signal.price,
                    'lowest_price': signal.price,
                    'trailing_active': False,
                    'trailing_stop_price': None,
                    'is_open': True,
                    'exit_reason': '',
                },
            )
            logger.info(f'持仓跟踪已创建/更新: {signal.inst_id} {side}')
        elif signal.signal in ('close_long', 'close_short'):
            tp = TrackedPosition.objects.filter(
                strategy=strategy, inst_id=signal.inst_id, is_open=True).first()
            if tp:
                tp.is_open = False
                tp.close_time = timezone.now()
                tp.exit_reason = signal.reason or 'signal'
                tp.save()
                logger.info(f'持仓跟踪已关闭: {signal.inst_id} 原因={tp.exit_reason}')

    @staticmethod
    def monitor_positions_for_strategy(strategy: StrategyConfig):
        """监控放量跟随策略持仓：硬止损 / 固定止盈 / 移动止盈，并统计单日止损"""
        from apps.strategy.models import TrackedPosition
        from datetime import timedelta

        if strategy.strategy_type != 'volume_breakout':
            return
        client = get_okx_client(user=strategy.user)
        trailing_trigger = float(StrategyService._vb_param(strategy, 'trailing_trigger', 0.5))
        trailing_factor = float(StrategyService._vb_param(strategy, 'trailing_factor', 0.8))
        today = timezone.now().date()

        open_positions = TrackedPosition.objects.filter(strategy=strategy, is_open=True)
        for tp in open_positions:
            try:
                MarketDataService.fetch_klines(inst_id=tp.inst_id, bar=strategy.bar, limit=limit, user=strategy.user)
                df = MarketDataService.get_klines_df(inst_id=tp.inst_id, bar=strategy.bar, limit=limit, user=strategy.user)
                if df.empty:
                    continue
                cur_price = float(df['close'].iloc[-1])
                cur_high = float(df['high'].iloc[-1])
                cur_low = float(df['low'].iloc[-1])

                if tp.highest_price is None or cur_high > float(tp.highest_price):
                    tp.highest_price = Decimal(str(cur_high))
                if tp.lowest_price is None or cur_low < float(tp.lowest_price):
                    tp.lowest_price = Decimal(str(cur_low))

                sl = float(tp.stop_loss_price)
                entry = float(tp.entry_price)
                sl_dist = abs(entry - sl)

                triggered = False
                exit_reason = ''
                if tp.side == 'long':
                    if cur_price <= sl:
                        triggered = True
                        exit_reason = 'stop_loss'
                    elif tp.tp_mode == 'fixed' and tp.take_profit_price and cur_price >= float(tp.take_profit_price):
                        triggered = True
                        exit_reason = 'take_profit'
                    elif tp.tp_mode == 'trailing':
                        if cur_price - entry >= trailing_trigger * sl_dist:
                            tp.trailing_active = True
                        if tp.trailing_active:
                            trail = float(tp.highest_price) - trailing_factor * float(tp.entry_atr)
                            tp.trailing_stop_price = Decimal(str(round(trail, 8)))
                            if cur_price <= trail:
                                triggered = True
                                exit_reason = 'trailing_stop'
                else:  # short
                    if cur_price >= sl:
                        triggered = True
                        exit_reason = 'stop_loss'
                    elif tp.tp_mode == 'fixed' and tp.take_profit_price and cur_price <= float(tp.take_profit_price):
                        triggered = True
                        exit_reason = 'take_profit'
                    elif tp.tp_mode == 'trailing':
                        if entry - cur_price >= trailing_trigger * sl_dist:
                            tp.trailing_active = True
                        if tp.trailing_active:
                            trail = float(tp.lowest_price) + trailing_factor * float(tp.entry_atr)
                            tp.trailing_stop_price = Decimal(str(round(trail, 8)))
                            if cur_price >= trail:
                                triggered = True
                                exit_reason = 'trailing_stop'

                # 校验 OKX 实际持仓是否还存在（防止手动平仓导致跟踪漂移）
                try:
                    pos_resp = client.get_positions(inst_type=strategy.inst_type)
                    all_pos = pos_resp.get('data', []) if pos_resp.get('code') == '0' else []
                    matching = [p for p in all_pos if p.get('instId') == tp.inst_id
                                and float(p.get('pos', 0)) != 0
                                and ((tp.side == 'long' and p.get('posSide') == 'long')
                                     or (tp.side == 'short' and p.get('posSide') == 'short'))]
                    if not matching:
                        tp.is_open = False
                        tp.close_time = timezone.now()
                        tp.exit_reason = 'external_closed'
                        tp.save()
                        continue
                    sz = str(abs(float(matching[0].get('pos', 0))))
                except Exception as e:
                    logger.warning(f'检查持仓异常: {e}')
                    tp.save()
                    continue

                tp.save()

                if triggered:
                    side = 'sell' if tp.side == 'long' else 'buy'
                    pos_side = tp.side
                    try:
                        result = client.place_order(
                            inst_id=tp.inst_id, td_mode=strategy.td_mode,
                            side=side, pos_side=pos_side, ord_type='market', sz=sz,
                        )
                        if result.get('code') == '0':
                            tp.is_open = False
                            tp.close_time = timezone.now()
                            tp.exit_reason = exit_reason
                            # 单日止损统计
                            if exit_reason == 'stop_loss':
                                if tp.daily_stop_date != today:
                                    tp.daily_stop_count = 0
                                    tp.daily_stop_date = today
                                tp.daily_stop_count += 1
                            tp.save()
                            SignalRecord.objects.create(
                                strategy=strategy, inst_id=tp.inst_id,
                                signal='close_long' if tp.side == 'long' else 'close_short',
                                pos_side=pos_side, td_mode=strategy.td_mode,
                                leverage=strategy.leverage, score=Decimal('0.5'),
                                price=Decimal(str(cur_price)),
                                reason=f'监控触发出场: {exit_reason}',
                                is_executed=True,
                            )
                            logger.info(f'监控平仓成功: {tp.inst_id} {tp.side} 原因={exit_reason} '
                                        f'止损计数={tp.daily_stop_count}')
                    except Exception as e:
                        logger.error(f'监控平仓失败: {tp.inst_id} {e}')
            except Exception as e:
                logger.error(f'监控持仓 {tp.inst_id} 异常: {e}')

    @staticmethod
    def monitor_all_active_strategies():
        """监控所有活跃的放量跟随策略持仓"""
        from apps.strategy.models import StrategyConfig
        for strategy in StrategyConfig.objects.filter(status='active', strategy_type='volume_breakout'):
            try:
                StrategyService.monitor_positions_for_strategy(strategy)
            except Exception as e:
                logger.error(f'监控策略 [{strategy.name}] 失败: {e}')


    # ========== 回测 ==========
    @staticmethod
    def run_backtest(strategy: StrategyConfig,
                     start_date: datetime, end_date: datetime, user=None) -> BacktestResult:
        """简单回测引擎（基于历史K线）"""
        from apps.market.models import KLine
        from apps.account.models import SystemConfig
        import numpy as np

        env = SystemConfig.get_config(user=user).active_environment

        # 一次性载入回测区间全部K线到内存（避免逐根K线查库的性能瓶颈）
        import pandas as pd
        all_klines = list(
            KLine.objects.select_related('instrument').filter(
                environment=env,
                instrument__inst_id__in=strategy.symbols,
                bar=strategy.bar,
                timestamp__gte=start_date,
                timestamp__lte=end_date,
            ).order_by('timestamp')
        )
        if not all_klines:
            raise StrategyError('回测区间内无K线数据')

        # 按品种分组构建 DataFrame 缓存 {symbol: DataFrame(index=timestamp)}
        from collections import defaultdict
        symbol_rows = defaultdict(list)
        for k in all_klines:
            symbol_rows[k.instrument.inst_id].append({
                'timestamp': k.timestamp,
                'open': float(k.open), 'high': float(k.high),
                'low': float(k.low), 'close': float(k.close),
                'volume': float(k.vol),
            })
        df_cache = {}
        for sym, rows in symbol_rows.items():
            sym_df = pd.DataFrame(rows).set_index('timestamp')
            df_cache[sym] = sym_df

        capital = float(strategy.initial_capital)
        initial_capital = capital
        equity_curve = [(start_date, capital)]
        trades_log = []

        # 按时间分组（保持时间有序）
        all_klines.sort(key=lambda k: k.timestamp)
        from itertools import groupby
        grouped = groupby(all_klines, key=lambda k: k.timestamp)

        factor_lookback = 200  # 因子计算窗口

        for timestamp, klines_group in grouped:
            # 每根K线评估一次信号
            for kline in klines_group:
                sym = kline.instrument.inst_id
                sym_df = df_cache.get(sym)
                if sym_df is None or sym_df.empty:
                    continue

                # 从内存切片该时间点前的数据（最后 factor_lookback 根）
                df = sym_df.loc[:timestamp].iloc[-factor_lookback:]
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

    # ========== 策略参数优化器（网格搜索） ==========
    @staticmethod
    def optimize_params(strategy: StrategyConfig,
                        start_date: datetime, end_date: datetime,
                        param_grid: Dict[str, list], user=None) -> List[Dict]:
        """网格搜索策略参数，返回按目标指标排序的结果列表。
        仅对放量跟随策略的可调参数做网格搜索（或传入任意 params 键）。
        """
        from apps.strategy.models import BacktestResult

        base_params = dict(strategy.params or {})
        keys = list(param_grid.keys())
        results = []

        # 生成网格组合
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
            # 临时修改策略参数并回测
            strategy.params = {**base_params, **combo}
            try:
                bt = StrategyService.run_backtest(
                    strategy, start_date=start_date, end_date=end_date, user=user
                )
                # 清理临时回测记录，只保留最佳
                bt.delete()
                results.append({
                    'params': combo,
                    'total_return': float(bt.total_return),
                    'sharpe_ratio': float(bt.sharpe_ratio or 0),
                    'max_drawdown': float(bt.max_drawdown),
                    'win_rate': float(bt.win_rate),
                    'total_trades': bt.total_trades,
                })
            except Exception as e:
                logger.warning(f'参数组合 {combo} 回测失败: {e}')
            finally:
                strategy.params = base_params

        # 按夏普比率降序，其次按收益
        results.sort(key=lambda r: (r['sharpe_ratio'], r['total_return']), reverse=True)
        return results[:50]

    # ========== 因子权重自动优化 ==========
    @staticmethod
    def optimize_factor_weights(strategy: StrategyConfig,
                                start_date: datetime, end_date: datetime,
                                user=None, iterations: int = 10) -> Dict:
        """基于回测结果自动优化因子权重（模拟退火简化版/随机爬山）"""
        import random

        factors = list(strategy.factors or [])
        if len(factors) < 2:
            return {'error': '至少需要2个因子才能优化权重'}

        def _score(weights: Dict) -> float:
            strategy.factor_weights = weights
            try:
                bt = StrategyService.run_backtest(
                    strategy, start_date=start_date, end_date=end_date, user=user
                )
                bt.delete()
                return float(bt.sharpe_ratio or 0) * 10 + float(bt.total_return) * 2
            except Exception:
                return float('-inf')
            finally:
                strategy.factor_weights = None

        best_weights = {f: 1.0 / len(factors) for f in factors}
        best_score = _score(best_weights)

        for i in range(iterations):
            # 随机扰动
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

    # ========== 多策略组合回测 ==========
    @staticmethod
    def run_portfolio_backtest(portfolio, start_date: datetime, end_date: datetime,
                               user=None) -> Dict:
        """组合回测：按权重分配资金给各策略独立回测，聚合权益曲线"""
        from apps.strategy.models import StrategyConfig, BacktestResult

        items = portfolio.strategies or []
        if not items:
            raise StrategyError('组合内无策略')

        total_weight = sum(float(i.get('weight', 0)) for i in items)
        if total_weight <= 0:
            raise StrategyError('组合权重总和需大于0')

        initial_capital = float(portfolio.initial_capital)
        curves = []  # (strategy_name, weight, equity_curve)
        for item in items:
            strategy = StrategyConfig.objects.filter(
                id=item.get('strategy_id'), user=user
            ).first()
            if not strategy:
                continue
            weight = float(item.get('weight', 0)) / total_weight
            try:
                bt = StrategyService.run_backtest(
                    strategy, start_date=start_date, end_date=end_date, user=user
                )
                curves.append({
                    'strategy_id': strategy.id,
                    'name': strategy.name,
                    'weight': weight,
                    'equity_curve': bt.equity_curve,
                    'total_return': float(bt.total_return),
                    'sharpe_ratio': float(bt.sharpe_ratio or 0),
                    'max_drawdown': float(bt.max_drawdown),
                })
            except Exception as e:
                logger.warning(f'组合成员 {strategy.name} 回测失败: {e}')

        if not curves:
            raise StrategyError('组合回测无有效结果')

        # 聚合权益曲线：按时间对齐
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

    # ========== 策略对比分析 ==========
    @staticmethod
    def compare_strategies(strategy_ids: List[int], start_date: datetime, end_date: datetime,
                           user=None) -> List[Dict]:
        """多策略回测结果对比"""
        from apps.strategy.models import StrategyConfig

        results = []
        strategies = StrategyConfig.objects.filter(id__in=strategy_ids, user=user)
        for strategy in strategies:
            try:
                bt = StrategyService.run_backtest(
                    strategy, start_date=start_date, end_date=end_date, user=user
                )
                results.append({
                    'strategy_id': strategy.id,
                    'name': strategy.name,
                    'strategy_type': strategy.strategy_type,
                    'symbols': strategy.symbols,
                    'total_return': float(bt.total_return),
                    'annual_return': float(bt.annual_return or 0),
                    'sharpe_ratio': float(bt.sharpe_ratio or 0),
                    'max_drawdown': float(bt.max_drawdown),
                    'win_rate': float(bt.win_rate),
                    'total_trades': bt.total_trades,
                    'profit_factor': float(bt.profit_factor or 0),
                    'equity_curve': bt.equity_curve,
                })
            except Exception as e:
                results.append({
                    'strategy_id': strategy.id,
                    'name': strategy.name,
                    'error': str(e),
                })
        return results
