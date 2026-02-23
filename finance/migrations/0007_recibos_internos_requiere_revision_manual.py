from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('finance', '0006_recibos_internos_soporte_hash'),
    ]

    operations = [
        migrations.AddField(
            model_name='recibos_internos',
            name='requiere_revision_manual',
            field=models.BooleanField(default=False, help_text='Marca si la solicitud requiere revisión manual antes de procesar'),
        ),
    ]
