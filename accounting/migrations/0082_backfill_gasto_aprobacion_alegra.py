from django.db import migrations


def backfill_alegra_gasto_estado(apps, schema_editor):
    Facturas = apps.get_model('accounting', 'Facturas')
    Facturas.objects.filter(
        origen='Alegra',
        gasto_aprobacion_estado='no_aplica',
        gasto_aprobado=False,
    ).update(gasto_aprobacion_estado='pendiente_asignacion')


class Migration(migrations.Migration):

    dependencies = [
        ('accounting', '0081_gasto_aprobacion_alegra'),
    ]

    operations = [
        migrations.RunPython(backfill_alegra_gasto_estado, migrations.RunPython.noop),
    ]
