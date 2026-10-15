from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('conciliacion_terceros', '0005_facturacion'),
    ]

    operations = [
        migrations.AddField(model_name='configfacturacion', name='costo_m2', field=models.DecimalField(decimal_places=2, default=0, max_digits=18)),
        migrations.AddField(model_name='configfacturacion', name='cuenta_costo_id', field=models.CharField(blank=True, default='', max_length=40)),
        migrations.AddField(model_name='configfacturacion', name='cuenta_costo_codigo', field=models.CharField(blank=True, default='', max_length=30)),
        migrations.AddField(model_name='configfacturacion', name='cuenta_costo_nombre', field=models.CharField(blank=True, default='', max_length=255)),
        migrations.AddField(model_name='configfacturacion', name='cuenta_inventario_id', field=models.CharField(blank=True, default='', max_length=40)),
        migrations.AddField(model_name='configfacturacion', name='cuenta_inventario_codigo', field=models.CharField(blank=True, default='', max_length=30)),
        migrations.AddField(model_name='configfacturacion', name='cuenta_inventario_nombre', field=models.CharField(blank=True, default='', max_length=255)),
        migrations.AddField(model_name='facturaconciliacion', name='costo', field=models.DecimalField(decimal_places=2, default=0, max_digits=18)),
        migrations.AddField(model_name='facturaconciliacion', name='costo_estado', field=models.CharField(choices=[('no_aplica', 'Ya cruzado en contabilidad'), ('pendiente', 'Pendiente'), ('registrado', 'Journal registrado')], default='no_aplica', max_length=20)),
        migrations.AddField(model_name='facturaconciliacion', name='alegra_costo_journal_id', field=models.CharField(blank=True, default='', max_length=40)),
    ]
