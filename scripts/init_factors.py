"""
初始化因子定义数据
Usage: python manage.py shell < scripts/init_factors.py
"""

import os
import sys
import django

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth.models import User
from apps.strategy.models import FactorDefinition

# 默认用户（用于系统级因子）
DEFAULT_USER_ID = 1

FACTORS = [
    {
        'name': 'momentum',
        'display_name': '动量因子',
        'factor_type': 'momentum',
        'description': '基于多周期价格变化率的动量指标。正值表示上涨趋势，负值表示下跌趋势。',
        'params': {'periods': [5, 10, 20]},
    },
    {
        'name': 'volatility',
        'display_name': '波动率因子',
        'factor_type': 'volatility',
        'description': '基于历史收益率的年化波动率。低波动更适合趋势跟踪策略。',
        'params': {'window': 20},
    },
    {
        'name': 'rsi',
        'display_name': 'RSI相对强弱',
        'factor_type': 'momentum',
        'description': '14周期RSI指标，判断超买超卖区间。RSI<30超卖，RSI>70超买。',
        'params': {'period': 14},
    },
    {
        'name': 'macd',
        'display_name': 'MACD指标',
        'factor_type': 'trend',
        'description': 'MACD金叉死叉信号。金叉做多，死叉做空。',
        'params': {'fast': 12, 'slow': 26, 'signal': 9},
    },
    {
        'name': 'bb',
        'display_name': '布林带指标',
        'factor_type': 'volatility',
        'description': '价格在布林带中的位置。靠近下轨买入，靠近上轨卖出。',
        'params': {'window': 20, 'nbdev': 2},
    },
    {
        'name': 'volume_ratio',
        'display_name': '量比因子',
        'factor_type': 'volume',
        'description': '近期成交量与历史成交量的比值。放量上涨看多，缩量下跌看空。',
        'params': {'short': 5, 'long': 20},
    },
    {
        'name': 'ma_trend',
        'display_name': '均线趋势',
        'factor_type': 'trend',
        'description': '短周期与长周期均线的偏离程度。正值多头排列，负值空头排列。',
        'params': {'short': 10, 'long': 30},
    },
    {
        'name': 'atr',
        'display_name': 'ATR平均真实波幅',
        'factor_type': 'volatility',
        'description': '衡量市场波动性。高ATR表示高波动环境，适合设置更宽的止损。',
        'params': {'period': 14},
    },
    {
        'name': 'adx',
        'display_name': 'ADX趋势强度',
        'factor_type': 'trend',
        'description': '衡量趋势强度而非方向。ADX>25表示趋势明显。',
        'params': {'period': 14},
    },
    {
        'name': 'kdj',
        'display_name': 'KDJ随机指标',
        'factor_type': 'momentum',
        'description': 'KDJ超买超卖指标。K<20超卖买入，K>80超买卖出。',
        'params': {'k_period': 9, 'd_period': 3, 'j_period': 3},
    },
    {
        'name': 'ema_cross',
        'display_name': 'EMA交叉',
        'factor_type': 'trend',
        'description': '快慢EMA金叉死叉信号。',
        'params': {'fast': 12, 'slow': 26},
    },
    {
        'name': 'obv',
        'display_name': 'OBV能量潮',
        'factor_type': 'volume',
        'description': '基于成交量累计的能量潮指标。OBV斜率向上看多，向下看空。',
        'params': {'period': 20},
    },
    {
        'name': 'cci',
        'display_name': 'CCI顺势指标',
        'factor_type': 'momentum',
        'description': 'CCI<-100超卖买入，CCI>100超买卖出。',
        'params': {'period': 20},
    },
    {
        'name': 'wr',
        'display_name': '威廉指标WR',
        'factor_type': 'momentum',
        'description': 'WR<-80超卖买入，WR>-20超买卖出。',
        'params': {'period': 14},
    },
    {
        'name': 'ichimoku',
        'display_name': '一目均衡表',
        'factor_type': 'trend',
        'description': '价格在云层上方且转折线上穿基准线看多，反之看空。',
        'params': {'conversion': 9, 'base': 26, 'span': 52},
    },
]

default_user = User.objects.get(id=DEFAULT_USER_ID)
for factor_data in FACTORS:
    obj, created = FactorDefinition.objects.update_or_create(
        user=default_user,
        name=factor_data['name'],
        defaults=factor_data,
    )
    status = '创建' if created else '更新'
    print(f'{status}: {obj.display_name}')

print(f'\n共初始化 {len(FACTORS)} 个因子定义')
