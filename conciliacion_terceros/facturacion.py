"""
Facturas de los titulares desde la conciliación.

- Informativa: la factura ya se emitió (en Alegra, SIIGO o donde sea). Se registra número, fecha y valor; el
  negocio deja de sumar en Andinasoft por ese valor y, si el cruce aún no está en el archivo contable, se resta
  de la cuenta de anticipos.
- Alegra: se crea la factura por API (borrador o emitida según la configuración del proyecto) y, cuando está
  emitida, se cruza el anticipo con un journal: débito a la cuenta de anticipos y crédito a la cuenta por cobrar
  asociado a la factura. POST /invoices y /journals no se reintentan solos (podrían duplicar).

Se factura a cada titular en partes iguales.
"""
import datetime
import logging
import re
import uuid
from collections import Counter
from contextlib import contextmanager
from decimal import ROUND_DOWN, Decimal

from django.core.cache import cache
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from andinasoft.models import empresas
from conciliacion_terceros.models import Conciliacion, ConfigFacturacion, FacturaConciliacion

logger = logging.getLogger(__name__)
CENT = Decimal('0.01')


class FacturacionError(Exception):
    pass


class RequiereConfirmacion(FacturacionError):
    """El negocio ya tiene facturas para esos titulares: se registra otra solo si el usuario lo confirma."""


def partes_iguales(total, n):
    """Mismo reparto que los recibos: partes iguales, residuo al primero."""
    total = Decimal(total).quantize(CENT)
    n = max(1, n)
    base = (total / n).quantize(CENT, rounding=ROUND_DOWN)
    out = [base] * n
    out[0] = (out[0] + total - base * n).quantize(CENT)
    return out


# ---------------------------------------------------------------------------
# Referencias de Alegra para la pantalla de configuración
# ---------------------------------------------------------------------------

def cuentas_alegra(empresa, client=None):
    """Cuentas contables de movimiento activas de la empresa en Alegra: [{id, codigo, nombre}] por código."""
    # Mismo caché que el buscador de cuentas de la integración (alegra:categories:<empresa>).
    cats = cache.get(f'alegra:categories:{empresa.pk}')
    if cats is None:
        if client is None:
            from alegra_integration.client import AlegraMCPClient
            client = AlegraMCPClient(empresa, timeout=60)
        cats = client.rest('GET', '/categories?format=plain')
        if isinstance(cats, dict) and 'data' in cats:
            cats = cats['data']
        cats = cats if isinstance(cats, list) else []
        cache.set(f'alegra:categories:{empresa.pk}', cats, timeout=60 * 10)
    out = [{'id': str(c.get('id')), 'codigo': str(c.get('code') or ''), 'nombre': c.get('name') or ''}
           for c in cats if isinstance(c, dict) and c.get('use') == 'movement' and (c.get('status') or 'active') == 'active']
    return sorted(out, key=lambda c: c['codigo'])


def referencias_alegra(empresa):
    """Numeraciones de factura, ítems, impuestos, centros de costo y cuentas contables de movimiento.
    Las cuentas se piden una sola vez y alimentan todos los selectores de cuenta del formulario."""
    from alegra_integration.client import AlegraMCPClient

    key = f'conciliacion_terceros:facturacion:refs:{empresa.pk}'
    hit = cache.get(key)
    if hit:
        return hit
    client = AlegraMCPClient(empresa, timeout=60)

    def nombre_num(n):
        pref = n.get('prefix') or ''
        return f"{n.get('name') or ''} {('(' + pref + ')') if pref else ''}".strip()

    def lista(path, **params):
        return client._rest_list_all(path, extra_params=params or None)

    refs = {
        'numeraciones_factura': [{'id': str(n.get('id')), 'nombre': nombre_num(n)} for n in lista('/number-templates', documentType='invoice')],
        'items': [{'id': str(i.get('id')), 'nombre': i.get('name') or ''} for i in lista('/items') if (i.get('status') or 'active') == 'active'],
        'impuestos': [{'id': str(t.get('id')), 'nombre': f"{t.get('name') or ''} {t.get('percentage') or ''}%".strip()} for t in client._rest_taxes()],
        'centros_costo': [{'id': str(c.get('id')), 'nombre': f"{c.get('code') or ''} {c.get('name') or ''}".strip()} for c in lista('/cost-centers')],
        'cuentas': cuentas_alegra(empresa, client),
    }
    cache.set(key, refs, 60 * 10)
    return refs


def config_de(proyecto):
    return ConfigFacturacion.objects.select_related('empresa').filter(proyecto=proyecto).first()


def costo_sugerido(proyecto, negocio_ref):
    """Costo sugerido del inmueble: valor por m² del proyecto × área del lote."""
    from andinasoft.shared_models import Adjudicacion, Inmuebles

    config = config_de(proyecto)
    out = {'inmueble': '', 'area': '0', 'costo_m2': str(config.costo_m2 if config else 0), 'sugerido': '0'}
    adj = Adjudicacion.objects.using(proyecto).filter(pk=negocio_ref).first() if (negocio_ref or '').upper().startswith('ADJ') else None
    if not adj:
        return out
    inm = Inmuebles.objects.using(proyecto).filter(pk=adj.idinmueble).first()
    area = (inm.area_lt or inm.areaprivada or 0) if inm else 0
    out.update(inmueble=adj.idinmueble or '', area=str(Decimal(area or 0)))
    if config and config.costo_m2:
        out['sugerido'] = str((Decimal(area or 0) * config.costo_m2).quantize(CENT))
    return out


# ---------------------------------------------------------------------------
# Registro
# ---------------------------------------------------------------------------

def registrar(conciliacion, datos, user):
    """
    datos = {tipo, empresa, proyecto, negocio_ref, concepto, fecha, nota,
             titulares: [{identificacion, nombre, valor_venta, valor_intereses, numero, cruce_cuenta, cruce_cuenta_nombre, ya_cruzado}]}
    """
    tipo = datos.get('tipo')
    if tipo not in dict(FacturaConciliacion.TIPO_CHOICES):
        raise FacturacionError('Tipo de factura inválido.')
    try:
        fecha = datetime.date.fromisoformat(datos.get('fecha') or '')
    except ValueError:
        raise FacturacionError('Indica la fecha de la factura.')
    titulares = datos.get('titulares') or []
    if not titulares:
        raise FacturacionError('No hay titulares para facturar.')
    empresa = empresas.objects.filter(pk=datos.get('empresa')).first()
    if not empresa:
        raise FacturacionError('Selecciona la empresa que factura.')
    config = config_de(datos.get('proyecto'))
    if tipo == FacturaConciliacion.TIPO_ALEGRA:
        if not empresa.alegra_enabled:
            raise FacturacionError(f'{empresa.nombre} no tiene integración con Alegra.')
        if not config or config.modo != ConfigFacturacion.MODO_ALEGRA or str(config.empresa_id) != str(empresa.pk):
            raise FacturacionError('El proyecto no está configurado para facturar en Alegra con esta empresa.')
        faltan = config.faltantes_alegra()
        if faltan:
            raise FacturacionError('Completa la configuración de facturación del proyecto: ' + ', '.join(faltan) + '.')

    costo = Decimal(0)
    if tipo == FacturaConciliacion.TIPO_ALEGRA:
        try:
            costo = Decimal(str(datos.get('costo') or 0)).quantize(CENT)
        except Exception:
            raise FacturacionError('Costo del inmueble inválido.')
        if costo < 0:
            raise FacturacionError('El costo del inmueble no puede ser negativo.')

    if tipo == FacturaConciliacion.TIPO_ALEGRA:
        codigos = Counter(c['codigo'] for c in cuentas_alegra(empresa))
        for t in titulares:
            cta = (t.get('cruce_cuenta') or '').strip()
            if cta and codigos[cta] != 1:
                motivo = 'no existe en Alegra como cuenta de movimiento' if not codigos[cta] else 'está repetida en Alegra con el mismo código'
                raise FacturacionError(f'{t.get("identificacion")}: la cuenta {cta} {motivo}; elige otra cuenta de anticipos para el cruce.')

    idents = [str(t.get('identificacion') or '').strip() for t in titulares]
    if len(set(idents)) != len(idents):
        raise FacturacionError('Hay titulares repetidos en la factura.')
    # La revisión de duplicados y la creación van bajo un bloqueo de la conciliación: dos pestañas o un
    # reintento del navegador no pueden pasar la revisión a la vez y crear dos grupos (dos facturas DIAN).
    with transaction.atomic():
        Conciliacion.objects.select_for_update().filter(pk=conciliacion.pk).first()
        facturas = _crear_registros(conciliacion, datos, user, tipo, fecha, titulares, idents, empresa, costo)
    if tipo == FacturaConciliacion.TIPO_INFORMATIVA:
        con_venta = [f for f in facturas if f.valor_venta > 0]  # solo intereses no factura el inmueble
        if con_venta:
            marcar_escritura(con_venta[0], getattr(user, 'username', ''))
    # Las de Alegra quedan pendientes: la pantalla envía cada una en su propia petición (factura, costo y cruce
    # por separado), para que ninguna petición dependa de varias llamadas largas a Alegra.
    return facturas


def _crear_registros(conciliacion, datos, user, tipo, fecha, titulares, idents, empresa, costo):
    previas = list(FacturaConciliacion.objects.filter(
        proyecto=datos.get('proyecto') or '', negocio_ref=datos.get('negocio_ref') or '', identificacion__in=idents,
    ).exclude(estado=FacturaConciliacion.ESTADO_ANULADA).order_by('id'))
    sin_terminar = [p for p in previas if p.estado in (FacturaConciliacion.ESTADO_PENDIENTE, FacturaConciliacion.ESTADO_ERROR)]
    if sin_terminar:
        raise FacturacionError(
            'Ya hay facturas de este negocio que no terminaron de crearse (' +
            ', '.join(f'{p.identificacion} #{p.pk}' for p in sin_terminar) +
            '). Reintenta esas desde el historial o anula su registro; no se crea otra para no duplicar.')
    if previas and not datos.get('confirmar_duplicado'):
        raise RequiereConfirmacion(
            'Este negocio ya tiene ' + str(len(previas)) + ' factura(s) para estos titulares: ' +
            ', '.join(f'{p.identificacion} {p.numero or "#" + str(p.pk)} por ${p.total:,.0f} ({p.get_estado_display().lower()})' for p in previas) +
            '. ¿Registrar otra de todos modos?')

    grupo = str(uuid.uuid4())
    creadas = []
    intereses_grupo, con_previos = Decimal(0), False
    for t in titulares:
        try:
            venta = Decimal(str(t.get('valor_venta') or 0)).quantize(CENT)
            intereses = Decimal(str(t.get('valor_intereses') or 0)).quantize(CENT)
            previos = Decimal(str(t.get('intereses_previos') or 0)).quantize(CENT)
        except Exception:
            raise FacturacionError(f'{t.get("identificacion")}: valores inválidos.')
        total = venta + intereses
        if venta < 0 or intereses < 0 or previos < 0:
            raise FacturacionError(f'{t.get("identificacion")}: los valores no pueden ser negativos.')
        if total <= 0:
            raise FacturacionError(f'{t.get("identificacion")}: el valor a facturar debe ser mayor que cero.')
        intereses_grupo += intereses + previos
        con_previos = con_previos or previos > 0
        if tipo == FacturaConciliacion.TIPO_INFORMATIVA and not (t.get('numero') or '').strip():
            raise FacturacionError(f'{t.get("identificacion")}: indica el número de la factura emitida.')
        cruce_cuenta = (t.get('cruce_cuenta') or '').strip()
        # Sin cuenta de anticipos no hay cruce; en informativas también puede venir ya cruzado en contabilidad.
        ya_cruzado = not cruce_cuenta or (bool(t.get('ya_cruzado')) and tipo == FacturaConciliacion.TIPO_INFORMATIVA)
        creadas.append(FacturaConciliacion(
            conciliacion=conciliacion, grupo=grupo, tipo=tipo, empresa=empresa, proyecto=datos.get('proyecto') or '',
            negocio_ref=datos.get('negocio_ref') or '', identificacion=t['identificacion'], nombre=t.get('nombre') or '',
            concepto=datos.get('concepto') or 'venta_intereses', fecha=fecha, numero=(t.get('numero') or '').strip(),
            valor_venta=venta, valor_intereses=intereses, total=total, intereses_previos=previos,
            cruce_cuenta=cruce_cuenta, cruce_cuenta_nombre=(t.get('cruce_cuenta_nombre') or '') if cruce_cuenta else '',
            cruce_estado=FacturaConciliacion.CRUCE_NO_APLICA if ya_cruzado else FacturaConciliacion.CRUCE_PENDIENTE,
            estado=FacturaConciliacion.ESTADO_REGISTRADA if tipo == FacturaConciliacion.TIPO_INFORMATIVA else FacturaConciliacion.ESTADO_PENDIENTE,
            nota=(datos.get('nota') or '')[:2000], created_by=user,
        ))
    if con_previos:
        # El tope es el del negocio, no el de cada titular: a veces todo se le facturó a uno solo de ellos.
        recaudados = _intereses_negocio(conciliacion, idents, datos.get('proyecto'), datos.get('negocio_ref'))
        if recaudados is not None and intereses_grupo > recaudados + 1:
            raise FacturacionError(
                f'Los intereses a facturar más los ya facturados antes (${intereses_grupo:,.0f}) superan los intereses '
                f'recaudados del negocio (${recaudados:,.0f}).')
    if creadas and costo > 0:
        # El costo es uno por negocio y va a nombre de la empresa: se guarda en la primera factura del grupo.
        creadas[0].costo = costo
        creadas[0].costo_estado = FacturaConciliacion.CRUCE_PENDIENTE
    FacturaConciliacion.objects.bulk_create(creadas)
    return list(FacturaConciliacion.objects.filter(grupo=grupo).order_by('id'))


def _intereses_negocio(conciliacion, idents, proyecto, negocio_ref):
    """Intereses recaudados del negocio completo (todos sus titulares) según la última ejecución (None si no aparece)."""
    def del_negocio(linea):
        return next((n for n in (linea.negocios or []) if n.get('situacion') != 'factura' and n.get('proyecto') == proyecto
                     and str(n.get('ref')) == str(negocio_ref)), None)
    n = next((del_negocio(l) for l in conciliacion.lineas.filter(identificacion__in=idents) if del_negocio(l)), None)
    if n is None:
        return None
    titulares = n.get('titulares') or idents
    total = Decimal(0)
    for l in conciliacion.lineas.filter(identificacion__in=titulares):
        x = del_negocio(l)
        total += Decimal(str(x.get('intereses') or 0)) if x else Decimal(0)
    return total


# ---------------------------------------------------------------------------
# Alegra
# ---------------------------------------------------------------------------

def _client(empresa):
    from alegra_integration.client import AlegraMCPClient
    return AlegraMCPClient(empresa, timeout=90)


def _contacto(empresa, identificacion):
    from alegra_integration.exceptions import AlegraConfigurationError
    from alegra_integration.mapping import MappingResolver
    from conciliacion_terceros.engine import alias_identificaciones, equivalencias
    # Si el contacto se corrigió en Alegra después de registrar el movimiento, allá ya está con el Id nuevo.
    identificacion = alias_identificaciones()[0].get((str(empresa.pk), identificacion), identificacion)
    # Y si en contabilidad va con otro Id (Alegra no admite letras), el contacto está con ese.
    identificacion = equivalencias()[1].get(identificacion, identificacion)
    try:
        return str(MappingResolver(empresa).contact_for_cliente(identificacion))
    except AlegraConfigurationError as exc:
        raise SinContactoAlegra(empresa, identificacion, f'{identificacion} no tiene contacto en Alegra ({empresa.nombre}): {exc}')


class SinContactoAlegra(FacturacionError):
    """El tercero existe en Alegra pero no está enlazado (o no existe): la pantalla ofrece enlazarlo por su id."""
    def __init__(self, empresa, identificacion, mensaje):
        super().__init__(mensaje)
        self.falta_contacto = {'empresa': str(empresa.pk), 'empresa_nombre': empresa.nombre, 'identificacion': identificacion}


def payload_factura(f, config, contacto_id):
    items = []
    tax = [{'id': int(config.impuesto_id)}] if config.impuesto_id else []

    def linea(item_id, valor, descripcion):
        d = {'id': int(item_id), 'price': float(valor), 'quantity': 1, 'description': descripcion[:500]}
        if tax:
            d['tax'] = tax
        return d

    ref = f'{f.proyecto} {f.negocio_ref}'
    if f.valor_venta > 0:
        items.append(linea(config.item_venta_id, f.valor_venta, f'Venta inmueble {ref}'))
    if f.valor_intereses > 0:
        items.append(linea(config.item_intereses_id, f.valor_intereses, f'Intereses de financiación {ref}'))
    payload = {
        'date': f.fecha.isoformat(),
        'dueDate': (f.fecha + datetime.timedelta(days=config.dias_vencimiento or 0)).isoformat(),
        'client': {'id': int(contacto_id)},
        'items': items,
        'numberTemplate': {'id': int(config.numeracion_id)},
        'paymentForm': config.forma_pago or 'CREDIT',
        'observations': f'Conciliación de terceros · {ref} · FC-{f.pk}'[:500],
    }
    if (config.forma_pago or 'CREDIT') == 'CASH':
        payload['paymentMethod'] = 'INSTRUMENT_NOT_DEFINED'
    if config.centro_costo_id:
        payload['costCenter'] = {'id': int(config.centro_costo_id)}
    if config.emision == ConfigFacturacion.EMISION_EMITIR:
        payload['status'] = 'open'
        payload['stamp'] = {'generateStamp': True}
    else:
        payload['status'] = 'draft'
    return payload


def _numero(resp):
    nt = (resp or {}).get('numberTemplate') or {}
    return nt.get('fullNumber') or f"{nt.get('prefix') or ''}{nt.get('number') or ''}" or str((resp or {}).get('id') or '')


# ---------------------------------------------------------------------------
# Protección contra duplicados
#
# Cada paso (factura, costo, cruce) es independiente y se puede reintentar solo. Antes de crear algo en Alegra:
#   1. Se toma un bloqueo del paso en la base (dos clics, dos pestañas o dos personas no envían a la vez).
#   2. Se busca en Alegra si el documento ya existe (factura con «FC-<id>» en observaciones; journal con la
#      referencia exacta). Si existe uno se enlaza sin crear otro; si hay varios se detiene para revisión manual;
#      si no se puede consultar Alegra, no se envía.
#   3. Si el envío falla sin respuesta clara (timeout, 5xx) se vuelve a buscar: si quedó creado, se enlaza.
# ---------------------------------------------------------------------------

BLOQUEO_MINUTOS = 10
ESTADOS_ALEGRA_EMITIDA = ('open', 'closed')


@contextmanager
def _bloqueo(f, paso):
    ahora = timezone.now()
    libre = Q(paso_en_curso='') | Q(paso_en_curso_desde__lt=ahora - datetime.timedelta(minutes=BLOQUEO_MINUTOS))
    if not FacturaConciliacion.objects.filter(libre, pk=f.pk).update(paso_en_curso=paso, paso_en_curso_desde=ahora):
        raise FacturacionError('Este paso ya se está enviando a Alegra (otra pestaña u otra persona). '
                               'Espera un momento y recarga la página antes de volver a intentarlo.')
    try:
        f.refresh_from_db()  # estado fresco: otro proceso pudo completarlo
        yield
    finally:
        FacturaConciliacion.objects.filter(pk=f.pk, paso_en_curso=paso).update(paso_en_curso='', paso_en_curso_desde=None)
        f.paso_en_curso, f.paso_en_curso_desde = '', None


def _lista(resp):
    data = resp.get('data') if isinstance(resp, dict) and 'data' in resp else resp
    return data if isinstance(data, list) else []


def _token_factura(pk):
    return re.compile(r'(?<![\w-])FC-%d(?!\d)' % pk)


def _buscar_facturas_alegra(f, contacto_id):
    """Facturas del cliente en esa fecha cuyas observaciones traen «FC-<id>» (las que creó este registro)."""
    client, token, hallados, start = _client(f.empresa), _token_factura(f.pk), [], 0
    for _ in range(10):
        data = _lista(client.rest('GET', f'/invoices?start={start}&limit=30&client_id={contacto_id}&date={f.fecha.isoformat()}'))
        hallados += [i for i in data if isinstance(i, dict) and token.search(i.get('observations') or '')]
        if len(data) < 30:
            return hallados
        start += 30
    raise FacturacionError('El cliente tiene demasiadas facturas en esa fecha para verificar duplicados; revisa en Alegra.')


def _ya_enlazada(campo, alegra_id, f):
    return bool(alegra_id) and FacturaConciliacion.objects.filter(empresa_id=f.empresa_id, **{campo: str(alegra_id)}).exclude(pk=f.pk).exists()


def _journal_idempotente(f, referencia, construir_payload):
    return journal_idempotente(f.empresa, referencia, construir_payload)


ESTADOS_JOURNAL_ANULADO = ('void', 'voided', 'annulled', 'cancelled', 'canceled')


def journal_idempotente(empresa, referencia, construir_payload):
    """Devuelve (journal, ya_existia). Nunca crea un segundo journal con la misma referencia.
    Solo devuelve un journal válido: con id y no anulado; si no, lanza FacturacionError."""
    journal, ya = _journal_idempotente_crudo(empresa, referencia, construir_payload)
    jid = str(journal.get('id') or '') if isinstance(journal, dict) else ''
    if not jid:
        raise FacturacionError(f'Alegra no devolvió el journal «{referencia}»; no quedó registrado. Respuesta: {journal}'[:1000])
    if str(journal.get('status') or '').lower() in ESTADOS_JOURNAL_ANULADO:
        raise FacturacionError(f'En Alegra existe el journal {jid} con la referencia «{referencia}», pero está anulado. '
                               'Elimínalo en Alegra para volver a registrarlo.')
    return journal, ya


def _journal_idempotente_crudo(empresa, referencia, construir_payload):
    from alegra_integration.journal_reconcile import _journal_reference, list_journals_by_reference

    client = _client(empresa)

    def buscar():
        return [j for j in list_journals_by_reference(client, referencia) if _journal_reference(j) == referencia]

    try:
        hallados = buscar()
    except Exception as exc:
        raise FacturacionError(f'No se pudo verificar en Alegra si el journal «{referencia}» ya existe ({exc}); '
                               'no se envió nada. Intenta de nuevo en un momento.')
    if len(hallados) > 1:
        raise FacturacionError(f'En Alegra hay {len(hallados)} journals con la referencia «{referencia}». '
                               'Elimina los sobrantes en Alegra y vuelve a intentar.')
    if hallados:
        return hallados[0], True
    payload = construir_payload()
    try:
        return client.rest('POST', '/journals', json_payload=payload), False
    except Exception:
        try:
            hallados = buscar()
        except Exception:
            hallados = []
        if len(hallados) == 1:
            return hallados[0], True
        raise


def _aplicar_factura_alegra(f, inv, reconciliada=False):
    status = (inv or {}).get('status')
    if status == 'voided':
        raise FacturacionError(f'La factura {_numero(inv)} está anulada en Alegra.')
    f.alegra_invoice_id = str(inv.get('id') or '')
    f.numero = _numero(inv) or f.numero
    f.estado = FacturaConciliacion.ESTADO_EMITIDA if status in ESTADOS_ALEGRA_EMITIDA else FacturaConciliacion.ESTADO_BORRADOR
    f.respuesta = dict(f.respuesta or {}, factura=inv, **({'factura_reconciliada': True} if reconciliada else {}))
    f.error = ''


def _encadenar(f, config, usuario):
    """Tras la factura emitida: marca la escrituración (local). El costo y el cruce van cada uno en su propia
    petición (la pantalla los encadena), para no juntar varias llamadas largas a Alegra en un solo request."""
    if f.estado == FacturaConciliacion.ESTADO_EMITIDA:
        marcar_escritura(f, usuario)
    return f


def siguiente_paso(f):
    """Lo que le falta a una factura de Alegra, en orden: 'enviar', 'costo', 'cruzar' o '' si no falta nada
    (o si lo que sigue depende de una acción del usuario, como emitir un borrador)."""
    if f.tipo != FacturaConciliacion.TIPO_ALEGRA or f.estado == FacturaConciliacion.ESTADO_ANULADA:
        return ''
    if f.estado in (FacturaConciliacion.ESTADO_PENDIENTE, FacturaConciliacion.ESTADO_ERROR) and not f.error:
        return 'enviar'
    if f.estado != FacturaConciliacion.ESTADO_EMITIDA:
        return ''
    if f.costo_estado == FacturaConciliacion.CRUCE_PENDIENTE and f.costo > 0 and not f.error_costo:
        return 'costo'
    if f.cruce_estado == FacturaConciliacion.CRUCE_PENDIENTE and f.cruce_cuenta and not f.error_cruce:
        return 'cruzar'
    return ''


def crear_en_alegra(f, config, user=None):
    """Paso 1: la factura. Si ya existe en Alegra (por un intento anterior) se enlaza en vez de crear otra."""
    usuario = getattr(user, 'username', '') or getattr(f.created_by, 'username', '')
    with _bloqueo(f, 'factura'):
        if f.alegra_invoice_id and f.estado in (FacturaConciliacion.ESTADO_BORRADOR, FacturaConciliacion.ESTADO_EMITIDA):
            pass  # otro proceso ya la creó
        else:
            try:
                contacto = _contacto(f.empresa, f.identificacion)
                try:
                    existentes = _buscar_facturas_alegra(f, contacto)
                except FacturacionError:
                    raise
                except Exception as exc:
                    raise FacturacionError(f'No se pudo verificar en Alegra si la factura ya existe ({exc}); no se envió nada.')
                if len(existentes) > 1:
                    raise FacturacionError(f'En Alegra hay {len(existentes)} facturas con «FC-{f.pk}» en observaciones: '
                                           'anula las sobrantes en Alegra y vuelve a intentar.')
                if existentes:
                    _aplicar_factura_alegra(f, existentes[0], reconciliada=True)
                else:
                    payload = payload_factura(f, config, contacto)
                    try:
                        inv = _client(f.empresa).rest('POST', '/invoices', json_payload=payload)
                        reconciliada = False
                    except Exception:
                        try:
                            existentes = _buscar_facturas_alegra(f, contacto)
                        except Exception:
                            existentes = []
                        if len(existentes) != 1:
                            raise
                        inv, reconciliada = existentes[0], True
                    _aplicar_factura_alegra(f, inv, reconciliada)
                if _ya_enlazada('alegra_invoice_id', f.alegra_invoice_id, f):
                    raise FacturacionError(f'La factura {f.numero} de Alegra ya está enlazada a otro registro.')
                f.save()
            except Exception as exc:
                f.estado = FacturaConciliacion.ESTADO_ERROR
                f.error = (f'{exc} Al reintentar, el sistema busca primero en Alegra la factura «FC-{f.pk}» para no duplicarla.')[:4000]
                f.save()
                return f
    return _encadenar(f, config, usuario)


def emitir(f):
    """Emite (DIAN) una factura que quedó en borrador. Si ya está emitida en Alegra, solo se actualiza aquí."""
    if f.estado != FacturaConciliacion.ESTADO_BORRADOR or not f.alegra_invoice_id:
        raise FacturacionError('Solo se puede emitir una factura en borrador de Alegra.')
    with _bloqueo(f, 'factura'):
        if f.estado != FacturaConciliacion.ESTADO_BORRADOR:
            return f
        client = _client(f.empresa)
        inv = client.rest('GET', f'/invoices/{f.alegra_invoice_id}')
        if (inv or {}).get('status') == 'draft':
            resp = client.rest('POST', '/invoices/stamp', json_payload={'ids': [f.alegra_invoice_id]})
            filas = resp if isinstance(resp, list) else (resp.get('data') or resp.get('results') or [resp]) if isinstance(resp, dict) else []
            ok = any(str(r.get('id')) == f.alegra_invoice_id and r.get('success') for r in filas if isinstance(r, dict))
            f.respuesta = dict(f.respuesta or {}, emision=resp)
            inv = client.rest('GET', f'/invoices/{f.alegra_invoice_id}')
            if not ok and (inv or {}).get('status') not in ESTADOS_ALEGRA_EMITIDA:
                f.error = f'Alegra no emitió la factura: {resp}'[:4000]
                f.save(update_fields=['respuesta', 'error'])
                raise FacturacionError(f.error)
        _aplicar_factura_alegra(f, inv)
        f.save()
    config = config_de(f.proyecto)
    if config:
        _encadenar(f, config, getattr(f.created_by, 'username', ''))
    return f


def registrar_costo(f, config):
    """Paso 2: journal de costo de venta (débito costo 6, crédito inventario 15), a nombre de la empresa."""
    if f.costo_estado != FacturaConciliacion.CRUCE_PENDIENTE or f.costo <= 0:
        return f
    if f.estado != FacturaConciliacion.ESTADO_EMITIDA:
        raise FacturacionError('El costo se registra cuando la factura está emitida.')
    with _bloqueo(f, 'costo'):
        if f.costo_estado != FacturaConciliacion.CRUCE_PENDIENTE:
            return f
        referencia = f'COSTO-FC-{f.pk}'

        def construir():
            from alegra_integration.mapping import MappingResolver
            try:
                empresa_contacto = {'client': {'id': int(MappingResolver(f.empresa).contact_for_empresa(f.empresa.pk))}}
            except Exception:
                empresa_contacto = {}
            cc = {'costCenter': {'id': int(config.centro_costo_id)}} if config.centro_costo_id else {}
            desc = f'Costo de venta {f.proyecto} {f.negocio_ref} · factura {f.numero}'
            payload = {
                'date': f.fecha.isoformat(),
                'observations': f'{desc} · FC-{f.pk}'[:500],
                'reference': referencia,
                'entries': [
                    dict({'id': int(config.cuenta_costo_id), 'debit': float(f.costo), 'credit': 0, 'description': desc[:255]}, **empresa_contacto, **cc),
                    dict({'id': int(config.cuenta_inventario_id), 'debit': 0, 'credit': float(f.costo), 'description': desc[:255]}, **empresa_contacto, **cc),
                ],
            }
            if config.numeracion_journal_id:
                payload['numberTemplate'] = str(config.numeracion_journal_id)  # mismo contrato que caja (_journal_payload)
            return payload

        try:
            resp, ya = _journal_idempotente(f, referencia, construir)
            f.alegra_costo_journal_id = str(resp.get('id') or '')
            f.costo_estado = FacturaConciliacion.CRUCE_REGISTRADO
            f.respuesta = dict(f.respuesta or {}, costo=resp, **({'costo_reconciliado': True} if ya else {}))
            f.error_costo = ''
        except Exception as exc:
            f.error_costo = (f'{exc} Al reintentar, el sistema busca primero en Alegra el journal «{referencia}».')[:4000]
        f.save()
    return f


def cruzar(f, config):
    """Paso 3: RC. Débito a la cuenta de anticipos del tercero, crédito a la CxC asociado a la factura."""
    if f.cruce_estado != FacturaConciliacion.CRUCE_PENDIENTE:
        return f
    if f.tipo != FacturaConciliacion.TIPO_ALEGRA or f.estado != FacturaConciliacion.ESTADO_EMITIDA:
        raise FacturacionError('El cruce por journal se hace sobre una factura emitida en Alegra.')
    with _bloqueo(f, 'cruce'):
        if f.cruce_estado != FacturaConciliacion.CRUCE_PENDIENTE:
            return f
        referencia = f'CRUCE-FC-{f.pk}'

        def construir():
            # El cruce acredita la CxC por el valor registrado. Si la factura en Alegra vale otra cosa (p. ej. con
            # impuesto), quedaría un saldo abierto en la CxC: no se envía y queda el error para revisarlo.
            total_alegra = ((f.respuesta or {}).get('factura') or {}).get('total')
            try:
                total_alegra = Decimal(str(total_alegra)) if total_alegra not in (None, '') else None
            except Exception:
                total_alegra = None
            if total_alegra is not None and abs(total_alegra - f.total) > 1:
                raise FacturacionError(
                    f'La factura en Alegra vale ${total_alegra:,.0f} y el registro ${f.total:,.0f} (¿impuesto en la factura?). '
                    'No se envió el cruce: dejaría un saldo abierto en la cuenta por cobrar. Revisa el impuesto configurado del proyecto.')
            halladas = [c for c in cuentas_alegra(f.empresa) if f.cruce_cuenta and c['codigo'] == f.cruce_cuenta]
            if len(halladas) != 1:
                raise FacturacionError(f'La cuenta de anticipos {f.cruce_cuenta or "(vacía)"} '
                                       + ('no existe en Alegra como cuenta de movimiento.' if not halladas else 'está repetida en Alegra con el mismo código.'))
            contacto = {'id': int(_contacto(f.empresa, f.identificacion))}
            cc = {'costCenter': {'id': int(config.centro_costo_id)}} if config.centro_costo_id else {}
            payload = {
                'date': f.fecha.isoformat(),
                'observations': f'Cruce anticipo factura {f.numero} · {f.proyecto} {f.negocio_ref} · FC-{f.pk}'[:500],
                'reference': referencia,
                'entries': [
                    dict({'id': int(halladas[0]['id']), 'debit': float(f.total), 'credit': 0, 'client': contacto,
                          'description': f'Cruce anticipo {f.proyecto} {f.negocio_ref}'}, **cc),
                    dict({'id': int(config.cuenta_cxc_id), 'debit': 0, 'credit': float(f.total), 'client': contacto,
                          'description': f'Factura {f.numero}',
                          'associatedDocument': {'idResource': int(f.alegra_invoice_id), 'resourceType': 'invoice'}}, **cc),
                ],
            }
            if config.numeracion_journal_id:
                payload['numberTemplate'] = str(config.numeracion_journal_id)  # mismo contrato que caja (_journal_payload)
            return payload

        try:
            resp, ya = _journal_idempotente(f, referencia, construir)
            f.alegra_journal_id = str(resp.get('id') or '')
            f.cruce_estado = FacturaConciliacion.CRUCE_REGISTRADO
            f.respuesta = dict(f.respuesta or {}, cruce=resp, **({'cruce_reconciliado': True} if ya else {}))
            f.error_cruce = ''
        except Exception as exc:
            f.error_cruce = (f'{exc} Al reintentar, el sistema busca primero en Alegra el journal «{referencia}».')[:4000]
        f.save()
    return f


# ---------------------------------------------------------------------------
# Escrituración: la factura deja la ADJ como escriturada y con el paso "Facturado"
# ---------------------------------------------------------------------------

def marcar_escritura(f, usuario):
    """
    Marca en el módulo de escrituración el paso "Facturado" y deja la ADJ escriturada.
    No exige los pasos previos (muchas escrituras antiguas no los tienen cargados) y no pisa fechas existentes.
    Guarda en la factura qué cambió para poder deshacerlo si se anula.
    """
    from andinasoft import promesas_service
    from andinasoft.models import PromesaCumplimiento, PromesaHito

    if not (f.negocio_ref or '').upper().startswith('ADJ'):
        return None  # ventas sin adjudicar: no hay escritura
    if f.valor_venta <= 0:
        return None  # solo intereses: el inmueble no se ha facturado, la escritura no avanza
    ya = FacturaConciliacion.objects.filter(
        proyecto=f.proyecto, negocio_ref=f.negocio_ref, respuesta__escritura__isnull=False,
    ).exclude(pk=f.pk).exclude(estado=FacturaConciliacion.ESTADO_ANULADA).exists()
    if ya:
        return None  # otra factura vigente del negocio ya lo marcó
    cambios = {'cumplimiento': {}, 'promesa': {}}
    try:
        cambios['cumplimiento_creado'] = not PromesaCumplimiento.objects.filter(proyecto_id=f.proyecto, adj=f.negocio_ref).exists()
        cump = promesas_service.ensure_cumplimiento(f.proyecto, f.negocio_ref)
        for campo in ('fecha_facturado', 'fecha_escritura_real'):
            if not getattr(cump, campo):
                cambios['cumplimiento'][campo] = None
                setattr(cump, campo, f.fecha)
        hechos = promesas_service.hechos_from_cumplimiento(cump)
        hechos.add(PromesaCumplimiento.PASO_FACTURADO)
        cambios['cumplimiento']['paso_escritura_actual'] = cump.paso_escritura_actual
        cump.paso_escritura_actual = promesas_service.resumen_paso(hechos)
        if not cump.usuario_escritura:
            cambios['cumplimiento']['usuario_escritura'] = ''
            cump.usuario_escritura = str(usuario or '')
        cump.save()
        hito = PromesaHito.objects.create(
            proyecto=cump.proyecto, adj=f.negocio_ref, paso=PromesaCumplimiento.PASO_FACTURADO, fecha=f.fecha,
            usuario=str(usuario or ''),
            nota=f'Registrado desde la conciliación de terceros: factura {f.numero or "(sin número)"} ({f.get_tipo_display().lower()}).',
        )
        cambios['hito_id'] = hito.pk
        promesa = promesas_service.ensure_promesa(f.proyecto, f.negocio_ref, usuario=usuario)
        if not promesa.escriturado:
            cambios['promesa']['escriturado'] = promesa.escriturado
            promesa.escriturado = True
        if not promesa.fechaescritura:
            cambios['promesa']['fechaescritura'] = None
            promesa.fechaescritura = f.fecha
        if cambios['promesa']:
            promesa.save(using=f.proyecto)
    except Exception as exc:
        logger.exception('No se pudo marcar la escritura de %s %s', f.proyecto, f.negocio_ref)
        f.error = (f.error + ' ' if f.error else '') + f'La factura quedó registrada pero no se pudo marcar la escrituración: {exc}'
        f.save(update_fields=['error'])
        return None
    f.respuesta = dict(f.respuesta or {}, escritura=cambios)
    f.save(update_fields=['respuesta'])
    return cambios


def desmarcar_escritura(f):
    """Deshace lo que hizo `marcar_escritura` si no queda otra factura vigente del negocio."""
    from andinasoft.models import PromesaCumplimiento, PromesaHito
    from andinasoft.shared_models import Promesas

    f.refresh_from_db()
    cambios = (f.respuesta or {}).get('escritura')
    if not cambios:
        return
    otra = FacturaConciliacion.objects.filter(proyecto=f.proyecto, negocio_ref=f.negocio_ref).exclude(pk=f.pk).exclude(
        estado__in=(FacturaConciliacion.ESTADO_ANULADA, FacturaConciliacion.ESTADO_ERROR, FacturaConciliacion.ESTADO_PENDIENTE)).first()
    if otra:
        # Otra factura del negocio sigue vigente: le pasa el registro de lo cambiado.
        otra.respuesta = dict(otra.respuesta or {}, escritura=cambios)
        otra.save(update_fields=['respuesta'])
    else:
        cump = PromesaCumplimiento.objects.filter(proyecto_id=f.proyecto, adj=f.negocio_ref).first()
        if cump and cambios.get('cumplimiento_creado'):
            cump.delete()
        elif cump:
            for campo, antes in (cambios.get('cumplimiento') or {}).items():
                setattr(cump, campo, antes)
            cump.save()
        if cambios.get('hito_id'):
            PromesaHito.objects.filter(pk=cambios['hito_id']).delete()
        if cambios.get('promesa'):
            Promesas.objects.using(f.proyecto).filter(idadjudicacion=f.negocio_ref).update(**cambios['promesa'])
    f.respuesta = dict(f.respuesta or {}, escritura_revertida=cambios)
    f.respuesta.pop('escritura', None)
    f.save(update_fields=['respuesta'])


def _no_existe(exc):
    return 'HTTP 404' in str(exc)


def verificar_anulacion(f, user):
    """Factura emitida o en borrador: consulta Alegra. Si allá está anulada (o el borrador se eliminó), el registro
    se anula aquí y deja de contar. Devuelve (anulada, mensaje)."""
    if f.tipo != FacturaConciliacion.TIPO_ALEGRA or f.estado not in (FacturaConciliacion.ESTADO_EMITIDA, FacturaConciliacion.ESTADO_BORRADOR) \
            or not f.alegra_invoice_id:
        raise FacturacionError('Solo se verifica una factura emitida o en borrador en Alegra.')
    try:
        inv = _client(f.empresa).rest('GET', f'/invoices/{f.alegra_invoice_id}')
    except Exception as exc:
        if not _no_existe(exc):
            raise FacturacionError(f'No se pudo consultar la factura en Alegra ({exc}).')
        inv = None
    status = (inv or {}).get('status') if isinstance(inv, dict) else None
    if inv is not None and status != 'voided':
        return False, f'En Alegra la factura {_numero(inv) or f.numero} sigue vigente (estado «{status}»). No se cambió nada.'
    estado_antes = f.estado
    marca = {'fecha': timezone.now().isoformat(), 'usuario': getattr(user, 'username', ''),
             'motivo': 'anulada en Alegra' if inv is not None else 'ya no existe en Alegra'}
    if not FacturaConciliacion.objects.filter(pk=f.pk, estado=estado_antes).update(
            estado=FacturaConciliacion.ESTADO_ANULADA, anulada_por=user, anulada_en=timezone.now()):
        raise FacturacionError('El registro cambió mientras se verificaba; recarga la página.')
    f.refresh_from_db()
    f.respuesta = dict(f.respuesta or {}, anulada_en_alegra=marca)
    f.save(update_fields=['respuesta'])
    desmarcar_escritura(f)
    extra = ''
    if f.alegra_journal_id or f.alegra_costo_journal_id:
        extra = ' Revisa en Alegra que también estén anulados sus journals de ' + ' y '.join(
            x for x, j in (('cruce', f.alegra_journal_id), ('costo', f.alegra_costo_journal_id)) if j) + '.'
    return True, f'La factura {f.numero} está {marca["motivo"]}: el registro quedó anulado aquí y deja de contar.{extra}'


def anular_registro(f, user):
    """Anula el registro local. Una factura emitida en Alegra no se anula aquí (requiere nota crédito).
    Si el registro es de Alegra y quedó pendiente o con error, antes se verifica que no se haya creado allá:
    anularlo y registrar otra produciría una segunda factura electrónica."""
    if f.tipo == FacturaConciliacion.TIPO_ALEGRA and f.estado == FacturaConciliacion.ESTADO_EMITIDA:
        raise FacturacionError('La factura ya está emitida en Alegra: se anula con nota crédito en Alegra.')
    if f.tipo == FacturaConciliacion.TIPO_ALEGRA and f.estado == FacturaConciliacion.ESTADO_BORRADOR:
        raise FacturacionError('La factura está como borrador en Alegra: elimínala allá antes de anular el registro.')
    estado_antes = f.estado
    if f.tipo == FacturaConciliacion.TIPO_ALEGRA:
        if f.paso_en_curso and f.paso_en_curso_desde and f.paso_en_curso_desde > timezone.now() - datetime.timedelta(minutes=BLOQUEO_MINUTOS):
            raise FacturacionError('La factura se está enviando a Alegra en este momento; espera y recarga la página.')
        try:
            contacto = _contacto(f.empresa, f.identificacion)
        except FacturacionError:
            contacto = None  # sin contacto en Alegra no se pudo crear la factura
        if contacto:
            try:
                existentes = _buscar_facturas_alegra(f, contacto)
            except Exception as exc:
                raise FacturacionError(f'No se pudo verificar en Alegra si la factura «FC-{f.pk}» quedó creada ({exc}); '
                                       'no se anuló. Intenta de nuevo en un momento.')
            if existentes:
                raise FacturacionError(f'En Alegra sí existe la factura {_numero(existentes[0])} de este registro (FC-{f.pk}). '
                                       'Usa «Reintentar» para enlazarla en vez de anular y crear otra.')
    # Cambio condicional: si otro proceso cambió el estado mientras tanto, no se anula.
    if not FacturaConciliacion.objects.filter(pk=f.pk, estado=estado_antes).update(
            estado=FacturaConciliacion.ESTADO_ANULADA, anulada_por=user, anulada_en=timezone.now()):
        raise FacturacionError('El registro cambió mientras se anulaba; recarga la página.')
    f.refresh_from_db()
    desmarcar_escritura(f)
    return f
