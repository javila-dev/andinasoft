from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    """Envío de los ajustes a Alegra como journal: fecha, resultado del envío y registro manual (empresas sin Alegra)."""

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('conciliacion_terceros', '0008_pasos_factura'),
    ]

    operations = [
        migrations.AddField(model_name='configempresa', name='numeracion_journal_id',
                            field=models.CharField(blank=True, default='', max_length=40)),
        migrations.AlterField(model_name='ajusteconciliacion', name='journal_estado',
                              field=models.CharField(choices=[('pendiente', 'Pendiente'), ('enviado', 'Enviado a Alegra'), ('manual', 'Registrado a mano')],
                                                     default='pendiente', max_length=20)),
        migrations.AddField(model_name='ajusteconciliacion', name='fecha', field=models.DateField(blank=True, null=True)),
        migrations.AddField(model_name='ajusteconciliacion', name='journal_error', field=models.TextField(blank=True, default='')),
        migrations.AddField(model_name='ajusteconciliacion', name='journal_respuesta', field=models.JSONField(blank=True, null=True)),
        migrations.AddField(model_name='ajusteconciliacion', name='enviado_en', field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name='ajusteconciliacion', name='enviado_por',
                            field=models.ForeignKey(blank=True, db_constraint=False, null=True, on_delete=django.db.models.deletion.SET_NULL,
                                                    related_name='+', to=settings.AUTH_USER_MODEL)),
        migrations.AddField(model_name='ajusteconciliacion', name='envio_en_curso_desde', field=models.DateTimeField(blank=True, null=True)),
    ]
