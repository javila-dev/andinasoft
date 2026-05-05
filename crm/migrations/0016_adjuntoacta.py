from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('crm', '0015_actareunion_compromisos'),
    ]

    operations = [
        migrations.CreateModel(
            name='AdjuntoActa',
            fields=[
                ('id_adjunto', models.AutoField(primary_key=True, serialize=False)),
                ('tipo', models.CharField(choices=[('Nota', 'Nota'), ('Audio', 'Audio'), ('Documento', 'Documento'), ('Imagen', 'Imagen'), ('Otro', 'Otro')], default='Documento', max_length=255)),
                ('descripcion', models.CharField(blank=True, max_length=255, null=True)),
                ('archivo', models.FileField(upload_to='crm/actas')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('acta', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='adjuntos', to='crm.ActaReunion')),
                ('cargado_por', models.ForeignKey(db_constraint=False, on_delete=django.db.models.deletion.PROTECT, related_name='adjuntos_acta_cargados', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Adjunto de acta',
                'verbose_name_plural': 'Adjuntos de acta',
                'ordering': ['-created_at'],
            },
        ),
    ]
