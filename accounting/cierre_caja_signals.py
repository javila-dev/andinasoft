"""Impide mover el efectivo de un día que ya tiene cierre de caja.

Se valida al guardar o borrar pagos, anticipos, otros ingresos y transferencias.
Un cambio que no toca fecha, cuenta ni valor (p. ej. adjuntar un soporte) se permite.
"""
from decimal import Decimal

from django.db.models.signals import pre_delete, pre_save

from accounting.models import Anticipos, Pagos, otros_ingresos, transferencias_companias
from accounting.saldo_caja import _fecha, validar_caja_abierta


CAMPOS_EFECTIVO = {
    Pagos: ('fecha_pago', ('cuenta_id',)),
    Anticipos: ('fecha_pago', ('cuenta_id',)),
    otros_ingresos: ('fecha_ing', ('cuenta_id',)),
    transferencias_companias: ('fecha', ('cuenta_entra_id', 'cuenta_sale_id')),
}


def _huella(fecha, cuentas, valor):
    try:
        fecha = _fecha(fecha)
    except (TypeError, ValueError):
        pass
    cuentas = tuple(int(c) if c not in (None, '') else None for c in cuentas)
    try:
        valor = Decimal(str(valor).replace(',', ''))
    except Exception:
        pass
    return fecha, cuentas, valor


def _huella_instancia(instance):
    fecha_attr, cuentas_attrs = CAMPOS_EFECTIVO[type(instance)]
    return _huella(getattr(instance, fecha_attr),
                   [getattr(instance, a) for a in cuentas_attrs],
                   instance.valor)


def validar_guardado(sender, instance, raw=False, using=None, **kwargs):
    if raw:
        return
    nueva = _huella_instancia(instance)
    if instance.pk:
        fecha_attr, cuentas_attrs = CAMPOS_EFECTIVO[sender]
        anterior = (sender.objects.using(using).filter(pk=instance.pk)
                    .values(fecha_attr, *cuentas_attrs, 'valor').first())
        if anterior is not None:
            vieja = _huella(anterior[fecha_attr], [anterior[a] for a in cuentas_attrs], anterior['valor'])
            if vieja == nueva:
                return
            validar_caja_abierta(vieja[1], vieja[0])
    validar_caja_abierta(nueva[1], nueva[0])


def validar_borrado(sender, instance, **kwargs):
    fecha, cuentas, _ = _huella_instancia(instance)
    validar_caja_abierta(cuentas, fecha)


def conectar():
    for model in CAMPOS_EFECTIVO:
        pre_save.connect(validar_guardado, sender=model, dispatch_uid=f'cierre_caja_save_{model.__name__}')
        pre_delete.connect(validar_borrado, sender=model, dispatch_uid=f'cierre_caja_delete_{model.__name__}')
