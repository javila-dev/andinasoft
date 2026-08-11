"""
Elimina (o marca) radicados Facturas creados por webhook a partir de bills de caja.

Uso:
  python manage.py cleanup_caja_webhook_facturas --dry-run
  python manage.py cleanup_caja_webhook_facturas --empresa=901018375
  python manage.py cleanup_caja_webhook_facturas --empresa=901018375 --dry-run
"""
from django.core.management.base import BaseCommand, CommandError

from andinasoft.models import empresas
from alegra_integration.webhook_bills import (
    _handle_delete_bill,
    queryset_caja_phantom_facturas,
)


class Command(BaseCommand):
    help = (
        'Limpia radicados Alegra fantasma de bills de caja '
        '(marker [caja-gasto:N] o AlegraDocument caja_bill sent).'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--empresa',
            default='',
            help='NIT de la empresa. Vacío = todas.',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Solo lista candidatos; no elimina ni marca.',
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=0,
            help='Máximo de radicados a procesar (0 = sin límite).',
        )

    def handle(self, *args, **options):
        empresa_id = (options.get('empresa') or '').strip()
        dry_run = bool(options.get('dry_run'))
        limit = int(options.get('limit') or 0)

        if empresa_id:
            if not empresas.objects.filter(pk=empresa_id).exists():
                raise CommandError(f'Empresa no encontrada: {empresa_id}')

        qs = queryset_caja_phantom_facturas(empresa_id=empresa_id or None).order_by('pk')
        if limit > 0:
            qs = qs[:limit]

        rows = list(qs)
        self.stdout.write(f'Candidatos: {len(rows)}' + (' (dry-run)' if dry_run else ''))

        soft = 0
        hard = 0
        missing = 0
        for fac in rows:
            composite = (fac.alegra_bill_id or '').strip()
            desc = (fac.descripcion or '')[:80]
            self.stdout.write(
                f'  #{fac.pk} empresa={fac.empresa_id} bill={composite} '
                f'desc={desc!r}'
            )
            if dry_run:
                continue
            result = _handle_delete_bill(composite)
            if result.get('deleted_soft'):
                soft += 1
            elif result.get('deleted_hard'):
                hard += 1
            else:
                missing += 1
                self.stdout.write(
                    self.style.WARNING(
                        f'    omitido: {result.get("skip_reason") or result}'
                    )
                )

        if dry_run:
            self.stdout.write(self.style.SUCCESS(f'Dry-run OK: {len(rows)} candidatos'))
            return

        self.stdout.write(
            self.style.SUCCESS(
                f'Limpieza OK: soft={soft} hard={hard} omitidos={missing} total={len(rows)}'
            )
        )
