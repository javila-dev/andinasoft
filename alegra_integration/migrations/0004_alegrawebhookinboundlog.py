# Generated manually for AlegraWebhookInboundLog

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('alegra_integration', '0003_alegrawebhooksubscriptionlog'),
    ]

    operations = [
        migrations.CreateModel(
            name='AlegraWebhookInboundLog',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('http_method', models.CharField(db_index=True, max_length=16)),
                ('content_type', models.CharField(blank=True, default='', max_length=255)),
                ('remote_addr', models.CharField(blank=True, default='', max_length=255)),
                ('query_string', models.TextField(blank=True, default='')),
                ('payload', models.JSONField(blank=True, default=dict)),
                ('raw_body', models.TextField(blank=True, default='')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'verbose_name': 'Log webhook entrante Alegra',
                'verbose_name_plural': 'Logs webhooks entrantes Alegra',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='alegrawebhookinboundlog',
            index=models.Index(fields=['created_at'], name='alegra_whk_in_created_idx'),
        ),
    ]
