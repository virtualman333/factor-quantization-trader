"""策略引擎 API 视图"""

import re

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.strategy.models import StrategyConfig, FactorDefinition, SignalRecord, BacktestResult, StrategyPortfolio
from apps.strategy.serializers import (
    StrategyConfigSerializer, FactorDefinitionSerializer,
    SignalRecordSerializer, BacktestResultSerializer,
    StrategyPortfolioSerializer,
)
from apps.strategy.services import StrategyService, StrategyError
from apps.strategy.factors import FactorEngine
from core.okx_client import get_okx_client


def _parse_dt(value, is_end=False):
    """解析日期/日期时间字符串"""
    from datetime import datetime
    from django.utils.dateparse import parse_datetime, parse_date

    if not value:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        if re.match(r'^\d{4}-\d{2}-\d{2}$', value):
            d = parse_date(value)
            if d is not None:
                if is_end:
                    return datetime(d.year, d.month, d.day, 23, 59, 59, 999999)
                return datetime(d.year, d.month, d.day, 0, 0, 0, 0)
        dt = parse_datetime(value)
        if dt is not None:
            return dt
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None
    return None


def _parse_backtest_dates(request):
    """解析回测起止日期，缺省为近30天"""
    from datetime import timedelta
    from django.utils import timezone

    start_date = request.data.get('start_date')
    end_date = request.data.get('end_date')

    start_dt = _parse_dt(start_date, is_end=False)
    end_dt = _parse_dt(end_date, is_end=True)

    if not start_dt or not end_dt:
        now = timezone.now()
        end_dt = now
        start_dt = now - timedelta(days=30)

    if timezone.is_naive(start_dt):
        start_dt = timezone.make_aware(start_dt)
    if timezone.is_naive(end_dt):
        end_dt = timezone.make_aware(end_dt)
    return start_dt, end_dt


class StrategyConfigViewSet(viewsets.ModelViewSet):
    """策略配置 CRUD API"""
    serializer_class = StrategyConfigSerializer

    def get_queryset(self):
        # superuser（管理员）可查看所有用户的策略，普通用户仅看自己的
        if self.request.user.is_superuser:
            qs = StrategyConfig.objects.all()
        else:
            qs = StrategyConfig.objects.filter(user=self.request.user)
        params = self.request.query_params
        keyword = params.get('keyword')
        if keyword:
            qs = qs.filter(name__icontains=keyword.strip())
        for field in ('strategy_type', 'inst_type', 'status', 'direction'):
            val = params.get(field)
            if val:
                qs = qs.filter(**{field: val})
        return qs

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=False, methods=['get'])
    def instruments(self, request):
        """获取 OKX 交易产品列表（支持下拉选交易对）"""
        inst_type = request.query_params.get('inst_type', 'SWAP')
        client = get_okx_client(user=request.user)
        try:
            result = client.get_instruments(inst_type=inst_type)
            data = result.get('data', [])
            items = [
                {
                    'instId': item.get('instId'),
                    'instType': item.get('instType'),
                    'baseCcy': item.get('baseCcy', ''),
                    'quoteCcy': item.get('quoteCcy', ''),
                    'state': item.get('state', ''),
                    'label': item.get('instId'),
                    'value': item.get('instId'),
                }
                for item in data
                if item.get('state') == 'live' and item.get('instId')
            ]
            return Response({'inst_type': inst_type, 'instruments': items})
        except Exception as e:
            fallback = [
                'BTC-USDT-SWAP', 'ETH-USDT-SWAP', 'SOL-USDT-SWAP',
                'XRP-USDT-SWAP', 'DOGE-USDT-SWAP', 'LTC-USDT-SWAP',
                'BNB-USDT-SWAP', 'ADA-USDT-SWAP', 'AVAX-USDT-SWAP',
                'MATIC-USDT-SWAP', 'LINK-USDT-SWAP', 'UNI-USDT-SWAP',
            ]
            items = [{'label': s, 'value': s, 'instType': inst_type} for s in fallback]
            return Response({
                'inst_type': inst_type,
                'instruments': items,
                'fallback': True,
                'error': str(e),
            })

    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        """激活策略"""
        strategy = self.get_object()
        strategy.status = 'active'
        strategy.save(update_fields=['status'])
        return Response({'status': 'activated'})

    @action(detail=True, methods=['post'])
    def pause(self, request, pk=None):
        """暂停策略"""
        strategy = self.get_object()
        strategy.status = 'paused'
        strategy.save(update_fields=['status'])
        return Response({'status': 'paused'})

    @action(detail=True, methods=['post'])
    def run_signals(self, request, pk=None):
        """手动运行信号生成"""
        strategy = self.get_object()
        signals = StrategyService.generate_signals(strategy, user=request.user)
        serializer = SignalRecordSerializer(signals, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def execute_signals(self, request, pk=None):
        """执行策略未执行信号"""
        strategy = self.get_object()
        signals = strategy.signals.filter(is_executed=False).order_by('-created_at')[:10]
        results = []
        for sig in signals:
            try:
                r = StrategyService.execute_signal(sig, user=request.user)
                results.append({'id': sig.id, 'success': True, 'result': r})
            except Exception as e:
                results.append({'id': sig.id, 'success': False, 'error': str(e)})
        return Response(results)

    @action(detail=True, methods=['post'])
    def backtest(self, request, pk=None):
        """运行回测（异步任务执行，返回 task_id 供查询进度）"""
        strategy = self.get_object()
        start_dt, end_dt = _parse_backtest_dates(request)
        try:
            fee_rate = float(request.data.get('fee_rate', 0.001))
            slippage = float(request.data.get('slippage', 0.001))
            from apps.strategy.tasks import run_backtest_task
            task = run_backtest_task.delay(
                strategy_id=strategy.id,
                start_date=start_dt.isoformat(),
                end_date=end_dt.isoformat(),
                user_id=request.user.id if request.user.is_authenticated else None,
                fee_rate=fee_rate,
                slippage=slippage,
            )
            return Response({
                'task_id': str(task.id),
                'submitted': True,
                'strategy_id': strategy.id,
                'strategy_name': strategy.name,
            }, status=202)
        except Exception as e:
            return Response({'error': str(e)}, status=500)

    @action(detail=False, methods=['get'])
    def backtest_tasks(self, request):
        """获取当前用户最近的回测任务列表（含状态）"""
        from datetime import timedelta
        import json
        from django.utils import timezone
        from django_celery_results.models import TaskResult

        since = timezone.now() - timedelta(hours=2)
        # 查询所有策略相关异步任务
        strategy_tasks = [
            'apps.strategy.tasks.run_backtest_task',
            'apps.strategy.tasks.run_monte_carlo_task',
            'apps.strategy.tasks.run_walk_forward_task',
            'apps.strategy.tasks.run_optimize_params_task',
            'apps.strategy.tasks.run_optimize_weights_task',
            'apps.strategy.tasks.run_portfolio_backtest_task',
            'apps.strategy.tasks.run_compare_strategies_task',
            'apps.strategy.tasks.run_multi_symbol_backtest_task',
        ]
        rows = TaskResult.objects.filter(
            task_name__in=strategy_tasks,
            date_created__gte=since,
        ).order_by('-date_created')[:50]

        # 任务名 -> 中文标签
        TASK_LABELS = {
            'run_backtest_task': '回测',
            'run_monte_carlo_task': '蒙特卡洛',
            'run_walk_forward_task': 'Walk-forward',
            'run_optimize_params_task': '参数优化',
            'run_optimize_weights_task': '权重优化',
            'run_portfolio_backtest_task': '组合回测',
            'run_compare_strategies_task': '策略对比',
            'run_multi_symbol_backtest_task': '多品种回测',
        }

        results = []
        for t in rows:
            strategy_id = None
            backtest_id = None
            try:
                kwargs = json.loads(t.task_kwargs or '{}')
                strategy_id = kwargs.get('strategy_id') or kwargs.get('portfolio_id')
                backtest_id = kwargs.get('backtest_id')
            except Exception:
                pass

            task_label = t.task_name.split('.')[-1]
            result_data = {}
            if t.result:
                try:
                    result_data = json.loads(t.result)
                except Exception:
                    result_data = {'raw': t.result[:200]}

            # 尝试补充策略名
            strategy_name = None
            if result_data.get('strategy_name'):
                strategy_name = result_data['strategy_name']
            elif result_data.get('result') and isinstance(result_data['result'], dict):
                strategy_name = result_data['result'].get('name') or result_data['result'].get('strategy_name')

            results.append({
                'task_id': t.task_id,
                'strategy_id': strategy_id,
                'backtest_id': backtest_id,
                'strategy_name': strategy_name,
                'task_type': TASK_LABELS.get(task_label, task_label),
                'state': t.status,
                'result': result_data,
                'created_at': t.date_created.isoformat() if t.date_created else None,
                'done_at': t.date_done.isoformat() if t.date_done else None,
            })
        return Response({'results': results})

    @action(detail=True, methods=['post'])
    def monte_carlo(self, request, pk=None):
        """蒙特卡洛模拟（异步任务执行）"""
        strategy = self.get_object()
        bt = strategy.backtests.order_by('-created_at').first()
        if not bt:
            return Response({'error': '请先运行回测'}, status=400)
        n_simulations = int(request.data.get('n_simulations', 1000))
        from apps.strategy.tasks import run_monte_carlo_task
        task = run_monte_carlo_task.delay(backtest_id=bt.id, n_simulations=n_simulations)
        return Response({'task_id': str(task.id), 'submitted': True}, status=202)

    @action(detail=True, methods=['post'])
    def walk_forward(self, request, pk=None):
        """Walk-forward 分析（异步任务执行）"""
        strategy = self.get_object()
        start_dt, end_dt = _parse_backtest_dates(request)
        window_days = int(request.data.get('window_days', 14))
        from apps.strategy.tasks import run_walk_forward_task
        task = run_walk_forward_task.delay(
            strategy_id=strategy.id,
            start_date=start_dt.isoformat(),
            end_date=end_dt.isoformat(),
            window_days=window_days,
            user_id=request.user.id if request.user.is_authenticated else None,
        )
        return Response({'task_id': str(task.id), 'submitted': True}, status=202)

    @action(detail=True, methods=['get'])
    def export_report(self, request, pk=None):
        """导出回测报告（HTML，可打印为PDF）"""
        strategy = self.get_object()
        bt = strategy.backtests.order_by('-created_at').first()
        if not bt:
            return Response({'error': '请先运行回测'}, status=400)
        html = StrategyService.export_backtest_html(bt)
        from django.http import HttpResponse
        resp = HttpResponse(html, content_type='text/html; charset=utf-8')
        resp['Content-Disposition'] = f'attachment; filename="backtest_{strategy.name}_{bt.id}.html"'
        return resp

    @action(detail=True, methods=['post'])
    def multi_symbol_backtest(self, request, pk=None):
        """多品种并行回测（异步任务执行）"""
        strategy = self.get_object()
        start_dt, end_dt = _parse_backtest_dates(request)
        fee_rate = float(request.data.get('fee_rate', 0.001))
        slippage = float(request.data.get('slippage', 0.001))
        from apps.strategy.tasks import run_multi_symbol_backtest_task
        task = run_multi_symbol_backtest_task.delay(
            strategy_id=strategy.id,
            start_date=start_dt.isoformat(),
            end_date=end_dt.isoformat(),
            fee_rate=fee_rate, slippage=slippage,
            user_id=request.user.id if request.user.is_authenticated else None,
        )
        return Response({'task_id': str(task.id), 'submitted': True}, status=202)

    @action(detail=True, methods=['post'])
    def optimize_params(self, request, pk=None):
        """策略参数优化器（网格搜索，异步任务执行）"""
        strategy = self.get_object()
        param_grid = request.data.get('param_grid')
        if not isinstance(param_grid, dict) or not param_grid:
            return Response({'error': 'param_grid 必填，如 {"vol_ratio": [1.5, 1.8, 2.0]}'}, status=400)
        start_dt, end_dt = _parse_backtest_dates(request)
        from apps.strategy.tasks import run_optimize_params_task
        task = run_optimize_params_task.delay(
            strategy_id=strategy.id,
            start_date=start_dt.isoformat(),
            end_date=end_dt.isoformat(),
            param_grid=param_grid,
            user_id=request.user.id if request.user.is_authenticated else None,
        )
        return Response({'task_id': str(task.id), 'submitted': True}, status=202)

    @action(detail=True, methods=['post'])
    def optimize_weights(self, request, pk=None):
        """因子权重自动优化（异步任务执行）"""
        strategy = self.get_object()
        start_dt, end_dt = _parse_backtest_dates(request)
        iterations = request.data.get('iterations', 10)
        from apps.strategy.tasks import run_optimize_weights_task
        task = run_optimize_weights_task.delay(
            strategy_id=strategy.id,
            start_date=start_dt.isoformat(),
            end_date=end_dt.isoformat(),
            iterations=int(iterations),
            user_id=request.user.id if request.user.is_authenticated else None,
        )
        return Response({'task_id': str(task.id), 'submitted': True}, status=202)

    @action(detail=False, methods=['post'])
    def compare(self, request):
        """多策略回测结果对比"""
        strategy_ids = request.data.get('strategy_ids', [])
        if not strategy_ids:
            return Response({'error': 'strategy_ids 必填'}, status=400)
        start_dt, end_dt = _parse_backtest_dates(request)
        from apps.strategy.tasks import run_compare_strategies_task
        task = run_compare_strategies_task.delay(
            strategy_ids=strategy_ids,
            start_date=start_dt.isoformat(),
            end_date=end_dt.isoformat(),
            user_id=request.user.id if request.user.is_authenticated else None,
        )
        return Response({'task_id': str(task.id), 'submitted': True}, status=202)


class PortfolioViewSet(viewsets.ModelViewSet):
    """多策略组合管理 API"""
    serializer_class = StrategyPortfolioSerializer

    def get_queryset(self):
        return StrategyPortfolio.objects.filter(user=self.request.user).order_by('-created_at')

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=True, methods=['post'])
    def backtest(self, request, pk=None):
        """组合回测（异步任务执行）"""
        portfolio = self.get_object()
        start_dt, end_dt = _parse_backtest_dates(request)
        from apps.strategy.tasks import run_portfolio_backtest_task
        task = run_portfolio_backtest_task.delay(
            portfolio_id=portfolio.id,
            start_date=start_dt.isoformat(),
            end_date=end_dt.isoformat(),
            user_id=request.user.id if request.user.is_authenticated else None,
        )
        return Response({'task_id': str(task.id), 'submitted': True}, status=202)


class FactorDefinitionViewSet(viewsets.ModelViewSet):
    """因子定义 API"""
    serializer_class = FactorDefinitionSerializer

    def get_queryset(self):
        return FactorDefinition.objects.filter(is_active=True, user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    def perform_update(self, serializer):
        serializer.save()

    @action(detail=False, methods=['post'])
    def calculate(self, request):
        """实时计算因子"""
        from apps.market.services import MarketDataService
        inst_id = request.data.get('inst_id')
        bar = request.data.get('bar', '1H')
        factor_names = request.data.get('factors', None)

        if not inst_id:
            return Response({'error': 'inst_id is required'}, status=400)

        # DB 优先读取，数据不足时后台异步补齐（不阻塞）
        df = MarketDataService.get_klines_cached(inst_id=inst_id, bar=bar, limit=200, user=request.user)

        if df.empty:
            return Response({'error': 'No K-line data'}, status=404)

        engine = FactorEngine(df)
        # 注册用户自定义因子
        custom_factors = FactorDefinition.objects.filter(
            is_active=True, is_custom=True, user=request.user, formula__gt=''
        )
        custom_names = []
        for cf in custom_factors:
            engine.set_custom_formula(cf.name, cf.formula)
            custom_names.append(cf.name)
        if factor_names is None and custom_names:
            factor_names = custom_names
        results = engine.calculate_all(factor_names)
        composite, signal = engine.get_composite_score()

        return Response({
            'inst_id': inst_id,
            'bar': bar,
            'composite_score': composite,
            'composite_signal': signal,
            'factors': {
                name: {
                    'value': r.value,
                    'score': r.score,
                    'signal': r.signal,
                }
                for name, r in results.items()
            }
        })


class SignalRecordViewSet(viewsets.ReadOnlyModelViewSet):
    """交易信号 API"""
    serializer_class = SignalRecordSerializer
    filterset_fields = ['strategy', 'inst_id', 'signal', 'is_executed']

    def get_queryset(self):
        # superuser 可查看所有信号，普通用户仅自己的
        if self.request.user.is_superuser:
            return SignalRecord.objects.all()
        return SignalRecord.objects.filter(strategy__user=self.request.user)

    @action(detail=True, methods=['post'])
    def execute(self, request, pk=None):
        """执行单个信号"""
        signal = self.get_object()
        try:
            result = StrategyService.execute_signal(signal, user=request.user)
            return Response({'success': True, 'result': result})
        except Exception as e:
            return Response({'success': False, 'error': str(e)})


class BacktestResultViewSet(viewsets.ReadOnlyModelViewSet):
    """回测结果 API"""
    serializer_class = BacktestResultSerializer
    filterset_fields = ['strategy']

    def get_queryset(self):
        # superuser 可查看所有回测，普通用户仅自己的
        if self.request.user.is_superuser:
            return BacktestResult.objects.all()
        return BacktestResult.objects.filter(strategy__user=self.request.user)

    @action(detail=True, methods=['post'])
    def monte_carlo(self, request, pk=None):
        """蒙特卡洛模拟：优先返回缓存，否则异步任务执行并立即返回 task_id"""
        bt = self.get_object()
        n_simulations = int(request.data.get('n_simulations', 1000))
        # 优先使用缓存（已完成过且模拟次数一致）
        cached = bt.monte_carlo or {}
        if cached.get('status') == 'success' and cached.get('n_simulations') == n_simulations:
            return Response({**cached.get('result', {}), 'from_cache': True})

        # 同步小规模（<=300次）直接算；大规模异步
        if n_simulations <= 300:
            try:
                result = StrategyService.run_monte_carlo(bt, n_simulations=n_simulations)
                bt.monte_carlo = {'status': 'success', 'n_simulations': n_simulations, 'result': result}
                bt.save(update_fields=['monte_carlo'])
                return Response(result)
            except Exception as e:
                return Response({'error': str(e)}, status=500)

        # 异步执行
        from apps.strategy.tasks import run_monte_carlo_task
        task = run_monte_carlo_task.delay(backtest_id=bt.id, n_simulations=n_simulations)
        return Response({'task_id': str(task.id), 'submitted': True, 'backtest_id': bt.id}, status=202)

    @action(detail=True, methods=['get'])
    def export_report(self, request, pk=None):
        """导出回测报告（HTML，可打印为PDF）"""
        bt = self.get_object()
        html = StrategyService.export_backtest_html(bt)
        from django.http import HttpResponse
        resp = HttpResponse(html, content_type='text/html; charset=utf-8')
        safe_name = (bt.strategy.name or 'strategy').replace('"', '_')
        resp['Content-Disposition'] = f'attachment; filename="backtest_{safe_name}_{bt.id}.html"'
        return resp
