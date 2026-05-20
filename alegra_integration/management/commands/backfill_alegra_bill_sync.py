"""
Sincroniza radicados Alegra existentes con GET /bills/{id} (descripción, importes, PDF).

Uso:
  python manage.py backfill_alegra_bill_sync --empresa=901018375
  python manage.py backfill_alegra_bill_sync --empresa=901018375 --dry-run
  python manage.py backfill_alegra_bill_sync --only-placeholder-desc
  python manage.py backfill_alegra_bill_sync --only-missing-pdf
"""
import time

from django.core.management.base import BaseCommand, CommandError

from accounting.models import Facturas
from alegra_integration.bill_mapping import is_placeholder_descripcion, parse_alegra_bill_id_for_api
from alegra_integration.bill_pdf import sync_factura_from_alegra_bill
from andinasoft.models import empresas


class Command(BaseCommand):
    help = 'GET /bills/{id} para radicados Alegra ya creados (enrich + PDF).'

    def add_arguments(self, parser):
        parser.add_argument(
            '--empresa',
            default='',
            help='Filtrar por NIT (alegra_bill_id empieza por NIT:). Vacío = todas las empresas.',
        )
        parser.add_argument(
            '--only-placeholder-desc',
            action='store_true',
            help='Solo radicados con descripción a corregir (genérica o texto autorización DIAN).',
        )
        parser.add_argument(
            '--only-missing-pdf',
            action='store_true',
            help='Solo radicados sin soporte_radicado.',
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=0,
            help='Máximo de radicados a procesar (0 = sin límite).',
        )
        parser.add_argument(
            '--sleep',
            type=float,
            default=0.35,
            help='Segundos entre llamadas a Alegra (evitar ráfagas).',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Lista candidatos sin llamar a Alegra.',
        )

    def handle(self, *args, **options):
        nit_filter = (options.get('empresa') or '').strip()
        only_desc = bool(options.get('only_placeholder_desc'))
        only_pdf = bool(options.get('only_missing_pdf'))
        limit = int(options.get('limit') or 0)
        sleep_s = float(options.get('sleep') or 0)
        dry_run = bool(options.get('dry_run'))

        if nit_filter:
            try:
                empresas.objects.get(pk=nit_filter)
            except empresas.DoesNotExist:
                raise CommandError(f'Empresa no encontrada: {nit_filter}') from None

        qs = (
            Facturas.objects.filter(origen='Alegra')
            .exclude(alegra_bill_id__isnull=True)
            .exclude(alegra_bill_id='')
            .exclude(alegra_bill_id__contains=':journal:')
            .select_related('empresa')
            .order_by('pk')
        )
        if nit_filter:
            qs = qs.filter(alegra_bill_id__startswith=f'{nit_filter}:')

        candidates = []
        for fac in qs.iterator():
            emp_nit, bill_id = parse_alegra_bill_id_for_api(fac.alegra_bill_id)
            if not emp_nit or not bill_id:
                continue
            if only_desc and not is_placeholder_descripcion(fac.descripcion):
                continue
            if only_pdf and fac.soporte_radicado:
                continue
            candidates.append((fac, emp_nit, bill_id))

        if limit > 0:
            candidates = candidates[:limit]

        if not candidates:
            self.stdout.write(self.style.WARNING('Sin radicados candidatos.'))
            return

        self.stdout.write(
            f'{"[dry-run] " if dry_run else ""}{len(candidates)} radicado(s)'
            + (f' empresa {nit_filter}' if nit_filter else '')
            + '…'
        )

        ok_enrich = ok_pdf = errors = 0
        for i, (fac, emp_nit, bill_id) in enumerate(candidates, 1):
            label = f'#{fac.pk} bill={bill_id} ({fac.alegra_bill_id})'
            if dry_run:
                self.stdout.write(f'  {label}')
                continue

            empresa_obj = fac.empresa
            if str(empresa_obj.pk) != emp_nit:
                try:
                    empresa_obj = empresas.objects.get(pk=emp_nit)
                except empresas.DoesNotExist:
                    self.stdout.write(self.style.ERROR(f'  {label} → empresa {emp_nit} no existe'))
                    errors += 1
                    continue

            try:
                result = sync_factura_from_alegra_bill(empresa_obj, bill_id, fac)
            except Exception as exc:
                self.stdout.write(self.style.ERROR(f'  {label} → error: {exc}'))
                errors += 1
                continue

            enriched = result.get('enriched_fields') or []
            pdf = bool(result.get('pdf_saved'))
            if enriched:
                ok_enrich += 1
            if pdf:
                ok_pdf += 1
            parts = []
            if enriched:
                parts.append('datos: ' + ', '.join(enriched))
            if pdf:
                parts.append('PDF')
            if not parts:
                parts.append('sin cambios')
            self.stdout.write(f'  [{i}/{len(candidates)}] {label} → {"; ".join(parts)}')

            if sleep_s > 0 and i < len(candidates):
                time.sleep(sleep_s)

        if dry_run:
            self.stdout.write(self.style.SUCCESS('Fin dry-run.'))
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f'Listo: {len(candidates)} procesados, '
                    f'{ok_enrich} con datos, {ok_pdf} con PDF, {errors} errores.'
                )
            )
