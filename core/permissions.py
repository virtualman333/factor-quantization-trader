"""自定义权限类"""

from rest_framework import permissions


class IsOwnerOrReadOnly(permissions.BasePermission):
    """对象级权限：只有所有者可以编辑，其他用户只读"""

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        return obj.user == request.user


class IsOwner(permissions.BasePermission):
    """对象级权限：只有所有者可以访问"""

    def has_object_permission(self, request, view, obj):
        return obj.user == request.user
