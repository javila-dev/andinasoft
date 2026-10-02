from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('andinasoft', '0093_purpose_extraccion_factura_caja'),
    ]

    operations = [
        migrations.AddField(
            model_name='promesaotrosi',
            name='fecha_promesa_anterior',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='promesaotrosi',
            name='fecha_promesa_nueva',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='promesaotrosi',
            name='tipo',
            field=models.CharField(
                choices=[
                    ('entrega', 'Entrega'),
                    ('escritura', 'Escritura'),
                    ('ambos', 'Entrega y escritura'),
                    ('novacion', 'Novacion'),
                ],
                max_length=20,
            ),
        ),
    ]
