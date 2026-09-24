"""Radicacion, listado y ficha de PQRS (tabla legacy por proyecto + sidecar)."""
import datetime

from django.conf import settings
from django.core.files.storage import default_storage

from andinasoft.handlers_functions import upload_docs
from andinasoft.models import PqrsGestion, PqrsNota, proyectos as ProyectosModel, clientes
from andinasoft.shared_models import Pqrs, documentos_contratos, timeline, Vista_Adjudicacion, titulares_por_adj


TIPOS_PQRS = ('Peticion', 'Queja', 'Reclamo', 'Solicitud')
DIAS_VENCIMIENTO_DEFAULT = 15


def _as_date(value):
    if value is None:
        return None
    if isinstance(value, datetime.datetime):
        return value.date()
    if isinstance(value, datetime.date):
        return value
    text = str(value).strip()[:10]
    try:
        return datetime.date.fromisoformat(text)
    except ValueError:
        return None


def fecha_vencimiento_sugerida(fecha_rad, dias=DIAS_VENCIMIENTO_DEFAULT):
    fecha_rad = _as_date(fecha_rad) or datetime.date.today()
    return fecha_rad + datetime.timedelta(days=dias)


def doc_path(proyecto, adj, filename):
    if not filename:
        return ''
    return f'docs_andinasoft/doc_contratos/{proyecto}/{adj}/{filename}'


def doc_url(proyecto, adj, filename):
    path = doc_path(proyecto, adj, filename)
    if not path:
        return ''
    try:
        return default_storage.url(path)
    except Exception:
        media = getattr(settings, 'MEDIA_URL', '/media/') or '/media/'
        return f"{media.rstrip('/')}/{path.lstrip('/')}"


def _titular(proyecto, adj):
    try:
        row = titulares_por_adj.objects.using(proyecto).filter(adj=adj).first()
        if row:
            return row.titular1 or ''
    except Exception:
        pass
    return ''


def _cliente_id(proyecto, adj):
    try:
        row = titulares_por_adj.objects.using(proyecto).filter(adj=adj).first()
        if row:
            return row.IdTercero1 or ''
    except Exception:
        pass
    return ''


def plazo_info(fecha_vencimiento, estado, today=None):
    today = today or datetime.date.today()
    fecha = _as_date(fecha_vencimiento)
    cerrado = (estado or '') == 'Cerrado'
    if cerrado:
        return {'codigo': 'cerrado', 'label': 'Cerrado', 'dias': None}
    if not fecha:
        return {'codigo': 'sin_fecha', 'label': 'Sin plazo', 'dias': None}
    dias = (fecha - today).days
    if dias < 0:
        return {'codigo': 'vencida', 'label': f'Vencida ({abs(dias)} d)', 'dias': dias}
    if dias == 0:
        return {'codigo': 'hoy', 'label': 'Vence hoy', 'dias': 0}
    return {'codigo': 'ok', 'label': f'{dias} d', 'dias': dias}


def _ensure_proyecto(proyecto):
    obj, _ = ProyectosModel.objects.get_or_create(proyecto=proyecto, defaults={'activo': True})
    return obj


def gestion_map(proyecto, ids=None):
    qs = PqrsGestion.objects.filter(proyecto_id=proyecto)
    if ids is not None:
        qs = qs.filter(id_pqrs__in=list(ids))
    return {g.id_pqrs: g for g in qs}


def enriquecer_row(proyecto, rad, gestion=None, today=None):
    today = today or datetime.date.today()
    adj = rad.idadjudicacion or (gestion.adj if gestion else '') or ''
    plazo = plazo_info(rad.fecha_vencimiento, rad.estado, today=today)
    return {
        'id': rad.pk,
        'adj': adj,
        'titular': _titular(proyecto, adj) if adj else '',
        'cliente_id': _cliente_id(proyecto, adj) if adj else '',
        'tipo': rad.tipo or '',
        'estado': rad.estado or '',
        'fecha_radicado': _as_date(rad.fecha_radicado),
        'fecha_vencimiento': _as_date(rad.fecha_vencimiento),
        'fecha_respuesta': _as_date(rad.fecha_respuesta),
        'usuario_radica': rad.usuario_radica or '',
        'usuario_cierra': rad.usuario_cierra or '',
        'req_respuesta': rad.req_respuesta or '',
        'tipo_respuesta': rad.tipo_respuesta or '',
        'asunto': (gestion.asunto if gestion else '') or (rad.tipo or 'PQRS'),
        'resumen': (gestion.resumen if gestion else '') or '',
        'resumen_respuesta': (gestion.resumen_respuesta if gestion else '') or '',
        'origen': (gestion.origen if gestion else 'interno'),
        'canal': (gestion.canal if gestion else ''),
        'relevante_juridica': bool(gestion.relevante_juridica) if gestion else False,
        'plazo': plazo,
        'doc_peticion_url': doc_url(proyecto, adj, rad.doc_peticion),
        'doc_respuesta_url': doc_url(proyecto, adj, rad.doc_respuesta),
        'doc_envio_url': doc_url(proyecto, adj, rad.doc_envio),
        'doc_peticion': rad.doc_peticion or '',
        'doc_respuesta': rad.doc_respuesta or '',
        'doc_envio': rad.doc_envio or '',
    }


def listar_pqrs(proyecto, *, estado='', tipo='', vencimiento='', q='', juridica=False, today=None):
    today = today or datetime.date.today()
    rads_all = list(Pqrs.objects.using(proyecto).all().order_by('-id_pqrs'))
    gestiones = gestion_map(proyecto, [r.pk for r in rads_all])
    all_rows = [enriquecer_row(proyecto, r, gestiones.get(r.pk), today=today) for r in rads_all]
    rows = all_rows
    if estado:
        rows = [r for r in rows if r['estado'] == estado]
    if tipo:
        rows = [r for r in rows if r['tipo'] == tipo]
    if juridica:
        rows = [r for r in rows if r['relevante_juridica']]
    if vencimiento == 'hoy':
        rows = [r for r in rows if r['plazo']['codigo'] == 'hoy']
    elif vencimiento == 'vencidas':
        rows = [r for r in rows if r['plazo']['codigo'] == 'vencida']
    elif vencimiento == 'abiertas':
        rows = [r for r in rows if r['estado'] != 'Cerrado']
    q = (q or '').strip().lower()
    if q:
        rows = [
            r for r in rows
            if q in (r['asunto'] or '').lower()
            or q in (r['titular'] or '').lower()
            or q in str(r['id'])
            or q in (r['adj'] or '').lower()
        ]
    kpis = {
        'abiertas': sum(1 for r in all_rows if r['estado'] != 'Cerrado'),
        'hoy': sum(1 for r in all_rows if r['plazo']['codigo'] == 'hoy'),
        'vencidas': sum(1 for r in all_rows if r['plazo']['codigo'] == 'vencida'),
        'cerradas': sum(1 for r in all_rows if r['estado'] == 'Cerrado'),
        'juridica': sum(1 for r in all_rows if r['relevante_juridica'] and r['estado'] != 'Cerrado'),
        'total': len(all_rows),
    }
    return rows, kpis


def radicar_pqrs(
    proyecto,
    adj,
    *,
    tipo,
    asunto,
    fecha_rad,
    fecha_ven,
    req_respuesta,
    archivo,
    usuario,
    canal='',
    relevante_juridica=False,
    resumen='',
    origen='interno',
):
    tipo = (tipo or 'Solicitud').strip()
    asunto = (asunto or '').strip()
    if not asunto:
        raise ValueError('El asunto es obligatorio.')
    if not adj:
        raise ValueError('Indique la adjudicacion.')
    if not archivo:
        raise ValueError('Adjunte el PDF de la peticion.')
    fecha_rad = _as_date(fecha_rad) or datetime.date.today()
    fecha_ven = _as_date(fecha_ven) or fecha_vencimiento_sugerida(fecha_rad)
    nombre_archivo = f'{tipo}_{datetime.datetime.now()}'.replace(':', '.')
    rad = Pqrs.objects.using(proyecto).create(
        idadjudicacion=adj,
        estado='Abierta',
        tipo=tipo,
        fecha_radicado=fecha_rad,
        fecha_vencimiento=fecha_ven,
        req_respuesta=req_respuesta or 'Si',
        doc_peticion=nombre_archivo + '.pdf',
        usuario_radica=str(usuario),
    )
    ruta = f'{settings.DIR_DOCS}/doc_contratos/{proyecto}/{adj}/'
    upload_docs(archivo, ruta, nombre_archivo)
    documentos_contratos.objects.using(proyecto).create(
        adj=adj,
        descripcion_doc=nombre_archivo,
        fecha_carga=datetime.date.today(),
        usuario_carga=str(usuario),
    )
    timeline.objects.using(proyecto).create(
        adj=adj,
        fecha=datetime.date.today(),
        usuario=usuario,
        accion=f'Radico una {tipo} del {fecha_rad} (Radicado #{rad.pk})',
    )
    gestion = PqrsGestion.objects.create(
        proyecto=_ensure_proyecto(proyecto),
        id_pqrs=rad.pk,
        adj=adj,
        asunto=asunto,
        resumen=resumen or '',
        origen=origen or 'interno',
        canal=canal or '',
        relevante_juridica=bool(relevante_juridica),
    )
    PqrsNota.objects.create(
        gestion=gestion,
        usuario=str(usuario),
        comentario=f'Radicada. Asunto: {asunto}',
    )
    return rad, gestion


def cerrar_pqrs(
    proyecto,
    radicado_id,
    *,
    fecha_respuesta,
    medio,
    archivo_respuesta,
    archivo_envio,
    usuario,
    resumen_respuesta='',
):
    rad = Pqrs.objects.using(proyecto).get(pk=radicado_id)
    if rad.estado == 'Cerrado':
        raise ValueError('Esta PQRS ya esta cerrada.')
    adj = rad.idadjudicacion
    fecha_respuesta = _as_date(fecha_respuesta) or datetime.date.today()
    req = (rad.req_respuesta or 'Si').strip()
    if req != 'No' and not archivo_respuesta:
        raise ValueError('Adjunte el PDF de la respuesta.')
    if (medio or '') != 'Presencial' and req != 'No' and not archivo_envio:
        raise ValueError('Adjunte la constancia de envio.')
    if req != 'No' and not (resumen_respuesta or '').strip():
        raise ValueError('Escriba un resumen de la respuesta.')

    archivo_rta = f'Respuesta_{rad.tipo}_{datetime.datetime.now()}'.replace(':', '.')
    archivo_env = f'Constancia_Envio_Respuesta_{rad.tipo}_{datetime.datetime.now()}'.replace(':', '.')
    ruta = f'{settings.DIR_DOCS}/doc_contratos/{proyecto}/{adj}/'
    if archivo_respuesta:
        rad.doc_respuesta = archivo_rta + '.pdf'
        upload_docs(archivo_respuesta, ruta, archivo_rta)
        documentos_contratos.objects.using(proyecto).create(
            adj=adj, descripcion_doc=archivo_rta,
            fecha_carga=datetime.date.today(), usuario_carga=str(usuario),
        )
    if archivo_envio:
        rad.doc_envio = archivo_env + '.pdf'
        upload_docs(archivo_envio, ruta, archivo_env)
        documentos_contratos.objects.using(proyecto).create(
            adj=adj, descripcion_doc=archivo_env,
            fecha_carga=datetime.date.today(), usuario_carga=str(usuario),
        )
    rad.fecha_respuesta = fecha_respuesta
    rad.tipo_respuesta = medio or ''
    rad.estado = 'Cerrado'
    rad.usuario_cierra = str(usuario)
    rad.save()
    timeline.objects.using(proyecto).create(
        adj=adj,
        fecha=datetime.date.today(),
        usuario=usuario,
        accion=f'Cerro la {rad.tipo} #{rad.pk}',
    )
    gestion = PqrsGestion.objects.filter(proyecto_id=proyecto, id_pqrs=rad.pk).first()
    if gestion:
        gestion.resumen_respuesta = (resumen_respuesta or '').strip()
        gestion.save(update_fields=['resumen_respuesta', 'actualizado'])
        PqrsNota.objects.create(
            gestion=gestion,
            usuario=str(usuario),
            comentario='Cerrada. ' + (resumen_respuesta or '')[:400],
        )
    return rad


def agregar_nota(proyecto, radicado_id, usuario, comentario):
    comentario = (comentario or '').strip()
    if not comentario:
        raise ValueError('Escriba una nota.')
    gestion = PqrsGestion.objects.filter(proyecto_id=proyecto, id_pqrs=radicado_id).first()
    if not gestion:
        rad = Pqrs.objects.using(proyecto).get(pk=radicado_id)
        gestion = PqrsGestion.objects.create(
            proyecto=_ensure_proyecto(proyecto),
            id_pqrs=rad.pk,
            adj=rad.idadjudicacion or '',
            asunto=rad.tipo or 'PQRS',
            origen='interno',
        )
    return PqrsNota.objects.create(gestion=gestion, usuario=str(usuario), comentario=comentario)


def ficha_pqrs(proyecto, radicado_id, today=None):
    rad = Pqrs.objects.using(proyecto).get(pk=radicado_id)
    gestion = PqrsGestion.objects.filter(proyecto_id=proyecto, id_pqrs=rad.pk).first()
    row = enriquecer_row(proyecto, rad, gestion, today=today)
    notas = []
    if gestion:
        notas = list(gestion.notas.all())
    vista = None
    if row['adj']:
        vista = Vista_Adjudicacion.objects.using(proyecto).filter(IdAdjudicacion=row['adj']).first()
    row['inmueble'] = getattr(vista, 'Inmueble', None) if vista else ''
    row['estado_negocio'] = getattr(vista, 'Estado', None) if vista else ''
    row['notas'] = notas
    row['gestion'] = gestion
    return row


def pqrs_de_adj(proyecto, adj, today=None):
    rads = Pqrs.objects.using(proyecto).filter(idadjudicacion=adj).order_by('-id_pqrs')
    gestiones = gestion_map(proyecto, [r.pk for r in rads])
    return [enriquecer_row(proyecto, r, gestiones.get(r.pk), today=today) for r in rads]


def marcar_juridica(proyecto, radicado_id, relevante, usuario=''):
    rad = Pqrs.objects.using(proyecto).get(pk=radicado_id)
    gestion = PqrsGestion.objects.filter(proyecto_id=proyecto, id_pqrs=rad.pk).first()
    if not gestion:
        gestion = PqrsGestion.objects.create(
            proyecto=_ensure_proyecto(proyecto),
            id_pqrs=rad.pk,
            adj=rad.idadjudicacion or '',
            asunto=rad.tipo or 'PQRS',
            origen='interno',
        )
    gestion.relevante_juridica = bool(relevante)
    gestion.save(update_fields=['relevante_juridica', 'actualizado'])
    if usuario:
        PqrsNota.objects.create(
            gestion=gestion,
            usuario=str(usuario),
            comentario='Marcada como relevante para juridica' if relevante else 'Quitada de juridica',
        )
    return gestion
