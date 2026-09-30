from django.db import migrations, models


def seed_factura_caja_purpose(apps, schema_editor):
    Cred = apps.get_model('andinasoft', 'IntegrationCredential')
    Mapping = apps.get_model('andinasoft', 'IntegrationPurposeMapping')
    if Mapping.objects.filter(purpose='extraccion_factura_caja').exists():
        return
    cred = (
        Cred.objects.filter(provider='openai', activo=True)
        .exclude(api_key='')
        .order_by('id')
        .first()
    )
    Mapping.objects.create(
        purpose='extraccion_factura_caja',
        credential=cred,
        model_override='',
    )


class Migration(migrations.Migration):

    dependencies = [
        ('andinasoft', '0089_carteracartaconfig'),
    ]

    operations = [
        migrations.AlterField(
            model_name='integrationpurposemapping',
            name='purpose',
            field=models.CharField(
                choices=[
                    ('extraccion_fechas_contrato', 'Extraccion fechas — PDF con texto'),
                    ('extraccion_fechas_escaneado', 'Extraccion fechas — PDF escaneado (vision)'),
                    ('extraccion_factura_caja', 'Extraccion factura de caja (PDF)'),
                ],
                max_length=64,
                unique=True,
            ),
        ),
        migrations.RunPython(seed_factura_caja_purpose, migrations.RunPython.noop),
    ]
