from django.db import migrations, models
import django.db.models.deletion


DEFAULT_CHECKPOINTS = (
    # codigo, label, dias_desde, dias_hasta, orden
    ('lt30', '0 a 30', 1, 30, 10),
    ('lt60', '30 a 60', 31, 60, 20),
    ('lt90', '60 a 90', 61, 90, 30),
    ('lt120', '90 a 120', 91, 120, 40),
    ('gt120', 'Mas de 120', 121, None, 50),
)

STUB_PLANTILLA = 'pdf/cartas_cobro/stub.html'


def seed_checkpoints(apps, schema_editor):
    Proyectos = apps.get_model('andinasoft', 'proyectos')
    CarteraCheckpoint = apps.get_model('andinasoft', 'CarteraCheckpoint')
    CarteraCartaPlantilla = apps.get_model('andinasoft', 'CarteraCartaPlantilla')
    for proyecto in Proyectos.objects.filter(activo=True).exclude(proyecto='default'):
        for codigo, label, dias_desde, dias_hasta, orden in DEFAULT_CHECKPOINTS:
            ck, _ = CarteraCheckpoint.objects.update_or_create(
                proyecto=proyecto,
                codigo=codigo,
                defaults={
                    'label': label,
                    'dias_desde': dias_desde,
                    'dias_hasta': dias_hasta,
                    'orden': orden,
                    'activo': True,
                },
            )
            if not CarteraCartaPlantilla.objects.filter(checkpoint=ck, activo=True).exists():
                CarteraCartaPlantilla.objects.create(
                    checkpoint=ck,
                    motor='weasyprint',
                    plantilla=STUB_PLANTILLA,
                    activo=True,
                )


def unseed_checkpoints(apps, schema_editor):
    CarteraCheckpoint = apps.get_model('andinasoft', 'CarteraCheckpoint')
    CarteraCheckpoint.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('andinasoft', '0077_promesacumplimiento'),
    ]

    operations = [
        migrations.CreateModel(
            name='CarteraCheckpoint',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('codigo', models.CharField(max_length=32)),
                ('label', models.CharField(max_length=64)),
                (
                    'dias_desde',
                    models.PositiveIntegerField(
                        help_text='Dias de mora a partir de los cuales el checkpoint se considera alcanzado',
                    ),
                ),
                (
                    'dias_hasta',
                    models.PositiveIntegerField(
                        blank=True,
                        help_text='Inclusive. Vacio = sin limite superior (ej. >120)',
                        null=True,
                    ),
                ),
                ('orden', models.PositiveSmallIntegerField(default=0)),
                ('activo', models.BooleanField(default=True)),
                (
                    'proyecto',
                    models.ForeignKey(
                        db_constraint=False,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='cartera_checkpoints',
                        to='andinasoft.proyectos',
                    ),
                ),
            ],
            options={
                'verbose_name': 'Checkpoint cartera',
                'verbose_name_plural': 'Checkpoints cartera',
                'ordering': ['orden', 'dias_desde'],
                'unique_together': {('proyecto', 'codigo')},
            },
        ),
        migrations.CreateModel(
            name='CarteraCartaPlantilla',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                (
                    'motor',
                    models.CharField(
                        choices=[('xhtml2pdf', 'xhtml2pdf'), ('weasyprint', 'WeasyPrint')],
                        default='weasyprint',
                        max_length=20,
                    ),
                ),
                (
                    'plantilla',
                    models.CharField(
                        default='pdf/cartas_cobro/stub.html',
                        help_text='Ruta HTML bajo templates (ej. pdf/cartas_cobro/stub.html)',
                        max_length=255,
                    ),
                ),
                ('activo', models.BooleanField(default=True)),
                (
                    'checkpoint',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='plantillas',
                        to='andinasoft.CarteraCheckpoint',
                    ),
                ),
            ],
            options={
                'verbose_name': 'Plantilla carta cobro',
                'verbose_name_plural': 'Plantillas cartas cobro',
            },
        ),
        migrations.RunPython(seed_checkpoints, unseed_checkpoints),
    ]
