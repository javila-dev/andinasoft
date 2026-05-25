# Generated manually — notificaciones tesorería gastos Alegra aprobados

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def crear_oficinas_notificacion(apps, schema_editor):
    Oficina = apps.get_model('accounting', 'GastoNotificacionOficina')
    for codigo, etiqueta in (('MONTERIA', 'MONTERIA'), ('MEDELLIN', 'MEDELLIN')):
        Oficina.objects.get_or_create(codigo=codigo, defaults={'etiqueta': etiqueta})


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('andinasoft', '0073_empresas_alegra_gasto_max_sin_aprobador'),
        ('accounting', '0088_gasto_aprobador_telefono'),
    ]

    operations = [
        migrations.CreateModel(
            name='GastoNotificacionOficina',
            fields=[
                ('codigo', models.CharField(max_length=32, primary_key=True, serialize=False)),
                ('etiqueta', models.CharField(max_length=64)),
            ],
            options={
                'verbose_name': 'Oficina notificación gasto',
                'verbose_name_plural': 'Oficinas notificación gasto',
            },
        ),
        migrations.CreateModel(
            name='GastoTesoreriaNotificacion',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('activo', models.BooleanField(default=True)),
                (
                    'user',
                    models.OneToOneField(
                        db_constraint=False,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='gasto_tesoreria_notificacion',
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                'verbose_name': 'Notificación tesorería gasto Alegra',
                'verbose_name_plural': 'Notificaciones tesorería gasto Alegra',
            },
        ),
        migrations.AddField(
            model_name='gastotesorerianotificacion',
            name='empresas',
            field=models.ManyToManyField(
                blank=True,
                db_constraint=False,
                related_name='gasto_tesoreria_notificaciones',
                to='andinasoft.empresas',
            ),
        ),
        migrations.AddField(
            model_name='gastotesorerianotificacion',
            name='oficinas',
            field=models.ManyToManyField(
                blank=True,
                related_name='tesoreria_notificaciones',
                to='accounting.GastoNotificacionOficina',
            ),
        ),
        migrations.RunPython(crear_oficinas_notificacion, migrations.RunPython.noop),
    ]
