"""Resolución de cuentas PUC de conceptos de legalización / caja por empresa."""

CAJA_FORMA_PAGO_TO_PUC = {
    'Promotora Sandville': 'cuenta_andina',
    'Status Comercializadora': 'cuenta_status',
    'Quadrata Constructores': 'cuenta_quadrata',
}

CAJA_EXPENSE_LOCAL_CODE = 'caja_expense'


def caja_puc_attr_for_forma_pago(empresa_name):
    key = (empresa_name or '').strip().lower()
    if not key:
        return 'cuenta_andina'
    for label, attr in CAJA_FORMA_PAGO_TO_PUC.items():
        ll = label.lower()
        if ll in key or key in ll:
            return attr
    return 'cuenta_andina'


def caja_puc_attr_for_empresa(empresa):
    from andinasoft.models import cuentas_pagos

    sample = (
        cuentas_pagos.objects.filter(nit_empresa_id=empresa.pk, es_caja=True, activo=True)
        .exclude(empresa__isnull=True)
        .exclude(empresa='')
        .values_list('empresa', flat=True)
        .first()
    )
    if sample:
        return caja_puc_attr_for_forma_pago(sample)
    return caja_puc_attr_for_forma_pago(getattr(empresa, 'nombre', '') or '')


def caja_puc_code(concepto, puc_attr):
    return (getattr(concepto, puc_attr, None) or '').strip()


def caja_puc_field_label(puc_attr):
    labels = {
        'cuenta_andina': 'Andina / Sandville',
        'cuenta_status': 'Status Comercializadora',
        'cuenta_quadrata': 'Quadrata Constructores',
    }
    return labels.get(puc_attr, puc_attr)
