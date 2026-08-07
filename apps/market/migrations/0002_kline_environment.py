# Generated migration: add environment field to KLine

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('market', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='kline',
            name='environment',
            field=models.CharField(
                choices=[('demo', '模拟盘'), ('live', '实盘')],
                db_index=True,
                default='demo',
                max_length=10,
                verbose_name='交易环境',
            ),
        ),
        migrations.AlterUniqueTogether(
            name='kline',
            unique_together={('environment', 'instrument', 'bar', 'timestamp')},
        ),
        migrations.AddIndex(
            model_name='kline',
            index=models.Index(
                fields=['environment', 'instrument', 'bar', 'timestamp'],
                name='market_klin_environ_cd74b9_idx',
            ),
        ),
    ]
