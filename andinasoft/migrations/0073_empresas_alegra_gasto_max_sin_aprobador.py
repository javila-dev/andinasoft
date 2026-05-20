from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('andinasoft', '0072_empresas_alegra'),
    ]

    operations = [
        migrations.AddField(
            model_name='empresas',
            name='alegra_gasto_max_sin_aprobador',
            field=models.BigIntegerField(
                blank=True,
                null=True,
                help_text=(
                    'Monto máximo (COP, entero) para asignar/aprobar un gasto Alegra sin aprobador. '
                    'Vacío o 0 = siempre exige aprobador.'
                ),
            ),
        ),
    ]
