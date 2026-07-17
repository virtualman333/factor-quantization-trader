"""
策略运行脚本
用于直接在命令行运行策略信号生成和执行
Usage:
    python scripts/run_strategy.py --name my_strategy
    python scripts/run_strategy.py --name my_strategy --execute
    python scripts/run_strategy.py --name my_strategy --backtest
"""

import os
import sys
import django

# 设置 Django 环境
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

import argparse
from datetime import datetime, timedelta
from django.utils import timezone

from apps.strategy.models import StrategyConfig
from apps.strategy.services import StrategyService


def main():
    parser = argparse.ArgumentParser(description='量化策略运行脚本')
    parser.add_argument('--name', '-n', type=str, required=True, help='策略名称')
    parser.add_argument('--execute', '-e', action='store_true', help='执行生成的信号')
    parser.add_argument('--backtest', '-b', action='store_true', help='运行回测')
    parser.add_argument('--start', type=str, help='回测开始日期 (YYYY-MM-DD)')
    parser.add_argument('--end', type=str, help='回测结束日期 (YYYY-MM-DD)')
    parser.add_argument('--symbols', type=str, help='覆盖标的列表 (逗号分隔)')
    args = parser.parse_args()

    try:
        strategy = StrategyConfig.objects.get(name=args.name)
    except StrategyConfig.DoesNotExist:
        print(f'错误: 未找到策略 "{args.name}", 请在 Django Admin 中先创建')
        sys.exit(1)

    print(f'策略: {strategy.name} [{strategy.get_status_display()}]')
    print(f'标的: {strategy.symbols}')

    if args.backtest:
        print('\n>>> 开始回测...')
        now = timezone.now()
        start = datetime.fromisoformat(args.start) if args.start else now - timedelta(days=30)
        end = datetime.fromisoformat(args.end) if args.end else now

        result = StrategyService.run_backtest(strategy, start, end)
        print(f'\n=== 回测结果 ===')
        print(f'时间范围: {result.start_date.date()} ~ {result.end_date.date()}')
        print(f'总收益率: {float(result.total_return):.2%}')
        print(f'年化收益率: {float(result.annual_return or 0):.2%}')
        print(f'夏普比率: {float(result.sharpe_ratio or 0):.2f}')
        print(f'最大回撤: {float(result.max_drawdown):.2%}')
        print(f'胜率: {float(result.win_rate):.2%}')
        print(f'总交易: {result.total_trades} | 盈利: {result.profit_trades} | 亏损: {result.loss_trades}')
        print(f'盈亏比: {float(result.profit_factor or 0):.2f}')
    else:
        print('\n>>> 生成交易信号...')
        if args.symbols:
            strategy.symbols = [s.strip() for s in args.symbols.split(',')]

        signals = StrategyService.generate_signals(strategy)
        print(f'\n生成 {len(signals)} 个信号:')

        for sig in signals:
            print(f'  [{sig.inst_id}] {sig.get_signal_display()} | '
                  f'评分: {float(sig.score):.4f} | 价格: {sig.price}')

        if args.execute:
            print('\n>>> 执行信号...')
            for sig in signals:
                if sig.signal in ('buy', 'sell'):
                    try:
                        result = StrategyService.execute_signal(sig)
                        if result:
                            print(f'  [{sig.inst_id}] 执行成功: {sig.get_signal_display()}')
                        else:
                            print(f'  [{sig.inst_id}] 跳过: {sig.get_signal_display()}')
                    except Exception as e:
                        print(f'  [{sig.inst_id}] 执行失败: {e}')


if __name__ == '__main__':
    main()
