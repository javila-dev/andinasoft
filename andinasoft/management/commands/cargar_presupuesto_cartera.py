from types import SimpleNamespace

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from andinasoft.presupuesto_cartera_service import (
    ensure_presupuestos,
    periodo_actual,
    proyectos_accesibles,
)

# Usuario que queda registrado en presupuesto_cartera.Usuario y que "ve" todos
# los proyectos activos (mismo filtro que usa la UI para un superusuario).
SISTEMA = SimpleNamespace(is_superuser=True, username='schedule')


class Command(BaseCommand):
    help = (
        'Carga el presupuesto de cartera del periodo (por defecto el mes actual) en todos '
        'los proyectos activos. Idempotente: los proyectos que ya tienen el periodo se saltan, '
        'así que se puede programar varios días seguidos como reintento.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--periodo', help='YYYYMM. Por defecto el mes actual.')
        parser.add_argument(
            '--proyecto', action='append', dest='proyectos',
            help='Limitar a un proyecto (se puede repetir).',
        )

    def handle(self, *args, **options):
        periodo = options['periodo'] or periodo_actual(timezone.localdate())
        if len(periodo) != 6 or not periodo.isdigit() or not 1 <= int(periodo[-2:]) <= 12:
            raise CommandError(f'Periodo inválido: {periodo!r} (formato YYYYMM).')

        proyectos = proyectos_accesibles(SISTEMA)
        if options['proyectos']:
            desconocidos = set(options['proyectos']) - set(proyectos)
            if desconocidos:
                raise CommandError(f'Proyectos no activos o sin BD: {", ".join(sorted(desconocidos))}')
            proyectos = [p for p in proyectos if p in options['proyectos']]

        fallidos = []
        for proyecto, res in ensure_presupuestos(proyectos, periodo, SISTEMA):
            if not res['ok']:
                fallidos.append(proyecto)
                self.stderr.write(self.style.ERROR(f'{proyecto}: error — {res["error"]}'))
            elif res['skipped']:
                self.stdout.write(f'{proyecto}: ya existía {periodo}, sin cambios')
            else:
                self.stdout.write(self.style.SUCCESS(f'{proyecto}: {res["count"]} cuotas cargadas'))

        if fallidos:
            # Código de salida != 0 para que el schedule quede marcado como fallido.
            raise CommandError(f'cargar_presupuesto_cartera {periodo}: falló en {", ".join(fallidos)}')
        self.stdout.write(self.style.SUCCESS(f'cargar_presupuesto_cartera {periodo}: ok ({len(proyectos)} proyectos)'))
