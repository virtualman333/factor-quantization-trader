"""
通知 API：
- GET  /notifications/                分页列表（?unread_only=1 仅未读 / ?type=xxx）
- POST /notifications/mark_read/      单条或批量标记已读 {ids: [...]}
- POST /notifications/mark_all_read/  全部标记已读
- GET  /notifications/summary/        未读数汇总（顶栏铃铛角标）
- DELETE /notifications/<id>/         删除一条
- POST /notifications/clear_all/      清空历史（可选）
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import Notification
from .serializers import NotificationSerializer, NotificationSummarySerializer


class NotificationViewSet(viewsets.ModelViewSet):
    serializer_class = NotificationSerializer
    # 写操作（POST/PUT/DELETE）按项目全局权限走；当前项目 AllowAny，生产需收紧
    http_method_names = ['get', 'post', 'delete', 'head', 'options']

    def get_queryset(self):
        qs = Notification.objects.all()
        # 多用户模式下按当前用户过滤；AllowAny 单用户模式下 user=None 也显示
        if getattr(self.request, 'user', None) and self.request.user.is_authenticated:
            qs = qs.filter(user=self.request.user)
        else:
            qs = qs.filter(user__isnull=True)
        # 查询参数过滤
        if self.request.query_params.get('unread_only') in ('1', 'true'):
            qs = qs.filter(read=False)
        t = self.request.query_params.get('type')
        if t:
            qs = qs.filter(type=t)
        limit = self.request.query_params.get('limit')
        try:
            qs = qs[: int(limit)] if (limit and int(limit) > 0) else qs[:200]
        except (TypeError, ValueError):
            qs = qs[:200]
        return qs

    @action(detail=False, methods=['post'], url_path='mark_read')
    def mark_read(self, request):
        """单条或批量标记已读。body: {ids: [1,2,3]} 或 {id: 1}"""
        ids = request.data.get('ids') or []
        single_id = request.data.get('id')
        if single_id:
            ids = [single_id]
        if not isinstance(ids, list) or not ids:
            return Response({'error': '参数 ids 需要非空数组'}, status=400)
        qs = self.get_queryset().filter(pk__in=ids, read=False)
        updated = qs.update(read=True)
        return Response({'updated': updated})

    @action(detail=False, methods=['post'], url_path='mark_all_read')
    def mark_all_read(self, request):
        qs = self.get_queryset().filter(read=False)
        updated = qs.update(read=True)
        return Response({'updated': updated})

    @action(detail=False, methods=['get'], url_path='summary')
    def summary(self, request):
        """顶栏铃铛所需：未读数按 type/level 汇总。"""
        from django.db.models import Count
        qs = self.get_queryset().filter(read=False)
        total = qs.count()
        by_type = dict(
            qs.values_list('type').annotate(n=Count('id')).order_by()
        )
        by_level = dict(
            qs.values_list('level').annotate(n=Count('id')).order_by()
        )
        # 把 IntegerChoice 的 key 从数字转成字符串（前端更好用）
        by_level = {Notification.LEVEL(k).label: v for k, v in by_level.items()}
        data = {'total_unread': total, 'by_type': by_type, 'by_level': by_level}
        return Response(NotificationSummarySerializer(data).data)

    @action(detail=False, methods=['post'], url_path='clear_all')
    def clear_all(self, request):
        qs = self.get_queryset()
        count, _ = qs.delete()
        return Response({'deleted': count})
