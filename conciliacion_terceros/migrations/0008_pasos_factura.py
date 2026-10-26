from django.db import migrations, models


class Migration(migrations.Migration):
    """Error por paso (factura, costo, cruce) y bloqueo del paso que se está enviando a Alegra."""

    dependencies = [
        ('conciliacion_terceros', '0007_quitar_cuenta_anticipo'),
    ]

    operations = [
        migrations.AddField(model_name='facturaconciliacion', name='error_costo', field=models.TextField(blank=True, default='')),
        migrations.AddField(model_name='facturaconciliacion', name='error_cruce', field=models.TextField(blank=True, default='')),
        migrations.AddField(model_name='facturaconciliacion', name='paso_en_curso', field=models.CharField(blank=True, default='', max_length=20)),
        migrations.AddField(model_name='facturaconciliacion', name='paso_en_curso_desde', field=models.DateTimeField(blank=True, null=True)),
    ]
