from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('andinasoft', '0071_proyectos_activo'),
        ('crm', '0014_auto_20210907_2042'),
    ]

    operations = [
        migrations.CreateModel(
            name='ActaReunion',
            fields=[
                ('id_acta', models.AutoField(primary_key=True, serialize=False)),
                ('fecha_reunion', models.DateField()),
                ('hora_reunion', models.TimeField(blank=True, null=True)),
                ('tipo_reunion', models.CharField(choices=[('Servicio al cliente', 'Servicio al cliente'), ('Gerencia', 'Gerencia'), ('Comercial', 'Comercial'), ('Otro', 'Otro')], max_length=255)),
                ('canal', models.CharField(choices=[('Presencial', 'Presencial'), ('Llamada', 'Llamada'), ('Meet', 'Meet'), ('WhatsApp', 'WhatsApp'), ('Correo', 'Correo')], max_length=255)),
                ('asunto', models.CharField(max_length=255)),
                ('resumen', models.TextField()),
                ('decisiones', models.TextField(blank=True, null=True)),
                ('proxima_reunion', models.DateField(blank=True, null=True)),
                ('estado', models.CharField(choices=[('Borrador', 'Borrador'), ('Cerrada', 'Cerrada'), ('Anulada', 'Anulada')], default='Borrador', max_length=255)),
                ('fecha_creacion', models.DateTimeField(auto_now_add=True)),
                ('fecha_actualizacion', models.DateTimeField(auto_now=True)),
                ('cliente', models.ForeignKey(blank=True, null=True, db_constraint=False, on_delete=django.db.models.deletion.PROTECT, to='andinasoft.clientes')),
                ('creado_por', models.ForeignKey(db_constraint=False, on_delete=django.db.models.deletion.PROTECT, related_name='actas_creadas', to=settings.AUTH_USER_MODEL)),
                ('lider_reunion', models.ForeignKey(db_constraint=False, on_delete=django.db.models.deletion.PROTECT, related_name='actas_lideradas', to=settings.AUTH_USER_MODEL)),
                ('proyecto', models.ForeignKey(blank=True, null=True, db_constraint=False, on_delete=django.db.models.deletion.PROTECT, to='andinasoft.proyectos')),
            ],
            options={
                'verbose_name': 'Acta de reunion',
                'verbose_name_plural': 'Actas de reunion',
                'ordering': ['-fecha_reunion', '-id_acta'],
            },
        ),
        migrations.CreateModel(
            name='CompromisoActa',
            fields=[
                ('id_compromiso', models.AutoField(primary_key=True, serialize=False)),
                ('titulo', models.CharField(max_length=255)),
                ('descripcion', models.TextField()),
                ('fecha_compromiso', models.DateField()),
                ('prioridad', models.CharField(choices=[('Alta', 'Alta'), ('Media', 'Media'), ('Baja', 'Baja')], default='Media', max_length=255)),
                ('estado', models.CharField(choices=[('Pendiente', 'Pendiente'), ('En proceso', 'En proceso'), ('Cumplido', 'Cumplido'), ('Vencido', 'Vencido'), ('Cancelado', 'Cancelado')], default='Pendiente', max_length=255)),
                ('fecha_cierre', models.DateField(blank=True, null=True)),
                ('resultado_cierre', models.TextField(blank=True, null=True)),
                ('fecha_creacion', models.DateTimeField(auto_now_add=True)),
                ('fecha_actualizacion', models.DateTimeField(auto_now=True)),
                ('acta', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='compromisos', to='crm.ActaReunion')),
                ('creado_por', models.ForeignKey(db_constraint=False, on_delete=django.db.models.deletion.PROTECT, related_name='compromisos_creados', to=settings.AUTH_USER_MODEL)),
                ('responsable', models.ForeignKey(db_constraint=False, on_delete=django.db.models.deletion.PROTECT, related_name='compromisos_asignados', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Compromiso de acta',
                'verbose_name_plural': 'Compromisos de acta',
                'ordering': ['estado', 'fecha_compromiso', '-id_compromiso'],
            },
        ),
        migrations.CreateModel(
            name='SeguimientoCompromiso',
            fields=[
                ('id_seguimiento', models.AutoField(primary_key=True, serialize=False)),
                ('comentario', models.TextField()),
                ('estado_nuevo', models.CharField(blank=True, choices=[('Pendiente', 'Pendiente'), ('En proceso', 'En proceso'), ('Cumplido', 'Cumplido'), ('Vencido', 'Vencido'), ('Cancelado', 'Cancelado')], max_length=255, null=True)),
                ('fecha_proxima', models.DateField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('compromiso', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='seguimientos', to='crm.CompromisoActa')),
                ('usuario', models.ForeignKey(db_constraint=False, on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Seguimiento de compromiso',
                'verbose_name_plural': 'Seguimientos de compromisos',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='ActaParticipante',
            fields=[
                ('id_participante', models.AutoField(primary_key=True, serialize=False)),
                ('nombre_externo', models.CharField(blank=True, max_length=255, null=True)),
                ('email_externo', models.EmailField(blank=True, max_length=254, null=True)),
                ('rol', models.CharField(choices=[('Interno', 'Interno'), ('Cliente', 'Cliente'), ('Invitado', 'Invitado')], max_length=255)),
                ('acta', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='participantes', to='crm.ActaReunion')),
                ('usuario', models.ForeignKey(blank=True, null=True, db_constraint=False, on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Participante de acta',
                'verbose_name_plural': 'Participantes de acta',
            },
        ),
        migrations.AddIndex(
            model_name='compromisoacta',
            index=models.Index(fields=['responsable', 'estado', 'fecha_compromiso'], name='crm_comprom_respons_bfb79d_idx'),
        ),
        migrations.AddIndex(
            model_name='compromisoacta',
            index=models.Index(fields=['estado', 'fecha_compromiso'], name='crm_comprom_estado_13abfa_idx'),
        ),
    ]
