"""策略 Celery 定时任务"""
from celery import shared_task
from apps.strategy.models import StrategyConfig
from apps.strategy.services import StrategyService


@shared_task
def run_strategy_signals(strategy_id: int):
    """运行指定策略的信号生成"""
    try:
        strategy = StrategyConfig.objects.get(id=strategy_id)
        signals = StrategyService.generate_signals(strategy)
        return [s.id for s in signals]
    except StrategyConfig.DoesNotExist:
        return {'error': f'Strategy {strategy_id} not found'}
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f'Strategy {strategy_id} failed: {e}')
        return {'error': str(e)}


@shared_task
def execute_pending_signals():
    """执行所有未执行的活跃策略信号"""
    from apps.strategy.models import SignalRecord
    signals = SignalRecord.objects.filter(
        is_executed=False,
        strategy__status='active',
    ).order_by('created_at')[:20]

    executed = []
    for sig in signals:
        try:
            result = StrategyService.execute_signal(sig)
            if result:
                executed.append(sig.id)
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f'Exec signal {sig.id} failed: {e}')

    return executed


@shared_task
def run_active_strategies():
    """批量运行所有活跃策略（含放量跟随持仓监控出场）"""
    active = StrategyConfig.objects.filter(status='active')
    results = {}
    for s in active:
        try:
            # 先监控持仓出场（硬止损/止盈/移动止盈），再生成新信号
            StrategyService.monitor_positions_for_strategy(s)
            signals = StrategyService.generate_signals(s)
            results[s.name] = len(signals)
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f'Strategy {s.name} failed: {e}')
            results[s.name] = 0
    return results
