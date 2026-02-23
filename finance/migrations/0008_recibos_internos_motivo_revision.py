from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('finance', '0007_recibos_internos_requiere_revision_manual'),
    ]

    operations = [
        migrations.AddField(
            model_name='recibos_internos',
            name='motivo_revision',
            field=models.TextField(blank=True, help_text='Motivo por el cual la solicitud requiere revisión manual', null=True),
        ),
    ]
