from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('andinasoft', '0091_escritura_carga_paralelo'),
    ]

    operations = [
        migrations.AddField(
            model_name='promesacumplimiento',
            name='fecha_factura_notaria',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='promesacumplimiento',
            name='documento_factura_notaria',
            field=models.CharField(blank=True, default='', max_length=500),
        ),
        migrations.AlterField(
            model_name='promesacumplimiento',
            name='paso_escritura_actual',
            field=models.CharField(
                choices=[
                    ('pendiente', 'Pendiente'),
                    ('firma_cliente', 'Firma cliente'),
                    ('factura_notaria', 'Factura notaria'),
                    ('firma_empresa', 'Firma empresa'),
                    ('carga_escritura', 'Carga escritura'),
                    ('registro', 'Registro'),
                    ('facturado', 'Facturado'),
                ],
                db_index=True,
                default='pendiente',
                max_length=32,
            ),
        ),
        migrations.AlterField(
            model_name='promesahito',
            name='paso',
            field=models.CharField(
                choices=[
                    ('pendiente', 'Pendiente'),
                    ('firma_cliente', 'Firma cliente'),
                    ('factura_notaria', 'Factura notaria'),
                    ('firma_empresa', 'Firma empresa'),
                    ('carga_escritura', 'Carga escritura'),
                    ('registro', 'Registro'),
                    ('facturado', 'Facturado'),
                ],
                max_length=32,
            ),
        ),
    ]
