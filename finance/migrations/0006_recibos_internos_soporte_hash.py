from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('finance', '0005_recibos_internos_anulado'),
    ]

    operations = [
        migrations.AddField(
            model_name='recibos_internos',
            name='soporte_hash',
            field=models.CharField(blank=True, max_length=64, null=True),
        ),
    ]
