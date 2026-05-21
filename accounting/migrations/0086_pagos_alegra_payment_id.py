from django.db import migrations, models
from django.db.models import Q


def backfill_pagos_alegra_payment_id(apps, schema_editor):
    AlegraDocument = apps.get_model('alegra_integration', 'AlegraDocument')
    Pagos = apps.get_model('accounting', 'Pagos')
    qs = (
        AlegraDocument.objects.filter(
            source_model='accounting.Pagos',
            status='sent',
        )
        .exclude(alegra_id__isnull=True)
        .exclude(alegra_id='')
        .only('source_pk', 'alegra_id')
    )
    for doc in qs.iterator():
        pk = str(doc.source_pk or '').strip()
        aid = str(doc.alegra_id or '').strip()
        if not pk or not aid:
            continue
        Pagos.objects.filter(pk=pk).filter(
            Q(alegra_payment_id__isnull=True) | Q(alegra_payment_id='')
        ).update(alegra_payment_id=aid)


class Migration(migrations.Migration):

    dependencies = [
        ('accounting', '0085_facturas_alegra_document_type'),
        ('alegra_integration', '0006_alegrawebhookinboundlog_process_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='pagos',
            name='alegra_payment_id',
            field=models.CharField(
                blank=True,
                db_index=True,
                help_text='Id del pago en Alegra (POST /payments), tras envío exitoso desde integración.',
                max_length=64,
                null=True,
            ),
        ),
        migrations.RunPython(backfill_pagos_alegra_payment_id, migrations.RunPython.noop),
    ]
