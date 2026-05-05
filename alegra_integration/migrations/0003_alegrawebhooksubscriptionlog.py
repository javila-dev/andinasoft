# Generated manually for AlegraWebhookSubscriptionLog

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('alegra_integration', '0002_alegracontactindex'),
    ]

    operations = [
        migrations.CreateModel(
            name='AlegraWebhookSubscriptionLog',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('event', models.CharField(db_index=True, max_length=40)),
                ('callback_url', models.TextField()),
                ('request_json', models.JSONField(blank=True, default=dict)),
                ('response_status', models.PositiveSmallIntegerField(blank=True, null=True)),
                ('response_json', models.JSONField(blank=True, default=dict)),
                ('success', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                (
                    'created_by',
                    models.ForeignKey(
                        blank=True,
                        db_constraint=False,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='alegra_webhook_subscription_logs',
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    'empresa',
                    models.ForeignKey(
                        db_constraint=False,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='alegra_webhook_logs',
                        to='andinasoft.empresas',
                    ),
                ),
            ],
            options={
                'verbose_name': 'Log suscripción webhook Alegra',
                'verbose_name_plural': 'Logs suscripción webhooks Alegra',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='alegrawebhooksubscriptionlog',
            index=models.Index(fields=['empresa', 'created_at'], name='alegra_whk_log_empresa_idx'),
        ),
    ]
