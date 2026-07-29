"""
Generacion centralizada del documento unico (contrato/promesa) por proyecto.

Motores soportados: reportlab | xhtml2pdf | weasyprint.
La seleccion sale de ConfigDocumento (andinasoft.models), no de if/elif por proyecto.
"""
from andinasoft.create_pdf import GenerarPDF
from andinasoft.utilities import pdf_gen, pdf_gen_weasy

MOTOR_REPORTLAB = 'reportlab'
MOTOR_XHTML2PDF = 'xhtml2pdf'
MOTOR_WEASYPRINT = 'weasyprint'

ORIGEN_VENTA = 'venta'
ORIGEN_MODULO = 'modulo'

# Exportadores vivos (impPromesa / modulo). No incluir ExportOpcion*.
REPORTLAB_EXPORTERS = frozenset({
    'ExportPromesaSandvilleBeach',
    'ExportPromesaBugambilias',
    'ExportCBFVegasVenecia',
})

# Seed 1:1 del camino vivo actual (sin Sandville del Sol).
DEFAULT_CONFIG_SEED = (
    # proyecto, origen, motor, plantilla, forma_pago_manual
    ('Sandville Beach', ORIGEN_VENTA, MOTOR_REPORTLAB, 'ExportPromesaSandvilleBeach', False),
    ('Sandville Beach', ORIGEN_MODULO, MOTOR_REPORTLAB, 'ExportPromesaSandvilleBeach', False),
    ('Perla del Mar', ORIGEN_VENTA, MOTOR_XHTML2PDF, 'pdf/Perla del Mar/contrato.html', False),
    ('Perla del Mar', ORIGEN_MODULO, MOTOR_XHTML2PDF, 'pdf/Perla del Mar/contrato.html', False),
    ('Tesoro Escondido', ORIGEN_VENTA, MOTOR_REPORTLAB, 'ExportPromesaBugambilias', False),
    ('Tesoro Escondido', ORIGEN_MODULO, MOTOR_REPORTLAB, 'ExportPromesaBugambilias', False),
    ('Vegas de Venecia', ORIGEN_VENTA, MOTOR_REPORTLAB, 'ExportCBFVegasVenecia', False),
    ('Vegas de Venecia', ORIGEN_MODULO, MOTOR_REPORTLAB, 'ExportCBFVegasVenecia', False),
    ('Carmelo Reservado', ORIGEN_VENTA, MOTOR_XHTML2PDF, 'pdf/Carmelo Reservado/contrato.html', False),
    ('Casas de Verano', ORIGEN_VENTA, MOTOR_XHTML2PDF, 'pdf/Casas de Verano/contrato.html', False),
    ('Oasis', ORIGEN_VENTA, MOTOR_WEASYPRINT, 'pdf/Oasis/contrato.html', False),
    ('Oasis', ORIGEN_MODULO, MOTOR_WEASYPRINT, 'pdf/Oasis/contrato.html', False),
    ('Sotavento', ORIGEN_MODULO, MOTOR_XHTML2PDF, 'pdf/Sotavento/contrato.html', False),
)


class DocumentoNoConfigurado(Exception):
    """El proyecto no tiene ConfigDocumento para el origen solicitado."""


class ConfigDocumentoInvalida(Exception):
    """Motor/plantilla no validos para generar el PDF."""


def get_config_documento(proyecto, origen):
    from andinasoft.models import ConfigDocumento

    try:
        return ConfigDocumento.objects.get(proyecto_id=proyecto, origen=origen)
    except ConfigDocumento.DoesNotExist as exc:
        raise DocumentoNoConfigurado(
            f'El proyecto {proyecto} no tiene formato de documento asignado para {origen}'
        ) from exc


def forma_pago_es_manual(proyecto, origen):
    try:
        return bool(get_config_documento(proyecto, origen).forma_pago_manual)
    except DocumentoNoConfigurado:
        return False


def validar_config(motor, plantilla):
    if motor == MOTOR_REPORTLAB:
        if plantilla not in REPORTLAB_EXPORTERS:
            raise ConfigDocumentoInvalida(
                f'Exportador ReportLab no permitido: {plantilla}'
            )
        return
    if motor in (MOTOR_XHTML2PDF, MOTOR_WEASYPRINT):
        if not plantilla or not str(plantilla).startswith('pdf/'):
            raise ConfigDocumentoInvalida(
                f'Plantilla HTML invalida: {plantilla}'
            )
        return
    raise ConfigDocumentoInvalida(f'Motor no soportado: {motor}')


def generar_documento_pdf_directo(
    motor,
    plantilla,
    *,
    reportlab_kwargs=None,
    html_context=None,
    filename=None,
):
    """
    Genera el PDF con motor/plantilla explicitos (sin leer ConfigDocumento).

    Returns dict: motor, root, url, filename
    """
    validar_config(motor, plantilla)

    if motor == MOTOR_REPORTLAB:
        pdf = GenerarPDF()
        method = getattr(pdf, plantilla, None)
        if method is None:
            raise ConfigDocumentoInvalida(
                f'No existe el exportador ReportLab: {plantilla}'
            )
        kwargs = dict(reportlab_kwargs or {})
        method(**kwargs)
        ruta = kwargs.get('ruta')
        out_name = filename
        if not out_name and ruta:
            out_name = str(ruta).replace('\\', '/').rsplit('/', 1)[-1]
        return {
            'motor': motor,
            'root': ruta,
            'url': None,
            'filename': out_name or 'documento.pdf',
        }

    if not filename:
        raise ConfigDocumentoInvalida('filename es obligatorio para plantillas HTML')
    context = html_context or {}
    if motor == MOTOR_WEASYPRINT:
        result = pdf_gen_weasy(plantilla, context, filename)
    else:
        result = pdf_gen(plantilla, context, filename)

    return {
        'motor': motor,
        'root': result.get('root'),
        'url': result.get('url'),
        'filename': filename,
    }


def generar_documento_pdf(
    proyecto,
    origen,
    *,
    reportlab_kwargs=None,
    html_context=None,
    filename=None,
):
    """Genera el PDF segun ConfigDocumento del proyecto/origen."""
    cfg = get_config_documento(proyecto, origen)
    return generar_documento_pdf_directo(
        cfg.motor,
        cfg.plantilla,
        reportlab_kwargs=reportlab_kwargs,
        html_context=html_context,
        filename=filename,
    )


def _sample_titular(nombre, cc):
    from types import SimpleNamespace
    return SimpleNamespace(pk=cc, idTercero=cc, nombrecompleto=nombre)


def _sample_inmueble():
    from types import SimpleNamespace
    return SimpleNamespace(
        etapa='1',
        lotenumero='12',
        manzananumero='A',
        area_lt=120.5,
        areaprivada=95.0,
        area_mz=1000.0,
        porcentaje_derecho=9.5,
        nro_fraccion='-',
        norte=10.0,
        sur=10.0,
        este=12.0,
        oeste=12.0,
        colindante_norte='Calle 1',
        colindante_sur='Calle 2',
        colidante_este='Lote 13',
        colindante_oeste='Lote 11',
    )


def build_preview_sample_payload(proyecto, origen, motor, plantilla):
    """
    Datos de muestra para previsualizar el documento configurado.
    No usa adjudicaciones reales: solo confirma motor/plantilla.
    """
    import datetime
    from types import SimpleNamespace
    from django.conf import settings

    hoy = datetime.date.today()
    fecha_entrega = hoy + datetime.timedelta(days=180)
    fecha_escritura = hoy + datetime.timedelta(days=210)
    filename = f'preview_{proyecto}_{origen}.pdf'.replace(' ', '_')
    ruta = settings.DIR_EXPORT + filename

    t1 = _sample_titular('CLIENTE DE PRUEBA UNO', '1000001')
    t2 = _sample_titular('CLIENTE DE PRUEBA DOS', '1000002')
    t3 = _sample_titular('', '')
    t4 = _sample_titular('', '')

    if motor == MOTOR_REPORTLAB:
        reportlab_kwargs = {
            'nro_contrato': 9999,
            'nombre_t1': t1.nombrecompleto, 'cc_t1': t1.pk, 'tel_t1': '6040000000', 'cel_t1': '3000000001',
            'ofic_t1': 'Oficina demo', 'cdof_t1': 'Medellin', 'telof_t1': '6040000001',
            'resid_t1': 'Calle demo 1', 'cdresid_t1': 'Medellin', 'telresid_t1': '6040000000', 'email_t1': 'demo1@example.com',
            'nombre_t2': t2.nombrecompleto, 'cc_t2': t2.pk, 'tel_t2': '6040000002', 'cel_t2': '3000000002',
            'ofic_t2': '', 'cdof_t2': '', 'telof_t2': '',
            'resid_t2': 'Calle demo 2', 'cdresid_t2': 'Medellin', 'telresid_t2': '6040000002', 'email_t2': 'demo2@example.com',
            'nombre_t3': t3.nombrecompleto, 'cc_t3': t3.pk, 'tel_t3': '', 'cel_t3': '',
            'ofic_t3': '', 'cdof_t3': '', 'telof_t3': '',
            'resid_t3': '', 'cdresid_t3': '', 'telresid_t3': '', 'email_t3': '',
            'nombre_t4': t4.nombrecompleto, 'cc_t4': t4.pk, 'tel_t4': '', 'cel_t4': '',
            'ofic_t4': '', 'cdof_t4': '', 'telof_t4': '',
            'resid_t4': '', 'cdresid_t4': '', 'telresid_t4': '', 'email_t4': '',
            'lote': '12', 'manzana': 'A', 'area': '95.0',
            'mtsnorte': '10', 'colnorte': 'Calle 1', 'mtseste': '12', 'coleste': 'Lote 13',
            'mtssur': '10', 'colsur': 'Calle 2', 'mtsoeste': '12', 'coloeste': 'Lote 11',
            'valor': 150000000, 'valor_letras': 'CIENTO CINCUENTA MILLONES DE PESOS M/CTE',
            'ci': 45000000, 'saldo': 105000000,
            'contado_x': '', 'credic_x': 'x', 'amort_x': '',
            'formaCI': '3 cuotas mensuales de $15.000.000 a partir del ' + str(hoy),
            'formaFN': '36 cuotas mensuales de $2.916.667 a partir del ' + str(fecha_entrega),
            'obs': 'DOCUMENTO DE PREVISUALIZACION - DATOS DE MUESTRA',
            'dia_contrato': str(hoy.day), 'mes_contrato': hoy.month, 'año_contrato': str(hoy.year),
            'fecha_escritura': fecha_escritura, 'fecha_entrega': fecha_entrega,
            'ciudad_entrega': 'Medellin', 'ruta': ruta,
        }
        if plantilla == 'ExportPromesaBugambilias':
            reportlab_kwargs['porcderecho'] = '9.50'
            reportlab_kwargs['area_parcela'] = '1000.0'
        if plantilla == 'ExportCBFVegasVenecia':
            reportlab_kwargs['meses_entrega'] = '6'
        return {
            'reportlab_kwargs': reportlab_kwargs,
            'html_context': None,
            'filename': filename,
            'download_url': settings.DIR_DOWNLOADS + filename,
        }

    inmueble = _sample_inmueble()
    general_info = {
        'valor': 150000000,
        'inmueble': inmueble,
        'valor_en_letras': 'CIENTO CINCUENTA MILLONES DE PESOS M/CTE',
        'ci': 45000000,
        'saldo': 105000000,
        'fp_ci': '3 cuotas mensuales de $15.000.000 a partir del ' + str(hoy),
        'fp_saldo': '36 cuotas mensuales de $2.916.667 a partir del ' + str(fecha_entrega),
    }
    ctr = SimpleNamespace(
        pk='PREV',
        titulares=[t1, t2],
        general_info=general_info,
        forma_pago='Credicontado',
        formapago='Credicontado',
        formaci=general_info['fp_ci'],
        formasaldo=general_info['fp_saldo'],
        observaciones='DOCUMENTO DE PREVISUALIZACION - DATOS DE MUESTRA',
        fecha_contrato=hoy,
        fechapromesa=hoy,
        fechaentrega=fecha_entrega,
        fechaescritura=fecha_escritura,
    )
    html_context = {
        'proyecto': proyecto,
        'ctr': ctr,
        'fecha_escritura': fecha_escritura,
        'meses_entrega': 6,
        'oficina': 'Medellin',
        'es_promesa': origen == ORIGEN_MODULO,
    }
    return {
        'reportlab_kwargs': None,
        'html_context': html_context,
        'filename': filename,
        'download_url': None,
    }


def generar_preview_documento(proyecto, origen, motor, plantilla):
    """Genera PDF de muestra con motor/plantilla del formulario de parametros."""
    from django.conf import settings

    sample = build_preview_sample_payload(proyecto, origen, motor, plantilla)
    result = generar_documento_pdf_directo(
        motor,
        plantilla,
        reportlab_kwargs=sample['reportlab_kwargs'],
        html_context=sample['html_context'],
        filename=sample['filename'],
    )
    url = result.get('url') or sample.get('download_url')
    if not url and result.get('root'):
        # ReportLab escribio en DIR_EXPORT
        url = settings.DIR_DOWNLOADS + sample['filename']
    return {
        'motor': motor,
        'plantilla': plantilla,
        'root': result.get('root'),
        'url': url,
        'filename': result.get('filename') or sample['filename'],
    }
