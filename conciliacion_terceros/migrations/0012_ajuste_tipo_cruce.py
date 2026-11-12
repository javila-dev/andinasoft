from django.db import migrations, models


class Migration(migrations.Migration):
    """Traslado tipo «cruce»: el saldo se cruza contra una cuenta que no hace parte de la conciliación."""

    dependencies = [
        ('conciliacion_terceros', '0011_fuente_incluidos'),
    ]

    operations = [
        migrations.AlterField(
            model_name='ajusteconciliacion',
            name='tipo',
            field=models.CharField(choices=[('cuenta', 'Entre cuentas del mismo tercero'), ('tercero', 'Entre terceros'),
                                            ('cruce', 'Cruce con otra cuenta')], max_length=10),
        ),
    ]
