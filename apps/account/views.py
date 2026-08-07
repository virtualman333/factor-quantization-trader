"""账户管理 API 视图"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.account.models import (
    BalanceSnapshot, PositionSnapshot, NetValueHistory,
    OKXCredential, SystemConfig,
)
from apps.account.serializers import (
    BalanceSnapshotSerializer, PositionSnapshotSerializer, NetValueHistorySerializer,
    OKXCredentialSerializer, SystemConfigSerializer,
)
from apps.account.services import AccountService
from core.okx_client import OKXClient


def get_active_credential():
    """根据系统当前环境获取对应凭证"""
    config = SystemConfig.get_config()
    return OKXCredential.objects.filter(name=config.active_environment).first()


class SystemConfigViewSet(viewsets.ViewSet):
    """系统全局配置 API"""

    def list(self, request):
        config = SystemConfig.get_config()
        return Response(SystemConfigSerializer(config).data)

    def create(self, request):
        config = SystemConfig.get_config()
        env = request.data.get('active_environment')
        if env not in ('demo', 'live'):
            return Response({'detail': 'active_environment 必须是 demo 或 live'}, status=400)
        config.active_environment = env
        config.save()
        # 切换环境后重置 OKX 客户端
        import core.okx_client as okx_client_module
        okx_client_module._okx_client = None
        return Response(SystemConfigSerializer(config).data)


class OKXCredentialViewSet(viewsets.ModelViewSet):
    """OKX API 凭证管理 API（按 demo / live 分别存储）"""
    queryset = OKXCredential.objects.all().order_by('name')
    serializer_class = OKXCredentialSerializer
    lookup_field = 'name'

    def get_object(self):
        # 允许通过 name=demo 或 name=live 访问
        name = self.kwargs.get(self.lookup_field)
        if name in ('demo', 'live'):
            obj, _ = OKXCredential.objects.get_or_create(name=name, defaults={
                'api_key': '', 'api_secret': '', 'passphrase': '',
                'flag': '1' if name == 'demo' else '0',
            })
            return obj
        return super().get_object()

    def perform_create(self, serializer):
        instance = serializer.save()
        self._reset_okx_client()

    def perform_update(self, serializer):
        serializer.save()
        self._reset_okx_client()

    def perform_destroy(self, instance):
        instance.delete()
        self._reset_okx_client()

    def _reset_okx_client(self):
        """凭证变更后重置全局 OKX 客户端单例"""
        import core.okx_client as okx_client_module
        okx_client_module._okx_client = None

    @action(detail=False, methods=['get'])
    def active(self, request):
        """获取当前环境对应的凭证"""
        credential = get_active_credential()
        if not credential:
            config = SystemConfig.get_config()
            return Response({'detail': f'未配置 {config.get_active_environment_display()} 凭证'}, status=404)
        serializer = self.get_serializer(credential)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def by_env(self, request):
        """按环境名获取凭证 ?env=demo/live"""
        env = request.query_params.get('env')
        if env not in ('demo', 'live'):
            return Response({'detail': 'env 参数必须是 demo 或 live'}, status=400)
        credential, _ = OKXCredential.objects.get_or_create(name=env, defaults={
            'api_key': '', 'api_secret': '', 'passphrase': '',
            'flag': '1' if env == 'demo' else '0',
        })
        serializer = self.get_serializer(credential)
        return Response(serializer.data)

    @action(detail=False, methods=['post'])
    def switch_env(self, request):
        """切换当前交易环境"""
        env = request.data.get('environment')
        if env not in ('demo', 'live'):
            return Response({'detail': 'environment 必须是 demo 或 live'}, status=400)
        config = SystemConfig.get_config()
        config.active_environment = env
        config.save()
        self._reset_okx_client()
        credential = get_active_credential()
        return Response({
            'environment': env,
            'credential_configured': credential is not None and bool(credential.api_key),
        })

    @action(detail=False, methods=['post'])
    def test_connection(self, request):
        """测试指定环境凭证能否连接 OKX（默认当前环境）"""
        env = request.data.get('env') or request.query_params.get('env')
        if env and env not in ('demo', 'live'):
            return Response({'detail': 'env 参数必须是 demo 或 live'}, status=400)

        if env:
            credential = OKXCredential.objects.filter(name=env).first()
            env_label = '模拟盘' if env == 'demo' else '实盘'
        else:
            credential = get_active_credential()
            config = SystemConfig.get_config()
            env_label = config.get_active_environment_display()

        if not credential or not credential.api_key:
            return Response({'connected': False, 'error': f'未配置 {env_label} 凭证'}, status=400)

        client = OKXClient(
            api_key=credential.api_key,
            api_secret=credential.api_secret,
            passphrase=credential.passphrase,
            flag=credential.flag,
        )
        try:
            result = client.get_account_config()
            if result.get('code') == '0':
                return Response({'connected': True, 'data': result.get('data', [])})
            return Response({'connected': False, 'error': result.get('msg', 'Unknown error')}, status=400)
        except Exception as e:
            return Response({'connected': False, 'error': str(e)}, status=400)





class BalanceSnapshotViewSet(viewsets.ReadOnlyModelViewSet):
    """余额快照 API"""
    queryset = BalanceSnapshot.objects.all()
    serializer_class = BalanceSnapshotSerializer
    filterset_fields = ['ccy']

    @action(detail=False, methods=['post'])
    def snapshot(self, request):
        """手动保存余额快照"""
        snapshots = AccountService.snapshot_balance()
        serializer = BalanceSnapshotSerializer(snapshots, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def live(self, request):
        """获取实时余额（直接从 OKX）"""
        try:
            balance = AccountService.get_balance_from_api()
            return Response(balance)
        except Exception as e:
            return Response({'error': str(e)}, status=500)


class PositionSnapshotViewSet(viewsets.ReadOnlyModelViewSet):
    """持仓快照 API"""
    queryset = PositionSnapshot.objects.all()
    serializer_class = PositionSnapshotSerializer
    filterset_fields = ['inst_id', 'pos_side']

    @action(detail=False, methods=['post'])
    def snapshot(self, request):
        """手动保存持仓快照"""
        inst_type = request.data.get('inst_type', '')
        snapshots = AccountService.snapshot_positions(inst_type)
        serializer = PositionSnapshotSerializer(snapshots, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def live(self, request):
        """获取实时持仓"""
        try:
            inst_type = request.query_params.get('inst_type', '')
            positions = AccountService.get_positions_from_api(inst_type)
            return Response({
                inst_id: {
                    'pos': p.pos, 'avg_px': p.avg_px,
                    'mark_px': p.mark_px, 'upl': p.upl,
                    'margin': p.margin, 'leverage': p.leverage,
                }
                for inst_id, p in positions.items()
            })
        except Exception as e:
            return Response({'error': str(e)}, status=500)


class NetValueHistoryViewSet(viewsets.ReadOnlyModelViewSet):
    """净值历史 API"""
    queryset = NetValueHistory.objects.all()
    serializer_class = NetValueHistorySerializer

    @action(detail=False, methods=['post'])
    def record(self, request):
        """手动记录净值"""
        record = AccountService.record_net_value()
        serializer = NetValueHistorySerializer(record)
        return Response(serializer.data)
