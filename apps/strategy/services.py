"""
策略服务门面层

对外提供统一的策略服务接口，内部委托给：
- 策略注册表（registry）与策略实现（strategies/）
- 通用回测引擎（backtest_engine）
- 分析功能（analysis）

新增策略无需修改本文件，只需在 strategies/ 下实现并注册。
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from django.db import transaction

from apps.market.models import Instrument
from apps.market.services import MarketDataService
from apps.strategy.models import StrategyConfig, SignalRecord, BacktestResult
from apps.strategy.registry import registry
from core.okx_client import get_okx_client
from core.exceptions import StrategyError

logger = logging.getLogger(__name__)


def _safe_push_signal(signal, user=None):
    """信号通知推送（失败不影响主流程）。"""
    try:
        from apps.notifications.services import NotificationService
        NotificationService.from_signal(signal, user=user)
    except Exception as exc:  # pragma: no cover - 防御性
        logger.warning(f'推送信号通知失败: {exc}', exc_info=False)


class StrategyService:
    """策略服务门面"""

    # ========== 策略注册表访问 ==========
    @staticmethod
    def get_strategy_impl(strategy: StrategyConfig):
        """获取策略实现实例（按 strategy_type 分发）"""
        return registry.get_or_error(strategy.strategy_type)(strategy)

    @staticmethod
    def strategy_meta_list() -> List[Dict]:
        """所有已注册策略的元信息（前端下拉与动态参数表单）"""
        return registry.meta_list()

    # ========== 信号生成（统一入口，按注册表分发） ==========
    @staticmethod
    def generate_signals(strategy: StrategyConfig, user=None) -> List[SignalRecord]:
        """为策略的所有标的生成交易信号（按注册表分发到具体策略实现）"""
        impl = StrategyService.get_strategy_impl(strategy)
        signals = []

        for symbol in strategy.symbols:
            try:
                # DB 优先读取，数据不足时后台异步补齐（不阻塞）
                df = MarketDataService.get_klines_cached(
                    inst_id=symbol, bar=strategy.bar, limit=200,
                    min_required=impl.MIN_BARS, user=user,
                )
                if df.empty or len(df) < impl.MIN_BARS:
                    logger.warning(f'{symbol} K线数据不足({len(df)}<{impl.MIN_BARS})，跳过信号生成')
                    continue

                # 实时持仓（判断平仓）
                position = StrategyService._current_position(strategy, symbol, user)

                # 自定义因子（仅因子策略使用）
                custom_factors = StrategyService._get_custom_factors(strategy, user=user)

                sig = impl.generate_signal(
                    df, symbol, position=position,
                    context={'check_cooling': True, 'user': user,
                             'custom_factors': custom_factors},
                )
                if sig.is_hold:
                    continue

                # 方向过滤：只约束开仓，平仓不受限
                final_signal = impl.filter_by_direction(sig.signal)

                # 现货不支持做空：无持仓时 sell（开空）信号必须被抑制，
                # 只有已有持仓时才允许卖出（平多）
                if StrategyService._is_spot(strategy):
                    if final_signal == 'sell' and not (position and position.get('side') == 'long'):
                        logger.info(f'现货 {symbol} 无持仓，抑制做空信号 sell')
                        continue
                    if final_signal in ('close_long', 'close_short'):
                        if final_signal == 'close_short' or not (position and position.get('side') == 'long'):
                            # 现货只有多头持仓，close_short 无意义，无持仓时 close_long 也跳过
                            logger.info(f'现货 {symbol} 无对应持仓，跳过平仓信号 {final_signal}')
                            continue

                current_price = float(df['close'].iloc[-1])
                record = SignalRecord.objects.create(
                    strategy=strategy,
                    inst_id=symbol,
                    signal=final_signal,
                    pos_side=impl.infer_pos_side(final_signal),
                    td_mode=strategy.td_mode,
                    leverage=strategy.leverage,
                    score=__import__('decimal').Decimal(str(round(sig.score, 4))),
                    factors_detail=sig.detail,
                    price=__import__('decimal').Decimal(str(round(current_price, 4))),
                    reason=sig.reason,
                    stop_loss_price=sig.stop_loss_price,
                    take_profit_price=sig.take_profit_price,
                    entry_atr=sig.entry_atr,
                    tp_mode=sig.tp_mode,
                )
                signals.append(record)
                _safe_push_signal(record, user=user)
            except Exception as e:
                logger.error(f'{symbol} 信号生成异常: {e}')

        logger.info(f'策略 [{strategy.name}] 生成 {len(signals)} 个信号')
        return signals

    @staticmethod
    def _is_spot(strategy: StrategyConfig, td_mode: str = '') -> bool:
        """判断是否为现货交易（现货：td_mode=cash 或 inst_type=SPOT）"""
        mode = (td_mode or strategy.td_mode or '').lower()
        inst_type = (strategy.inst_type or '').upper()
        return mode == 'cash' or inst_type == 'SPOT'

    @staticmethod
    def _current_position(strategy: StrategyConfig, symbol: str, user=None) -> Optional[Dict]:
        """查询当前持仓状态（用于平仓/防重复开仓判断）。

        优先取 OKX 实际持仓；若 OKX 无持仓，但最近已有同向开仓信号
        （已执行或待执行），仍视为"持有"该方向，避免反复发同向开仓信号。
        """
        client = get_okx_client(user=user)
        spot = StrategyService._is_spot(strategy)

        try:
            if spot:
                # 现货：持仓 = 账户中该币种余额（现货无 get_positions 概念）
                balance = client.get_account_balance()
                if balance.get('code') == '0':
                    base_ccy = symbol.split('-')[0] if '-' in symbol else symbol
                    details = balance.get('data', [{}])[0].get('details', [])
                    coin = next((d for d in details if d.get('ccy') == base_ccy), None)
                    if coin:
                        free = float(coin.get('availEq', coin.get('cashBal', 0)) or 0)
                        frozen = float(coin.get('frozenBal', 0) or 0)
                        total = free + frozen
                        if total > 0:
                            return {'side': 'long', 'pos': total,
                                    'avail': free, 'spot': True}
            else:
                # 合约：用 OKX 持仓接口
                pos_resp = client.get_positions(inst_type=strategy.inst_type)
                if pos_resp.get('code') == '0':
                    for p in pos_resp.get('data', []):
                        if p.get('instId') == symbol and float(p.get('pos', 0)) != 0:
                            return {'side': p.get('posSide'), 'pos': abs(float(p.get('pos', 0)))}
        except Exception as e:
            logger.warning(f'获取持仓失败: {e}')

        # 最近的开仓信号视为"虚拟持仓"（防重复开仓）
        from apps.strategy.models import SignalRecord
        from django.utils import timezone
        from datetime import timedelta
        recent = SignalRecord.objects.filter(
            strategy=strategy, inst_id=symbol,
            created_at__gte=timezone.now() - timedelta(hours=2),
        ).order_by('-created_at').first()
        if recent and recent.signal in ('buy', 'sell') and not recent.is_executed:
            return {'side': 'long' if recent.signal == 'buy' else 'short',
                    'pos': 0, 'pending': True}
        return None

    @staticmethod
    def _get_custom_factors(strategy: StrategyConfig, user=None) -> List[Dict]:
        """获取用户的启用的自定义因子列表"""
        from apps.strategy.models import FactorDefinition
        qs = FactorDefinition.objects.filter(
            is_active=True, is_custom=True, user=strategy.user
        )
        if not qs.exists():
            return []
        return [{'name': f.name, 'formula': f.formula} for f in qs if f.formula]

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

        if td_mode in ('cross', 'isolated'):
            try:
                client.set_leverage(
                    lever=str(int(leverage)), mgn_mode=td_mode, inst_id=signal.inst_id,
                )
            except Exception as e:
                logger.warning(f'设置杠杆失败（可能已设置）: {e}')

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

        # 仓位大小：有止损价的开仓信号用风险公式，其余按比例
        impl = StrategyService.get_strategy_impl(strategy)
        if signal.signal in ('buy', 'sell') and signal.stop_loss_price is not None:
            risk_pct = float(impl.param('risk_per_trade', 0.01))
            sl_price = float(signal.stop_loss_price)
            sl_dist = abs(current_price - sl_price)
            if sl_dist <= 0:
                logger.warning(f'信号 #{signal.id} 止损距离为0，跳过')
                return None
            risk_amount = available_usd * risk_pct
            order_value = risk_amount / sl_dist * current_price
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

        # ===== 现货风控：不能没仓位就卖；只有合约才可以开空 =====
        is_spot = StrategyService._is_spot(strategy, td_mode)
        tgt_ccy = ''
        if is_spot:
            # 现货做空（无持仓的 sell）一律拒绝
            if signal.signal == 'sell':
                logger.warning(f'现货 {signal.inst_id} 不能做空，拒绝执行信号 #{signal.id}')
                return None
            # 现货平多（close_long）：必须有持仓，且卖出数量不超过持仓
            if signal.signal in ('close_long', 'sell'):
                spot_pos = StrategyService._current_position(strategy, signal.inst_id, user)
                if not spot_pos or spot_pos.get('side') != 'long':
                    logger.warning(f'现货 {signal.inst_id} 无持仓，拒绝卖出')
                    return None
                # 卖出数量 = 持仓数量（市价全平），不传 posSide
                sz = str(round(float(spot_pos.get('pos')), 6))
            else:
                # 现货市价买单：sz 需按计价币金额（tgtCcy=quote_ccy）
                try:
                    ticker = client.get_ticker(signal.inst_id)
                    if ticker.get('code') == '0' and ticker.get('data'):
                        last = float(ticker['data'][0]['last'])
                        if last > 0:
                            sz = str(round(float(sz) * last, 6))
                            tgt_ccy = 'quote_ccy'
                except Exception as e:
                    logger.warning(f'现货市价买单换算金额失败: {e}')
            pos_side = ''  # 现货不传 posSide

        # 现货订单不传 client_oid：OKX 现货对 clOrdId 校验严格（卖单常报 51000）
        submit_cl_oid = '' if is_spot else f'qt{signal.id}'
        # 合约单向持仓(net_mode)：不传 posSide，平仓信号用 reduceOnly
        submit_pos_side = ''
        reduce_only = False
        if not is_spot:
            if signal.signal in ('close_long', 'close_short'):
                reduce_only = True
        try:
            result = client.place_order(
                inst_id=signal.inst_id, td_mode=td_mode, side=side,
                pos_side=submit_pos_side, ord_type='market', sz=sz,
                tgt_ccy=tgt_ccy, reduce_only=reduce_only,
                client_oid=submit_cl_oid,
            )
            if result['code'] == '0':
                signal.is_executed = True
                signal.save(update_fields=['is_executed'])
                logger.info(f'信号 #{signal.id} 执行成功: {signal.inst_id} {signal.signal} '
                            f'td_mode={td_mode} leverage={leverage}')
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

    # ========== 持仓跟踪（放量跟随出场管理） ==========
    @staticmethod
    def _sync_tracked_position_after_exec(signal: SignalRecord, strategy: StrategyConfig, td_mode: str):
        """信号执行成功后，维护持仓跟踪状态"""
        # 无止损价的开仓信号不创建持仓跟踪；平仓信号仍尝试更新已有持仓
        if signal.signal in ('buy', 'sell') and not signal.stop_loss_price:
            return
        from apps.strategy.models import TrackedPosition
        if signal.signal in ('buy', 'sell'):
            side = 'long' if signal.signal == 'buy' else 'short'
            TrackedPosition.objects.update_or_create(
                strategy=strategy, inst_id=signal.inst_id,
                defaults={
                    'side': side,
                    'entry_price': signal.price or __import__('decimal').Decimal('0'),
                    'entry_atr': signal.entry_atr or __import__('decimal').Decimal('0'),
                    'stop_loss_price': signal.stop_loss_price or __import__('decimal').Decimal('0'),
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
                tp.close_time = __import__('django.utils.timezone', fromlist=['timezone']).timezone.now()
                tp.exit_reason = signal.reason or 'signal'
                tp.save()

    @staticmethod
    def monitor_positions_for_strategy(strategy: StrategyConfig):
        """监控放量跟随策略持仓：硬止损 / 固定止盈 / 移动止盈，并统计单日止损"""
        from apps.strategy.models import TrackedPosition
        from apps.strategy.services import StrategyService as S
        from django.utils import timezone
        from datetime import timedelta

        if not TrackedPosition.objects.filter(strategy=strategy, is_open=True).exists():
            return
        client = get_okx_client(user=strategy.user)
        impl = S.get_strategy_impl(strategy)
        trailing_trigger = float(impl.param('trailing_trigger', 0.5))
        trailing_factor = float(impl.param('trailing_factor', 0.8))
        today = timezone.now().date()

        open_positions = TrackedPosition.objects.filter(strategy=strategy, is_open=True)
        for tp in open_positions:
            try:
                df = MarketDataService.get_klines_cached(
                    inst_id=tp.inst_id, bar=strategy.bar, limit=100,
                    min_required=60, user=strategy.user,
                )
                if df.empty:
                    continue
                cur_price = float(df['close'].iloc[-1])
                cur_high = float(df['high'].iloc[-1])
                cur_low = float(df['low'].iloc[-1])

                if tp.highest_price is None or cur_high > float(tp.highest_price):
                    tp.highest_price = __import__('decimal').Decimal(str(cur_high))
                if tp.lowest_price is None or cur_low < float(tp.lowest_price):
                    tp.lowest_price = __import__('decimal').Decimal(str(cur_low))

                sl = float(tp.stop_loss_price)
                entry = float(tp.entry_price)
                sl_dist = abs(entry - sl)

                triggered = False
                exit_reason = ''
                if tp.side == 'long':
                    if cur_price <= sl:
                        triggered, exit_reason = True, 'stop_loss'
                    elif tp.tp_mode == 'fixed' and tp.take_profit_price and cur_price >= float(tp.take_profit_price):
                        triggered, exit_reason = True, 'take_profit'
                    elif tp.tp_mode == 'trailing':
                        if cur_price - entry >= trailing_trigger * sl_dist:
                            tp.trailing_active = True
                        if tp.trailing_active:
                            trail = float(tp.highest_price) - trailing_factor * float(tp.entry_atr)
                            tp.trailing_stop_price = __import__('decimal').Decimal(str(round(trail, 8)))
                            if cur_price <= trail:
                                triggered, exit_reason = True, 'trailing_stop'
                else:
                    if cur_price >= sl:
                        triggered, exit_reason = True, 'stop_loss'
                    elif tp.tp_mode == 'fixed' and tp.take_profit_price and cur_price <= float(tp.take_profit_price):
                        triggered, exit_reason = True, 'take_profit'
                    elif tp.tp_mode == 'trailing':
                        if entry - cur_price >= trailing_trigger * sl_dist:
                            tp.trailing_active = True
                        if tp.trailing_active:
                            trail = float(tp.lowest_price) + trailing_factor * float(tp.entry_atr)
                            tp.trailing_stop_price = __import__('decimal').Decimal(str(round(trail, 8)))
                            if cur_price >= trail:
                                triggered, exit_reason = True, 'trailing_stop'

                # 校验 OKX 实际持仓
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
                    try:
                        result = client.place_order(
                            inst_id=tp.inst_id, td_mode=strategy.td_mode,
                            side=side, ord_type='market', sz=sz,
                            reduce_only=True,  # 平仓：单向模式不需要 posSide
                        )
                        if result.get('code') == '0':
                            tp.is_open = False
                            tp.close_time = timezone.now()
                            tp.exit_reason = exit_reason
                            if exit_reason == 'stop_loss':
                                if tp.daily_stop_date != today:
                                    tp.daily_stop_count = 0
                                    tp.daily_stop_date = today
                                tp.daily_stop_count += 1
                            tp.save()
                            close_sig = SignalRecord.objects.create(
                                strategy=strategy, inst_id=tp.inst_id,
                                signal='close_long' if tp.side == 'long' else 'close_short',
                                pos_side=pos_side, td_mode=strategy.td_mode,
                                leverage=strategy.leverage, score=__import__('decimal').Decimal('0.5'),
                                price=__import__('decimal').Decimal(str(cur_price)),
                                reason=f'监控触发出场: {exit_reason}',
                                is_executed=True,
                            )
                            _safe_push_signal(close_sig, user=strategy.user)
                            logger.info(f'监控平仓成功: {tp.inst_id} {tp.side} 原因={exit_reason}')
                    except Exception as e:
                        logger.error(f'监控平仓失败: {tp.inst_id} {e}')
            except Exception as e:
                logger.error(f'监控持仓 {tp.inst_id} 异常: {e}')

    @staticmethod
    def monitor_all_active_strategies():
        """监控所有活跃策略持仓（硬止损 / 固定止盈 / 移动止盈）"""
        for strategy in StrategyConfig.objects.filter(status='active'):
            try:
                StrategyService.monitor_positions_for_strategy(strategy)
            except Exception as e:
                logger.error(f'监控策略 [{strategy.name}] 失败: {e}')

    # ========== 回测（统一入口，委托通用回测引擎） ==========
    @staticmethod
    def run_backtest(strategy: StrategyConfig,
                     start_date: datetime, end_date: datetime, user=None,
                     fee_rate: float = 0.001, slippage: float = 0.001) -> BacktestResult:
        """回测引擎（通用）：调用策略自身信号逻辑，支持手续费/滑点模拟"""
        from apps.strategy.backtest_engine import BacktestEngine
        from decimal import Decimal

        engine = BacktestEngine(strategy, user=user, fee_rate=fee_rate, slippage=slippage)
        m = engine.run(start_date=start_date, end_date=end_date)

        result = BacktestResult.objects.create(
            strategy=strategy,
            start_date=start_date,
            end_date=end_date,
            initial_capital=Decimal(str(m['initial_capital'])),
            final_capital=Decimal(str(m['final_capital'])),
            total_return=Decimal(str(m['total_return'])),
            annual_return=Decimal(str(m['annual_return'])),
            sharpe_ratio=Decimal(str(round(float(m['sharpe_ratio']), 4))),
            max_drawdown=Decimal(str(m['max_drawdown'])),
            win_rate=Decimal(str(m['win_rate'])),
            total_trades=m['total_trades'],
            profit_trades=m['profit_trades'],
            loss_trades=m['loss_trades'],
            avg_profit=Decimal(str(round(float(m['avg_profit']), 4))),
            avg_loss=Decimal(str(round(float(m['avg_loss']), 4))),
            profit_factor=Decimal(str(round(float(m['profit_factor']), 4))),
            equity_curve=m['equity_curve'],
            fee_rate=Decimal(str(fee_rate)),
            slippage=Decimal(str(slippage)),
            trade_detail=m['trade_detail'],
        )
        logger.info(f'回测完成: 总收益 {m["total_return"]:.2%}, '
                    f'夏普 {m["sharpe_ratio"]:.2f}, 最大回撤 {m["max_drawdown"]:.2%}')
        return result

    # ========== 回测报告导出（HTML） ==========
    @staticmethod
    def export_backtest_html(backtest_result: BacktestResult) -> str:
        """生成回测报告 HTML（可直接打印为 PDF）"""
        from datetime import datetime

        curve = backtest_result.equity_curve or []
        curve_rows = ''.join(
            f'<tr><td>{ts[:16].replace("T", " ")}</td><td>{float(v):,.2f}</td></tr>'
            for ts, v in curve[-500:]
        )
        trades = backtest_result.trade_detail or []
        trade_rows = ''.join(
            f'<tr><td>{t.get("timestamp", "")}</td><td>{t.get("symbol", "")}</td>'
            f'<td>{t.get("action", "")}</td><td>{t.get("price", "")}</td>'
            f'<td>{t.get("amount", "")}</td><td>{t.get("pnl", "-")}</td>'
            f'<td>{t.get("fee", "-")}</td></tr>'
            for t in trades[-200:]
        )

        return f"""<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="utf-8">
<title>回测报告 - {backtest_result.strategy.name}</title>
<style>
body {{ font-family: 'Segoe UI', 'Microsoft YaHei', sans-serif; margin: 30px; color: #333; }}
h1 {{ border-bottom: 2px solid #409eff; padding-bottom: 8px; }}
h2 {{ margin-top: 28px; color: #409eff; }}
table {{ border-collapse: collapse; width: 100%; margin-top: 10px; }}
th, td {{ border: 1px solid #ddd; padding: 6px 10px; font-size: 13px; text-align: right; }}
th {{ background: #f5f7fa; }}
.metrics {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-top: 16px; }}
.metric {{ border: 1px solid #ebeef5; border-radius: 8px; padding: 12px; text-align: center; }}
.metric .label {{ color: #909399; font-size: 12px; }}
.metric .value {{ font-size: 20px; font-weight: bold; margin-top: 4px; }}
.positive {{ color: #67c23a; }}
.negative {{ color: #f56c6c; }}
@media print {{ body {{ margin: 10mm; }} }}
</style>
</head>
<body>
<h1>策略回测报告</h1>
<p>策略: <b>{backtest_result.strategy.name}</b> | 类型: {backtest_result.strategy.get_strategy_type_display()}</p>
<p>回测区间: {backtest_result.start_date.strftime('%Y-%m-%d')} ~ {backtest_result.end_date.strftime('%Y-%m-%d')} | 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}</p>

<h2>核心指标</h2>
<div class="metrics">
  <div class="metric"><div class="label">总收益率</div><div class="value {'positive' if float(backtest_result.total_return)>=0 else 'negative'}">{float(backtest_result.total_return)*100:.2f}%</div></div>
  <div class="metric"><div class="label">年化收益率</div><div class="value">{float(backtest_result.annual_return or 0)*100:.2f}%</div></div>
  <div class="metric"><div class="label">夏普比率</div><div class="value">{backtest_result.sharpe_ratio}</div></div>
  <div class="metric"><div class="label">最大回撤</div><div class="value negative">{float(backtest_result.max_drawdown)*100:.2f}%</div></div>
  <div class="metric"><div class="label">胜率</div><div class="value">{float(backtest_result.win_rate)*100:.1f}%</div></div>
  <div class="metric"><div class="label">交易次数</div><div class="value">{backtest_result.total_trades}</div></div>
  <div class="metric"><div class="label">盈亏比</div><div class="value">{backtest_result.profit_factor}</div></div>
  <div class="metric"><div class="label">初始/最终资金</div><div class="value" style="font-size:14px">{backtest_result.initial_capital} → {backtest_result.final_capital}</div></div>
</div>

<h2>权益曲线</h2>
<table>
<tr><th>时间</th><th>权益</th></tr>
{curve_rows}
</table>

<h2>交易明细（最近{min(len(trades),200)}笔）</h2>
<table>
<tr><th>时间</th><th>品种</th><th>方向</th><th>价格</th><th>金额</th><th>盈亏</th><th>手续费</th></tr>
{trade_rows}
</table>

<p style="margin-top:20px;color:#909399;font-size:12px">手续费率 {backtest_result.fee_rate} | 滑点 {backtest_result.slippage}</p>
</body>
</html>"""

    # ========== 分析功能（委托 analysis 模块） ==========
    @staticmethod
    def run_monte_carlo(backtest_result: BacktestResult, n_simulations: int = 1000) -> Dict:
        from apps.strategy.analysis import run_monte_carlo
        return run_monte_carlo(backtest_result.equity_curve or [], n_simulations=n_simulations)

    @staticmethod
    def run_walk_forward(strategy, start_date, end_date, window_days=14, user=None) -> Dict:
        from apps.strategy.analysis import run_walk_forward
        return run_walk_forward(strategy, start_date, end_date, window_days=window_days, user=user)

    @staticmethod
    def optimize_params(strategy, start_date, end_date, param_grid=None, user=None) -> List[Dict]:
        from apps.strategy.analysis import optimize_params
        return optimize_params(strategy, start_date, end_date, param_grid or {}, user=user)

    @staticmethod
    def optimize_factor_weights(strategy, start_date, end_date, user=None, iterations=10) -> Dict:
        from apps.strategy.analysis import optimize_factor_weights
        return optimize_factor_weights(strategy, start_date, end_date, user=user, iterations=iterations)

    @staticmethod
    def run_portfolio_backtest(portfolio, start_date, end_date, user=None) -> Dict:
        from apps.strategy.analysis import run_portfolio_backtest
        return run_portfolio_backtest(portfolio, start_date, end_date, user=user)

    @staticmethod
    def compare_strategies(strategy_ids, start_date, end_date, user=None) -> List[Dict]:
        from apps.strategy.analysis import compare_strategies
        return compare_strategies(strategy_ids, start_date, end_date, user=user)

    @staticmethod
    def run_multi_symbol_backtest(strategy, start_date, end_date, user=None,
                                  fee_rate=0.001, slippage=0.001) -> Dict:
        from apps.strategy.analysis import run_multi_symbol_backtest
        return run_multi_symbol_backtest(strategy, start_date, end_date, user=user,
                                         fee_rate=fee_rate, slippage=slippage)

    @staticmethod
    def strategy_ranking(user=None, limit=10) -> List[Dict]:
        """策略收益排行：按最近回测总收益排序"""
        from django.db.models import Max

        rows = []
        strategies = StrategyConfig.objects.filter(user=user).annotate(
            latest_bt=Max('backtests__created_at')
        )
        for s in strategies:
            bt = s.backtests.order_by('-created_at').first()
            rows.append({
                'id': s.id,
                'name': s.name,
                'strategy_type': s.strategy_type,
                'symbols': s.symbols,
                'status': s.status,
                'latest_return': float(bt.total_return) if bt else None,
                'latest_sharpe': float(bt.sharpe_ratio or 0) if bt else None,
                'backtest_date': bt.created_at.isoformat() if bt else None,
            })
        rows.sort(key=lambda r: (r['latest_return'] is not None, r['latest_return'] or -999), reverse=True)
        return rows[:limit]

    @staticmethod
    def factor_heatmap(user=None, n_signals=200) -> List[Dict]:
        """因子热力图：各策略各因子的平均得分/方向贡献"""
        signals = list(
            SignalRecord.objects.filter(strategy__user=user)
            .order_by('-created_at')[:n_signals]
        )
        if not signals:
            return []

        agg = {}
        for sig in signals:
            detail = sig.factors_detail or {}
            if not isinstance(detail, dict):
                continue
            strategy_key = sig.strategy.name if sig.strategy else 'unknown'
            agg.setdefault(strategy_key, {})
            for factor, score in detail.items():
                try:
                    score = float(score)
                except (TypeError, ValueError):
                    continue
                agg[strategy_key].setdefault(factor, []).append(score)

        result = []
        for strategy_name, factors in agg.items():
            for factor, scores in factors.items():
                result.append({
                    'strategy': strategy_name,
                    'factor': factor,
                    'score': round(sum(scores) / len(scores), 4),
                    'samples': len(scores),
                })
        result.sort(key=lambda r: -r['score'])
        return result

    @staticmethod
    def market_overview(user=None, limit=20) -> List[Dict]:
        """市场概览：涨跌幅排行"""
        from apps.market.models import Ticker
        from apps.account.models import SystemConfig

        env = SystemConfig.get_config(user=user).active_environment
        tickers = Ticker.objects.select_related('instrument').filter(
            instrument__is_active=True
        )[:limit * 2]

        rows = []
        for t in tickers:
            try:
                last = float(t.last)
                open24 = float(t.open_24h) if t.open_24h else 0
            except (TypeError, ValueError):
                continue
            if not last or not open24:
                continue
            change = (last - open24) / open24 * 100
            rows.append({
                'inst_id': t.instrument.inst_id,
                'last': last,
                'change_pct': round(change, 2),
                'vol_24h': float(t.vol_24h) if t.vol_24h else 0,
            })
        rows.sort(key=lambda r: -r['change_pct'])
        return rows[:limit]

    @staticmethod
    def correlation_matrix(symbols, bar='1D', limit=200, user=None) -> Dict:
        from apps.strategy.analysis import correlation_matrix
        return correlation_matrix(symbols, bar=bar, limit=limit, user=user)

    @staticmethod
    def factor_ic_analysis(strategy, bar='1D', lookback=100, user=None) -> Dict:
        from apps.strategy.analysis import factor_ic_analysis
        return factor_ic_analysis(strategy, bar=bar, lookback=lookback, user=user)

    @staticmethod
    def market_state(inst_id, bar='1D', lookback=60, user=None) -> Dict:
        from apps.strategy.analysis import market_state
        return market_state(inst_id, bar=bar, lookback=lookback, user=user)

    # ========== 兼容旧接口（脚本测试使用） ==========
    @staticmethod
    def _generate_volume_breakout_signals(strategy, user=None) -> List[SignalRecord]:
        """兼容脚本测试：调用新的策略实现生成信号"""
        return StrategyService.generate_signals(strategy, user=user)

    @staticmethod
    def _vb_param(strategy, key, default=None):
        """兼容旧调用：读取策略参数"""
        impl = StrategyService.get_strategy_impl(strategy)
        return impl.param(key, default)

    @staticmethod
    def _filter_by_direction(signal, direction):
        """兼容旧调用：方向过滤"""
        if signal in ('close_long', 'close_short', 'hold'):
            return signal
        if direction == 'long':
            return signal if signal in ('buy',) else 'hold'
        if direction == 'short':
            return signal if signal in ('sell',) else 'hold'
        return signal
