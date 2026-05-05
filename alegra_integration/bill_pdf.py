"""
Descarga el PDF (u otro archivo de soporte) de una factura de proveedor en Alegra
mediante GET /bills/{id} con fields adicionales y guarda en Facturas.soporte_radicado.

Referencia: https://developer.alegra.com/reference/get_bills-id
"""
import json
import logging
import re

import requests

from django.core.files.base import ContentFile

from alegra_integration.client import AlegraMCPClient
from alegra_integration.exceptions import AlegraClientError, AlegraConfigurationError
from alegra_integration.models import AlegraBillGetLog

logger = logging.getLogger(__name__)

# Incluye attachments; Alegra anida URLs profundamente en stamp / stampFiles / attachments.
DEFAULT_BILL_FIELDS = 'url,stampFiles,stamp,attachments'


def _looks_pdf_url(url):
    if not url or not isinstance(url, str):
        return False
    u = url.lower().strip()
    return u.endswith('.pdf') or '/pdf' in u or 'pdf' in u.split('?')[0][-8:]


def _path_before_query(url):
    if not url or not isinstance(url, str):
        return ''
    return url.split('?', 1)[0].lower()


def _is_likely_xml_download(url):
    p = _path_before_query(url)
    return p.endswith('.xml') or p.endswith('.zip') or '/stamp-files/' in url.lower() and '.xml' in p


def _score_pdf_candidate(url):
    """
    Puntuación para elegir URL del PDF. Penaliza XML de factura electrónica (p. ej. stampFiles en CO).
    """
    if not url or not isinstance(url, str) or not url.startswith('http'):
        return -999
    p = _path_before_query(url)
    if p.endswith('.pdf') or p.rstrip('/').endswith('.pdf'):
        return 100
    if '.pdf' in p:
        return 85
    if _looks_pdf_url(url):
        return 70
    if _is_likely_xml_download(url):
        return -80
    if 'pdf' in url.lower():
        return 40
    return 5


def _extract_pdf_from_attachments_list(bill_data):
    """Colombia: el PDF representación suele venir en attachments[].url con name *.pdf."""
    att = bill_data.get('attachments')
    if not isinstance(att, list):
        return None
    for item in att:
        if not isinstance(item, dict):
            continue
        name = (item.get('name') or '').strip().lower()
        u = item.get('url')
        if not (name.endswith('.pdf') and isinstance(u, str) and u.startswith('http')):
            continue
        return u
    return None


_URL_KEY_HINTS = frozenset({
    'url', 'link', 'href', 'publicurl', 'publicURL', 'fileurl', 'fileUrl', 'pdfurl', 'pdfUrl',
    'downloadurl', 'downloadUrl', 'documenturl', 'documentUrl', 'path', 'src',
})


def _walk_collect_http_urls(obj, out, depth=0, max_depth=14):
    """Recoge todas las cadenas http(s) del JSON de la factura."""
    if depth > max_depth:
        return
    if isinstance(obj, dict):
        for k, v in obj.items():
            kl = k.lower()
            if isinstance(v, str) and v.startswith('http'):
                out.append(v)
            elif kl in _URL_KEY_HINTS or kl.endswith('url') or kl.endswith('link'):
                if isinstance(v, str) and v.startswith('http'):
                    out.append(v)
                else:
                    _walk_collect_http_urls(v, out, depth + 1, max_depth)
            else:
                _walk_collect_http_urls(v, out, depth + 1, max_depth)
    elif isinstance(obj, list):
        for item in obj:
            _walk_collect_http_urls(item, out, depth + 1, max_depth)
    elif isinstance(obj, str) and obj.startswith('http'):
        out.append(obj)


def _pick_best_pdf_url(urls):
    """Elige la mejor URL para PDF; no usa la primera «alegra» genérica (evita XML de stampFiles)."""
    if not urls:
        return None
    seen = []
    for u in urls:
        if u not in seen:
            seen.append(u)
    scored = [(_score_pdf_candidate(u), u) for u in seen]
    scored.sort(key=lambda x: -x[0])
    best_s, best_u = scored[0]
    if best_s < 0:
        return None
    # Preferir solo candidatos con señal clara de PDF si existen
    for s, u in scored:
        if s >= 70:
            return u
    for s, u in scored:
        if s > 0:
            return u
    return None


def _extract_pdf_url(bill_data):
    """Busca URL de descarga del PDF en la respuesta GET /bills (estructura variable por país)."""
    if not isinstance(bill_data, dict):
        return None

    u_att = _extract_pdf_from_attachments_list(bill_data)
    if u_att:
        return u_att

    top = bill_data.get('url')
    if isinstance(top, str) and top.startswith('http') and _score_pdf_candidate(top) >= 40:
        return top

    candidates = []
    _walk_collect_http_urls(bill_data, candidates)
    # Incluye S3 Alegra/CDN (stampFiles en CO son URLs a XML/PDF)
    filtered = [
        u
        for u in candidates
        if (
            'alegra.com' in u
            or 'alegra.s3' in u.lower()
            or 'amazonaws.com' in u.lower()
            or '/api/' in u
            or '/files/' in u
            or '.pdf' in u.lower()
        )
    ]
    pool = filtered if filtered else candidates
    return _pick_best_pdf_url(pool)


def _log_structure_hint(bill_data, alegra_numeric_id):
    """Ayuda a depurar cuando Alegra no expone aún una URL descargable."""
    for k in ('stamp', 'stampFiles', 'attachments', 'url'):
        v = bill_data.get(k)
        try:
            snippet = json.dumps(v, default=str, ensure_ascii=False)[:500]
        except Exception:
            snippet = str(v)[:500]
        logger.info('Alegra bill %s campo %s: %s', alegra_numeric_id, k, snippet)


def _download_bytes(url, auth_header=None):
    """Intenta GET público; si 401, reintenta con Basic Auth (URLs de API Alegra)."""
    headers = {}
    r = requests.get(url, headers=headers, timeout=90)
    if r.status_code == 401 and auth_header:
        r = requests.get(url, headers={'Authorization': auth_header}, timeout=90)
    r.raise_for_status()
    return r.content


def _is_pdf_magic(content):
    return len(content) >= 4 and content[:4] == b'%PDF'


def _save_bill_get_snapshot(empresa, alegra_numeric_id, factura, fields_str, bill_data, error, pdf_saved):
    """Persiste la respuesta de GET /bills (o el fallo) para inspección en Admin."""
    try:
        payload = bill_data if isinstance(bill_data, dict) else {}
        AlegraBillGetLog.objects.create(
            empresa=empresa,
            alegra_bill_id=str(alegra_numeric_id)[:64],
            factura=factura,
            fields=(fields_str or '')[:255],
            response_json=payload,
            error=(error or '')[:8000],
            pdf_saved=bool(pdf_saved),
        )
    except Exception:
        logger.exception(
            'No se pudo guardar AlegraBillGetLog empresa=%s bill=%s',
            getattr(empresa, 'pk', empresa),
            alegra_numeric_id,
        )


def attach_bill_pdf_from_alegra(empresa, alegra_numeric_id, factura, *, fields=None):
    """
    Descarga PDF desde Alegra y lo guarda en factura.soporte_radicado.
    Retorna True si se guardó un archivo con contenido tipo PDF.
    """
    fields = fields or DEFAULT_BILL_FIELDS
    try:
        client = AlegraMCPClient(empresa)
    except AlegraConfigurationError as exc:
        logger.warning('Alegra PDF: %s', exc)
        _save_bill_get_snapshot(empresa, alegra_numeric_id, factura, fields, None, str(exc), False)
        return False

    auth_header = client.get_authorization_header()

    try:
        bill_data = client.get_bill(alegra_numeric_id, fields=fields)
    except AlegraClientError as exc:
        logger.warning('Alegra GET /bills/%s: %s', alegra_numeric_id, exc)
        _save_bill_get_snapshot(empresa, alegra_numeric_id, factura, fields, None, str(exc), False)
        return False

    if not isinstance(bill_data, dict):
        _save_bill_get_snapshot(
            empresa, alegra_numeric_id, factura, fields, {}, 'respuesta GET /bills no es objeto JSON', False
        )
        return False

    pdf_url = _extract_pdf_url(bill_data)
    if not pdf_url:
        logger.info(
            'Alegra bill %s: sin URL http usable para PDF (keys=%s)',
            alegra_numeric_id,
            list(bill_data.keys())[:40],
        )
        _log_structure_hint(bill_data, alegra_numeric_id)
        _save_bill_get_snapshot(empresa, alegra_numeric_id, factura, fields, bill_data, '', False)
        return False

    try:
        content = _download_bytes(pdf_url, auth_header=auth_header)
    except requests.RequestException as exc:
        logger.warning('Descarga PDF fallida %s: %s', pdf_url, exc)
        _save_bill_get_snapshot(empresa, alegra_numeric_id, factura, fields, bill_data, f'descarga: {exc}', False)
        return False

    if not content or len(content) < 100:
        logger.warning('Descarga PDF vacía o demasiado corta bill=%s', alegra_numeric_id)
        _save_bill_get_snapshot(empresa, alegra_numeric_id, factura, fields, bill_data, 'descarga vacía o corta', False)
        return False

    if not _is_pdf_magic(content):
        logger.warning(
            'Descarga no es PDF válido (bill=%s url=%s primeros bytes=%r)',
            alegra_numeric_id,
            pdf_url,
            content[:12],
        )
        _save_bill_get_snapshot(empresa, alegra_numeric_id, factura, fields, bill_data, 'contenido no es PDF', False)
        return False

    safe_name = re.sub(r'[^\w.\-]', '_', str(alegra_numeric_id))[:40]
    fname = f'alegra_bill_{safe_name}.pdf'
    factura.soporte_radicado.save(fname, ContentFile(content), save=True)
    logger.info('PDF Alegra guardado en Facturas.pk=%s archivo=%s', factura.pk, fname)
    _save_bill_get_snapshot(empresa, alegra_numeric_id, factura, fields, bill_data, '', True)
    return True
