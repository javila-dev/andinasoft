from django.db import migrations, models
import django.db.models.deletion


CARTA_TELEFONO = '301 8585672'
CARTA_EMAIL = 'haroldtangarife@somosandina.co'
CARTA_FIRMA_NOMBRE = {
    'Oasis': 'OASIS DEL CARIBE',
}


def seed_config(apps, schema_editor):
    Proyectos = apps.get_model('andinasoft', 'proyectos')
    Config = apps.get_model('andinasoft', 'CarteraCartaConfig')
    for proyecto in Proyectos.objects.exclude(proyecto='default'):
        Config.objects.get_or_create(
            proyecto=proyecto,
            defaults={
                'firma_nombre': CARTA_FIRMA_NOMBRE.get(proyecto.pk, ''),
                'telefono': CARTA_TELEFONO,
                'email': CARTA_EMAIL,
            },
        )


def unseed_config(apps, schema_editor):
    Config = apps.get_model('andinasoft', 'CarteraCartaConfig')
    Config.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('andinasoft', '0088_carta_cobro_d90_plantilla'),
    ]

    operations = [
        migrations.CreateModel(
            name='CarteraCartaConfig',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                (
                    'firma_nombre',
                    models.CharField(
                        blank=True,
                        default='',
                        help_text='Nombre en Atentamente y pie. Vacio = nombre del proyecto en mayusculas.',
                        max_length=120,
                    ),
                ),
                ('telefono', models.CharField(blank=True, default='', max_length=40)),
                ('email', models.CharField(blank=True, default='', max_length=120)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                (
                    'proyecto',
                    models.OneToOneField(
                        db_constraint=False,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='cartera_carta_config',
                        to='andinasoft.proyectos',
                    ),
                ),
            ],
            options={
                'verbose_name': 'Config carta cobro',
                'verbose_name_plural': 'Config cartas cobro',
            },
        ),
        migrations.RunPython(seed_config, unseed_config),
    ]
