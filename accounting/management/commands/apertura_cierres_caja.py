"""
Crea el cierre de apertura de las cajas de la planilla diaria a partir del
último arqueo registrado en el esquema anterior (saldos_cuentas_tesoreria).

Solo actúa sobre cuentas de efectivo sin cierres. Omite las cuentas cuyo último
arqueo es más viejo que --max-dias: su saldo ya no sirve como punto de partida y
deben abrirse con un conteo nuevo desde la planilla.

Uso:
  python manage.py apertura_cierres_caja            # muestra lo que haría
  python manage.py apertura_cierres_caja --aplicar
"""
import datetime
import json

from django.core.management.base import BaseCommand

from accounting.models import CierreCaja, saldos_cuentas_tesoreria
from accounting.saldo_caja import es_caja_planilla, movimientos_caja, neto
from andinasoft.models import cuentas_pagos


class Command(BaseCommand):
    help = 'Toma el último arqueo de cada caja de efectivo como cierre de apertura.'

    def add_arguments(self, parser):
        parser.add_argument('--aplicar', action='store_true', help='Crea los cierres (sin esto solo los muestra).')
        parser.add_argument('--max-dias', type=int, default=180,
                            help='Antigüedad máxima del último arqueo para usarlo como apertura.')

    def handle(self, *args, **options):
        limite = datetime.date.today() - datetime.timedelta(days=options['max_dias'])
        for cuenta in cuentas_pagos.objects.filter(activo=True).order_by('pk'):
            if not es_caja_planilla(cuenta):
                continue
            nombre = f'{cuenta.pk} {cuenta.cuentabanco} ({cuenta.nit_empresa_id})'
            if CierreCaja.objects.filter(cuenta=cuenta).exists():
                self.stdout.write(f'{nombre}: ya tiene cierres, se omite.')
                continue
            arqueo = saldos_cuentas_tesoreria.objects.filter(cuenta=cuenta).order_by('-fecha').first()
            if arqueo is None:
                self.stdout.write(self.style.WARNING(f'{nombre}: sin arqueos anteriores; abrir desde la planilla.'))
                continue
            if arqueo.fecha < limite:
                self.stdout.write(self.style.WARNING(
                    f'{nombre}: último arqueo del {arqueo.fecha:%d/%m/%Y}, demasiado viejo; abrir desde la planilla.'))
                continue

            movs = movimientos_caja(cuenta.pk, arqueo.fecha, arqueo.fecha)
            saldo_fisico = round(arqueo.saldo_inicial, 2)
            self.stdout.write(
                f'{nombre}: apertura el {arqueo.fecha:%d/%m/%Y} con ${saldo_fisico:,.0f} '
                f'(arqueo de {arqueo.usuario.username}).')
            if not options['aplicar']:
                continue
            try:
                forma = json.dumps(json.loads(arqueo.forma or '{}'))
            except ValueError:
                forma = '{}'
            CierreCaja.objects.create(
                cuenta=cuenta,
                fecha=arqueo.fecha,
                es_apertura=True,
                saldo_inicial=saldo_fisico - float(neto(movs)),
                movimientos={k: float(v) for k, v in movs.items()},
                saldo_teorico=saldo_fisico,
                saldo_fisico=saldo_fisico,
                forma=forma,
                diferencia=0,
                motivo_diferencia='Apertura tomada del último arqueo del esquema anterior.',
                usuario=arqueo.usuario,
            )
        if not options['aplicar']:
            self.stdout.write(self.style.NOTICE('Nada se guardó. Usa --aplicar para crear los cierres.'))
