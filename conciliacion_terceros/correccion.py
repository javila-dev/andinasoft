"""
Corrección de la identificación de un tercero (cédula/NIT mal digitada en Andinasoft o en Alegra).

En Andinasoft la identificación es la llave de `clientes` y se repite como texto (sin llave foránea) en la
base principal y en la base de cada proyecto. La corrección:
- renombra el cliente si el Id correcto no existe, o lo fusiona con el existente (se conservan los datos del
  correcto y se completan sus campos vacíos con los del errado);
- reemplaza el Id en todas las tablas que lo guardan;
- deja registro de cada fila cambiada (`CorreccionIdentificacion.detalle`) para poder revertir.
No hay transacción que abarque las 12 bases: cada base se hace en su propia transacción y el registro
permite revertir lo aplicado si algo falla a mitad de camino.

En Alegra (empresas con integración) la identificación del contacto se corrige con PUT /contacts/{id}.
Si ya existen los dos contactos, no hay fusión en Alegra: se registra el traslado del saldo como ajuste.
"""
import logging

from django.conf import settings
from django.db import connections, transaction
from django.forms.models import model_to_dict
from django.utils import timezone

from andinasoft.models import Novacion, Peticiones, clientes, empresas, proyectos, sagrilaft_info
from andinasoft.shared_models import Adjudicacion, Recaudos_general, timeline, ventas_nuevas
from conciliacion_terceros.parser import norm_ident

logger = logging.getLogger(__name__)

# Columnas de proyecto con longitud limitada.
LIMITES = {('adjudicacion', 'idtercero1'): 12, ('adjudicacion', 'idtercero2'): 12, ('recaudos_general', 'idtercero'): 12}
NIT_PESOS = [3, 7, 13, 17, 19, 23, 29, 37, 41, 43, 47, 53, 59, 67, 71]


class CorreccionError(Exception):
    pass


def digito_verificacion(nit):
    """Dígito de verificación DIAN de un NIT (sin DV)."""
    digitos = [int(d) for d in str(nit) if d.isdigit()][::-1]
    total = sum(d * NIT_PESOS[i] for i, d in enumerate(digitos) if i < len(NIT_PESOS))
    r = total % 11
    return r if r in (0, 1) else 11 - r


def sugerir_sin_dv(ident):
    """Si el Id parece un NIT con el dígito de verificación pegado, devuelve el NIT sin DV."""
    ident = norm_ident(ident)
    if ident.isdigit() and len(ident) == 10 and ident[0] in '89':
        base = ident[:-1]
        if digito_verificacion(base) == int(ident[-1]):
            return base
    return ''


def _proyectos():
    out = []
    for p in proyectos.objects.order_by('proyecto').values_list('pk', flat=True):
        if p not in settings.DATABASES:
            continue
        try:
            if 'adjudicacion' in connections[p].introspection.table_names():
                out.append(p)
        except Exception:
            continue
    return out


def _cliente_info(ident):
    c = clientes.objects.filter(pk=ident).first()
    return {'existe': bool(c), 'nombre': c.nombrecompleto if c else '', 'sagrilaft': sagrilaft_info.objects.filter(pk=ident).exists()}


# ---------------------------------------------------------------------------
# Vista previa
# ---------------------------------------------------------------------------

def vista_previa(errado, correcto):
    errado, correcto = norm_ident(errado), norm_ident(correcto)
    if not errado or not correcto or errado == correcto:
        raise CorreccionError('Indica un Id errado y un Id correcto distintos.')
    origen, destino = _cliente_info(errado), _cliente_info(correcto)
    prev = {
        'errado': errado, 'correcto': correcto,
        'cliente_errado': origen, 'cliente_correcto': destino,
        'modo': 'fusionar' if destino['existe'] else 'renombrar',
        'principal': [], 'proyectos': [], 'avisos': [], 'alegra': [],
    }
    if not origen['existe']:
        prev['avisos'].append(f'{errado} no existe como cliente en Andinasoft: solo se cambiarán las tablas que lo usen.')
    if destino['existe'] and origen['sagrilaft'] and destino['sagrilaft']:
        prev['avisos'].append('Ambos tienen SARLAFT: se conserva el del Id correcto.')

    def add(tabla, n, nota=''):
        if n:
            prev['principal'].append({'tabla': tabla, 'registros': n, 'nota': nota})
    add('Cliente (andinasoft_clientes)', 1 if origen['existe'] else 0,
        'se fusiona con el correcto' if destino['existe'] else 'se renombra')
    add('SARLAFT', 1 if origen['sagrilaft'] else 0)
    from crm.models import ActaReunion
    from chatwoot_panel.models import ChatwootContactLink
    from alegra_integration.models import AlegraMapping
    add('Actas de reunión (CRM)', ActaReunion.objects.filter(cliente_id=errado).count())
    add('Vínculos Chatwoot', ChatwootContactLink.objects.filter(cliente_id=errado).count())
    add('Novaciones', Novacion.objects.filter(titular=errado).count())
    try:
        add('Radicados (Peticiones)', Peticiones.objects.filter(idcliente=errado).count())
    except Exception:
        pass
    add('Mapeos Alegra (contacto local)', AlegraMapping.objects.filter(
        mapping_type=AlegraMapping.CONTACT, local_model__in=('andinasoft.clientes', 'andinasoft.terceros_raw'), local_pk=errado).count())

    for p in _proyectos():
        fila = {'proyecto': p, 'adjudicaciones': 0, 'ventas': 0, 'recibos': 0}
        for col in ('idtercero1', 'idtercero2', 'idtercero3', 'idtercero4'):
            n = Adjudicacion.objects.using(p).filter(**{col: errado}).count()
            fila['adjudicaciones'] += n
            if n and len(correcto) > LIMITES.get(('adjudicacion', col), 255):
                prev['avisos'].append(f'{p}: el Id correcto tiene {len(correcto)} caracteres y la columna {col} admite {LIMITES[("adjudicacion", col)]}.')
        for col in ('id_t1', 'id_t2', 'id_t3', 'id_t4'):
            fila['ventas'] += ventas_nuevas.objects.using(p).filter(**{col: errado}).count()
        fila['recibos'] = Recaudos_general.objects.using(p).filter(idtercero=errado).count()
        if fila['recibos'] and len(correcto) > 12:
            prev['avisos'].append(f'{p}: el Id correcto no cabe en recaudos_general.IdTercero (12 caracteres).')
        if fila['adjudicaciones'] or fila['ventas'] or fila['recibos']:
            prev['proyectos'].append(fila)
    prev['alegra'] = _vista_previa_alegra(errado, correcto)
    prev['bloqueado'] = any('admite' in a or 'no cabe' in a for a in prev['avisos'])
    return prev


def _buscar_contactos(client, ident):
    """Contactos de Alegra cuya identificación (sin DV) coincide exactamente con ident."""
    import requests
    out = []
    try:
        res = client.rest('GET', f'/contacts?identification={requests.utils.quote(ident)}&limit=30')
    except Exception as exc:
        raise CorreccionError(f'No se pudo consultar Alegra: {exc}')
    data = res.get('data') if isinstance(res, dict) else res
    for c in data or []:
        ident_c = c.get('identification')
        if isinstance(ident_c, dict):
            ident_c = ident_c.get('number')
        num = norm_ident(ident_c or (c.get('identificationObject') or {}).get('number'))
        if num == ident:
            out.append({'id': str(c.get('id')), 'nombre': c.get('name') or '', 'identificacion': num})
    return out


def _vista_previa_alegra(errado, correcto):
    from alegra_integration.client import AlegraMCPClient

    out = []
    for emp in empresas.objects.filter(alegra_enabled=True).order_by('nombre'):
        fila = {'empresa': emp.pk, 'empresa_nombre': emp.nombre, 'errado': [], 'correcto': [], 'accion': 'nada', 'error': ''}
        try:
            client = AlegraMCPClient(emp, timeout=30)
            fila['errado'] = _buscar_contactos(client, errado)
            fila['correcto'] = _buscar_contactos(client, correcto)
        except Exception as exc:
            fila['error'] = str(exc)
            out.append(fila)
            continue
        if len(fila['errado']) > 1:
            fila['accion'] = 'revisar'
            fila['error'] = 'Hay varios contactos con el Id errado; corrígelos manualmente en Alegra.'
        elif fila['errado'] and not fila['correcto']:
            fila['accion'] = 'corregir_contacto'
        elif fila['errado'] and fila['correcto']:
            fila['accion'] = 'trasladar_saldo'
        out.append(fila)
    return out


# ---------------------------------------------------------------------------
# Ejecución
# ---------------------------------------------------------------------------

def ejecutar(registro, prev, empresas_alegra, user):
    """Aplica la corrección en Andinasoft y, para las empresas indicadas, en Alegra. Llena `registro`."""
    errado, correcto = prev['errado'], prev['correcto']
    detalle = {'principal': [], 'proyectos': {}, 'cliente_errado': None, 'cliente_correcto_antes': None, 'sagrilaft': None}
    registro.detalle = detalle
    try:
        _ejecutar_principal(errado, correcto, detalle)
        for p in _proyectos():
            _ejecutar_proyecto(p, errado, correcto, detalle, user, registro)
        registro.estado = registro.ESTADO_EJECUTADA
    except Exception as exc:
        logger.exception('Corrección de identificación %s -> %s falló', errado, correcto)
        registro.estado = registro.ESTADO_PARCIAL
        registro.error = f'Andinasoft: {exc}'
    registro.alegra = []
    if registro.estado == registro.ESTADO_EJECUTADA:
        for fila in prev.get('alegra', []):
            if fila['empresa'] not in empresas_alegra:
                continue
            registro.alegra.append(_ejecutar_alegra(fila, errado, correcto, registro))
        if any(a.get('estado') == 'error' for a in registro.alegra):
            registro.error = (registro.error + ' ' if registro.error else '') + 'Alegra: revisa el detalle por empresa.'
    registro.save()
    return registro


def _ejecutar_principal(errado, correcto, detalle):
    from crm.models import ActaReunion
    from chatwoot_panel.models import ChatwootContactLink
    from alegra_integration.models import AlegraMapping

    with transaction.atomic(using='default'):
        origen = clientes.objects.filter(pk=errado).first()
        destino = clientes.objects.filter(pk=correcto).first()
        if origen:
            detalle['cliente_errado'] = model_to_dict(origen)
        if destino:
            detalle['cliente_correcto_antes'] = model_to_dict(destino)

        if origen and not destino:
            datos = model_to_dict(origen)
            datos.pop('idTercero', None)
            for fk in ('pais', 'estado', 'city'):
                if fk in datos:
                    datos[f'{fk}_id'] = datos.pop(fk)
            clientes.objects.create(idTercero=correcto, **datos)
        elif origen and destino:
            cambios = []
            for f in clientes._meta.concrete_fields:
                if f.primary_key:
                    continue
                if getattr(destino, f.attname) in (None, '') and getattr(origen, f.attname) not in (None, ''):
                    setattr(destino, f.attname, getattr(origen, f.attname))
                    cambios.append(f.attname)
            if cambios:
                destino.save(update_fields=cambios)

        sag = sagrilaft_info.objects.filter(pk=errado).first()
        if sag:
            detalle['sagrilaft'] = model_to_dict(sag)
            if not sagrilaft_info.objects.filter(pk=correcto).exists():
                detalle['sagrilaft_movido'] = True
                datos = model_to_dict(sag)
                datos.pop('cliente', None)
                if 'codigo_ciuu' in datos:
                    datos['codigo_ciuu_id'] = datos.pop('codigo_ciuu')
                sagrilaft_info.objects.create(cliente_id=correcto, **datos)
            sag.delete()

        def mover(nombre, qs, campo):
            pks = list(qs.values_list('pk', flat=True))
            if pks:
                qs.model.objects.filter(pk__in=pks).update(**{campo: correcto})
                detalle['principal'].append({'tabla': nombre, 'modelo': qs.model._meta.label, 'campo': campo, 'pks': [str(x) for x in pks]})

        mover('Actas de reunión', ActaReunion.objects.filter(cliente_id=errado), 'cliente_id')
        mover('Vínculos Chatwoot', ChatwootContactLink.objects.filter(cliente_id=errado), 'cliente_id')
        mover('Novaciones', Novacion.objects.filter(titular=errado), 'titular')
        try:
            mover('Radicados', Peticiones.objects.filter(idcliente=errado), 'idcliente')
        except Exception:
            pass
        mover('Mapeos Alegra', AlegraMapping.objects.filter(
            mapping_type=AlegraMapping.CONTACT, local_model__in=('andinasoft.clientes', 'andinasoft.terceros_raw'), local_pk=errado), 'local_pk')

        if origen:
            clientes.objects.filter(pk=errado).delete()


def _ejecutar_proyecto(p, errado, correcto, detalle, user, registro):
    cambios = []
    with transaction.atomic(using=p):
        for col in ('idtercero1', 'idtercero2', 'idtercero3', 'idtercero4'):
            pks = list(Adjudicacion.objects.using(p).filter(**{col: errado}).values_list('pk', flat=True))
            if pks:
                Adjudicacion.objects.using(p).filter(pk__in=pks).update(**{col: correcto})
                cambios.append({'tabla': 'adjudicacion', 'campo': col, 'pks': pks})
        for col in ('id_t1', 'id_t2', 'id_t3', 'id_t4'):
            pks = list(ventas_nuevas.objects.using(p).filter(**{col: errado}).values_list('pk', flat=True))
            if pks:
                ventas_nuevas.objects.using(p).filter(pk__in=pks).update(**{col: correcto})
                cambios.append({'tabla': 'nuevas_ventas', 'campo': col, 'pks': pks})
        pks = list(Recaudos_general.objects.using(p).filter(idtercero=errado).values_list('pk', flat=True))
        if pks:
            Recaudos_general.objects.using(p).filter(pk__in=pks).update(idtercero=correcto)
            cambios.append({'tabla': 'recaudos_general', 'campo': 'idtercero', 'pks': pks})
    if cambios:
        detalle['proyectos'][p] = cambios
        # timeline_adj es MyISAM: se escribe fuera de la transacción y no se revierte.
        adjs = sorted({pk for c in cambios if c['tabla'] == 'adjudicacion' for pk in c['pks']})
        usuario = (getattr(user, 'username', '') or '')[:12]
        for adj in adjs:
            try:
                timeline.objects.using(p).create(
                    adj=adj, fecha=timezone.localdate(), usuario=usuario,
                    accion=f'Corrección de identificación de titular {errado} -> {correcto} (registro {registro.pk})'[:255],
                )
            except Exception:
                logger.warning('No se pudo escribir timeline para %s %s', p, adj)


def _payload_contacto(contacto, correcto):
    """Payload de PUT /contacts con la identificación corregida (se reenvían los datos principales)."""
    ident = contacto.get('identificationObject') or {}
    tipo = ident.get('type') or ('NIT' if contacto.get('kindOfPerson') == 'LEGAL_ENTITY' else 'CC')
    nuevo = {'type': tipo, 'number': correcto}
    if tipo == 'NIT':
        nuevo['dv'] = str(digito_verificacion(correcto))
    payload = {'identificationObject': nuevo}
    for k in ('name', 'nameObject', 'kindOfPerson', 'regime', 'type', 'email', 'phonePrimary', 'mobile', 'address'):
        if contacto.get(k) not in (None, '', {}, []):
            payload[k] = contacto[k]
    return payload


def _ejecutar_alegra(fila, errado, correcto, registro):
    from alegra_integration.client import AlegraMCPClient
    from alegra_integration.models import AlegraContactIndex

    res = {'empresa': fila['empresa'], 'empresa_nombre': fila['empresa_nombre'], 'accion': fila['accion'], 'estado': 'omitido', 'mensaje': ''}
    if fila['accion'] == 'corregir_contacto':
        contacto_id = fila['errado'][0]['id']
        try:
            client = AlegraMCPClient(empresas.objects.get(pk=fila['empresa']), timeout=60)
            contacto = client.get_contact(contacto_id)
            payload = _payload_contacto(contacto, correcto)
            client.rest('PUT', f'/contacts/{contacto_id}', json_payload=payload)
            AlegraContactIndex.objects.filter(empresa_id=fila['empresa'], alegra_id=contacto_id).update(identification=correcto)
            res.update(estado='ok', mensaje=f'Contacto {contacto_id} actualizado a {correcto}.', contacto_id=contacto_id, antes=errado)
        except Exception as exc:
            res.update(estado='error', mensaje=str(exc))
    elif fila['accion'] == 'trasladar_saldo':
        res.update(estado='pendiente', mensaje='Existen los dos contactos en Alegra: traslada el saldo con un ajuste entre terceros (queda para journal).')
    elif fila['accion'] == 'revisar':
        res.update(estado='error', mensaje=fila.get('error') or 'Revisar manualmente.')
    else:
        res.update(mensaje='El Id errado no existe en esta empresa.')
    return res


# ---------------------------------------------------------------------------
# Reversión (solo Andinasoft)
# ---------------------------------------------------------------------------

def revertir(registro):
    d = registro.detalle or {}
    errado, correcto = registro.id_errado, registro.id_correcto
    for p, cambios in (d.get('proyectos') or {}).items():
        with transaction.atomic(using=p):
            for c in cambios:
                modelo = {'adjudicacion': Adjudicacion, 'nuevas_ventas': ventas_nuevas, 'recaudos_general': Recaudos_general}[c['tabla']]
                modelo.objects.using(p).filter(pk__in=c['pks'], **{c['campo']: correcto}).update(**{c['campo']: errado})
    from django.apps import apps
    with transaction.atomic(using='default'):
        for c in d.get('principal') or []:
            modelo = apps.get_model(c['modelo'])
            modelo.objects.filter(pk__in=c['pks']).update(**{c['campo']: errado})
        if d.get('cliente_errado'):
            datos = dict(d['cliente_errado'])
            datos.pop('idTercero', None)
            for fk in ('pais', 'estado', 'city'):
                if fk in datos:
                    datos[f'{fk}_id'] = datos.pop(fk)
            clientes.objects.update_or_create(idTercero=errado, defaults=datos)
        if d.get('cliente_correcto_antes'):
            antes = dict(d['cliente_correcto_antes'])
            antes.pop('idTercero', None)
            for fk in ('pais', 'estado', 'city'):
                if fk in antes:
                    antes[f'{fk}_id'] = antes.pop(fk)
            clientes.objects.filter(pk=correcto).update(**antes)
        elif d.get('cliente_errado'):
            # El correcto se creó con la corrección: se elimina si nada más lo usa.
            sagrilaft_info.objects.filter(pk=correcto).delete()
            clientes.objects.filter(pk=correcto).delete()
        if d.get('sagrilaft'):
            if d.get('sagrilaft_movido'):
                sagrilaft_info.objects.filter(pk=correcto).delete()
            datos = dict(d['sagrilaft'])
            datos.pop('cliente', None)
            if 'codigo_ciuu' in datos:
                datos['codigo_ciuu_id'] = datos.pop('codigo_ciuu')
            sagrilaft_info.objects.update_or_create(cliente_id=errado, defaults=datos)
    registro.estado = registro.ESTADO_REVERTIDA
    registro.revertido_en = timezone.now()
    registro.save(update_fields=['estado', 'revertido_en'])
