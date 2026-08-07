"""策略 Celery 定时任务"""

import logging

from celery import shared_task
from django.contrib.auth import get_user_model

from apps.strategy.models import StrategyConfig, SignalRecord
from apps.strategy.services import StrategyService

logger = logging.getLogger(__name__)
User = get_user_model()


@shared_task
def run_strategy_signals(strategy_id: int, user_id: int = None):
    """运行指定策略的信号生成"""
    try:
        strategy = StrategyConfig.objects.get(id=strategy_id)
        user = User.objects.get(id=user_id) if user_id else strategy.user
        signals = StrategyService.generate_signals(strategy, user=user)
        return [s.id for s in signals]
    except StrategyConfig.DoesNotExist:
        return {'error': f'Strategy {strategy_id} not found'}
    except Exception as e:
        logger.error(f'Strategy {strategy_id} failed: {e}')
        return {'error': str(e)}


@shared_task
def execute_pending_signals():
    """执行所有未执行的活跃策略信号（按用户分组隔离执行）"""
    signals = SignalRecord.objects.filter(
        is_executed=False,
        strategy__status='active',
    ).select_related('strategy', 'strategy__user').order_by('created_at')[:20]

    executed = []
    for sig in signals:
        try:
            result = StrategyService.execute_signal(sig, user=sig.strategy.user)
            if result:
                executed.append(sig.id)
        except Exception as e:
            logger.error(f'Exec signal {sig.id} failed: {e}')

    return executed


@shared_task
def run_active_strategies():
    """批量运行所有活跃策略（含放量跟随持仓监控出场），按用户分组隔离执行"""
    active = StrategyConfig.objects.filter(status='active').select_related('user')
    results = {}
    for s in active:
        try:
            StrategyService.monitor_positions_for_strategy(s)
            signals = StrategyService.generate_signals(s, user=s.user)
            results[s.name] = len(signals)
        except Exception as e:
            logger.error(f'Strategy {s.name} failed: {e}')
            results[s.name] = 0
    return results
