from django.db.models import Q

from andinasoft.models import proyectos
from andinasoft.shared_models import Adjudicacion, Vista_Adjudicacion, titulares_por_adj
from client_portal.selectors.payments import get_payment_summary


def _iter_project_aliases():
    return list(
        proyectos.objects.filter(activo=True).order_by('proyecto').values_list('proyecto', flat=True)
    )


def list_business_cards(client_id):
    cards = []
    seen = set()

    for project_alias in _iter_project_aliases():
        try:
            relations = titulares_por_adj.objects.using(project_alias).filter(
                Q(IdTercero1=client_id) |
                Q(IdTercero2=client_id) |
                Q(IdTercero3=client_id) |
                Q(IdTercero4=client_id)
            )
        except Exception:
            continue

        for relation in relations:
            adj_id = (relation.adj or '').strip()
            key = (project_alias, adj_id)
            if not adj_id or key in seen:
                continue
            seen.add(key)

            try:
                summary = Vista_Adjudicacion.objects.using(project_alias).filter(IdAdjudicacion=adj_id).first()
                adj_obj = Adjudicacion.objects.using(project_alias).filter(pk=adj_id).first()
            except Exception:
                continue

            if not summary or not adj_obj:
                continue

            titulares = []
            try:
                titulares = [tit.nombrecompleto for tit in adj_obj.titulares2()]
            except Exception:
                titulares = [name for name in [relation.titular1, relation.titular2, relation.titular3, relation.titular4] if name]

            cards.append({
                'project_alias': project_alias,
                'adj_id': adj_id,
                'project_name': project_alias,
                'inmueble': summary.Inmueble,
                'estado_ui': _map_status(summary, adj_obj),
                'valor_negocio': summary.Valor,
                'saldo_total': summary.saldo,
                'titulares': titulares,
            })

    cards.sort(key=lambda item: (item['project_name'], item['adj_id']))
    return cards


def get_business_snapshot(client_id, project_alias, adj_id):
    adj_id = (adj_id or '').strip()
    try:
        relation = titulares_por_adj.objects.using(project_alias).filter(adj=adj_id).first()
        summary = Vista_Adjudicacion.objects.using(project_alias).filter(IdAdjudicacion=adj_id).first()
        adj_obj = Adjudicacion.objects.using(project_alias).filter(pk=adj_id).first()
    except Exception:
        return None

    if not relation or not summary or not adj_obj:
        return None

    client_ids = {
        relation.IdTercero1,
        relation.IdTercero2,
        relation.IdTercero3,
        relation.IdTercero4,
    }
    if str(client_id) not in {str(item).strip() for item in client_ids if item not in (None, '')}:
        return None

    recaudo = adj_obj.recaudo_detallado()
    saldos = adj_obj.saldos_por_cartera()
    payment_summary = get_payment_summary(project_alias, adj_id)

    try:
        titulares = [tit.nombrecompleto for tit in adj_obj.titulares2()]
    except Exception:
        titulares = [name for name in [relation.titular1, relation.titular2, relation.titular3, relation.titular4] if name]

    return {
        'project_alias': project_alias,
        'adj_id': adj_id,
        'project_name': project_alias,
        'estado_ui': _map_status(summary, adj_obj),
        'estado_tecnico': summary.Estado,
        'fecha_contrato': summary.FechaContrato,
        'inmueble': summary.Inmueble,
        'valor_negocio': summary.Valor,
        'capital_pagado': recaudo.get('capital', 0),
        'saldo_capital': recaudo.get('saldo_cap', 0),
        'saldo_pendiente': summary.saldo,
        'titulares': titulares,
        'payment_summary': payment_summary,
        'pago_hoy': saldos.get('pago_hoy', {}),
    }


def _map_status(summary, adj_obj):
    if not summary:
        return 'Activo'
    saldo = getattr(summary, 'saldo', None)
    if saldo == 0:
        return 'Pagado'
    if (summary.Estado or '').strip().lower() == 'aprobado':
        return 'Activo'
    return 'Activo'
