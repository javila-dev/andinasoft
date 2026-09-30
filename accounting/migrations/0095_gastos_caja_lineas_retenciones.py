from django.db import migrations, models
import django.db.models.deletion


def backfill_lineas(apps, schema_editor):
    Gastos = apps.get_model('accounting', 'gastos_caja')
    Linea = apps.get_model('accounting', 'gastos_caja_linea')
    Retencion = apps.get_model('accounting', 'gastos_caja_retencion')
    for gasto in Gastos.objects.all().iterator():
        if Linea.objects.filter(gasto_id=gasto.pk).exists():
            continue
        vr_iva = gasto.valor_iva or 0
        vr_rte = gasto.valor_rte or 0
        base = (gasto.valor or 0) - vr_iva + vr_rte
        if gasto.rte_asumida:
            base -= vr_rte
        Linea.objects.create(
            gasto_id=gasto.pk,
            orden=1,
            descripcion=(gasto.descripcion or '')[:255],
            base=base,
            impuesto_id=gasto.cuenta_iva_id if vr_iva else None,
            valor_impuesto=vr_iva or 0,
        )
        if vr_rte and gasto.cuenta_rte_id:
            Retencion.objects.create(
                gasto_id=gasto.pk,
                impuesto_id=gasto.cuenta_rte_id,
                valor=vr_rte,
                asumida=bool(gasto.rte_asumida),
            )


class Migration(migrations.Migration):

    dependencies = [
        ('accounting', '0094_gastos_caja_soporte_hash'),
    ]

    operations = [
        migrations.CreateModel(
            name='gastos_caja_linea',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('orden', models.PositiveIntegerField(default=1)),
                ('descripcion', models.CharField(blank=True, default='', max_length=255)),
                ('base', models.DecimalField(decimal_places=2, default=0, max_digits=18)),
                ('valor_impuesto', models.DecimalField(decimal_places=2, default=0, max_digits=18)),
                ('gasto', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='lineas', to='accounting.gastos_caja')),
                ('impuesto', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='lineas_gasto_caja', to='accounting.impuestos_legalizacion')),
            ],
            options={
                'verbose_name': 'Línea de gasto de caja',
                'verbose_name_plural': 'Líneas de gasto de caja',
                'ordering': ['orden', 'pk'],
            },
        ),
        migrations.CreateModel(
            name='gastos_caja_retencion',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('valor', models.DecimalField(decimal_places=2, default=0, max_digits=18)),
                ('asumida', models.BooleanField(default=False)),
                ('gasto', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='retenciones', to='accounting.gastos_caja')),
                ('impuesto', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='retenciones_gasto_caja', to='accounting.impuestos_legalizacion')),
            ],
            options={
                'verbose_name': 'Retención de gasto de caja',
                'verbose_name_plural': 'Retenciones de gasto de caja',
                'ordering': ['pk'],
            },
        ),
        migrations.RunPython(backfill_lineas, migrations.RunPython.noop),
    ]
