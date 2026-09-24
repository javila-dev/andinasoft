from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('crm', '0018_actareunion_duracion'),
    ]

    operations = [
        migrations.AddField(
            model_name='actareunion',
            name='adj',
            field=models.CharField(blank=True, default='', max_length=255),
        ),
        migrations.AddField(
            model_name='compromisoacta',
            name='tipo',
            field=models.CharField(
                choices=[
                    ('cambio_proyecto', 'Cambio a otro proyecto'),
                    ('envio_informacion', 'Envio de informacion'),
                    ('cita_visita', 'Cita / visita'),
                    ('respuesta_formal', 'Respuesta formal'),
                    ('gestion_interna', 'Gestion interna'),
                    ('otro', 'Otro'),
                ],
                db_index=True,
                default='otro',
                max_length=40,
            ),
        ),
        migrations.AddField(
            model_name='compromisoacta',
            name='detalle',
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AlterField(
            model_name='compromisoacta',
            name='descripcion',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.AddIndex(
            model_name='compromisoacta',
            index=models.Index(fields=['tipo', 'estado', 'fecha_compromiso'], name='crm_comprom_tipo_est_idx'),
        ),
    ]
