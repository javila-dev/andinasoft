from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounting', '0093_gastos_caja_estado_antes_devolver'),
    ]

    operations = [
        migrations.AddField(
            model_name='gastos_caja',
            name='soporte_hash',
            field=models.CharField(
                blank=True,
                db_index=True,
                help_text='SHA256 del PDF de soporte (dedupe exacto por contenido).',
                max_length=64,
                null=True,
            ),
        ),
    ]
