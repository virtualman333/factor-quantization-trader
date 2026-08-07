"""用户认证相关 API。

提供登录、Token 刷新、当前用户信息查看以及管理员创建用户接口。
"""

from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from rest_framework import permissions, serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from apps.account.throttles import LoginRateThrottle


class LoginSerializer(serializers.Serializer):
    """登录请求参数校验。"""

    username = serializers.CharField(required=True, allow_blank=False)
    password = serializers.CharField(
        required=True, allow_blank=False, write_only=True
    )


class RegisterSerializer(serializers.Serializer):
    """管理员创建用户请求参数校验。"""

    username = serializers.CharField(required=True, allow_blank=False)
    password = serializers.CharField(
        required=True, allow_blank=False, write_only=True, min_length=6
    )
    is_staff = serializers.BooleanField(default=False, required=False)


class LoginView(APIView):
    """用户登录，返回 JWT access/refresh token。"""

    permission_classes = [permissions.AllowAny]
    authentication_classes = []
    throttle_classes = [LoginRateThrottle]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        username = serializer.validated_data['username']
        password = serializer.validated_data['password']
        user = authenticate(username=username, password=password)
        if user is None or not user.is_active:
            return Response(
                {
                    'code': status.HTTP_401_UNAUTHORIZED,
                    'message': '用户名或密码错误',
                    'data': None,
                },
                status=status.HTTP_401_UNAUTHORIZED,
            )
        refresh = RefreshToken.for_user(user)
        return Response(
            {
                'code': status.HTTP_200_OK,
                'message': '登录成功',
                'data': {
                    'access': str(refresh.access_token),
                    'refresh': str(refresh),
                    'user': {
                        'id': user.id,
                        'username': user.username,
                        'is_staff': user.is_staff,
                    },
                },
            },
            status=status.HTTP_200_OK,
        )


class TokenRefreshView(APIView):
    """刷新 access token。"""

    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def post(self, request):
        refresh_token = request.data.get('refresh')
        if not refresh_token:
            return Response(
                {
                    'code': status.HTTP_400_BAD_REQUEST,
                    'message': '缺少 refresh token',
                    'data': None,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            refresh = RefreshToken(refresh_token)
            access = refresh.access_token
            return Response(
                {
                    'code': status.HTTP_200_OK,
                    'message': '刷新成功',
                    'data': {
                        'access': str(access),
                        'refresh': str(refresh),
                    },
                },
                status=status.HTTP_200_OK,
            )
        except Exception as exc:
            return Response(
                {
                    'code': status.HTTP_401_UNAUTHORIZED,
                    'message': 'refresh token 无效或已过期',
                    'data': str(exc),
                },
                status=status.HTTP_401_UNAUTHORIZED,
            )


class MeView(APIView):
    """获取当前登录用户信息。"""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        return Response(
            {
                'code': status.HTTP_200_OK,
                'message': 'success',
                'data': {
                    'id': user.id,
                    'username': user.username,
                    'is_staff': user.is_staff,
                },
            },
            status=status.HTTP_200_OK,
        )


class RegisterView(APIView):
    """用户注册（公开接口，允许任何人注册）。"""

    permission_classes = [permissions.AllowAny]
    authentication_classes = []
    throttle_classes = [LoginRateThrottle]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        username = serializer.validated_data['username']
        if User.objects.filter(username=username).exists():
            return Response(
                {
                    'code': status.HTTP_400_BAD_REQUEST,
                    'message': '用户名已存在',
                    'data': None,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        user = User.objects.create_user(
            username=username,
            password=serializer.validated_data['password'],
        )
        return Response(
            {
                'code': status.HTTP_201_CREATED,
                'message': '注册成功',
                'data': {
                    'id': user.id,
                    'username': user.username,
                    'is_staff': user.is_staff,
                },
            },
            status=status.HTTP_201_CREATED,
        )


class ChangePasswordView(APIView):
    """修改密码。"""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        old_password = request.data.get('old_password')
        new_password = request.data.get('new_password')
        if not old_password or not new_password:
            return Response(
                {'code': 400, 'message': '请提供旧密码和新密码', 'data': None},
                status=400,
            )
        if len(new_password) < 6:
            return Response(
                {'code': 400, 'message': '新密码长度至少6位', 'data': None},
                status=400,
            )
        user = request.user
        if not user.check_password(old_password):
            return Response(
                {'code': 400, 'message': '旧密码错误', 'data': None},
                status=400,
            )
        user.set_password(new_password)
        user.save()
        return Response(
            {'code': 200, 'message': '密码修改成功', 'data': None},
            status=200,
        )
