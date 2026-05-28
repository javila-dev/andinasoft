"""
Reconsulta GET /journals/{id} y actualiza Facturas.alegra_journal_detalle (CxP + account_code).

Uso:
  python manage.py backfill_alegra_journal_detalle --dry-run
  python manage.py backfill_alegra_journal_detalle --empresa=901018375
  python manage.py backfill_alegra_journal_detalle --empresa=901018375 --only-missing
  python manage.py backfill_alegra_journal_detalle --limit=20 --sleep=0.5
"""
import json
import time

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q

from accounting.journal_cxp import (
    extraer_lineas_cxp,
    parsear_journal_para_radicado,
    persist_journal_cxp_mappings,
    serializar_detalle_journal_pago,
)
from accounting.models import Facturas
from alegra_integration.bill_mapping import ALEGRA_DOC_JOURNAL, parse_alegra_journal_id_for_api
from alegra_integration.client import AlegraMCPClient
from alegra_integration.exceptions import AlegraClientError, AlegraConfigurationError
from andinasoft.models import empresas


def _detalle_necesita_backfill(factura):
    raw = (getattr(factura, 'alegra_journal_detalle', None) or '').strip()
    if not raw:
        return True
    try:
        data = json.loads(raw)
    except (TypeError, ValueError):
        return True
    if not isinstance(data, list) or not data:
        return True
    for row in data:
        if not isinstance(row, dict):
            return True
        if not (row.get('account_code') or '').strip():
            return True
        if not (row.get('alegra_category_id') or '').strip():
            return True
    return False


class Command(BaseCommand):
    help = 'Backfill alegra_journal_detalle desde journals Alegra (CxP + account_code por tercero).'

    def add_arguments(self, parser):
        parser.add_argument(
            '--empresa',
            default='',
            help='Filtrar por NIT (alegra_bill_id empieza por NIT:). Vacío = todas.',
        )
        parser.add_argument(
            '--only-missing',
            action='store_true',
            help='Solo radicados sin detalle o sin account_code en el JSON.',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Reconsultar aunque el detalle ya tenga account_code.',
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=0,
            help='Máximo de radicados (0 = sin límite).',
        )
        parser.add_argument(
            '--sleep',
            type=float,
            default=0.4,
            help='Segundos entre llamadas GET /journals.',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Lista candidatos sin llamar a Alegra.',
        )

    def handle(self, *args, **options):
        nit_filter = (options.get('empresa') or '').strip()
        only_missing = bool(options.get('only_missing'))
        force = bool(options.get('force'))
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
            .filter(
                Q(alegra_bill_id__contains=':journal:')
                | Q(alegra_document_type=ALEGRA_DOC_JOURNAL)
            )
            .exclude(alegra_bill_id__isnull=True)
            .exclude(alegra_bill_id='')
            .select_related('empresa')
            .order_by('pk')
        )
        if nit_filter:
            qs = qs.filter(alegra_bill_id__startswith=f'{nit_filter}:')

        candidates = []
        for fac in qs.iterator():
            if only_missing and not force and not _detalle_necesita_backfill(fac):
                continue
            emp_nit, journal_id = parse_alegra_journal_id_for_api(fac.alegra_bill_id)
            if not emp_nit or not journal_id:
                continue
            candidates.append((fac, emp_nit, journal_id))

        if limit > 0:
            candidates = candidates[:limit]

        if not candidates:
            self.stdout.write(self.style.WARNING('Sin radicados journal candidatos.'))
            return

        self.stdout.write(
            f'{"[dry-run] " if dry_run else ""}{len(candidates)} radicado(s) journal'
            + (f' empresa {nit_filter}' if nit_filter else '')
            + '…'
        )

        ok = skipped = errors = 0
        for i, (fac, emp_nit, journal_id) in enumerate(candidates, 1):
            label = f'#{fac.pk} journal={journal_id} ({fac.alegra_bill_id})'
            if dry_run:
                need = _detalle_necesita_backfill(fac)
                self.stdout.write(f'  {label}' + (' [falta detalle/cxp]' if need else ''))
                continue

            empresa_obj = fac.empresa
            if str(empresa_obj.pk) != emp_nit:
                try:
                    empresa_obj = empresas.objects.get(pk=emp_nit)
                except empresas.DoesNotExist:
                    self.stdout.write(self.style.ERROR(f'  {label} → empresa {emp_nit} no existe'))
                    errors += 1
                    continue

            if not getattr(empresa_obj, 'alegra_enabled', False):
                self.stdout.write(self.style.WARNING(f'  {label} → Alegra no habilitado en {emp_nit}'))
                skipped += 1
                continue

            try:
                journal = AlegraMCPClient(empresa_obj).get_journal(journal_id)
                lineas = extraer_lineas_cxp(journal)
                if not lineas:
                    self.stdout.write(self.style.WARNING(f'  {label} → journal sin líneas CxP'))
                    skipped += 1
                    continue
                detalle = serializar_detalle_journal_pago(lineas)
                detalle = persist_journal_cxp_mappings(empresa_obj, detalle)
                radicado = parsear_journal_para_radicado(journal)
            except ValueError as exc:
                self.stdout.write(self.style.WARNING(f'  {label} → {exc}'))
                skipped += 1
                continue
            except (AlegraConfigurationError, AlegraClientError) as exc:
                self.stdout.write(self.style.ERROR(f'  {label} → Alegra: {exc}'))
                errors += 1
                continue
            except Exception as exc:
                self.stdout.write(self.style.ERROR(f'  {label} → error: {exc}'))
                errors += 1
                continue

            update_fields = ['alegra_journal_detalle']
            fac.alegra_journal_detalle = json.dumps(detalle, ensure_ascii=False)
            if (fac.alegra_document_type or '') != ALEGRA_DOC_JOURNAL:
                fac.alegra_document_type = ALEGRA_DOC_JOURNAL
                update_fields.append('alegra_document_type')

            # Alinear importe con CxP extraída si el radicado no tenía valor coherente.
            nuevo_valor = int(radicado.get('valor') or 0)
            if nuevo_valor > 0 and (fac.valor or 0) != nuevo_valor:
                fac.valor = nuevo_valor
                fac.pago_neto = nuevo_valor
                update_fields.extend(['valor', 'pago_neto'])

            fac.save(update_fields=update_fields)
            ok += 1
            codes = ', '.join(
                sorted({(r.get('account_code') or '') for r in detalle if r.get('account_code')})
            ) or '—'
            cats = ', '.join(
                sorted({str(r.get('alegra_category_id') or '') for r in detalle if r.get('alegra_category_id')})
            ) or '—'
            self.stdout.write(
                f'  [{i}/{len(candidates)}] {label} → '
                f'{len(detalle)} tercero(s), PUC [{codes}] → Alegra cat [{cats}]'
            )

            if sleep_s > 0 and i < len(candidates):
                time.sleep(sleep_s)

        if dry_run:
            self.stdout.write(self.style.SUCCESS('Fin dry-run.'))
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f'Listo: {ok} actualizados, {skipped} omitidos, {errors} errores '
                    f'(de {len(candidates)} candidatos).'
                )
            )
