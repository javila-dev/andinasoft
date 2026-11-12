from django.db import migrations, models


class Migration(migrations.Migration):
    """Cuadra con justificación: diferencia aceptada por un valor exacto y con explicación."""

    dependencies = [
        ('conciliacion_terceros', '0012_ajuste_tipo_cruce'),
    ]

    operations = [
        migrations.AddField(
            model_name='conciliacionlinea',
            name='justificado_valor',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=18, null=True),
        ),
        migrations.AlterField(
            model_name='conciliacionlinea',
            name='estado',
            field=models.CharField(choices=[('cuadrado', 'Cuadra'), ('justificado', 'Cuadra con justificación'),
                                            ('diferencia', 'Con diferencia'), ('solo_contable', 'Solo en contabilidad'),
                                            ('solo_andina', 'Solo en Andinasoft')], db_index=True, max_length=20),
        ),
        migrations.AlterField(
            model_name='conciliacionlinea',
            name='revision',
            field=models.CharField(choices=[('pendiente', 'Pendiente'), ('ok', 'Revisado, sin acción'),
                                            ('ajuste', 'Requiere ajuste contable'), ('corregir_andina', 'Corregir en Andinasoft'),
                                            ('justificado', 'Cuadra con justificación')],
                                   db_index=True, default='pendiente', max_length=20),
        ),
    ]
