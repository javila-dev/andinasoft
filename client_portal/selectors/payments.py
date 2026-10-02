from datetime import date

from andinasoft.shared_models import PlanPagos


def get_payment_plan(project_alias, adj_id, limit=None):
    installments = []
    queryset = PlanPagos.objects.using(project_alias).filter(adj=adj_id).order_by('fecha', 'nrocta', 'idcta')

    for installment in queryset:
        pending = installment.pendiente()
        mora = installment.mora()
        status = _status_for_installment(installment, pending_total=pending.get('total', 0))
        item = {
            'idcta': installment.idcta,
            'nrocta': installment.nrocta,
            'tipocta': installment.tipocta,
            'fecha': installment.fecha,
            'capital': installment.capital or 0,
            'interes_corriente': installment.intcte or 0,
            'cuota': installment.cuota or 0,
            'capital_pendiente': pending.get('capital', 0) or 0,
            'interes_pendiente': pending.get('interes', 0) or 0,
            'mora_estimada': mora.get('valor', 0) or 0,
            'dias_mora': mora.get('dias_totales', 0) or 0,
            'saldo_total': (pending.get('total', 0) or 0) + (mora.get('valor', 0) or 0),
            'estado_ui': status,
        }
        installments.append(item)

    if limit is not None:
        return installments[:limit]
    return installments


def get_payment_summary(project_alias, adj_id):
    installments = get_payment_plan(project_alias, adj_id)
    summary = {
        'total_installments': len(installments),
        'paid_count': 0,
        'overdue_count': 0,
        'upcoming_count': 0,
        'pending_count': 0,
        'capital_pending': 0,
        'interest_pending': 0,
        'mora_estimada': 0,
        'total_pending': 0,
        'next_installments': [],
        'overdue_installments': [],
    }

    today = date.today()
    for item in installments:
        status = item['estado_ui']
        if status == 'pagada':
            summary['paid_count'] += 1
        elif status == 'vencida':
            summary['overdue_count'] += 1
            summary['overdue_installments'].append(item)
        elif status == 'proxima':
            summary['upcoming_count'] += 1
        else:
            summary['pending_count'] += 1

        summary['capital_pending'] += item['capital_pendiente']
        summary['interest_pending'] += item['interes_pendiente']
        summary['mora_estimada'] += item['mora_estimada']
        summary['total_pending'] += item['saldo_total']

    overdue = summary['overdue_installments']
    summary['max_dias_mora'] = max((i['dias_mora'] for i in overdue), default=0)
    summary['valor_en_mora'] = sum(i['saldo_total'] for i in overdue)

    # Meses crédito: rango entre la primera y última fecha de cuotas
    fechas = [i['fecha'] for i in installments if i['fecha']]
    if len(fechas) >= 2:
        delta = max(fechas) - min(fechas)
        summary['meses_credito'] = round(delta.days / 30.4)
    else:
        summary['meses_credito'] = 0

    # Total pago hoy: vencidas (capital + interés + mora) + capital de cuotas futuras pendientes
    capital_futuro = sum(
        i['capital_pendiente'] for i in installments
        if i['estado_ui'] not in ('pagada', 'vencida')
    )
    summary['total_pago_hoy'] = summary['valor_en_mora'] + capital_futuro

    future_or_today = [item for item in installments if item['fecha'] and item['fecha'] >= today and item['estado_ui'] != 'pagada']
    summary['next_installments'] = future_or_today[:3]
    summary['overdue_installments'] = overdue[:3]
    return summary


def _status_for_installment(installment, pending_total):
    if pending_total <= 0:
        return 'pagada'
    if installment.is_expired():
        return 'vencida'
    if installment.is_prx_to_expire():
        return 'proxima'
    return 'pendiente'
