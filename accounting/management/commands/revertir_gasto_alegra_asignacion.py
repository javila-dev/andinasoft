"""
Revierte un radicado Alegra a pendiente de asignación (pruebas / corrección).

Uso:
  python manage.py revertir_gasto_alegra_asignacion --radicado=17402
"""
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from accounting.models import Facturas, history_facturas


class Command(BaseCommand):
    help = 'Devuelve un gasto Alegra a pendiente_asignacion para reasignar (p. ej. probar canje).'

    def add_arguments(self, parser):
        parser.add_argument('--radicado', type=int, required=True, help='PK del radicado (Facturas)')

    def handle(self, *args, **options):
        pk = options['radicado']
        try:
            fac = Facturas.objects.get(pk=pk)
        except Facturas.DoesNotExist as exc:
            raise CommandError(f'Radicado {pk} no encontrado.') from exc

        if fac.origen != 'Alegra':
            raise CommandError(f'Radicado {pk} no es origen Alegra.')

        if fac.gasto_aprobacion_estado == Facturas.GASTO_APROB_PENDIENTE_ASIGNACION:
            self.stdout.write(self.style.WARNING(f'Radicado {pk} ya está pendiente de asignación.'))
            return

        estado_antes = fac.gasto_aprobacion_estado
        fac.gasto_aprobacion_estado = Facturas.GASTO_APROB_PENDIENTE_ASIGNACION
        fac.gasto_aprobado = False
        fac.gasto_aprobador_asignado_id = None
        fac.gasto_asignado_por_id = None
        fac.gasto_asignado_en = None
        fac.gasto_aprobado_por_id = None
        fac.gasto_aprobado_en = None
        fac.oficina = None
        fac.gasto_es_canje = False
        fac.save(
            update_fields=[
                'gasto_aprobacion_estado',
                'gasto_aprobado',
                'gasto_aprobador_asignado',
                'gasto_asignado_por',
                'gasto_asignado_en',
                'gasto_aprobado_por',
                'gasto_aprobado_en',
                'oficina',
                'gasto_es_canje',
            ]
        )

        User = get_user_model()
        u = User.objects.filter(is_superuser=True).first() or User.objects.order_by('pk').first()
        if u:
            history_facturas.objects.create(
                factura=fac,
                usuario=u,
                accion=f'Revertido de {estado_antes} a pendiente asignación (management)',
                ubicacion='Contabilidad',
            )

        self.stdout.write(
            self.style.SUCCESS(
                f'Radicado #{pk} → pendiente_asignacion '
                f'(valor={fac.valor}, pago_neto={fac.pago_neto}). '
                'Aparecerá en Asignar gastos Alegra.'
            )
        )
