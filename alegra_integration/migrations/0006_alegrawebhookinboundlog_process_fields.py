from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('alegra_integration', '0005_alegrabillgetlog'),
    ]

    operations = [
        migrations.AddField(
            model_name='alegrawebhookinboundlog',
            name='empresa_nit',
            field=models.CharField(blank=True, default='', max_length=32),
        ),
        migrations.AddField(
            model_name='alegrawebhookinboundlog',
            name='process_status',
            field=models.CharField(blank=True, default='', max_length=16),
        ),
        migrations.AddField(
            model_name='alegrawebhookinboundlog',
            name='process_detail',
            field=models.CharField(blank=True, default='', max_length=128),
        ),
        migrations.AddField(
            model_name='alegrawebhookinboundlog',
            name='factura_id',
            field=models.IntegerField(blank=True, null=True),
        ),
    ]
