"""Vistas de novaciones: registro desde una ADJ, documentacion, bandeja y aprobacion."""
from decimal import ROUND_DOWN, Decimal

from django import forms
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.core.validators import FileExtensionValidator
from django.http import Http404, JsonResponse
from django.shortcuts import redirect, render

from andina.decorators import check_project, group_perm_required
from andinasoft.adjudicacion_service import total_cuota_inicial
from andinasoft.cartera_gestor_service import listar_gestores_opciones
from andinasoft.forms import form_revision_op
from andinasoft.models import Novacion, clientes, empresas, proyectos
from andinasoft.novaciones_service import (
    COMPONENTES,
    DOCUMENTOS,
    NovacionError,
    aprobar,
    cambiar_aprobador,
    candidatos_aprobador,
    cargar_documento,
    checklist,
    crear_solicitud,
    devolver,
    documentos_cargados,
    eliminar_documento,
    enviar_a_aprobacion,
    novacion_pendiente_origen,
    pagado_por_componente,
    puede_gestionar,
    puede_resolver,
    rechazar,
    registrar_fechas_promesa,
    registrar_nota,
    ventas_destino_disponibles,
)
from andinasoft.shared_models import Adjudicacion, Inmuebles, ventas_nuevas

SOLO_PDF = [FileExtensionValidator(allowed_extensions=['pdf'])]


class NovacionSolicitudForm(forms.Form):
    proyecto_destino = forms.ChoiceField(label='Proyecto destino')
    venta_destino = forms.IntegerField(label='Venta destino')
    capital = forms.DecimalField(required=False, min_value=0, decimal_places=2, max_digits=16)
    interes_cte = forms.DecimalField(required=False, min_value=0, decimal_places=2, max_digits=16)
    interes_mora = forms.DecimalField(required=False, min_value=0, decimal_places=2, max_digits=16)
    aprobador = forms.ChoiceField(label='Quién revisa y aprueba')
    observaciones = forms.CharField(required=False, widget=forms.Textarea(attrs={'rows': 2}))

    def __init__(self, *args, proyectos_destino=(), aprobadores=(), **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['proyecto_destino'].choices = [(p, p) for p in proyectos_destino]
        self._aprobadores = {str(u.pk): u for u in aprobadores}
        self.fields['aprobador'].choices = [(str(u.pk), _etiqueta_usuario(u)) for u in aprobadores]

    def clean_aprobador(self):
        return self._aprobadores[self.cleaned_data['aprobador']]


class NovacionNotaForm(forms.Form):
    nro_nota = forms.CharField(max_length=12, label='Número de nota')
    fecha_nota = forms.DateField(label='Fecha')
    empresa_nota = forms.ModelChoiceField(queryset=empresas.objects.all().order_by('nombre'), label='Empresa')
    soporte = forms.FileField(required=False, label='PDF de la nota', validators=SOLO_PDF)


class NovacionFechasPromesaForm(forms.Form):
    fecha_entrega = forms.DateField(label='Fecha de entrega')
    fecha_escritura = forms.DateField(label='Fecha de escritura')


class NovacionDocumentoForm(forms.Form):
    tipo = forms.ChoiceField(choices=[(tipo, etiqueta) for tipo, etiqueta, _ in DOCUMENTOS])
    archivo = forms.FileField(label='PDF firmado', validators=SOLO_PDF)


class NovacionAprobacionForm(forms.Form):
    oficina = forms.ChoiceField(choices=form_revision_op.oficinas)
    gestor_cartera = forms.ChoiceField(choices=(), label='Asignar a cartera')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['gestor_cartera'].choices = listar_gestores_opciones(include_fijos=False)


def _proyectos_usuario(request):
    return [
        p.proyecto for p in proyectos.objects.filter(activo=True).order_by('proyecto')
        if check_project(request, p.proyecto, raise_exception=False)
    ]


def _etiqueta_usuario(user):
    nombre = (user.get_full_name() or '').strip()
    return f'{nombre} ({user.username})' if nombre else user.username


def _entero(valor):
    return str(int(Decimal(valor or 0).to_integral_value(rounding=ROUND_DOWN)))


def _nombre_cliente(id_tercero):
    if not id_tercero:
        return ''
    cliente = clientes.objects.filter(pk=id_tercero).first()
    return cliente.nombrecompleto if cliente else id_tercero


@group_perm_required(('andinasoft.view_novacion',), raise_exception=True)
def novaciones_lista(request):
    """Bandeja: todas las novaciones visibles; busqueda, filtros y paginacion van en el navegador."""
    qs = Novacion.objects.select_related('usuario_solicita', 'aprobador').order_by('-fecha_solicitud')
    if not request.user.is_superuser:
        qs = qs.filter(proyecto_origen_id__in=_proyectos_usuario(request))
    rows = list(qs)
    nombres = {
        c.pk: c.nombrecompleto
        for c in clientes.objects.filter(pk__in={n.titular for n in rows})
    }
    for n in rows:
        n.nombre_titular = nombres.get(n.titular, n.titular)
    por_revisar = sum(
        1 for n in rows if n.aprobador_id == request.user.pk and n.estado == Novacion.ESTADO_POR_APROBAR
    )
    return render(request, 'novaciones/lista.html', {
        'rows': rows,
        'estados': Novacion.ESTADO_CHOICES,
        'proyectos': sorted({n.proyecto_origen_id for n in rows} | {n.proyecto_destino_id for n in rows}),
        'por_revisar': por_revisar,
    })


@group_perm_required(('andinasoft.add_novacion',), raise_exception=True)
def novacion_nueva(request, proyecto, adj):
    check_project(request, proyecto)
    try:
        obj_adj = Adjudicacion.objects.using(proyecto).get(idadjudicacion=adj)
    except Adjudicacion.DoesNotExist:
        raise Http404('Adjudicación no encontrada')
    pendiente = novacion_pendiente_origen(proyecto, adj)
    if pendiente:
        messages.info(request, f'{adj} ya tiene la novación #{pendiente.pk} en curso.')
        return redirect('novacion detalle', pk=pendiente.pk)

    destinos = _proyectos_usuario(request)
    # Al volver de crear la venta destino en Nueva venta llegan proyecto y venta por la URL.
    inicial = {
        'proyecto_destino': request.GET.get('proyecto_destino') or '',
        'venta_destino': request.GET.get('venta') or '',
    }
    aprobadores = candidatos_aprobador(proyecto)
    form = NovacionSolicitudForm(
        request.POST or None, proyectos_destino=destinos, aprobadores=aprobadores, initial=inicial,
    )
    if request.method == 'POST' and form.is_valid():
        data = form.cleaned_data
        check_project(request, data['proyecto_destino'])
        try:
            novacion = crear_solicitud(
                usuario=request.user,
                proyecto_origen=proyecto,
                adj_origen=adj,
                proyecto_destino=data['proyecto_destino'],
                venta_id=data['venta_destino'],
                capital=data['capital'],
                interes_cte=data['interes_cte'],
                interes_mora=data['interes_mora'],
                aprobador=data['aprobador'],
                observaciones=data['observaciones'],
            )
        except NovacionError as exc:
            form.add_error(None, str(exc))
        else:
            messages.success(
                request,
                f'Novación #{novacion.pk} registrada. Ahora carga la nota contable y los documentos firmados.',
            )
            return redirect('novacion detalle', pk=novacion.pk)

    pagado = pagado_por_componente(proyecto, adj)
    componentes = [
        {
            'key': key,
            'label': label,
            'pagado': pagado[key],
            # Enteros sin formato para el input; hacia abajo para no pasar de lo pagado.
            'pagado_input': _entero(pagado[key]),
            'valor': (form[key].value() or '') if form.is_bound else _entero(pagado[key]),
            'marcado': (form[key].value() not in (None, '', '0')) if form.is_bound else True,
            'errores': form.errors.get(key, []),
        }
        for key, label in COMPONENTES
    ]
    return render(request, 'novaciones/nueva.html', {
        'proyecto': proyecto,
        'adj': adj,
        'obj_adj': obj_adj,
        'nombre_titular': _nombre_cliente(obj_adj.idtercero1),
        'componentes': componentes,
        'total_pagado': sum(pagado.values()),
        'form': form,
        'aprobadores': [(str(u.pk), _etiqueta_usuario(u)) for u in aprobadores],
    })


@group_perm_required(('andinasoft.add_novacion',), raise_exception=True)
def novacion_ventas_destino(request):
    """JSON con las ventas pendientes/aprobadas de un proyecto que pueden recibir la novacion."""
    proyecto = request.GET.get('proyecto') or ''
    check_project(request, proyecto)
    titular = request.GET.get('titular') or ''
    ventas = []
    for venta in ventas_destino_disponibles(proyecto):
        ids = [t for t in (venta.id_t1, venta.id_t2, venta.id_t3, venta.id_t4) if t]
        ventas.append({
            'id': venta.pk,
            'inmueble': venta.inmueble,
            'estado': venta.estado,
            'titular': _nombre_cliente(venta.id_t1),
            'valor': venta.valor_venta,
            'cuota_inicial': total_cuota_inicial(venta),
            'fecha': venta.fecha_contrato.isoformat() if venta.fecha_contrato else '',
            'es_del_titular': titular in ids,
        })
    # Primero las del mismo titular, que son las que normalmente se usan.
    ventas.sort(key=lambda v: not v['es_del_titular'])
    return JsonResponse({'ventas': ventas})


@group_perm_required(('andinasoft.add_novacion',), raise_exception=True)
def novacion_lotes_libres(request):
    """JSON con los lotes libres de un proyecto, para crear ahi la venta destino."""
    proyecto = request.GET.get('proyecto') or ''
    check_project(request, proyecto)
    lotes = Inmuebles.objects.using(proyecto).filter(estado='Libre').order_by('idinmueble')
    return JsonResponse({'lotes': [
        {'id': lote.idinmueble, 'manzana': lote.manzananumero, 'lote': lote.lotenumero, 'area': float(lote.areaprivada or 0)}
        for lote in lotes
    ]})


def _accion_detalle(request, novacion, accion, form_aprobar):
    """Ejecuta la accion del POST. Devuelve un mensaje de exito o None si el formulario no es valido."""
    usuario = request.user
    if accion in ('nota', 'promesa', 'documento', 'eliminar_documento', 'enviar', 'aprobador'):
        if not puede_gestionar(usuario, novacion):
            raise PermissionDenied
        if accion == 'nota':
            form = NovacionNotaForm(request.POST, request.FILES)
            if not form.is_valid():
                raise NovacionError(' '.join(e for errs in form.errors.values() for e in errs))
            data = form.cleaned_data
            if not data['soporte'] and not novacion.soporte:
                raise NovacionError('Adjunta el PDF de la nota.')
            registrar_nota(
                usuario, novacion, nro_nota=data['nro_nota'], fecha_nota=data['fecha_nota'],
                empresa_nota=data['empresa_nota'], soporte=data['soporte'],
            )
            return 'Nota contable guardada.'
        if accion == 'promesa':
            form = NovacionFechasPromesaForm(request.POST)
            if not form.is_valid():
                raise NovacionError(' '.join(e for errs in form.errors.values() for e in errs))
            registrar_fechas_promesa(usuario, novacion, **form.cleaned_data)
            return 'Fechas de la promesa guardadas.'
        if accion == 'documento':
            form = NovacionDocumentoForm(request.POST, request.FILES)
            if not form.is_valid():
                raise NovacionError(' '.join(e for errs in form.errors.values() for e in errs))
            cargar_documento(usuario, novacion, form.cleaned_data['tipo'], form.cleaned_data['archivo'])
            return 'Documento cargado en la venta nueva.'
        if accion == 'aprobador':
            aprobador = {str(u.pk): u for u in candidatos_aprobador(novacion.proyecto_origen_id)}.get(
                request.POST.get('aprobador') or '',
            )
            if aprobador is None:
                raise NovacionError('Elige un aprobador de la lista.')
            cambiar_aprobador(usuario, novacion, aprobador)
            return 'Aprobador actualizado.'
        if accion == 'eliminar_documento':
            eliminar_documento(usuario, novacion, request.POST.get('descripcion') or '')
            return 'Documento eliminado.'
        enviada = enviar_a_aprobacion(usuario, novacion.pk)
        return f'Novación enviada a aprobación. Se avisó a {_etiqueta_usuario(enviada.aprobador)}.'

    if not puede_resolver(usuario, novacion):
        raise PermissionDenied
    check_project(request, novacion.proyecto_destino_id)
    if accion == 'aprobar':
        if not form_aprobar.is_valid():
            return None
        aprobada = aprobar(
            request, novacion.pk,
            oficina=form_aprobar.cleaned_data['oficina'],
            gestor_cartera=form_aprobar.cleaned_data['gestor_cartera'],
        )
        return (
            f'Novación aprobada: {aprobada.adj_origen} desistida y {aprobada.adj_destino} '
            f'adjudicada en {aprobada.proyecto_destino_id} con su promesa registrada.'
        )
    if accion == 'devolver':
        devolver(usuario, novacion.pk, request.POST.get('comentario'))
        return 'Novación devuelta a documentación. Se avisó a quien la registró.'
    if accion == 'rechazar':
        rechazar(usuario, novacion.pk, request.POST.get('motivo'))
        return f'Novación #{novacion.pk} rechazada.'
    raise NovacionError('Acción no válida.')


@group_perm_required(('andinasoft.view_novacion',), raise_exception=True)
def novacion_detalle(request, pk):
    novacion = Novacion.objects.select_related(
        'empresa_nota', 'usuario_solicita', 'usuario_envia', 'usuario_resuelve', 'aprobador',
    ).filter(pk=pk).first()
    if not novacion:
        raise Http404('Novación no encontrada')
    check_project(request, novacion.proyecto_origen_id)

    accion = request.POST.get('accion') if request.method == 'POST' else None
    form_aprobar = NovacionAprobacionForm(request.POST if accion == 'aprobar' else None)
    if accion:
        try:
            mensaje = _accion_detalle(request, novacion, accion, form_aprobar)
        except NovacionError as exc:
            messages.error(request, str(exc))
        else:
            if mensaje:
                messages.success(request, mensaje)
                return redirect('novacion detalle', pk=novacion.pk)

    venta = ventas_nuevas.objects.using(novacion.proyecto_destino_id).filter(pk=novacion.venta_destino).first()
    componentes = [
        (label, pagado, trasladado, pagado - trasladado)
        for label, pagado, trasladado in (
            ('Capital', novacion.pagado_capital, novacion.capital_trasladado),
            ('Interés corriente', novacion.pagado_interes_cte, novacion.interes_cte_trasladado),
            ('Interés de mora', novacion.pagado_interes_mora, novacion.interes_mora_trasladado),
        )
    ]
    total_pagado = sum(c[1] for c in componentes)
    docs = documentos_cargados(novacion)
    items, completo = checklist(novacion, docs)
    cargados = {d['tipo'] for d in docs}
    tipos_documento = [
        {'tipo': tipo, 'etiqueta': etiqueta, 'obligatorio': obligatorio, 'cargado': tipo in cargados}
        for tipo, etiqueta, obligatorio in DOCUMENTOS
    ]
    puede_documentar = (
        puede_gestionar(request.user, novacion) and novacion.estado == Novacion.ESTADO_DOCUMENTACION
    )
    return render(request, 'novaciones/detalle.html', {
        'n': novacion,
        'venta': venta,
        'cuota_inicial_destino': total_cuota_inicial(venta) if venta else 0,
        'nombre_titular': _nombre_cliente(novacion.titular),
        'componentes': componentes,
        'total_pagado': total_pagado,
        'total_queda': total_pagado - novacion.total_trasladado,
        'documentos': docs,
        'checklist': items,
        'checklist_completo': completo,
        'tipos_documento': tipos_documento,
        'todos_cargados': all(t['cargado'] for t in tipos_documento),
        'empresas': empresas.objects.all().order_by('nombre'),
        'eventos': novacion.eventos.select_related('usuario')[:50],
        'puede_documentar': puede_documentar,
        'aprobadores': (
            [(u.pk, _etiqueta_usuario(u)) for u in candidatos_aprobador(novacion.proyecto_origen_id)]
            if puede_documentar else []
        ),
        'puede_resolver': puede_resolver(request.user, novacion),
        # Impresion de documentos de la venta nueva (misma pagina de acciones de la venta).
        'puede_imprimir': request.user.has_perm('andinasoft.add_ventas_nuevas'),
        'form_aprobar': form_aprobar,
    })
