"""放量跟随策略核心逻辑冒烟测试（不依赖真实 OKX 网络）。
通过 mock OKX 持仓查询与行情数据，验证：
1) 顺势放量上涨 -> 生成 buy 信号，止损/止盈价计算正确
2) 顺势放量下跌 -> 生成 sell 信号
3) 持有多仓 + 触发标准空头放量信号 -> 强制平多 close_long
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


def make_df(n=75, above_ma=True, last_up=True):
    if above_ma:
        base = np.linspace(2000, 2100, n)
    else:
        base = np.linspace(2100, 2000, n)
    close = base + np.sin(np.arange(n)) * 2.0
    rng = np.random.RandomState(0)
    open_ = close - rng.rand(n) * 1.0
    vol = np.full(n, 100.0)
    if last_up:
        vol[-1] = 420.0
        vol[-2] = 140.0
        close[-1] = close[-2] + 5.0
        open_[-1] = close[-2]
    else:
        vol[-1] = 420.0
        vol[-2] = 140.0
        close[-1] = close[-2] - 5.0
        open_[-1] = close[-2]
    high = np.maximum(close, open_) + 1.0
    low = np.minimum(close, open_) - 1.0
    df = pd.DataFrame({
        'open': open_, 'high': high, 'low': low, 'close': close, 'volume': vol,
    })
    df.index = pd.date_range(end=pd.Timestamp.now(), periods=n, freq='1min')
    return df


def build_strategy():
    return StrategyConfig.objects.create(
        name='TEST_VB_SMOKE', strategy_type='volume_breakout',
        inst_type='SWAP', bar='1m', symbols=['ETH-USDT-SWAP'],
        params={'vol_ma_len': 20, 'vol_ratio': 1.8, 'trend_ma_len': 60, 'atr_len': 14,
                'min_atr_factor': 0.0015, 'cooling_min': 3, 'stop_loss_mul': 1.2,
                'tp_mode': 'fixed', 'tp_ratio': 1.5, 'trailing_trigger': 0.5,
                'trailing_factor': 0.8, 'enhanced_no_single_pulse': False,
                'risk_per_trade': 0.01, 'daily_max_stop': 3},
        td_mode='cross', leverage=3, status='active',
    )


def run_with(strategy, df, positions_data):
    mock_client = MagicMock()
    mock_client.get_positions.return_value = {'code': '0', 'data': positions_data}
    with patch('apps.strategy.services.get_okx_client', return_value=mock_client), \
         patch.object(MarketDataService, 'fetch_klines', return_value=None), \
         patch.object(MarketDataService, 'get_klines_df', return_value=df):
        return StrategyService._generate_volume_breakout_signals(strategy)


def main():
    strategy = build_strategy()
    results = []
    try:
        # 场景1：顺势放量上涨 -> buy
        sigs = run_with(strategy, make_df(above_ma=True, last_up=True), [])
        assert len(sigs) == 1 and sigs[0].signal == 'buy', f'场景1失败: {[(s.signal,s.reason) for s in sigs]}'
        s = sigs[0]
        atr = float(s.entry_atr)
        expect_sl = float(s.price) - 1.2 * atr
        expect_tp = float(s.price) + 1.5 * (float(s.price) - expect_sl)
        assert abs(float(s.stop_loss_price) - expect_sl) < 1e-4, f'止损价错误: {s.stop_loss_price} vs {expect_sl}'
        assert abs(float(s.take_profit_price) - expect_tp) < 1e-4, f'止盈价错误: {s.take_profit_price} vs {expect_tp}'
        results.append('场景1 OK: 顺势放量上涨 -> buy, sl/tp 正确')

        # 场景2：顺势放量下跌 -> sell
        sigs = run_with(strategy, make_df(above_ma=False, last_up=False), [])
        assert len(sigs) == 1 and sigs[0].signal == 'sell', f'场景2失败: {[(s.signal,s.reason) for s in sigs]}'
        results.append('场景2 OK: 顺势放量下跌 -> sell')

        # 场景3：持有多仓 + 标准空头放量信号 -> 强制平多
        long_pos = [{'instId': 'ETH-USDT-SWAP', 'posSide': 'long', 'pos': '0.5', 'instType': 'SWAP'}]
        sigs = run_with(strategy, make_df(above_ma=True, last_up=False), long_pos)
        assert len(sigs) == 1 and sigs[0].signal == 'close_long', f'场景3失败: {[(s.signal,s.reason) for s in sigs]}'
        results.append('场景3 OK: 持有多仓+空头放量 -> close_long(强制平多)')

        # 场景4：震荡屏蔽 -> 极小波动无信号（构造 ATR 极小）
        df4 = make_df(above_ma=True, last_up=True)
        # 把波动压平，使 ATR < min_atr_factor*price
        df4['high'] = df4['close'] + 0.0001
        df4['low'] = df4['close'] - 0.0001
        sigs = run_with(strategy, df4, [])
        # 放量仍在，但 ATR 过小应被屏蔽（不产生 buy）
        assert all(s.signal != 'buy' for s in sigs), f'场景4失败: ATR过滤未生效 {[(s.signal,s.reason) for s in sigs]}'
        results.append('场景4 OK: ATR过小震荡屏蔽生效')
    finally:
        SignalRecord.objects.filter(strategy=strategy).delete()
        TrackedPosition.objects.filter(strategy=strategy).delete()
        strategy.delete()

    for r in results:
        print(r)
    print(f'\n全部 {len(results)} 项断言通过 [OK]')


if __name__ == '__main__':
    main()
