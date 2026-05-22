"""
Importa un radicado local desde GET /bills/{id} (bills creados en Alegra sin webhook).

Uso:
  python manage.py import_alegra_bill --empresa=901018375 --bill-id=2
  python manage.py import_alegra_bill --empresa=901018375 --bill-id=2 --no-pdf
"""
from django.core.management.base import BaseCommand, CommandError

from alegra_integration.webhook_bills import import_factura_from_alegra_bill
from andinasoft.models import empresas


class Command(BaseCommand):
    help = 'Crea o reconcilia accounting.Facturas desde GET /bills/{id} en Alegra.'

    def add_arguments(self, parser):
        parser.add_argument('--empresa', required=True, help='NIT de la empresa (empresas.pk)')
        parser.add_argument('--bill-id', required=True, help='Id numérico del bill en Alegra')
        parser.add_argument(
            '--no-pdf',
            action='store_true',
            help='No intentar descargar PDF del bill',
        )

    def handle(self, *args, **options):
        empresa_id = (options.get('empresa') or '').strip()
        bill_id = (options.get('bill_id') or '').strip()
        sync_pdf = not bool(options.get('no_pdf'))

        try:
            empresa = empresas.objects.get(pk=empresa_id)
        except empresas.DoesNotExist as exc:
            raise CommandError(f'Empresa no encontrada: {empresa_id}') from exc

        try:
            result = import_factura_from_alegra_bill(empresa, bill_id, sync_pdf=sync_pdf)
        except ValueError as exc:
            raise CommandError(str(exc)) from exc
        except Exception as exc:
            raise CommandError(str(exc)) from exc

        action = 'Creado' if result.get('created') else 'Ya existía (reconciliado)'
        self.stdout.write(
            self.style.SUCCESS(
                f'{action} radicado #{result["factura_pk"]} '
                f'← Alegra bill {result["alegra_bill_id"]}'
            )
        )
        if result.get('enriched_fields'):
            self.stdout.write('  Campos actualizados: ' + ', '.join(result['enriched_fields']))
        if result.get('pdf_saved'):
            self.stdout.write('  PDF adjunto en soporte_radicado')
