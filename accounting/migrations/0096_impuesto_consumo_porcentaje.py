from django.db import migrations

# El formulario de gastos saca la tasa del texto de la descripción ("... 8%").
ANTES = 'IMPUESTO AL CONSUMO'
DESPUES = 'IMPUESTO AL CONSUMO 8%'


def poner_porcentaje(apps, schema_editor):
    impuestos = apps.get_model('accounting', 'impuestos_legalizacion')
    impuestos.objects.filter(descripcion__iexact=ANTES).update(descripcion=DESPUES)


def quitar_porcentaje(apps, schema_editor):
    impuestos = apps.get_model('accounting', 'impuestos_legalizacion')
    impuestos.objects.filter(descripcion=DESPUES).update(descripcion=ANTES)


class Migration(migrations.Migration):

    dependencies = [
        ('accounting', '0095_gastos_caja_lineas_retenciones'),
    ]

    operations = [
        migrations.RunPython(poner_porcentaje, quitar_porcentaje),
    ]
