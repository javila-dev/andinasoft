from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('conciliacion_terceros', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='conciliacion',
            name='proyectos_excluidos',
            field=models.JSONField(blank=True, default=list),
        ),
    ]
