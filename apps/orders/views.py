"""订单管理 API 视图"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.orders.models import TradeOrder, OrderLog
from apps.orders.serializers import TradeOrderSerializer, OrderLogSerializer
from apps.orders.services import OrderService


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


class OrderLogViewSet(viewsets.ReadOnlyModelViewSet):
    """订单日志 API"""
    serializer_class = OrderLogSerializer
    filterset_fields = ['order', 'action']

    def get_queryset(self):
        return OrderLog.objects.filter(order__user=self.request.user)
