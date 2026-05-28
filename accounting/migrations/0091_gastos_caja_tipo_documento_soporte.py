from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounting', '0090_facturas_gasto_es_canje'),
    ]

    operations = [
        migrations.AddField(
            model_name='gastos_caja',
            name='tipo_documento_soporte',
            field=models.CharField(
                blank=True,
                choices=[
                    ('', 'Sin definir'),
                    ('fe', 'Factura electronica'),
                    ('cuenta_cobro', 'Cuenta de cobro'),
                ],
                default='',
                help_text='Tipo de soporte para envio a Alegra (factura electronica o cuenta de cobro).',
                max_length=20,
            ),
        ),
    ]
