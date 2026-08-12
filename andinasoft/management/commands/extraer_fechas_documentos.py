from django.core.management.base import BaseCommand, CommandError

from andinasoft.documento_fechas_service import (
    DOCS_DESDE_DEFAULT,
    analyze_adj,
    export_excel,
    list_adj_candidates,
)


class Command(BaseCommand):
    help = (
        'Extrae fechas de contrato/escritura/entrega desde PDFs de venta '
        '(Promesa -> Otrosi/Otros) y las persiste.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--proyecto', required=True, help='Nombre exacto del proyecto')
        parser.add_argument('--inmueble-contains', default='', help='Filtro inmueble contiene (ej: C1)')
        parser.add_argument('--adj', default='', help='Un ADJ concreto')
        parser.add_argument('--adj-query', default='', help='Filtro parcial de ADJ')
        parser.add_argument('--titular', default='', help='Filtro titular')
        parser.add_argument('--estado', default='', help='Estado extraccion (ok, pendiente, ...)')
        parser.add_argument('--solo-pendientes', action='store_true')
        parser.add_argument('--docs-desde', default=DOCS_DESDE_DEFAULT.isoformat())
        parser.add_argument('--force', action='store_true', help='Reprocesar aunque estado=ok')
        parser.add_argument('--resync-promesas', action='store_true')
        parser.add_argument('--overwrite', action='store_true', help='Sobrescribir fechas DB en sync')
        parser.add_argument('--dry-run', action='store_true')
        parser.add_argument('--limit', type=int, default=0)
        parser.add_argument('--export-excel', action='store_true')

    def handle(self, *args, **options):
        from datetime import date

        proyecto = options['proyecto']
        try:
            docs_desde = date.fromisoformat(options['docs_desde'][:10])
        except ValueError as exc:
            raise CommandError(f'docs-desde invalido: {exc}') from exc

        adj_ids = [options['adj']] if options['adj'] else None
        rows = list_adj_candidates(
            proyecto,
            inmueble_contains=options['inmueble_contains'],
            adj_query=options['adj_query'],
            titular_query=options['titular'],
            estado_extraccion=options['estado'],
            solo_pendientes=options['solo_pendientes'],
            adj_ids=adj_ids,
        )
        if options['limit'] and options['limit'] > 0:
            rows = rows[: options['limit']]

        self.stdout.write(f'Proyecto={proyecto} candidatos={len(rows)} docs_desde={docs_desde}')
        ok = err = skip = 0
        for row in rows:
            adj = row['adj']
            result = analyze_adj(
                proyecto,
                adj,
                docs_desde=docs_desde,
                force=options['force'],
                resync_promesas=options['resync_promesas'],
                overwrite_promesas=options['overwrite'],
                dry_run=options['dry_run'],
            )
            if result.get('skipped'):
                skip += 1
                tag = 'SKIP'
            elif result.get('estado') == 'ok':
                ok += 1
                tag = 'OK'
            else:
                err += 1
                tag = (result.get('estado') or 'ERR').upper()
            self.stdout.write(
                f'  [{tag}] {adj} contrato={result.get("fecha_contrato")} '
                f'entrega={result.get("fecha_entrega")} escritura={result.get("fecha_escritura")} '
                f'doc={result.get("documento_usado") or "-"} '
                f'{result.get("error_msg") or ""}'
            )

        self.stdout.write(self.style.SUCCESS(f'Terminado ok={ok} err={err} skip={skip}'))

        if options['export_excel']:
            # Refrescar filas para Excel
            rows_out = list_adj_candidates(
                proyecto,
                inmueble_contains=options['inmueble_contains'],
                adj_query=options['adj_query'],
                titular_query=options['titular'],
                estado_extraccion=options['estado'],
                solo_pendientes=False,
                adj_ids=adj_ids,
            )
            if options['limit'] and options['limit'] > 0:
                rows_out = rows_out[: options['limit']]
            ruta = export_excel(proyecto, rows_out)
            self.stdout.write(self.style.SUCCESS(f'Excel: {ruta}'))
