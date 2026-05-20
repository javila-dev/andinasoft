"""
Rellena empresa_nit y estado de procesamiento en AlegraWebhookInboundLog.

Uso:
  python manage.py backfill_webhook_inbound --empresa=901018375
  python manage.py backfill_webhook_inbound --empresa=901018375 --include-unassigned
  python manage.py backfill_webhook_inbound --empresa=901018375 --reprocess
  python manage.py backfill_webhook_inbound --empresa=901018375 --dry-run
"""
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from alegra_integration.models import AlegraWebhookInboundLog
from alegra_integration.webhook_bills import process_inbound_post
from alegra_integration.webhook_inbound_status import (
    infer_inbound_process_result,
    log_matches_empresa_backfill,
    update_inbound_log_from_process_result,
)
from andinasoft.models import empresas


class Command(BaseCommand):
    help = 'Backfill empresa_nit y estado Radicado en logs de webhooks entrantes Alegra.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--empresa',
            required=True,
            help='NIT de la empresa (segmento del path /webhooks/bills/<NIT>/).',
        )
        parser.add_argument(
            '--include-unassigned',
            action='store_true',
            help='Incluir logs sin empresa_nit guardado si el bill no pertenece a otra empresa.',
        )
        parser.add_argument(
            '--reprocess',
            action='store_true',
            help='Volver a ejecutar process_inbound_post (puede crear/actualizar radicados).',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Solo mostrar qué se actualizaría, sin escribir en BD.',
        )

    def handle(self, *args, **options):
        nit = (options.get('empresa') or '').strip()
        if not nit:
            raise CommandError('--empresa es requerido.')

        try:
            empresas.objects.get(pk=nit)
        except empresas.DoesNotExist:
            raise CommandError(f'Empresa no encontrada: {nit}') from None

        include_unassigned = bool(options.get('include_unassigned'))
        reprocess = bool(options.get('reprocess'))
        dry_run = bool(options.get('dry_run'))

        candidates = []
        for log in AlegraWebhookInboundLog.objects.filter(http_method='POST').order_by('pk'):
            if log_matches_empresa_backfill(log, nit, include_unassigned=include_unassigned):
                candidates.append(log)

        if not candidates:
            self.stdout.write(self.style.WARNING(f'Sin logs POST para NIT {nit}.'))
            return

        self.stdout.write(
            f'{"[dry-run] " if dry_run else ""}Procesando {len(candidates)} log(s) para empresa {nit}…'
        )

        updated = 0
        for log in candidates:
            payload = log.payload if isinstance(log.payload, dict) else {}
            if reprocess:
                result = process_inbound_post(nit, payload)
            else:
                result = infer_inbound_process_result(nit, payload)

            label = self._result_label(result)
            self.stdout.write(f'  log #{log.pk} → {label}')

            if dry_run:
                continue

            with transaction.atomic():
                update_inbound_log_from_process_result(log, nit, result)
            updated += 1

        if dry_run:
            self.stdout.write(self.style.SUCCESS(f'Fin dry-run: {len(candidates)} candidato(s).'))
        else:
            self.stdout.write(self.style.SUCCESS(f'Actualizados {updated} log(s).'))

    def _result_label(self, result):
        if result.get('processing_error'):
            return f'error: {result["processing_error"]}'
        if result.get('skip_reason'):
            return f'skip: {result["skip_reason"]}'
        if result.get('created'):
            return f'creado factura_pk={result.get("factura_pk")}'
        if result.get('idempotent'):
            return f'idempotente factura_pk={result.get("factura_pk")}'
        if result.get('updated'):
            return f'actualizado factura_pk={result.get("factura_pk")}'
        if result.get('deleted_soft') or result.get('deleted_hard'):
            return f'eliminado factura_pk={result.get("factura_pk")}'
        return 'sin cambio'
