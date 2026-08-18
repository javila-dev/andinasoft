from django.db import migrations


# Cartas: 30, 45, 60 y 90+ dias. Se habilitan al alcanzar el umbral.
NEW_CHECKPOINTS = (
    # old_codigo o None, new_codigo, label, dias_desde, dias_hasta, orden, plantilla
    ('lt30', 'd30', '30 dias', 30, None, 10, 'pdf/cartas_cobro/lt30.html'),
    ('lt60', 'd45', '45 dias', 45, None, 20, 'pdf/cartas_cobro/lt60.html'),
    ('lt90', 'd60', '60 dias', 60, None, 30, 'pdf/cartas_cobro/lt90.html'),
    ('lt120', 'd90', '90 dias o mas', 90, None, 40, 'pdf/cartas_cobro/stub.html'),
)
KEEP_CODIGOS = {row[1] for row in NEW_CHECKPOINTS}


def forwards(apps, schema_editor):
    Proyectos = apps.get_model('andinasoft', 'proyectos')
    CarteraCheckpoint = apps.get_model('andinasoft', 'CarteraCheckpoint')
    CarteraCartaPlantilla = apps.get_model('andinasoft', 'CarteraCartaPlantilla')

    for proyecto in Proyectos.objects.exclude(proyecto='default'):
        by_codigo = {
            ck.codigo: ck
            for ck in CarteraCheckpoint.objects.filter(proyecto=proyecto)
        }
        for old_codigo, new_codigo, label, dias_desde, dias_hasta, orden, plantilla in NEW_CHECKPOINTS:
            ck = by_codigo.get(new_codigo) or by_codigo.get(old_codigo)
            if ck is None:
                ck = CarteraCheckpoint.objects.create(
                    proyecto=proyecto,
                    codigo=new_codigo,
                    label=label,
                    dias_desde=dias_desde,
                    dias_hasta=dias_hasta,
                    orden=orden,
                    activo=True,
                )
            else:
                ck.codigo = new_codigo
                ck.label = label
                ck.dias_desde = dias_desde
                ck.dias_hasta = dias_hasta
                ck.orden = orden
                ck.activo = True
                ck.save()
            by_codigo[new_codigo] = ck
            rec = CarteraCartaPlantilla.objects.filter(checkpoint=ck, activo=True).order_by('id').first()
            if rec is None:
                CarteraCartaPlantilla.objects.create(
                    checkpoint=ck,
                    motor='weasyprint',
                    plantilla=plantilla,
                    activo=True,
                )
            else:
                rec.plantilla = plantilla
                rec.motor = 'weasyprint'
                rec.save(update_fields=['plantilla', 'motor'])

        CarteraCheckpoint.objects.filter(proyecto=proyecto).exclude(codigo__in=KEEP_CODIGOS).update(
            activo=False,
        )


def backwards(apps, schema_editor):
    Proyectos = apps.get_model('andinasoft', 'proyectos')
    CarteraCheckpoint = apps.get_model('andinasoft', 'CarteraCheckpoint')
    revert = (
        ('d30', 'lt30', '0 a 30', 1, 30, 10),
        ('d45', 'lt60', '30 a 60', 31, 60, 20),
        ('d60', 'lt90', '60 a 90', 61, 90, 30),
        ('d90', 'lt120', '90 a 120', 91, 120, 40),
    )
    for proyecto in Proyectos.objects.exclude(proyecto='default'):
        for new_codigo, old_codigo, label, dias_desde, dias_hasta, orden in revert:
            CarteraCheckpoint.objects.filter(proyecto=proyecto, codigo=new_codigo).update(
                codigo=old_codigo,
                label=label,
                dias_desde=dias_desde,
                dias_hasta=dias_hasta,
                orden=orden,
                activo=True,
            )
        CarteraCheckpoint.objects.filter(proyecto=proyecto, codigo='gt120').update(activo=True)


class Migration(migrations.Migration):

    dependencies = [
        ('andinasoft', '0086_carta_cobro_lt90_plantilla'),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
