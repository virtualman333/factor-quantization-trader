"""
量化因子计算引擎
基于 pandas + ta 实现常见技术因子
"""

import numpy as np
import pandas as pd
import ta
from typing import Dict, Tuple, Optional
from dataclasses import dataclass


@dataclass
class FactorResult:
    """单个因子计算结果"""
    name: str
    value: float           # 当前因子值
    score: float           # 标准化得分 (0~1)
    signal: str            # buy / sell / hold
    params: Dict = None


class FactorEngine:
    """因子计算引擎：输入 OHLCV DataFrame，输出因子得分和信号"""

    def __init__(self, df: pd.DataFrame):
        """
        Args:
            df: OHLCV DataFrame, 必须包含 [open, high, low, close, volume] 列
        """
        self.df = df.copy()
        self._results: Dict[str, FactorResult] = {}

    def calculate_all(self, factor_names: list = None) -> Dict[str, FactorResult]:
        """批量计算因子"""
        available = {
            'momentum': self.momentum,
            'volatility': self.volatility,
            'rsi': self.rsi,
            'macd': self.macd,
            'bb': self.bollinger_bands,
            'volume_ratio': self.volume_ratio,
            'ma_trend': self.ma_trend,
            'atr': self.atr,
            'adx': self.adx,
            'kdj': self.kdj,
            'ema_cross': self.ema_cross,
        }

        names = factor_names or list(available.keys())
        for name in names:
            if name in available:
                try:
                    self._results[name] = available[name]()
                except Exception as e:
                    self._results[name] = FactorResult(name=name, value=0, score=0, signal='hold')

        return self._results

    def get_composite_score(self) -> Tuple[float, str]:
        """综合评分：所有因子归一化后的加权平均"""
        if not self._results:
            return 0.0, 'hold'

        # 等权
        scores = [r.score for r in self._results.values()]
        avg = np.mean(scores)

        # 生成综合信号
        if avg >= 0.65:
            return avg, 'buy'
        elif avg <= 0.35:
            return avg, 'sell'
        else:
            return avg, 'hold'

    # ==================== 因子实现 ====================

    def momentum(self) -> FactorResult:
        """动量因子：N日收益率"""
        periods = [5, 10, 20]
        mom_values = []
        for period in periods:
            if len(self.df) > period:
                ret = self.df['close'].pct_change(period).iloc[-1]
                mom_values.append(ret)

        if mom_values:
            value = np.mean(mom_values)
        else:
            value = 0

        # 归一化：正值偏向 1，负值偏向 0
        score = self._sigmoid(value, center=0, scale=0.05)
        signal = 'buy' if value > 0.01 else 'sell' if value < -0.01 else 'hold'
        return FactorResult('momentum', value, score, signal)

    def volatility(self) -> FactorResult:
        """波动率因子：历史波动率，越低越好（适合做多）"""
        if len(self.df) < 20:
            return FactorResult('volatility', 0, 0.5, 'hold')

        returns = self.df['close'].pct_change().dropna()
        vol = returns.iloc[-20:].std() * np.sqrt(365 * 24)  # 年化
        # 波动率低 -> 偏向 1，高 -> 偏向 0
        score = 1.0 - self._sigmoid(vol, center=0.5, scale=0.2)
        score = np.clip(score, 0, 1)
        signal = 'buy' if vol < 0.4 else 'sell' if vol > 0.8 else 'hold'
        return FactorResult('volatility', float(vol), float(score), signal)

    def rsi(self, period: int = 14) -> FactorResult:
        """RSI 因子：超买超卖"""
        if len(self.df) < period:
            return FactorResult('rsi', 50, 0.5, 'hold')

        rsi_value = ta.momentum.RSIIndicator(self.df['close'], window=period).rsi().iloc[-1]
        if pd.isna(rsi_value):
            return FactorResult('rsi', 50, 0.5, 'hold')

        # RSI: 低于30买入，高于70卖出
        score = np.clip((50 - rsi_value) / 40 + 0.5, 0, 1)  # RSI 30->1.0, RSI 70->0.0
        signal = 'buy' if rsi_value < 35 else 'sell' if rsi_value > 65 else 'hold'
        return FactorResult('rsi', float(rsi_value), float(score), signal, {'period': period})

    def macd(self, fast=12, slow=26, signal_period=9) -> FactorResult:
        """MACD 因子：金叉死叉"""
        if len(self.df) < slow + signal_period:
            return FactorResult('macd', 0, 0.5, 'hold')

        macd_indicator = ta.trend.MACD(self.df['close'],
                                        window_slow=slow, window_fast=fast,
                                        window_sign=signal_period)
        macd_line = macd_indicator.macd().iloc[-1]
        signal_line = macd_indicator.macd_signal().iloc[-1]
        histogram = macd_indicator.macd_diff().iloc[-1]

        if pd.isna(macd_line) or pd.isna(signal_line):
            return FactorResult('macd', 0, 0.5, 'hold')

        diff = macd_line - signal_line
        # 使用柱状图变化方向判断
        value = float(histogram)
        score = self._sigmoid(diff, center=0, scale=max(abs(macd_line), 0.001) / 2)
        signal = 'buy' if diff > 0 else 'sell' if diff < 0 else 'hold'
        return FactorResult('macd', value, float(score), signal,
                            {'fast': fast, 'slow': slow, 'signal': signal_period})

    def bollinger_bands(self, window=20, nbdev=2) -> FactorResult:
        """布林带因子"""
        if len(self.df) < window:
            return FactorResult('bb', 0.5, 0.5, 'hold')

        bb = ta.volatility.BollingerBands(self.df['close'], window=window, window_dev=nbdev)
        hband = bb.bollinger_hband().iloc[-1]
        lband = bb.bollinger_lband().iloc[-1]
        close = self.df['close'].iloc[-1]

        if pd.isna(hband) or pd.isna(lband):
            return FactorResult('bb', 0.5, 0.5, 'hold')

        # 价格在带中的位置: 0=下轨, 1=上轨
        if hband != lband:
            position = np.clip((close - lband) / (hband - lband), 0, 1)
        else:
            position = 0.5

        # 下轨附近买入，上轨附近卖出
        score = 1.0 - position  # 靠近下轨 score 高
        signal = 'buy' if position < 0.2 else 'sell' if position > 0.8 else 'hold'
        return FactorResult('bb', float(position), float(score), signal,
                            {'window': window, 'nbdev': nbdev})

    def volume_ratio(self, short_period=5, long_period=20) -> FactorResult:
        """量比因子"""
        if len(self.df) < long_period:
            return FactorResult('volume_ratio', 1, 0.5, 'hold')

        short_vol = self.df['volume'].iloc[-short_period:].mean()
        long_vol = self.df['volume'].iloc[-long_period:].mean()

        if long_vol > 0:
            ratio = short_vol / long_vol
        else:
            ratio = 1

        # 放量上涨好，缩量下跌好
        price_change = self.df['close'].pct_change(5).iloc[-1]

        score = 0.5
        if ratio > 1.5 and price_change > 0:
            score = 0.8   # 放量上涨
        elif ratio < 0.5 and price_change < 0:
            score = 0.2   # 缩量下跌

        signal = 'buy' if score > 0.6 else 'sell' if score < 0.4 else 'hold'
        return FactorResult('volume_ratio', float(ratio), score, signal,
                            {'short': short_period, 'long': long_period})

    def ma_trend(self, short=10, long=30) -> FactorResult:
        """均线趋势因子"""
        if len(self.df) < long:
            return FactorResult('ma_trend', 0, 0.5, 'hold')

        ma_short = self.df['close'].iloc[-short:].mean()
        ma_long = self.df['close'].iloc[-long:].mean()
        close = self.df['close'].iloc[-1]

        # 多头排列程度
        if ma_long > 0:
            trend_strength = (ma_short - ma_long) / ma_long
        else:
            trend_strength = 0

        value = float(trend_strength)
        score = self._sigmoid(value, center=0, scale=0.05)
        signal = 'buy' if value > 0.02 else 'sell' if value < -0.02 else 'hold'
        return FactorResult('ma_trend', value, float(score), signal,
                            {'short': short, 'long': long})

    def atr(self, period=14) -> FactorResult:
        """ATR 波动因子：高ATR表示高风险"""
        if len(self.df) < period:
            return FactorResult('atr', 0, 0.5, 'hold')

        atr_value = ta.volatility.AverageTrueRange(
            self.df['high'], self.df['low'], self.df['close'], window=period
        ).average_true_range().iloc[-1]

        if pd.isna(atr_value):
            return FactorResult('atr', 0, 0.5, 'hold')

        # ATR 相对价格归一化
        avg_price = self.df['close'].iloc[-20:].mean()
        if avg_price > 0:
            atr_pct = atr_value / avg_price
        else:
            atr_pct = 0.01

        # 中低波动更适合趋势策略
        score = 1.0 - np.clip(atr_pct / 0.05, 0, 1)
        score = float(score)
        signal = 'hold'
        return FactorResult('atr', float(atr_pct), score, signal, {'period': period})

    def adx(self, period=14) -> FactorResult:
        """ADX 趋势强度因子"""
        if len(self.df) < period * 2:
            return FactorResult('adx', 0, 0.5, 'hold')

        adx_value = ta.trend.ADXIndicator(
            self.df['high'], self.df['low'], self.df['close'], window=period
        ).adx().iloc[-1]

        if pd.isna(adx_value):
            return FactorResult('adx', 0, 0.5, 'hold')

        # ADX > 25 趋势明显，偏高
        value = float(adx_value)
        score = np.clip(adx_value / 50, 0, 1)  # ADX 0->0, 50->1
        signal = 'buy' if adx_value > 25 else 'hold'
        return FactorResult('adx', value, float(score), signal, {'period': period})

    def kdj(self, k_period=9, d_period=3, j_period=3) -> FactorResult:
        """KDJ 因子"""
        if len(self.df) < max(k_period, d_period, j_period) * 3:
            return FactorResult('kdj', 50, 0.5, 'hold')

        kdj = ta.momentum.StochasticOscillator(
            self.df['high'], self.df['low'], self.df['close'],
            window=k_period, smooth_window=d_period
        )
        k = kdj.stoch().iloc[-1]
        d = kdj.stoch_signal().iloc[-1]

        if pd.isna(k) or pd.isna(d):
            return FactorResult('kdj', 50, 0.5, 'hold')

        value = float(k)
        # K < 20 超卖买入, K > 80 超买卖出
        score = np.clip((80 - value) / 60, 0, 1)
        signal = 'buy' if value < 25 else 'sell' if value > 75 else 'hold'
        return FactorResult('kdj', value, float(score), signal,
                            {'k_period': k_period, 'd_period': d_period})

    def ema_cross(self, fast=12, slow=26) -> FactorResult:
        """EMA 交叉因子"""
        if len(self.df) < slow:
            return FactorResult('ema_cross', 0, 0.5, 'hold')

        ema_fast = self.df['close'].ewm(span=fast, adjust=False).mean().iloc[-1]
        ema_slow = self.df['close'].ewm(span=slow, adjust=False).mean().iloc[-1]

        if ema_slow > 0:
            diff_pct = (ema_fast - ema_slow) / ema_slow
        else:
            diff_pct = 0

        value = float(diff_pct)
        score = self._sigmoid(value, center=0, scale=0.02)
        signal = 'buy' if value > 0.005 else 'sell' if value < -0.005 else 'hold'
        return FactorResult('ema_cross', value, float(score), signal,
                            {'fast': fast, 'slow': slow})

    # ==================== 工具方法 ====================
    @staticmethod
    def _sigmoid(x: float, center: float = 0, scale: float = 1) -> float:
        """Sigmoid 映射到 [0, 1]"""
        if scale <= 0:
            scale = 1
        return float(1 / (1 + np.exp(-(x - center) / scale)))
