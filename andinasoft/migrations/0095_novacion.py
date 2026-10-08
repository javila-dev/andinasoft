import andina.storage.media_policy
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('andinasoft', '0094_promesaotrosi_novacion'),
    ]

    operations = [
        migrations.CreateModel(
            name='Novacion',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('adj_origen', models.CharField(db_index=True, max_length=12)),
                ('inmueble_origen', models.CharField(max_length=50)),
                ('titular', models.CharField(help_text='Id del titular 1 de la ADJ de origen', max_length=255)),
                ('venta_destino', models.IntegerField(help_text='Id de nuevas_ventas en el proyecto destino')),
                ('inmueble_destino', models.CharField(max_length=50)),
                ('adj_destino', models.CharField(blank=True, default='', max_length=12)),
                ('pagado_capital', models.DecimalField(decimal_places=2, default=0, max_digits=16)),
                ('pagado_interes_cte', models.DecimalField(decimal_places=2, default=0, max_digits=16)),
                ('pagado_interes_mora', models.DecimalField(decimal_places=2, default=0, max_digits=16)),
                ('capital_trasladado', models.DecimalField(decimal_places=2, default=0, max_digits=16)),
                ('interes_cte_trasladado', models.DecimalField(decimal_places=2, default=0, max_digits=16)),
                ('interes_mora_trasladado', models.DecimalField(decimal_places=2, default=0, max_digits=16)),
                ('nro_nota', models.CharField(blank=True, default='', help_text='Numero de la nota contable (se usa como recibo)', max_length=12)),
                ('fecha_nota', models.DateField(blank=True, null=True)),
                ('soporte', models.FileField(blank=True, null=True, storage=andina.storage.media_policy.PRIVATE_MEDIA_STORAGE, upload_to='novaciones/%Y/%m/')),
                ('fecha_entrega', models.DateField(blank=True, null=True)),
                ('fecha_escritura', models.DateField(blank=True, null=True)),
                ('observaciones', models.TextField(blank=True, default='')),
                ('estado', models.CharField(choices=[('Documentacion', 'En documentación'), ('Por aprobar', 'Por aprobar'), ('Aprobada', 'Aprobada'), ('Rechazada', 'Rechazada')], db_index=True, default='Documentacion', max_length=20)),
                ('fecha_solicitud', models.DateTimeField(auto_now_add=True)),
                ('fecha_envio', models.DateTimeField(blank=True, null=True)),
                ('fecha_resuelve', models.DateTimeField(blank=True, null=True)),
                ('motivo_rechazo', models.TextField(blank=True, default='')),
                ('empresa_nota', models.ForeignKey(blank=True, db_constraint=False, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='novaciones', to='andinasoft.empresas')),
                ('proyecto_destino', models.ForeignKey(db_constraint=False, on_delete=django.db.models.deletion.PROTECT, related_name='novaciones_destino', to='andinasoft.proyectos')),
                ('proyecto_origen', models.ForeignKey(db_constraint=False, on_delete=django.db.models.deletion.PROTECT, related_name='novaciones_origen', to='andinasoft.proyectos')),
                ('aprobador', models.ForeignKey(blank=True, db_constraint=False, help_text='Quien revisa y aprueba; se le avisa al enviar a aprobacion.', null=True, on_delete=django.db.models.deletion.PROTECT, related_name='novaciones_por_revisar', to=settings.AUTH_USER_MODEL)),
                ('usuario_envia', models.ForeignKey(blank=True, db_constraint=False, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='novaciones_enviadas', to=settings.AUTH_USER_MODEL)),
                ('usuario_resuelve', models.ForeignKey(blank=True, db_constraint=False, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='novaciones_resueltas', to=settings.AUTH_USER_MODEL)),
                ('usuario_solicita', models.ForeignKey(db_constraint=False, on_delete=django.db.models.deletion.PROTECT, related_name='novaciones_solicitadas', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Novacion',
                'verbose_name_plural': 'Novaciones',
                'ordering': ['-fecha_solicitud'],
                'permissions': (('aprobar_novacion', 'Puede aprobar o rechazar novaciones'),),
            },
        ),
        migrations.CreateModel(
            name='NovacionEvento',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('fecha', models.DateTimeField(auto_now_add=True)),
                ('accion', models.CharField(max_length=40)),
                ('detalle', models.TextField(blank=True, default='')),
                ('novacion', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='eventos', to='andinasoft.novacion')),
                ('usuario', models.ForeignKey(db_constraint=False, on_delete=django.db.models.deletion.PROTECT, related_name='+', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-fecha', '-id'],
            },
        ),
    ]
