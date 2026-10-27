"""
Creación de solicitudes de recibo de caja fuera de la pantalla «Solicitar recibo» (p. ej. desde el panel de Chatwoot).

Aplica las mismas reglas que esa pantalla: soporte en PDF obligatorio, un mismo soporte no se puede usar dos veces y
una solicitud con el mismo valor para el mismo negocio en el mismo mes exige confirmación.
"""
import datetime
import unicodedata

from django.db import transaction
from django.utils.html import strip_tags

from andinasoft.models import proyectos
from andinasoft.shared_models import Adjudicacion
from finance.models import recibos_internos


class SolicitudError(Exception):
    def __init__(self, mensaje, code='invalido'):
        super().__init__(mensaje)
        self.code = code


def _nombre_seguro(nombre):
    return ''.join(c for c in unicodedata.normalize('NFD', nombre) if unicodedata.category(c) != 'Mn').replace('ñ', 'n')


def crear_solicitud(*, proyecto, adj, fecha_pago, valor, soporte, usuario,
                    abono_capital=False, condona_mora=False, confirmar_duplicado=False):
    from finance.views import _get_file_hash, _is_pdf

    proyecto_obj = proyectos.objects.filter(pk=proyecto).first()
    if not proyecto_obj:
        raise SolicitudError('El proyecto no es válido.')
    adj = strip_tags(str(adj or '')).strip()
    if not adj or not Adjudicacion.objects.using(proyecto).filter(pk=adj).exists():
        raise SolicitudError('El negocio no existe en el proyecto.')
    try:
        fecha = datetime.date.fromisoformat(str(fecha_pago or ''))
    except ValueError:
        raise SolicitudError('Indica la fecha del pago.')
    if fecha > datetime.date.today():
        raise SolicitudError('La fecha del pago no puede ser futura.')
    try:
        valor = int(str(valor or '').replace(',', '').replace('.', '').replace('$', '').strip())
    except ValueError:
        raise SolicitudError('El valor no es válido.')
    if valor <= 0:
        raise SolicitudError('El valor debe ser mayor que cero.')
    if soporte is None:
        raise SolicitudError('Adjunta el soporte del pago en PDF.')
    if not _is_pdf(soporte):
        raise SolicitudError('El soporte debe ser un PDF.')

    soporte_hash = _get_file_hash(soporte)
    soporte.name = _nombre_seguro(soporte.name)
    with transaction.atomic():
        if recibos_internos.objects.filter(soporte_hash=soporte_hash).exists():
            raise SolicitudError('Ya existe una solicitud con este mismo soporte. Verifica antes de continuar.', 'soporte_duplicado')
        mismo_mes = recibos_internos.objects.filter(
            proyecto=proyecto_obj, cliente=adj, valor=valor, anulado=False,
            fecha_pago__year=fecha.year, fecha_pago__month=fecha.month,
        )
        if mismo_mes.exists() and not confirmar_duplicado:
            raise SolicitudError(
                f'Ya hay una solicitud de este negocio por ${valor:,.0f} en {fecha:%m/%Y}.'.replace(',', '.') +
                ' Confírmalo si no es un duplicado.', 'posible_duplicado')
        return recibos_internos.objects.create(
            proyecto=proyecto_obj, fecha_pago=fecha, valor=valor, soporte=soporte, soporte_hash=soporte_hash,
            usuario_solicita=usuario, condonacion=bool(condona_mora), abono_capital=bool(abono_capital), cliente=adj,
        )
