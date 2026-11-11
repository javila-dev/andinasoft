from django.db import migrations, models


class Migration(migrations.Migration):
    """Intereses del negocio ya facturados antes de la conciliación: se descuentan de lo que espera Andinasoft."""

    dependencies = [
        ('conciliacion_terceros', '0009_ajustes_journal'),
    ]

    operations = [
        migrations.AddField(model_name='facturaconciliacion', name='intereses_previos',
                            field=models.DecimalField(decimal_places=2, default=0, max_digits=18)),
    ]
