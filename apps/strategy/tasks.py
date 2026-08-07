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


@shared_task(bind=True, max_retries=0)
def run_backtest_task(self, strategy_id: int, start_date: str = '',
                      end_date: str = '', user_id: int = None,
                      fee_rate: float = 0.001, slippage: float = 0.001):
    """异步执行策略回测（回测耗时较长，放入后台队列执行）"""
    from datetime import datetime
    from django.utils import timezone

    try:
        strategy = StrategyConfig.objects.get(id=strategy_id)
        user = User.objects.get(id=user_id) if user_id else strategy.user

        def _parse(value, is_end=False):
            if not value:
                return None
            try:
                dt = datetime.fromisoformat(value)
            except (ValueError, TypeError):
                dt = None
            if dt and timezone.is_naive(dt):
                dt = timezone.make_aware(dt)
            return dt

        start_dt = _parse(start_date) or (timezone.now() - __import__('datetime').timedelta(days=30))
        end_dt = _parse(end_date) or timezone.now()

        result = StrategyService.run_backtest(
            strategy,
            start_date=start_dt,
            end_date=end_dt,
            user=user,
            fee_rate=fee_rate,
            slippage=slippage,
        )
        return {
            'status': 'success',
            'backtest_id': result.id,
            'strategy_id': strategy_id,
            'strategy_name': strategy.name,
            'total_return': float(result.total_return),
            'sharpe_ratio': float(result.sharpe_ratio or 0),
            'total_trades': result.total_trades,
        }
    except Exception as e:
        logger.error(f'Backtest task {strategy_id} failed: {e}')
        return {'status': 'error', 'strategy_id': strategy_id, 'error': str(e)}


@shared_task(bind=True, max_retries=0)
def run_monte_carlo_task(self, backtest_id: int, n_simulations: int = 1000):
    """异步蒙特卡洛模拟"""
    from apps.strategy.models import BacktestResult
    try:
        bt = BacktestResult.objects.get(id=backtest_id)
        result = StrategyService.run_monte_carlo(bt, n_simulations=n_simulations)
        return {'status': 'success', 'backtest_id': backtest_id, 'result': result}
    except Exception as e:
        logger.error(f'Monte carlo task {backtest_id} failed: {e}')
        return {'status': 'error', 'backtest_id': backtest_id, 'error': str(e)}


@shared_task(bind=True, max_retries=0)
def run_walk_forward_task(self, strategy_id: int, start_date: str = '',
                          end_date: str = '', window_days: int = 14,
                          user_id: int = None):
    """异步 Walk-forward 分析"""
    from datetime import datetime
    from django.utils import timezone
    try:
        strategy = StrategyConfig.objects.get(id=strategy_id)
        user = User.objects.get(id=user_id) if user_id else strategy.user

        def _parse(value, is_end=False):
            if not value:
                return None
            try:
                dt = datetime.fromisoformat(value)
            except (ValueError, TypeError):
                dt = None
            if dt and timezone.is_naive(dt):
                dt = timezone.make_aware(dt)
            return dt

        start_dt = _parse(start_date) or (timezone.now() - __import__('datetime').timedelta(days=30))
        end_dt = _parse(end_date) or timezone.now()
        result = StrategyService.run_walk_forward(
            strategy, start_date=start_dt, end_date=end_dt,
            window_days=window_days, user=user,
        )
        return {'status': 'success', 'strategy_id': strategy_id, 'result': result}
    except Exception as e:
        logger.error(f'Walk forward task {strategy_id} failed: {e}')
        return {'status': 'error', 'strategy_id': strategy_id, 'error': str(e)}


@shared_task(bind=True, max_retries=0)
def run_optimize_params_task(self, strategy_id: int, start_date: str = '',
                             end_date: str = '', param_grid: dict = None,
                             user_id: int = None):
    """异步策略参数网格搜索"""
    from datetime import datetime
    from django.utils import timezone
    try:
        strategy = StrategyConfig.objects.get(id=strategy_id)
        user = User.objects.get(id=user_id) if user_id else strategy.user

        def _parse(value):
            if not value:
                return None
            try:
                dt = datetime.fromisoformat(value)
            except (ValueError, TypeError):
                dt = None
            if dt and timezone.is_naive(dt):
                dt = timezone.make_aware(dt)
            return dt

        start_dt = _parse(start_date) or (timezone.now() - __import__('datetime').timedelta(days=30))
        end_dt = _parse(end_date) or timezone.now()
        result = StrategyService.optimize_params(
            strategy, start_date=start_dt, end_date=end_dt,
            param_grid=param_grid or {}, user=user,
        )
        return {'status': 'success', 'strategy_id': strategy_id, 'result': result}
    except Exception as e:
        logger.error(f'Optimize params task {strategy_id} failed: {e}')
        return {'status': 'error', 'strategy_id': strategy_id, 'error': str(e)}


@shared_task(bind=True, max_retries=0)
def run_optimize_weights_task(self, strategy_id: int, start_date: str = '',
                              end_date: str = '', iterations: int = 10,
                              user_id: int = None):
    """异步因子权重优化"""
    from datetime import datetime
    from django.utils import timezone
    try:
        strategy = StrategyConfig.objects.get(id=strategy_id)
        user = User.objects.get(id=user_id) if user_id else strategy.user

        def _parse(value):
            if not value:
                return None
            try:
                dt = datetime.fromisoformat(value)
            except (ValueError, TypeError):
                dt = None
            if dt and timezone.is_naive(dt):
                dt = timezone.make_aware(dt)
            return dt

        start_dt = _parse(start_date) or (timezone.now() - __import__('datetime').timedelta(days=30))
        end_dt = _parse(end_date) or timezone.now()
        result = StrategyService.optimize_factor_weights(
            strategy, start_date=start_dt, end_date=end_dt,
            user=user, iterations=iterations,
        )
        return {'status': 'success', 'strategy_id': strategy_id, 'result': result}
    except Exception as e:
        logger.error(f'Optimize weights task {strategy_id} failed: {e}')
        return {'status': 'error', 'strategy_id': strategy_id, 'error': str(e)}


@shared_task(bind=True, max_retries=0)
def run_portfolio_backtest_task(self, portfolio_id: int, start_date: str = '',
                                end_date: str = '', user_id: int = None):
    """异步组合回测"""
    from datetime import datetime
    from django.utils import timezone
    from apps.strategy.models import StrategyPortfolio
    try:
        portfolio = StrategyPortfolio.objects.get(id=portfolio_id)
        user = User.objects.get(id=user_id) if user_id else None

        def _parse(value):
            if not value:
                return None
            try:
                dt = datetime.fromisoformat(value)
            except (ValueError, TypeError):
                dt = None
            if dt and timezone.is_naive(dt):
                dt = timezone.make_aware(dt)
            return dt

        start_dt = _parse(start_date) or (timezone.now() - __import__('datetime').timedelta(days=30))
        end_dt = _parse(end_date) or timezone.now()
        result = StrategyService.run_portfolio_backtest(
            portfolio, start_date=start_dt, end_date=end_dt, user=user,
        )
        return {'status': 'success', 'portfolio_id': portfolio_id, 'result': result}
    except Exception as e:
        logger.error(f'Portfolio backtest task {portfolio_id} failed: {e}')
        return {'status': 'error', 'portfolio_id': portfolio_id, 'error': str(e)}


@shared_task(bind=True, max_retries=0)
def run_compare_strategies_task(self, strategy_ids: list = None, start_date: str = '',
                                end_date: str = '', user_id: int = None):
    """异步多策略对比"""
    from datetime import datetime
    from django.utils import timezone
    try:
        user = User.objects.get(id=user_id) if user_id else None

        def _parse(value):
            if not value:
                return None
            try:
                dt = datetime.fromisoformat(value)
            except (ValueError, TypeError):
                dt = None
            if dt and timezone.is_naive(dt):
                dt = timezone.make_aware(dt)
            return dt

        start_dt = _parse(start_date) or (timezone.now() - __import__('datetime').timedelta(days=30))
        end_dt = _parse(end_date) or timezone.now()
        result = StrategyService.compare_strategies(
            strategy_ids or [], start_date=start_dt, end_date=end_dt, user=user,
        )
        return {'status': 'success', 'result': result}
    except Exception as e:
        logger.error(f'Compare strategies task failed: {e}')
        return {'status': 'error', 'error': str(e)}


@shared_task(bind=True, max_retries=0)
def run_multi_symbol_backtest_task(self, strategy_id: int, start_date: str = '',
                                   end_date: str = '', fee_rate: float = 0.001,
                                   slippage: float = 0.001, user_id: int = None):
    """异步多品种并行回测"""
    from datetime import datetime
    from django.utils import timezone
    try:
        strategy = StrategyConfig.objects.get(id=strategy_id)
        user = User.objects.get(id=user_id) if user_id else strategy.user

        def _parse(value):
            if not value:
                return None
            try:
                dt = datetime.fromisoformat(value)
            except (ValueError, TypeError):
                dt = None
            if dt and timezone.is_naive(dt):
                dt = timezone.make_aware(dt)
            return dt

        start_dt = _parse(start_date) or (timezone.now() - __import__('datetime').timedelta(days=30))
        end_dt = _parse(end_date) or timezone.now()
        result = StrategyService.run_multi_symbol_backtest(
            strategy, start_date=start_dt, end_date=end_dt,
            user=user, fee_rate=fee_rate, slippage=slippage,
        )
        return {'status': 'success', 'strategy_id': strategy_id, 'result': result}
    except Exception as e:
        logger.error(f'Multi symbol backtest task {strategy_id} failed: {e}')
        return {'status': 'error', 'strategy_id': strategy_id, 'error': str(e)}


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
