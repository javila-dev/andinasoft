from django.db import migrations, models
from django.db.models import F


def cargado_en_inicial(apps, schema_editor):
    Fuente = apps.get_model('conciliacion_terceros', 'FuenteConciliacion')
    Fuente.objects.filter(cargado_en__isnull=True).update(cargado_en=F('created_at'))


class Migration(migrations.Migration):
    """Evita contar dos veces: momento de carga del archivo, archivo anterior y movimientos que el archivo ya trae."""

    dependencies = [
        ('conciliacion_terceros', '0010_intereses_previos'),
    ]

    operations = [
        migrations.AddField(model_name='fuenteconciliacion', name='cargado_en', field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name='fuenteconciliacion', name='anterior', field=models.JSONField(blank=True, default=dict)),
        migrations.AddField(model_name='fuenteconciliacion', name='incluidos', field=models.JSONField(blank=True, default=dict)),
        migrations.RunPython(cargado_en_inicial, migrations.RunPython.noop),
    ]
