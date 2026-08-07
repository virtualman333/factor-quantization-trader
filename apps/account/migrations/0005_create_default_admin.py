"""创建默认管理员账号。

注意：此迁移仅用于首次部署/开发环境快速登录。
生产环境请务必：
  1. 通过环境变量 DEFAULT_ADMIN_PASSWORD 设置强密码；
  2. 登录后立即修改密码；
  3. 考虑移除此迁移并使用 python manage.py createsuperuser 手动创建。
"""

import os

from django.db import migrations


def create_default_admin(apps, schema_editor):
    User = apps.get_model('auth', 'User')
    if User.objects.filter(username='admin').exists():
        return
    password = os.environ.get('DEFAULT_ADMIN_PASSWORD', 'admin123')
    user = User(
        username='admin',
        is_staff=True,
        is_superuser=True,
    )
    user.set_password(password)
    user.save()


def remove_default_admin(apps, schema_editor):
    User = apps.get_model('auth', 'User')
    User.objects.filter(username='admin').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('account', '0004_migrate_default_to_demo'),
        ('auth', '0012_alter_user_first_name_max_length'),
    ]

    operations = [
        migrations.RunPython(create_default_admin, remove_default_admin),
    ]
