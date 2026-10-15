import django.core.serializers.json
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('conciliacion_terceros', '0003_ajustes'),
    ]

    operations = [
        migrations.CreateModel(
            name='CorreccionIdentificacion',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('id_errado', models.CharField(db_index=True, max_length=40)),
                ('id_correcto', models.CharField(db_index=True, max_length=40)),
                ('modo', models.CharField(max_length=20)),
                ('motivo', models.TextField(blank=True, default='')),
                ('estado', models.CharField(choices=[('ejecutada', 'Ejecutada'), ('parcial', 'Parcial (con error)'), ('revertida', 'Revertida')], default='ejecutada', max_length=20)),
                ('vista_previa', models.JSONField(blank=True, default=dict, encoder=django.core.serializers.json.DjangoJSONEncoder)),
                ('detalle', models.JSONField(blank=True, default=dict, encoder=django.core.serializers.json.DjangoJSONEncoder)),
                ('alegra', models.JSONField(blank=True, default=list, encoder=django.core.serializers.json.DjangoJSONEncoder)),
                ('error', models.TextField(blank=True, default='')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('revertido_en', models.DateTimeField(blank=True, null=True)),
                ('conciliacion', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='correcciones', to='conciliacion_terceros.conciliacion')),
                ('created_by', models.ForeignKey(blank=True, db_constraint=False, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL)),
            ],
            options={'verbose_name': 'Corrección de identificación', 'verbose_name_plural': 'Correcciones de identificación', 'ordering': ['-created_at']},
        ),
    ]
