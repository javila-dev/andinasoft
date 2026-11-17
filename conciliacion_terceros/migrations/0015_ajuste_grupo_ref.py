from django.db import migrations, models


class Migration(migrations.Migration):
    """Los traslados guardados juntos de una empresa van en un solo comprobante en Alegra."""

    dependencies = [
        ('conciliacion_terceros', '0014_equivalencia_identificacion'),
    ]

    operations = [
        migrations.AddField(
            model_name='ajusteconciliacion',
            name='grupo_ref',
            field=models.CharField(blank=True, db_index=True, default='', max_length=40),
        ),
    ]
