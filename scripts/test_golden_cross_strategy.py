"""金叉银叉策略核心逻辑冒烟测试（不依赖真实 OKX 网络）。

通过 mock OKX 持仓查询与行情数据，验证：
1) 多头共振（三档EMA多头排列 + MACD多头 + 放量 + 价在慢线上方） -> buy，止损止盈价方向正确
2) 空头共振（三档EMA空头排列 + MACD空头 + 放量 + 价在慢线下方） -> sell，止损止盈价方向正确
3) 持有多仓 + 触发空头共振 -> 强制平多 close_long
4) 窄幅震荡（无共振） -> 不产生 buy/sell 信号
"""
import os
import sys
import django
import numpy as np
import pandas as pd
from unittest.mock import patch, MagicMock

# 确保项目根目录在 sys.path（脚本位于 scripts/ 下）
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.strategy.services import StrategyService
from apps.strategy.models import StrategyConfig, SignalRecord, TrackedPosition
from apps.market.services import MarketDataService


def make_golden_cross_df(n=150, scenario='bull'):
    """构造三档 EMA 共振场景。

    scenario:
      'bull' - 前80根缓跌（空头排列）+ 后70根急涨（多头排列确立）+ 末根放量
      'bear' - 前80根缓涨（多头排列）+ 后70根急跌（空头排列确立）+ 末根放量
      'flat' - 窄幅震荡，无共振
    """
    if scenario == 'bull':
        base = np.concatenate([
            np.linspace(2100, 2000, 80),   # 下跌段：空头排列
            np.linspace(2000, 2200, 70),   # 急涨段：多头排列确立
        ])
        rng = np.random.RandomState(42)
        close = base + rng.randn(n) * 0.5
        open_ = close - rng.rand(n) * 1.0
        high = np.maximum(close, open_) + 1.0
        low = np.minimum(close, open_) - 1.0
        vol = np.full(n, 100.0)
        # 最后一根放量（>= 均量 × vol_ratio）+ 强方向K线
        vol[-1] = 250.0
        close[-1] = close[-2] + 8.0
        open_[-1] = close[-2]
        high[-1] = close[-1] + 1.0
    elif scenario == 'bear':
        base = np.concatenate([
            np.linspace(2000, 2100, 80),   # 上涨段：多头排列
            np.linspace(2100, 1900, 70),   # 急跌段：空头排列确立
        ])
        rng = np.random.RandomState(42)
        close = base + rng.randn(n) * 0.5
        open_ = close - rng.rand(n) * 1.0
        high = np.maximum(close, open_) + 1.0
        low = np.minimum(close, open_) - 1.0
        vol = np.full(n, 100.0)
        vol[-1] = 250.0
        close[-1] = close[-2] - 8.0
        open_[-1] = close[-2]
        low[-1] = close[-1] - 1.0
    else:  # flat - 完全平稳价格，所有EMA相等，align全False，不产生共振
        close = np.full(n, 2050.0)
        open_ = np.full(n, 2050.0)
        high = np.full(n, 2050.5)
        low = np.full(n, 2049.5)
        vol = np.full(n, 100.0)

    df = pd.DataFrame({
        'open': open_, 'high': high, 'low': low, 'close': close, 'volume': vol,
    })
    df.index = pd.date_range(end=pd.Timestamp.now(), periods=n, freq='1h')
    return df


def build_strategy():
    return StrategyConfig.objects.create(
        name='TEST_GC_SMOKE', strategy_type='golden_cross',
        inst_type='SWAP', bar='1H', symbols=['BTC-USDT-SWAP'],
        params={
            'ema_fast': 5, 'ema_mid': 20, 'ema_slow': 60,
            'macd_fast': 12, 'macd_slow': 26, 'macd_signal': 9,
            'vol_ma_len': 20, 'vol_ratio': 1.5,
            # 测试用较低阈值，确保排列状态即可触发（排列满分约0.50）
            'min_score': 0.40, 'exit_score': 0.35,
            'atr_len': 14, 'stop_loss_mul': 1.5,
            'tp_mode': 'fixed', 'tp_ratio': 2.0,
            'trailing_trigger': 0.8, 'trailing_factor': 0.6,
            'cooling_min': 5, 'daily_max_stop': 3,
        },
        td_mode='cross', leverage=3, status='active', direction='both',
    )


def run_with(strategy, df, positions_data):
    mock_client = MagicMock()
    mock_client.get_positions.return_value = {'code': '0', 'data': positions_data}
    with patch('apps.strategy.services.get_okx_client', return_value=mock_client), \
         patch.object(MarketDataService, 'fetch_klines', return_value=None), \
         patch.object(MarketDataService, 'get_klines_cached', return_value=df):
        return StrategyService.generate_signals(strategy)


def main():
    strategy = build_strategy()
    results = []
    try:
        # 场景1：多头共振 -> buy
        sigs = run_with(strategy, make_golden_cross_df(scenario='bull'), [])
        assert len(sigs) >= 1 and sigs[0].signal == 'buy', \
            f'场景1失败: {[(s.signal, s.reason) for s in sigs]}'
        s = sigs[0]
        price = float(s.price)
        sl = float(s.stop_loss_price)
        tp = float(s.take_profit_price)
        atr = float(s.entry_atr)
        assert sl < price, f'多头止损价应<入场价: sl={sl}, price={price}'
        assert tp > price, f'多头止盈价应>入场价: tp={tp}, price={price}'
        assert atr > 0, f'入场ATR应>0: atr={atr}'
        # 止盈距离 = 盈亏比 × 止损距离
        assert abs((tp - price) - 2.0 * (price - sl)) < 1e-4, \
            f'止盈距离应=2×止损距离: tp_dist={tp-price}, sl_dist={price-sl}'
        results.append(f'场景1 OK: 多头共振 -> buy, sl={sl:.2f}<price={price:.2f}<tp={tp:.2f}, atr={atr:.2f}')

        # 清理场景1产生的信号记录，避免冷却影响后续场景
        SignalRecord.objects.filter(strategy=strategy).delete()

        # 场景2：空头共振 -> sell
        sigs = run_with(strategy, make_golden_cross_df(scenario='bear'), [])
        assert len(sigs) >= 1 and sigs[0].signal == 'sell', \
            f'场景2失败: {[(s.signal, s.reason) for s in sigs]}'
        s = sigs[0]
        price = float(s.price)
        sl = float(s.stop_loss_price)
        tp = float(s.take_profit_price)
        assert sl > price, f'空头止损价应>入场价: sl={sl}, price={price}'
        assert tp < price, f'空头止盈价应<入场价: tp={tp}, price={price}'
        assert abs((price - tp) - 2.0 * (sl - price)) < 1e-4, \
            f'止盈距离应=2×止损距离: tp_dist={price-tp}, sl_dist={sl-price}'
        results.append(f'场景2 OK: 空头共振 -> sell, tp={tp:.2f}<price={price:.2f}<sl={sl:.2f}')

        SignalRecord.objects.filter(strategy=strategy).delete()

        # 场景3：持有多仓 + 空头共振 -> 强制平多 close_long
        long_pos = [{'instId': 'BTC-USDT-SWAP', 'posSide': 'long', 'pos': '0.5', 'instType': 'SWAP'}]
        sigs = run_with(strategy, make_golden_cross_df(scenario='bear'), long_pos)
        assert len(sigs) >= 1 and sigs[0].signal == 'close_long', \
            f'场景3失败: {[(s.signal, s.reason) for s in sigs]}'
        results.append('场景3 OK: 持有多仓+空头共振 -> close_long(强制平多)')

        SignalRecord.objects.filter(strategy=strategy).delete()

        # 场景4：窄幅震荡 -> 不产生 buy/sell
        sigs = run_with(strategy, make_golden_cross_df(scenario='flat'), [])
        assert all(s.signal not in ('buy', 'sell') for s in sigs), \
            f'场景4失败: 震荡应无开仓信号 {[(s.signal, s.reason) for s in sigs]}'
        results.append('场景4 OK: 窄幅震荡 -> 无开仓信号(共振不足)')
    finally:
        SignalRecord.objects.filter(strategy=strategy).delete()
        TrackedPosition.objects.filter(strategy=strategy).delete()
        strategy.delete()

    for r in results:
        print(r)
    print(f'\n全部 {len(results)} 项断言通过 [OK]')


if __name__ == '__main__':
    main()
