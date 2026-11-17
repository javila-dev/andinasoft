"""
Ajustes de la conciliación (traslados de saldo contable) llevados a la contabilidad.

- Empresa con Alegra: el ajuste se envía como journal (mismo contrato que caja: `_journal_payload`). Solo se da por
  aplicado cuando Alegra devuelve el journal creado, o cuando ya existía uno con la referencia AJ-CT-<id>. Si Alegra
  falla, el ajuste queda pendiente con el error y no mueve saldos; al reintentar se busca primero por referencia,
  así nunca se crea un journal duplicado.
- Empresa sin Alegra: queda pendiente hasta que alguien marque que lo registró a mano en su contabilidad.

El saldo de cada cuenta viene en su naturaleza (crédito positivo en las clases 2, 3 y 4), así que el origen y el
destino deben tener la misma naturaleza para que el asiento cuadre.

Excepción: el cruce con otra cuenta (tipo «cruce»), p. ej. anticipos 28 contra clientes 13. La otra cuenta no hace
parte de la conciliación y puede ser de cualquier naturaleza: el origen se debita (si es crédito) y la otra cuenta
recibe la contrapartida. En la conciliación solo baja el origen.
"""
import datetime
import logging
from decimal import Decimal

from django.db.models import Q
from django.utils import timezone

from conciliacion_terceros.models import AjusteConciliacion, ConfigEmpresa

logger = logging.getLogger(__name__)
BLOQUEO_MINUTOS = 10
ZERO = Decimal('0')


class AjusteError(Exception):
    pass


def naturaleza(cuenta):
    """'C' (crédito) para las clases 2, 3 y 4; 'D' (débito) para las demás."""
    return 'C' if str(cuenta or '')[:1] in '234' else 'D'


def lineas_asiento(a):
    """Las dos líneas del asiento: el origen pierde saldo y el destino lo gana.
    [{'lado', 'identificacion', 'cuenta', 'cuenta_nombre', 'debito', 'credito'}]"""
    v = a.valor
    credito_natural = naturaleza(a.origen_cuenta) == 'C'
    return [
        {'lado': 'origen', 'identificacion': a.origen_identificacion, 'cuenta': a.origen_cuenta,
         'cuenta_nombre': a.origen_cuenta_nombre, 'debito': v if credito_natural else ZERO, 'credito': ZERO if credito_natural else v},
        {'lado': 'destino', 'identificacion': a.destino_identificacion, 'cuenta': a.destino_cuenta,
         'cuenta_nombre': a.destino_cuenta_nombre, 'debito': ZERO if credito_natural else v, 'credito': v if credito_natural else ZERO},
    ]


def resolver(a, cuentas=None, grupo=None):
    """Cuentas, contactos y numeración en Alegra de todo el comprobante. Lanza AjusteError antes de enviar nada
    si falta algo: así un traslado con un dato incompleto no deja el comprobante a medias."""
    from conciliacion_terceros import facturacion

    empresa = a.origen_empresa
    grupo = list(grupo or [a])
    try:
        cuentas = cuentas if cuentas is not None else facturacion.cuentas_alegra(empresa)
    except Exception as exc:
        raise AjusteError(f'No se pudieron consultar las cuentas de {empresa.nombre} en Alegra ({exc}).')
    ids = {}
    for codigo in {c for x in grupo for c in (x.origen_cuenta, x.destino_cuenta)}:
        halladas = [c for c in cuentas if c['codigo'] == codigo]
        if len(halladas) != 1:
            raise AjusteError(f'La cuenta {codigo} ' + ('no existe en Alegra como cuenta de movimiento'
                                                        if not halladas else 'está repetida en Alegra con el mismo código')
                              + f' ({empresa.nombre}).')
        ids[codigo] = halladas[0]['id']
    contactos = {}
    for ident in {i for x in grupo for i in (x.origen_identificacion, x.destino_identificacion)}:
        try:
            contactos[ident] = facturacion._contacto(empresa, ident)
        except facturacion.FacturacionError as exc:
            err = AjusteError(str(exc))
            err.falta_contacto = getattr(exc, 'falta_contacto', None)  # la pantalla ofrece enlazarlo
            raise err
        except Exception as exc:
            raise AjusteError(f'No se pudo consultar el contacto {ident} en Alegra ({exc}).')
    cfg = ConfigEmpresa.objects.filter(empresa_id=empresa.pk).first()
    return {'cuentas': ids, 'contactos': contactos, 'numeracion': (cfg.numeracion_journal_id if cfg else '').strip()}


def payload(a, r, grupo=None):
    """Un solo comprobante con dos líneas por traslado: los guardados juntos van en el mismo journal."""
    from alegra_integration.builders import _journal_entry, _journal_payload

    corte = a.conciliacion.fecha_corte.strftime('%d/%m/%Y')
    grupo = list(grupo or [a])
    entries, notas = [], []
    for x in grupo:
        if x.nota and x.nota not in notas:
            notas.append(x.nota)
        for l in lineas_asiento(x):
            otro = x.destino_identificacion if l['lado'] == 'origen' else x.origen_identificacion
            if x.es_cruce:
                desc = f'Cruce {x.origen_cuenta} contra {x.destino_cuenta} · conciliación {corte}'
            elif otro == l['identificacion']:
                desc = f'Traslado entre cuentas · conciliación {corte}'
            elif l['lado'] == 'origen':
                desc = f'Traslado de saldo a {otro} · conciliación {corte}'
            else:
                desc = f'Traslado de saldo desde {otro} · conciliación {corte}'
            entries.append(_journal_entry(account_id=r['cuentas'][l['cuenta']], description=f'{desc} · {a.referencia}',
                                          debit=float(l['debito']), credit=float(l['credito']),
                                          client_id=r['contactos'][l['identificacion']]))
    observaciones = f'{a.referencia} · Conciliación de terceros {corte}' + (' · ' + ' | '.join(notas) if notas else '')
    p = _journal_payload(numeration_id=r['numeracion'], date=a.fecha.isoformat(), reference=a.referencia,
                         observations=observaciones, entries=entries)
    if not r['numeracion']:
        p.pop('numberTemplate')  # vacío = numeración predeterminada de Alegra
    return p


def pendientes_del_grupo(a):
    """Los traslados que van en el mismo comprobante que `a` y siguen pendientes, en el orden en que se registraron."""
    if not a.grupo_ref:
        return [a]
    return list(AjusteConciliacion.objects.filter(
        grupo_ref=a.grupo_ref, anulado=False, journal_estado=AjusteConciliacion.JOURNAL_PENDIENTE,
    ).select_related('origen_empresa', 'conciliacion').order_by('created_at', 'id'))


CAMPOS_ENVIO = ['journal_estado', 'journal_ref', 'journal_respuesta', 'journal_error', 'enviado_en',
                'enviado_por', 'envio_en_curso_desde']


def enviar(a, usuario=None):
    """Envía a Alegra el comprobante de `a` con todos los traslados pendientes de su grupo (un journal con dos líneas
    por traslado) y espera la respuesta. Solo con el journal confirmado quedan `enviado`; si falla siguen pendientes
    con el error y no mueven saldos."""
    from conciliacion_terceros import facturacion

    if a.anulado or a.journal_estado != AjusteConciliacion.JOURNAL_PENDIENTE:
        return a
    if not a.via_alegra:
        raise AjusteError(f'{a.origen_empresa.nombre} no tiene Alegra: este traslado se registra a mano.')
    if not a.fecha:
        raise AjusteError('Falta la fecha del comprobante.')
    ahora = timezone.now()
    libre = Q(envio_en_curso_desde__isnull=True) | Q(envio_en_curso_desde__lt=ahora - datetime.timedelta(minutes=BLOQUEO_MINUTOS))
    pks = [x.pk for x in pendientes_del_grupo(a)] or [a.pk]
    # Se toman todos los del comprobante a la vez: si otro envío ya tiene alguno, no se manda nada.
    tomados = AjusteConciliacion.objects.filter(libre, pk__in=pks, anulado=False,
                                                journal_estado=AjusteConciliacion.JOURNAL_PENDIENTE).update(envio_en_curso_desde=ahora)
    if tomados != len(pks):
        AjusteConciliacion.objects.filter(pk__in=pks, envio_en_curso_desde=ahora).update(envio_en_curso_desde=None)
        raise AjusteError('Este comprobante ya se está enviando a Alegra (otra pestaña u otra persona) o alguno de sus '
                          'traslados ya no está pendiente. Recarga la página.')
    try:
        grupo = list(AjusteConciliacion.objects.filter(pk__in=pks).select_related('origen_empresa', 'conciliacion')
                     .order_by('created_at', 'id'))
        a = next(x for x in grupo if x.pk == a.pk)
        error = ''
        try:
            r = resolver(a, grupo=grupo)
            journal, ya_existia = facturacion.journal_idempotente(a.origen_empresa, a.referencia,
                                                                  lambda: payload(a, r, grupo))
        except AjusteError as exc:
            error = f'No se envió nada a Alegra: {exc}'[:4000]
        except Exception as exc:
            logger.warning('Ajuste %s: envío a Alegra falló', a.pk, exc_info=True)
            error = (f'{exc} No quedó aplicado. Al reintentar se busca primero en Alegra el journal '
                     f'«{a.referencia}» para no duplicarlo.')[:4000]
        else:
            jid = str(journal.get('id') or '') if isinstance(journal, dict) else ''
            estado = str(journal.get('status') or '').lower() if isinstance(journal, dict) else ''
            if not jid:
                error = f'Alegra no devolvió el journal creado; no quedó aplicado. Respuesta: {journal}'[:4000]
            elif estado in ('void', 'voided', 'annulled', 'cancelled'):
                error = (f'En Alegra existe el journal {jid} con la referencia «{a.referencia}», pero está anulado. '
                         'Elimínalo en Alegra para volver a enviar, o anula estos traslados.')
        ahora_fin = timezone.now()
        for x in grupo:
            if error:
                x.journal_error = error
            else:
                x.journal_estado = AjusteConciliacion.JOURNAL_ENVIADO
                x.journal_ref = jid
                x.journal_respuesta = dict(journal, **({'_reconciliado': True} if ya_existia else {}))
                x.journal_error = ''
                x.enviado_en = ahora_fin
                x.enviado_por = usuario
            x.envio_en_curso_desde = None
            # Solo los campos del envío: no se pisa una anulación u otro cambio hecho en paralelo.
            x.save(update_fields=CAMPOS_ENVIO)
        a = next(x for x in grupo if x.pk == a.pk)
    finally:
        AjusteConciliacion.objects.filter(pk__in=pks, envio_en_curso_desde=ahora).update(envio_en_curso_desde=None)
    return a


def verificar_anulacion(a, usuario):
    """Traslado enviado: consulta el journal en Alegra. Si allá está anulado o ya no existe, se anula aquí y deja de
    contar. Devuelve (anulado, mensaje)."""
    from conciliacion_terceros import facturacion

    if a.anulado or a.journal_estado != AjusteConciliacion.JOURNAL_ENVIADO or not a.journal_ref:
        raise AjusteError('Solo se verifica un traslado enviado a Alegra.')
    try:
        j = facturacion._client(a.origen_empresa).rest('GET', f'/journals/{a.journal_ref}')
    except Exception as exc:
        if not facturacion._no_existe(exc):
            raise AjusteError(f'No se pudo consultar el journal en Alegra ({exc}).')
        j = None
    status = str((j or {}).get('status') or '').lower() if isinstance(j, dict) else ''
    if j is not None and status not in facturacion.ESTADOS_JOURNAL_ANULADO:
        return False, f'En Alegra el journal {a.journal_ref} sigue vigente. No se cambió nada.'
    motivo = 'anulado en Alegra' if j is not None else 'ya no existe en Alegra'
    # El journal puede llevar varios traslados: si se anula allá, todos dejan de contar.
    n = AjusteConciliacion.objects.filter(journal_ref=a.journal_ref, origen_empresa=a.origen_empresa_id, anulado=False,
                                          journal_estado=AjusteConciliacion.JOURNAL_ENVIADO).update(
        anulado=True, anulado_por=usuario, anulado_en=timezone.now(),
        journal_error=f'Journal {a.journal_ref} {motivo}.')
    if not n:
        raise AjusteError('El traslado cambió mientras se verificaba; recarga la página.')
    a.refresh_from_db()
    cuantos = f'{n} traslados quedaron anulados' if n > 1 else 'el traslado quedó anulado'
    return True, f'El journal {a.journal_ref} está {motivo}: {cuantos} aquí y deja(n) de contar.'


def marcar_manual(a, usuario, comprobante='', fecha=None):
    """Empresa sin Alegra: alguien confirma que ya registró el ajuste en su contabilidad. Desde ahí cuenta."""
    if a.anulado:
        raise AjusteError('El traslado está anulado.')
    if a.journal_estado != AjusteConciliacion.JOURNAL_PENDIENTE:
        raise AjusteError('El traslado ya no está pendiente.')
    if a.via_alegra:
        raise AjusteError(f'{a.origen_empresa.nombre} tiene Alegra: este traslado se envía a Alegra.')
    a.journal_estado = AjusteConciliacion.JOURNAL_MANUAL
    a.journal_ref = (comprobante or '').strip()[:100]
    a.fecha = fecha or a.fecha
    a.journal_error = ''
    a.enviado_en = timezone.now()
    a.enviado_por = usuario
    a.save(update_fields=['journal_estado', 'journal_ref', 'fecha', 'journal_error', 'enviado_en', 'enviado_por'])
    return a
