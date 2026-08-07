"""订单管理 API 视图"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.orders.models import TradeOrder, OrderLog, OrderTemplate
from apps.orders.serializers import TradeOrderSerializer, OrderLogSerializer, OrderTemplateSerializer
from apps.orders.services import OrderService


class OrderTemplateViewSet(viewsets.ModelViewSet):
    """订单模板 API"""
    serializer_class = OrderTemplateSerializer

    def get_queryset(self):
        return OrderTemplate.objects.filter(user=self.request.user).order_by('-created_at')

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=True, methods=['post'])
    def place(self, request, pk=None):
        """用模板下单"""
        template = self.get_object()
        try:
            result = OrderService.create_order(
                inst_id=request.data.get('inst_id') or template.inst_id,
                side=template.side,
                ord_type=template.ord_type,
                sz=request.data.get('sz') or (str(template.sz) if template.sz else None),
                px=request.data.get('px') or (str(template.px) if template.px else ''),
                td_mode=template.td_mode,
                source='template',
                user=request.user,
            )
            return Response(result, status=201)
        except Exception as e:
            return Response({'error': str(e)}, status=400)


class TradeOrderViewSet(viewsets.ModelViewSet):
    """交易订单 API"""
    serializer_class = TradeOrderSerializer
    filterset_fields = ['inst_id', 'side', 'ord_type', 'state', 'source']

    def get_queryset(self):
        return TradeOrder.objects.filter(user=self.request.user)

    def create(self, request, *args, **kwargs):
        """提交新订单"""
        try:
            result = OrderService.create_order(
                inst_id=request.data.get('inst_id'),
                side=request.data.get('side'),
                ord_type=request.data.get('ord_type', 'market'),
                sz=request.data.get('sz'),
                px=request.data.get('px', ''),
                td_mode=request.data.get('td_mode', 'cash'),
                source=request.data.get('source', 'api'),
                strategy_id=request.data.get('strategy_id'),
                signal_id=request.data.get('signal_id'),
                user=request.user,
            )
            return Response(result, status=201)
        except Exception as e:
            return Response({'error': str(e)}, status=400)

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """撤销订单"""
        order = self.get_object()
        try:
            result = OrderService.cancel_order(
                ord_id=order.ord_id,
                inst_id=order.inst_id,
                user=request.user,
            )
            return Response(result)
        except Exception as e:
            return Response({'error': str(e)}, status=400)

    @action(detail=True, methods=['post'])
    def sync(self, request, pk=None):
        """同步订单状态"""
        order = self.get_object()
        try:
            updated = OrderService.sync_order_status(order.ord_id, user=request.user)
            if updated:
                serializer = TradeOrderSerializer(updated)
                return Response(serializer.data)
            return Response({'error': 'Sync failed'}, status=500)
        except Exception as e:
            return Response({'error': str(e)}, status=500)

    @action(detail=False, methods=['post'])
    def sync_pending(self, request):
        """同步所有待处理订单"""
        count = OrderService.sync_pending_orders(user=request.user)
        return Response({'synced': count})

    @action(detail=False, methods=['post'])
    def close_position(self, request):
        """市价平仓"""
        try:
            result = OrderService.place_market_close(
                inst_id=request.data.get('inst_id'),
                sz=request.data.get('sz'),
                side=request.data.get('side', ''),
                td_mode=request.data.get('td_mode', 'cash'),
                source=request.data.get('source', 'api'),
                user=request.user,
            )
            return Response(result, status=201)
        except Exception as e:
            return Response({'error': str(e)}, status=400)

    @action(detail=False, methods=['post'])
    def batch(self, request):
        """批量下单"""
        orders = request.data.get('orders', [])
        if not orders:
            return Response({'error': 'orders 必填，如 [{inst_id, side, sz, ord_type}]'}, status=400)
        results = []
        for o in orders:
            try:
                result = OrderService.create_order(
                    inst_id=o.get('inst_id'),
                    side=o.get('side'),
                    ord_type=o.get('ord_type', 'market'),
                    sz=o.get('sz'),
                    px=o.get('px', ''),
                    td_mode=o.get('td_mode', 'cash'),
                    source='batch',
                    user=request.user,
                )
                results.append({'inst_id': o.get('inst_id'), 'success': True, **result})
            except Exception as e:
                results.append({'inst_id': o.get('inst_id'), 'success': False, 'error': str(e)})
        success_count = sum(1 for r in results if r.get('success'))
        return Response({'total': len(results), 'success': success_count, 'results': results})

    @action(detail=False, methods=['post'])
    def algo(self, request):
        """条件单/止盈止损单（OKX Algo 交易）"""
        try:
            result = OrderService.place_algo(
                inst_id=request.data.get('inst_id'),
                side=request.data.get('side'),
                sz=request.data.get('sz'),
                td_mode=request.data.get('td_mode', 'cash'),
                ord_type=request.data.get('ord_type', 'conditional'),
                trigger_px=request.data.get('trigger_px', ''),
                px=request.data.get('px', ''),
                tp_trigger_px=request.data.get('tp_trigger_px', ''),
                tp_order_px=request.data.get('tp_order_px', ''),
                sl_trigger_px=request.data.get('sl_trigger_px', ''),
                sl_order_px=request.data.get('sl_order_px', ''),
                source='algo',
                user=request.user,
            )
            return Response(result, status=201)
        except Exception as e:
            return Response({'error': str(e)}, status=400)

    @action(detail=False, methods=['post'])
    def twap(self, request):
        """TWAP 时间加权算法单：拆分为 N 个子单按时间间隔执行"""
        try:
            result = OrderService.place_twap(
                inst_id=request.data.get('inst_id'),
                side=request.data.get('side'),
                total_sz=request.data.get('total_sz'),
                slices=request.data.get('slices', 5),
                interval=request.data.get('interval', 60),
                td_mode=request.data.get('td_mode', 'cash'),
                user=request.user,
            )
            return Response(result, status=201)
        except Exception as e:
            return Response({'error': str(e)}, status=400)

    @action(detail=False, methods=['post'])
    def iceberg(self, request):
        """冰山算法单：每次只暴露部分数量"""
        try:
            result = OrderService.place_iceberg(
                inst_id=request.data.get('inst_id'),
                side=request.data.get('side'),
                total_sz=request.data.get('total_sz'),
                display_sz=request.data.get('display_sz'),
                slices=request.data.get('slices', 5),
                px=request.data.get('px', ''),
                td_mode=request.data.get('td_mode', 'cash'),
                user=request.user,
            )
            return Response(result, status=201)
        except Exception as e:
            return Response({'error': str(e)}, status=400)


class OrderLogViewSet(viewsets.ReadOnlyModelViewSet):
    """订单日志 API"""
    serializer_class = OrderLogSerializer
    filterset_fields = ['order', 'action']

    def get_queryset(self):
        return OrderLog.objects.filter(order__user=self.request.user)
