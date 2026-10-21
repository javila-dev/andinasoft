from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('andinasoft', '0095_novacion'),
        ('accounting', '0096_impuesto_consumo_porcentaje'),
    ]

    operations = [
        migrations.CreateModel(
            name='CierreCaja',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('fecha', models.DateField()),
                ('es_apertura', models.BooleanField(default=False)),
                ('saldo_inicial', models.DecimalField(decimal_places=2, max_digits=15)),
                ('movimientos', models.JSONField(default=dict)),
                ('saldo_teorico', models.DecimalField(decimal_places=2, max_digits=15)),
                ('saldo_fisico', models.DecimalField(decimal_places=2, max_digits=15)),
                ('forma', models.TextField(blank=True, default='{}')),
                ('diferencia', models.DecimalField(decimal_places=2, max_digits=15)),
                ('motivo_diferencia', models.TextField(blank=True, default='')),
                ('estado_ajuste', models.CharField(choices=[('Sin diferencia', 'Sin diferencia'), ('Pendiente', 'Pendiente'), ('Aprobado', 'Aprobado')], default='Sin diferencia', max_length=20)),
                ('ajuste_revisado_en', models.DateTimeField(blank=True, null=True)),
                ('fecha_registro', models.DateTimeField(auto_now_add=True)),
                ('ajuste_revisado_por', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, db_constraint=False, related_name='ajustes_caja_revisados', to=settings.AUTH_USER_MODEL)),
                ('cuenta', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, db_constraint=False, related_name='cierres_caja', to='andinasoft.cuentas_pagos')),
                ('usuario', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, db_constraint=False, related_name='cierres_caja', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Cierre de caja',
                'verbose_name_plural': 'Cierres de caja',
                'permissions': [('aprobar_ajuste_cierrecaja', 'Puede aprobar ajustes de arqueo y reabrir cierres de caja')],
                'unique_together': {('cuenta', 'fecha')},
            },
        ),
    ]
