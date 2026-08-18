from django.db import migrations


LT60_PLANTILLA = 'pdf/cartas_cobro/lt60.html'


def forwards(apps, schema_editor):
    CarteraCheckpoint = apps.get_model('andinasoft', 'CarteraCheckpoint')
    CarteraCartaPlantilla = apps.get_model('andinasoft', 'CarteraCartaPlantilla')
    ck_ids = CarteraCheckpoint.objects.filter(codigo='lt60').values_list('id', flat=True)
    CarteraCartaPlantilla.objects.filter(checkpoint_id__in=list(ck_ids), activo=True).update(
        plantilla=LT60_PLANTILLA,
        motor='weasyprint',
    )


def backwards(apps, schema_editor):
    CarteraCheckpoint = apps.get_model('andinasoft', 'CarteraCheckpoint')
    CarteraCartaPlantilla = apps.get_model('andinasoft', 'CarteraCartaPlantilla')
    ck_ids = CarteraCheckpoint.objects.filter(codigo='lt60').values_list('id', flat=True)
    CarteraCartaPlantilla.objects.filter(checkpoint_id__in=list(ck_ids)).update(
        plantilla='pdf/cartas_cobro/stub.html',
    )


class Migration(migrations.Migration):

    dependencies = [
        ('andinasoft', '0084_carta_cobro_lt30_plantilla'),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
