from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('andinasoft', '0082_integrationcredential_anthropic'),
    ]

    operations = [
        migrations.AlterField(
            model_name='integrationpurposemapping',
            name='purpose',
            field=models.CharField(
                choices=[
                    ('extraccion_fechas_contrato', 'Extraccion fechas — PDF con texto'),
                    ('extraccion_fechas_escaneado', 'Extraccion fechas — PDF escaneado (vision)'),
                ],
                max_length=64,
                unique=True,
            ),
        ),
    ]
