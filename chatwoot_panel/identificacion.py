"""Quién es el contacto de Chatwoot en Andinasoft y qué negocios tiene.

Orden: cédula guardada en el contacto de Chatwoot → vínculo confirmado →
teléfono → búsqueda manual. Ver docs/plan_integracion_chatwoot.md §4.
"""
import logging

from django.db.models import Q

from andinasoft.models import Usuarios_Proyectos, clientes, proyectos
from andinasoft.shared_models import Vista_Adjudicacion, titulares_por_adj
from chatwoot_panel.models import ChatwootContactLink
from chatwoot_panel.telefonos import buscar_clientes

logger = logging.getLogger(__name__)

ATRIBUTO_CEDULA = 'cedula_andinasoft'


def proyectos_activos():
    return list(proyectos.objects.filter(activo=True).order_by('proyecto').values_list('proyecto', flat=True))


def proyectos_del_usuario(user):
    """Mismo criterio que views.check_project: superusuario todos; si no, su asignación."""
    activos = proyectos_activos()
    if user.is_superuser:
        return activos
    asignacion = Usuarios_Proyectos.objects.filter(usuario=user).first()
    if asignacion is None:
        return []
    propios = set(asignacion.proyecto.values_list('proyecto', flat=True))
    return [p for p in activos if p in propios]


def puede_ver_proyecto(user, proyecto):
    return proyecto in proyectos_del_usuario(user)


def enmascarar(cedula):
    cedula = str(cedula or '')
    return ('•••' + cedula[-4:]) if len(cedula) > 4 else cedula


def _cliente(cedula):
    obj = clientes.objects.filter(pk=cedula).values('idTercero', 'nombrecompleto').first()
    if not obj:
        return None
    return {'cedula': obj['idTercero'], 'nombre': (obj['nombrecompleto'] or '').strip()}


def negocios_de(cedulas, proyectos_a_revisar):
    """Negocios (adjudicaciones) donde alguna de las cédulas es titular.

    Una consulta de titulares y una de resumen por proyecto.
    """
    cedulas = [str(c).strip() for c in cedulas if c]
    if not cedulas:
        return []
    filtro = Q(IdTercero1__in=cedulas) | Q(IdTercero2__in=cedulas) | Q(IdTercero3__in=cedulas) | Q(IdTercero4__in=cedulas)
    negocios = []
    for proyecto in proyectos_a_revisar:
        try:
            relaciones = list(titulares_por_adj.objects.using(proyecto).filter(filtro))
            if not relaciones:
                continue
            ids = [r.adj.strip() for r in relaciones if r.adj]
            resumen = {v.IdAdjudicacion: v for v in Vista_Adjudicacion.objects.using(proyecto).filter(IdAdjudicacion__in=ids)}
        except Exception:
            logger.exception('chatwoot_panel: no se pudieron leer negocios de %s', proyecto)
            continue
        for r in relaciones:
            adj = (r.adj or '').strip()
            v = resumen.get(adj)
            if not adj or v is None:
                continue
            titulares = [
                {'cedula': str(c).strip(), 'nombre': (n or '').strip()}
                for c, n in ((r.IdTercero1, r.titular1), (r.IdTercero2, r.titular2),
                             (r.IdTercero3, r.titular3), (r.IdTercero4, r.titular4))
                if c and str(c).strip()
            ]
            negocios.append({
                'proyecto': proyecto,
                'adj': adj,
                'inmueble': v.Inmueble or '',
                'estado': v.Estado or '',
                'valor': v.Valor,
                'titulares': titulares,
            })
    negocios.sort(key=lambda n: (n['proyecto'], n['adj']))
    return negocios


def _cedulas_de(negocio):
    return {t['cedula'] for t in negocio['titulares']}


def _un_solo_grupo(candidatos, negocios):
    """True si todos los candidatos están unidos por negocios en común (cotitulares)."""
    if len(candidatos) <= 1:
        return True
    cedulas = [c['cedula'] for c in candidatos]
    grupo = {cedulas[0]}
    cambio = True
    while cambio:
        cambio = False
        for n in negocios:
            titulares = _cedulas_de(n) & set(cedulas)
            if titulares & grupo and not titulares <= grupo:
                grupo |= titulares
                cambio = True
    return grupo == set(cedulas)


def _respuesta(user, estado, cliente=None, negocios=None, candidatos=None, avisos=None, via=''):
    propios = set(proyectos_del_usuario(user))
    negocios = negocios or []
    visibles = [n for n in negocios if n['proyecto'] in propios]
    return {
        'estado': estado,
        'via': via,
        'cliente': cliente,
        'negocios': visibles,
        'negocios_otros_proyectos': len(negocios) - len(visibles),
        'candidatos': candidatos or [],
        'avisos': avisos or [],
    }


def _candidato(c, negocios):
    propios = [n for n in negocios if c['cedula'] in _cedulas_de(n)]
    return {
        'cedula': c['cedula'],
        'cedula_mask': enmascarar(c['cedula']),
        'nombre': c['nombre'],
        'negocios': len(propios),
        'proyectos': sorted({n['proyecto'] for n in propios}),
        'posible': c.get('posible', False),
    }


def resolver_cliente(user, cedula):
    """Cliente elegido explícitamente (vínculo, atributo o selección del agente)."""
    cliente = _cliente(cedula)
    if cliente is None:
        return None
    return cliente, negocios_de([cliente['cedula']], proyectos_activos())


def resolver_contexto(user, *, account_id='', contact_id='', telefono='', cedula_atributo='', cedula=''):
    """Identifica al cliente del contacto de Chatwoot."""
    if cedula:
        r = resolver_cliente(user, cedula)
        if r:
            return _respuesta(user, 'seleccionado', r[0], r[1], via='seleccion')

    if cedula_atributo:
        r = resolver_cliente(user, cedula_atributo)
        if r:
            return _respuesta(user, 'identificado', r[0], r[1], via='atributo')

    if account_id and contact_id:
        link = ChatwootContactLink.objects.filter(
            chatwoot_account_id=str(account_id), chatwoot_contact_id=str(contact_id),
        ).first()
        if link:
            r = resolver_cliente(user, link.cliente_id)
            if r:
                return _respuesta(user, 'identificado', r[0], r[1], via='vinculo')

    if not telefono:
        return _respuesta(user, 'ninguno', avisos=['El contacto no tiene teléfono en Chatwoot.'])

    titulares, conyuges, es_asesor = buscar_clientes(telefono)
    avisos = []
    if es_asesor:
        avisos.append('Este número está registrado como teléfono de un asesor.')

    negocios = negocios_de([c['cedula'] for c in titulares], proyectos_activos()) if titulares else []
    con_negocio = [c for c in titulares if any(c['cedula'] in _cedulas_de(n) for n in negocios)]

    if not con_negocio:
        if titulares:
            avisos.append('El teléfono coincide con clientes que no tienen negocios.')
        conyuge_negocios = negocios_de([c['cedula'] for c in conyuges], proyectos_activos()) if conyuges else []
        candidatos = [_candidato(c, conyuge_negocios) for c in conyuges]
        candidatos = [c for c in candidatos if c['negocios']]
        for c in candidatos:
            c['motivo'] = 'El teléfono es del cónyuge registrado de este cliente.'
        return _respuesta(user, 'varias' if candidatos else 'ninguno', candidatos=candidatos, avisos=avisos)

    posible = all(c.get('posible') for c in con_negocio)
    if _un_solo_grupo(con_negocio, negocios) and not es_asesor and not posible:
        principal = con_negocio[0]
        nombre = ' y '.join(c['nombre'] for c in con_negocio) if len(con_negocio) > 1 else principal['nombre']
        cliente = {'cedula': principal['cedula'], 'nombre': nombre}
        return _respuesta(user, 'sugerido', cliente, negocios, via='telefono', avisos=avisos)

    candidatos = [_candidato(c, negocios) for c in con_negocio]
    if posible:
        avisos.append('Coincidencia solo por el número nacional (indicativo extranjero): confirma el cliente.')
    return _respuesta(user, 'varias', candidatos=candidatos, avisos=avisos)


def buscar_manual(user, texto, limite=10):
    """Búsqueda por cédula o nombre; solo devuelve clientes con negocios."""
    texto = (texto or '').strip()
    if len(texto) < 3:
        return []
    digitos = ''.join(ch for ch in texto if ch.isdigit())
    if digitos and len(digitos) >= len(texto.replace(' ', '').replace('.', '').replace('-', '')) - 4:
        ids = list(
            clientes.objects.filter(Q(idTercero=texto) | Q(idTercero=digitos) | Q(idTercero__endswith='-' + digitos))
            .values_list('idTercero', flat=True)[:30]
        )
    else:
        from mcp_server.tools.adjudicaciones import _find_clientes_por_nombre

        ids = _find_clientes_por_nombre(texto)[:30]
    if not ids:
        return []
    nombres = dict(clientes.objects.filter(pk__in=ids).values_list('idTercero', 'nombrecompleto'))
    negocios = negocios_de(ids, proyectos_activos())
    candidatos = [_candidato({'cedula': i, 'nombre': (nombres.get(i) or '').strip()}, negocios) for i in ids]
    return [c for c in candidatos if c['negocios']][:limite]
