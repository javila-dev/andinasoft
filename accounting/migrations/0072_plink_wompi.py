from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('andinasoft', '0001_initial'),
        ('accounting', '0071_parametros_valor'),
    ]

    operations = [
        migrations.CreateModel(
            name='PlinkMovement',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nit', models.CharField(max_length=30)),
                ('codigo_establecimiento', models.CharField(max_length=50)),
                ('origen_compra', models.CharField(blank=True, max_length=50, null=True)),
                ('tipo_transaccion', models.CharField(blank=True, max_length=30, null=True)),
                ('franquicia', models.CharField(blank=True, max_length=30, null=True)),
                ('identificador_red', models.CharField(blank=True, max_length=50, null=True)),
                ('fecha_transaccion', models.DateField()),
                ('fecha_canje', models.DateField(blank=True, null=True)),
                ('cuenta_consignacion', models.CharField(blank=True, max_length=50, null=True)),
                ('valor_compra', models.DecimalField(decimal_places=2, max_digits=18)),
                ('valor_propina', models.DecimalField(decimal_places=2, default=0, max_digits=18)),
                ('valor_iva', models.DecimalField(decimal_places=2, default=0, max_digits=18)),
                ('valor_impoconsumo', models.DecimalField(decimal_places=2, default=0, max_digits=18)),
                ('valor_total', models.DecimalField(decimal_places=2, max_digits=18)),
                ('valor_comision', models.DecimalField(decimal_places=2, default=0, max_digits=18)),
                ('valor_retefuente', models.DecimalField(decimal_places=2, default=0, max_digits=18)),
                ('valor_rete_iva', models.DecimalField(decimal_places=2, default=0, max_digits=18)),
                ('valor_rte_ica', models.DecimalField(decimal_places=2, default=0, max_digits=18)),
                ('valor_provision', models.DecimalField(decimal_places=2, default=0, max_digits=18)),
                ('valor_neto', models.DecimalField(decimal_places=2, max_digits=18)),
                ('codigo_autorizacion', models.CharField(blank=True, max_length=50, null=True)),
                ('tipo_tarjeta', models.CharField(blank=True, max_length=50, null=True)),
                ('numero_terminal', models.CharField(blank=True, max_length=50, null=True)),
                ('tarjeta', models.CharField(blank=True, max_length=50, null=True)),
                ('comision_porcentual', models.CharField(blank=True, max_length=20, null=True)),
                ('comision_base', models.DecimalField(decimal_places=2, default=0, max_digits=18)),
                ('fecha_compensacion', models.DateField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('empresa', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='plink_movements', to='andinasoft.empresas')),
            ],
            options={
                'verbose_name': 'Movimiento Plink',
                'verbose_name_plural': 'Movimientos Plink',
                'unique_together': {('empresa', 'codigo_autorizacion', 'fecha_transaccion')},
            },
        ),
        migrations.CreateModel(
            name='WompiMovement',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('transaction_id', models.CharField(max_length=100, unique=True)),
                ('fecha', models.DateTimeField()),
                ('referencia', models.CharField(max_length=255)),
                ('monto', models.DecimalField(decimal_places=2, max_digits=18)),
                ('iva', models.DecimalField(decimal_places=2, default=0, max_digits=18)),
                ('impuesto_consumo', models.DecimalField(decimal_places=2, default=0, max_digits=18)),
                ('moneda', models.CharField(max_length=10)),
                ('medio_pago', models.CharField(max_length=30)),
                ('email_pagador', models.EmailField(blank=True, max_length=254, null=True)),
                ('nombre_pagador', models.CharField(blank=True, max_length=255, null=True)),
                ('telefono_pagador', models.CharField(blank=True, max_length=50, null=True)),
                ('id_conciliacion', models.CharField(blank=True, max_length=100, null=True)),
                ('id_link_pago', models.CharField(blank=True, max_length=100, null=True)),
                ('documento_pagador', models.CharField(blank=True, max_length=50, null=True)),
                ('tipo_documento_pagador', models.CharField(blank=True, max_length=10, null=True)),
                ('referencia_1_nombre', models.CharField(blank=True, max_length=100, null=True)),
                ('referencia_1', models.CharField(blank=True, max_length=255, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('empresa', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='wompi_movements', to='andinasoft.empresas')),
            ],
            options={
                'verbose_name': 'Movimiento Wompi',
                'verbose_name_plural': 'Movimientos Wompi',
            },
        ),
    ]
