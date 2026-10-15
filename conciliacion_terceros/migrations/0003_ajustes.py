import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('andinasoft', '0095_novacion'),
        ('conciliacion_terceros', '0002_proyectos_excluidos'),
    ]

    operations = [
        migrations.CreateModel(
            name='AjusteConciliacion',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('grupo', models.CharField(db_index=True, max_length=36)),
                ('tipo', models.CharField(choices=[('cuenta', 'Entre cuentas del mismo tercero'), ('tercero', 'Entre terceros')], max_length=10)),
                ('origen_identificacion', models.CharField(db_index=True, max_length=40)),
                ('origen_cuenta', models.CharField(max_length=30)),
                ('origen_cuenta_nombre', models.CharField(blank=True, default='', max_length=255)),
                ('destino_identificacion', models.CharField(db_index=True, max_length=40)),
                ('destino_cuenta', models.CharField(max_length=30)),
                ('destino_cuenta_nombre', models.CharField(blank=True, default='', max_length=255)),
                ('valor', models.DecimalField(decimal_places=2, max_digits=18)),
                ('misma_empresa', models.BooleanField(default=True)),
                ('nota', models.TextField(blank=True, default='')),
                ('anulado', models.BooleanField(default=False)),
                ('anulado_en', models.DateTimeField(blank=True, null=True)),
                ('journal_estado', models.CharField(choices=[('pendiente', 'Pendiente'), ('enviado', 'Enviado')], default='pendiente', max_length=20)),
                ('journal_ref', models.CharField(blank=True, default='', max_length=100)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('anulado_por', models.ForeignKey(blank=True, db_constraint=False, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL)),
                ('conciliacion', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='ajustes', to='conciliacion_terceros.conciliacion')),
                ('created_by', models.ForeignKey(blank=True, db_constraint=False, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL)),
                ('destino_empresa', models.ForeignKey(db_constraint=False, on_delete=django.db.models.deletion.PROTECT, related_name='+', to='andinasoft.empresas')),
                ('origen_empresa', models.ForeignKey(db_constraint=False, on_delete=django.db.models.deletion.PROTECT, related_name='+', to='andinasoft.empresas')),
            ],
            options={
                'verbose_name': 'Ajuste de conciliación',
                'verbose_name_plural': 'Ajustes de conciliación',
                'ordering': ['created_at', 'id'],
            },
        ),
    ]
