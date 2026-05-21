from django.db import migrations, models


def backfill_alegra_document_type(apps, schema_editor):
    Facturas = apps.get_model('accounting', 'Facturas')
    AlegraMapping = apps.get_model('alegra_integration', 'AlegraMapping')

    for fac in Facturas.objects.exclude(alegra_bill_id__isnull=True).exclude(alegra_bill_id='').iterator():
        bid = (fac.alegra_bill_id or '').strip()
        if ':journal:' in bid:
            doc_type = 'journal'
        elif ':' in bid:
            doc_type = 'bill'
        else:
            continue
        Facturas.objects.filter(pk=fac.pk).update(alegra_document_type=doc_type)
        if doc_type != 'bill':
            continue
        nit, rest = bid.split(':', 1)
        if not rest or rest.startswith('journal'):
            continue
        AlegraMapping.objects.update_or_create(
            empresa_id=nit,
            proyecto_id=None,
            mapping_type='bill',
            local_model='accounting.Facturas',
            local_pk=str(fac.pk),
            local_code='',
            defaults={
                'alegra_id': rest,
                'description': (fac.nrofactura or '')[:255],
                'active': True,
            },
        )


class Migration(migrations.Migration):

    dependencies = [
        ('accounting', '0084_fix_gasto_aprobacion_comentario_mysql_default'),
        ('alegra_integration', '0006_alegrawebhookinboundlog_process_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='facturas',
            name='alegra_document_type',
            field=models.CharField(
                blank=True,
                choices=[
                    ('', '—'),
                    ('bill', 'Bill (documento compra / webhook)'),
                    ('journal', 'Journal (comprobante manual)'),
                ],
                db_index=True,
                default='',
                help_text='Origen del id en Alegra: bill vía webhook o journal al radicar manual.',
                max_length=16,
            ),
        ),
        migrations.RunPython(backfill_alegra_document_type, migrations.RunPython.noop),
    ]
