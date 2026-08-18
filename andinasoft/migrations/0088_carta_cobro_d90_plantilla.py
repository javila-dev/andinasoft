from django.db import migrations


D90_PLANTILLA = 'pdf/cartas_cobro/d90.html'


def forwards(apps, schema_editor):
    CarteraCheckpoint = apps.get_model('andinasoft', 'CarteraCheckpoint')
    CarteraCartaPlantilla = apps.get_model('andinasoft', 'CarteraCartaPlantilla')
    ck_ids = CarteraCheckpoint.objects.filter(codigo='d90').values_list('id', flat=True)
    CarteraCartaPlantilla.objects.filter(checkpoint_id__in=list(ck_ids), activo=True).update(
        plantilla=D90_PLANTILLA,
        motor='weasyprint',
    )


def backwards(apps, schema_editor):
    CarteraCheckpoint = apps.get_model('andinasoft', 'CarteraCheckpoint')
    CarteraCartaPlantilla = apps.get_model('andinasoft', 'CarteraCartaPlantilla')
    ck_ids = CarteraCheckpoint.objects.filter(codigo='d90').values_list('id', flat=True)
    CarteraCartaPlantilla.objects.filter(checkpoint_id__in=list(ck_ids)).update(
        plantilla='pdf/cartas_cobro/stub.html',
    )


class Migration(migrations.Migration):

    dependencies = [
        ('andinasoft', '0087_carta_checkpoints_30_45_60_90'),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
