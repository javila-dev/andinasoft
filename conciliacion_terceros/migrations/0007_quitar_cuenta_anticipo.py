from django.db import migrations


class Migration(migrations.Migration):
    """La cuenta de anticipos del cruce es la de cada tercero (se elige al facturar), no una de la configuración."""

    dependencies = [
        ('conciliacion_terceros', '0006_costo'),
    ]

    operations = [
        migrations.RemoveField(model_name='configfacturacion', name='cuenta_anticipo_id'),
        migrations.RemoveField(model_name='configfacturacion', name='cuenta_anticipo_codigo'),
        migrations.RemoveField(model_name='configfacturacion', name='cuenta_anticipo_nombre'),
    ]
