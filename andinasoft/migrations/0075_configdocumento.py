from django.db import migrations, models
import django.db.models.deletion


SEED = (
    ('Sandville Beach', 'venta', 'reportlab', 'ExportPromesaSandvilleBeach', False),
    ('Sandville Beach', 'modulo', 'reportlab', 'ExportPromesaSandvilleBeach', False),
    ('Perla del Mar', 'venta', 'xhtml2pdf', 'pdf/Perla del Mar/contrato.html', False),
    ('Perla del Mar', 'modulo', 'xhtml2pdf', 'pdf/Perla del Mar/contrato.html', False),
    ('Tesoro Escondido', 'venta', 'reportlab', 'ExportPromesaBugambilias', False),
    ('Tesoro Escondido', 'modulo', 'reportlab', 'ExportPromesaBugambilias', False),
    ('Vegas de Venecia', 'venta', 'reportlab', 'ExportCBFVegasVenecia', False),
    ('Vegas de Venecia', 'modulo', 'reportlab', 'ExportCBFVegasVenecia', False),
    ('Carmelo Reservado', 'venta', 'xhtml2pdf', 'pdf/Carmelo Reservado/contrato.html', False),
    ('Casas de Verano', 'venta', 'xhtml2pdf', 'pdf/Casas de Verano/contrato.html', False),
    ('Oasis', 'venta', 'weasyprint', 'pdf/Oasis/contrato.html', False),
    ('Oasis', 'modulo', 'weasyprint', 'pdf/Oasis/contrato.html', False),
    ('Sotavento', 'modulo', 'xhtml2pdf', 'pdf/Sotavento/contrato.html', False),
)


def seed_config_documento(apps, schema_editor):
    ConfigDocumento = apps.get_model('andinasoft', 'ConfigDocumento')
    Proyectos = apps.get_model('andinasoft', 'proyectos')
    for proyecto_id, origen, motor, plantilla, forma_pago_manual in SEED:
        proyecto, _ = Proyectos.objects.get_or_create(
            proyecto=proyecto_id,
            defaults={'activo': True},
        )
        ConfigDocumento.objects.update_or_create(
            proyecto=proyecto,
            origen=origen,
            defaults={
                'motor': motor,
                'plantilla': plantilla,
                'forma_pago_manual': forma_pago_manual,
            },
        )


def unseed_config_documento(apps, schema_editor):
    ConfigDocumento = apps.get_model('andinasoft', 'ConfigDocumento')
    ConfigDocumento.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('andinasoft', '0074_asesores_empresa_contable'),
    ]

    operations = [
        migrations.CreateModel(
            name='ConfigDocumento',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('origen', models.CharField(choices=[('venta', 'Venta'), ('modulo', 'Modulo promesas')], max_length=20)),
                ('motor', models.CharField(choices=[('reportlab', 'ReportLab'), ('xhtml2pdf', 'xhtml2pdf'), ('weasyprint', 'WeasyPrint')], max_length=20)),
                ('plantilla', models.CharField(help_text='Ruta HTML (pdf/.../contrato.html) o nombre de exportador ReportLab', max_length=255)),
                ('forma_pago_manual', models.BooleanField(default=False, help_text='Si esta activo, quien imprime debe digitar forma CI y forma saldo')),
                ('proyecto', models.ForeignKey(db_constraint=False, on_delete=django.db.models.deletion.CASCADE, related_name='config_documentos', to='andinasoft.proyectos')),
            ],
            options={
                'verbose_name': 'Configuracion documento',
                'verbose_name_plural': 'Configuraciones documento',
                'unique_together': {('proyecto', 'origen')},
            },
        ),
        migrations.RunPython(seed_config_documento, unseed_config_documento),
    ]
