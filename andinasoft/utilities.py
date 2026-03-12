import math
import mimetypes
import os
import re
import tempfile
from urllib.parse import urlparse
import numpy_financial as npf
#import pytesseract
from django.template.loader import get_template
from django.conf import settings
from django.http import HttpResponse
from django.core.files.storage import default_storage
from django.contrib.staticfiles import finders
from django.contrib.staticfiles.storage import staticfiles_storage
from xhtml2pdf import pisa
try:
    from weasyprint import HTML, default_url_fetcher
except ImportError:  # pragma: no cover
    HTML = None
    default_url_fetcher = None
from dateutil.relativedelta import relativedelta
from datetime import datetime
from decimal import Decimal
from PIL import Image
from pdf2image import convert_from_path
from django.db.models.fields.related import ForeignKey, ManyToManyField
from django.db.models.fields.files import FileField, ImageField




_HASHED_STATIC_RE = re.compile(r"^(?P<prefix>.+)\.[0-9a-f]{6,64}(?P<suffix>\.[^./]+)$")
_STATIC_URL_TOKEN_RE = re.compile(
    r"""(?P<prefix>url\(\s*['"]?|['"])(?P<url>(?:https?:)?//[^'")\s]+|/static/[^'")\s]+)(?P<suffix>['"]?\s*\)|['"])"""
)


def _unhashed_static_key(static_key):
    match = _HASHED_STATIC_RE.match(static_key or "")
    if not match:
        return None
    return f"{match.group('prefix')}{match.group('suffix')}"


def _resolve_static_path(static_key):
    cleaned_key = (static_key or "").lstrip("/")
    candidates = [cleaned_key]
    unhashed_key = _unhashed_static_key(cleaned_key)
    if unhashed_key and unhashed_key not in candidates:
        candidates.append(unhashed_key)

    for key in candidates:
        if getattr(settings, "STATIC_ROOT", None):
            candidate = os.path.join(settings.STATIC_ROOT, key)
            if os.path.exists(candidate):
                return candidate

        for static_dir in getattr(settings, "STATICFILES_DIRS", []):
            candidate = os.path.join(static_dir, key)
            if os.path.exists(candidate):
                return candidate

        found = finders.find(key)
        if isinstance(found, (list, tuple)):
            for item in found:
                if item and os.path.exists(item):
                    return item
            if found:
                return found[0]
        elif found:
            return found

    # Manifest storages can map hashed names to original names.
    for key in candidates:
        try:
            path = staticfiles_storage.path(key)
            if path and os.path.exists(path):
                return path
        except Exception:
            pass
    return None


def _replace_static_urls_with_file_urls(html):
    if not html:
        return html

    def _replace(match):
        raw_url = match.group("url")
        parsed = urlparse(raw_url)
        candidate = parsed.path if parsed.scheme else raw_url

        if not candidate.startswith(settings.STATIC_URL):
            return match.group(0)

        static_key = candidate.replace(settings.STATIC_URL, "", 1)
        static_path = _resolve_static_path(static_key)
        if not static_path or not os.path.exists(static_path):
            return match.group(0)

        return f"{match.group('prefix')}file://{static_path}{match.group('suffix')}"

    return _STATIC_URL_TOKEN_RE.sub(_replace, html)


def link_callback(uri, rel):
    path = ''
    parsed = urlparse(uri)
    candidate = parsed.path if parsed.scheme else uri

    if candidate.startswith(settings.STATIC_URL):
        static_key = candidate.replace(settings.STATIC_URL, "", 1)
        static_path = _resolve_static_path(static_key)
        if static_path:
            return static_path
        return os.path.join(settings.STATIC_ROOT, static_key)
    if candidate.startswith(settings.MEDIA_URL):
        media_key = candidate.replace(settings.MEDIA_URL, "", 1)
        if getattr(settings, 'USE_S3_MEDIA', False):
            suffix = os.path.splitext(media_key)[1]
            with default_storage.open(media_key, "rb") as stored_file:
                temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
                temp_file.write(stored_file.read())
                temp_file.flush()
                temp_file.close()
            return temp_file.name
        return os.path.join(settings.MEDIA_ROOT, media_key)
    return path

def pdf_gen(template_path,context,filename,):
    # Create a Django response object, and specify content_type as pdf
    #response = HttpResponse(content_type='application/pdf')
    #response['Content-Disposition'] = 'attachment; filename="report.pdf"'
    # find the template and render it.
    template = get_template(template_path)
    html = template.render(context)
    file_dir = settings.MEDIA_ROOT + f'/tmp/{filename}'
    os.makedirs(settings.MEDIA_ROOT + '/tmp', exist_ok=True)
    with open(file_dir, "w+b") as output_file:
        pisa_status = pisa.CreatePDF(
           html, dest=output_file, link_callback=link_callback)
    # if error then show some funy view
    if pisa_status.err:
       return HttpResponse('We had some errors <pre>' + html + '</pre>')
    
    output_url = settings.MEDIA_ROOT + f'/tmp/{filename}'
   
    output = {
        'url':settings.MEDIA_URL + f'tmp/{filename}',
        'root':settings.MEDIA_ROOT + f'/tmp/{filename}'
    }
   
    return output


def weasy_url_fetcher(url):
    if default_url_fetcher is None:
        raise RuntimeError("WeasyPrint no está instalado.")
    parsed = urlparse(url)
    candidate = parsed.path if parsed.scheme else url

    if candidate.startswith(settings.STATIC_URL):
        static_key = candidate.replace(settings.STATIC_URL, "", 1)
        static_path = _resolve_static_path(static_key)
        if static_path and os.path.exists(static_path):
            mime_type = mimetypes.guess_type(static_path)[0]
            return {"file_obj": open(static_path, "rb"), "mime_type": mime_type}

    if candidate.startswith(settings.MEDIA_URL):
        media_key = candidate.replace(settings.MEDIA_URL, "", 1)
        if getattr(settings, 'USE_S3_MEDIA', False):
            return {"file_obj": default_storage.open(media_key, "rb")}

        media_path = os.path.join(settings.MEDIA_ROOT, media_key)
        if os.path.exists(media_path):
            mime_type = mimetypes.guess_type(media_path)[0]
            return {"file_obj": open(media_path, "rb"), "mime_type": mime_type}

    return default_url_fetcher(url)


def pdf_gen_weasy(template_path, context, filename):
    if HTML is None:
        raise RuntimeError("WeasyPrint no está instalado.")
    template = get_template(template_path)
    html = template.render(context)
    html = _replace_static_urls_with_file_urls(html)
    oasis_logo_path = _resolve_static_path("img/logo_oasis.png")
    if oasis_logo_path:
        html = html.replace(
            "/static/img/logo_oasis.png",
            f"file://{oasis_logo_path}",
        )
    plano_oasis_path = _resolve_static_path("img/plano_oasis.jpg")
    if not plano_oasis_path or not os.path.exists(plano_oasis_path):
        plano_oasis_path = os.path.join(
            settings.BASE_DIR, "andinasoft/templates/pdf/Oasis/plano.jpg"
        )
    if plano_oasis_path and os.path.exists(plano_oasis_path):
        html = html.replace(
            "/static/img/plano_oasis.jpg",
            f"file://{plano_oasis_path}",
        )
    file_dir = settings.MEDIA_ROOT + f'/tmp/{filename}'
    os.makedirs(settings.MEDIA_ROOT + '/tmp', exist_ok=True)

    HTML(
        string=html,
        base_url=settings.BASE_DIR,
        url_fetcher=weasy_url_fetcher
    ).write_pdf(target=file_dir)

    output = {
        'url': settings.MEDIA_URL + f'tmp/{filename}',
        'root': settings.MEDIA_ROOT + f'/tmp/{filename}'
    }

    return output

def get_text_from_file(file_path):
    
    #pytesseract.pytesseract.tesseract_cmd = r'/usr/bin/tesseract'

    image_name = file_path.split('.')[0]

    text = ''
    
    """ if file_path.endswith('.pdf'):
        pages = convert_from_path(file_path, 500)
        i = 1
        for page in pages:
            image_path = f'{settings.MEDIA_ROOT}/tmp/image_for_ocr_{i}.png'
            page.save(image_path, 'PNG')
            
            
            text += pytesseract.image_to_string(Image.open(image_path), lang="spa") + f'\n------Fin pagina {i}-----'
            
            i+=1
            
            os.remove(image_path)
            
    else:
        text = ""#pytesseract.image_to_string(Image.open(file_path), lang="spa")
 """
    return text


class JsonRender():
    
    def __init__(self,queryset,reverse=False,query_functions=[]):
        self.queryset = queryset
        self.reverse = reverse
        self.query_functions = query_functions
    
    def render(self):
        object_dict = list()
        if self.queryset.count() > 0:
            fields = [f for f in self.queryset[0]._meta._get_fields(reverse=self.reverse)]
        else: 
            fields = []
        for obj in self.queryset:
            item = {}
            for field in fields:
                field_value = eval("obj."+field.name)     
                if isinstance(field, ForeignKey):
                    field_value = self.ForeingKeyRender(field,field_value)
                elif isinstance(field, ManyToManyField):
                    field_value = 'ManytoManyField'
                elif isinstance(field, (FileField, ImageField)):
                    field_value = self._media_value(field_value)
                item[field.name] = field_value
            for func in self.query_functions:
                item[func] = eval('obj.'+func+'()')
            object_dict.append(item)
        return object_dict

    def ForeingKeyRender(self,fk,queryset_item):
        query_dict = {}
        field_list = fk.related_model._meta._get_fields(reverse = self.reverse)
        for field in field_list:
            if queryset_item == None:
                field_value = None
            else:
                field_value = eval(f'queryset_item.{field.name}')
                if isinstance(field, ForeignKey):
                    field_value = self.ForeingKeyRender(field,field_value)
                elif isinstance(field, ManyToManyField):
                    field_value = 'ManytoManyField'
                elif isinstance(field, (FileField, ImageField)):
                    field_value = self._media_value(field_value)
            query_dict[field.name] = field_value
        return query_dict

    def _media_value(self, field_value):
        if not field_value:
            return ''
        try:
            return field_value.url
        except Exception:
            return str(field_value)


class Utilidades():

    def cambiar_moneda_entero(self,valor):
        if valor==None or valor=='':
            return 0
        else:
            entero=''
            for caracter in valor:
                if caracter=="$" or caracter=="," or caracter==".":
                    pass
                else:
                    entero+=caracter
            return int(entero)
    
    def redondear_numero(self,numero,multiplo=1,redondeo='>'):
        residuo=int(numero)%multiplo
        if redondeo=='>':
            numero_redondeado=int(numero)-residuo+multiplo
        elif redondeo=='<':
            numero_redondeado=int(numero)-residuo
        return numero_redondeado
    
    def numeros_letras(self,numero,formato='Moneda'):
        unidades={0:'',
                  1:'UN',
                  2:'DOS',
                  3:'TRES',
                  4:'CUATRO',
                  5:'CINCO',
                  6:'SEIS',
                  7:'SIETE',
                  8:'OCHO',
                  9:'NUEVE',
                 10:'DIEZ',
                 11:'ONCE',
                 12:'DOCE',
                 13:'TRECE',
                 14:'CATORCE',
                 15:'QUINCE',
                 16:'DIECISEIS',
                 17:'DIECISIETE',
                 18:'DIECIOCHO',
                 19:'DIECINUEVE'}
        decenas={20:('VEINTE','VEINTI'),
                 30:('TREINTA','TREINTA Y'),
                 40:('CUARENTA','CUARENTA Y'),
                 50:('CINCUENTA','CINCUENTA Y'),
                 60:('SESENTA','SESENTA Y'),
                 70:('SETENTA','SETENTA Y'),
                 80:('OCHENTA','OCHENTA Y'),
                 90:('NOVENTA','NOVENTA Y')}
        centenas={100:('CIEN','CIENTO'),
                 200:'DOSCIENTOS',
                 300:'TRESCIENTOS',
                 400:'CUATROCIENTOS',
                 500:'QUINIENTOS',
                 600:'SEISCIENTOS',
                 700:'SETECIENTOS',
                 800:'OCHOCIENTOS',
                 900:'NOVECIENTOS'}
        
        valor_letras=""
        millones=int(numero/1000000)
        numero-=(millones*1000000)
        miles=int(numero/1000)
        numero-=miles*1000
        cientos=int(numero)
        cifra=(millones,miles,cientos)
        
        index=1
        for valor in cifra:
            Cientos_valor=valor-valor%100
            Decenas_valor=valor%100
            if valor>0:
                #centenas
                if valor>=100:
                    if valor==100:
                        valor_letras+=centenas[Cientos_valor][0]
                    elif valor<200:
                        valor_letras+=centenas[Cientos_valor][1]
                    elif valor<1000:
                        valor_letras+=centenas[Cientos_valor]
                    if Decenas_valor>=20:
                        if Decenas_valor%10==0:
                            valor_letras+=' '+decenas[Decenas_valor][0]
                        else:
                            valor_letras+=' '+decenas[Decenas_valor-Decenas_valor%10][1]
                            valor_letras+=' '+unidades[Decenas_valor%10]
                    elif Decenas_valor<20 and Decenas_valor>0:
                        valor_letras+=' '+unidades[Decenas_valor]
                elif valor>=20:
                    if Decenas_valor>=20:
                        if Decenas_valor%10==0:
                            valor_letras+=' '+decenas[Decenas_valor][0]
                        else:
                            valor_letras+=' '+decenas[Decenas_valor-Decenas_valor%10][1]
                            valor_letras+=' '+unidades[Decenas_valor%10]
                    elif Decenas_valor<20:
                        valor_letras+=' '+unidades[Decenas_valor]
                elif valor>0:
                    valor_letras+=unidades[Decenas_valor]
                if index==1:
                    valor_letras+=' MILLONES '
                if index==2:
                    valor_letras+=' MIL '
                if index==3:
                    if valor==1:
                        valor_letras+=' PESO '
                    else:
                        valor_letras+=' PESOS '
            index+=1
            
        if miles==0 and cientos==0:
            valor_letras+='DE PESOS '
        elif miles!=0 and cientos==0:
            valor_letras+='PESOS '
        valor_letras+='M/CTE'    
        valor_letras.replace('VEINTI ','VEINTI')
        valor_letras.replace('  ',' ')
        
        if formato=='Numero':
            valor_letras = valor_letras.replace(' DE ',''
                ).replace('PESOS M/CTE',''
                ).replace('PESO M/CTE',''
                ).replace('  ',' ')
        
        if 'UN' in valor_letras and len(valor_letras)<5: valor_letras = 'UNO'
        
        return valor_letras
    
    def CalcularAnualidades(self,capital,tasa,nCuotas):
        if tasa==0:
            return math.ceil(capital/nCuotas)
        else:
            up=capital*tasa
            down=1-(1+tasa)**(-1*nCuotas)
            cuota=up/down
            return math.ceil(cuota)
    
    def calcularPeriodos(self,cuota,tasa,capital):
        """
        Calcula el numero de periodos en funcion del capital pendiente y el valor de las cuotas
        Los tres parametros deben ser del mismo tipo de datos.
        """
        #up=-1*math.log(1-(capital*tasa/cuota))
        #down=math.log(1+tasa)
        #value=up/down
        
        value = npf.nper(int(tasa),int(cuota),int(capital))
        
        return math.ceil(value)
    
    def CalcularVP(self,cuota,tasa,nCuotas):
        
        if tasa==0:
            return math.ceil(cuota*nCuotas)
        up=(1-(1+tasa)**(-1*nCuotas))*cuota
        down=tasa
        try:
            capital=up/down
        except ZeroDivisionError:
            capital=cuota*nCuotas
        return math.ceil(capital)        

    def NombreMes(self,nroMes):
        dctMeses={1:'Enero',
                  2:'Febrero',
                  3:'Marzo',
                  4:'Abril',
                  5:'Mayo',
                  6:'Junio',
                  7:'Julio',
                  8:'Agosto',
                  9:'Septiembre',
                  10:'Octubre',
                  11:'Noviembre',
                  12:'Diciembre'}
        return dctMeses[nroMes]


def calcular_tabla_amortizacion(ctr):
    """
    Genera la tabla de amortización (sistema francés, cuota fija) a partir
    de los datos de ventas_nuevas, sin requerir que exista plan_pagos.
    Incluye CI, CE y FN ordenadas por fecha.

    Retorna lista de dicts: {nrocta, fecha, tipo, capital, intcte, cuota, saldo_capital}.
    """
    from decimal import ROUND_HALF_UP

    filas_sin_orden = []
    saldo_corriente = Decimal(str(ctr.valor_venta))

    # ── Filas de Cuota Inicial ──────────────────────────────────────────
    for n in range(1, 8):
        cant  = getattr(ctr, f'cant_ci{n}',  None)
        fecha = getattr(ctr, f'fecha_ci{n}', None)
        valor = getattr(ctr, f'valor_ci{n}', None)
        if cant is None or fecha is None or valor is None:
            continue
        valor = Decimal(str(valor))
        for j in range(int(cant)):
            filas_sin_orden.append({
                'fecha':  fecha + relativedelta(months=j),
                'tipo':   'Cuota Inicial',
                'capital': valor,
                'intcte':  Decimal('0'),
                'cuota':   valor,
            })

    # ── Filas de Cuota Extraordinaria ───────────────────────────────────
    valor_ce    = ctr.valor_ctas_ce
    inicio_ce   = ctr.inicio_ce
    nro_ce      = ctr.nro_cuotas_ce
    periodo_ce  = ctr.period_ce

    if all([valor_ce, inicio_ce, nro_ce, periodo_ce]):
        valor_ce   = Decimal(str(valor_ce))
        intervalo  = int(periodo_ce)
        for j in range(int(nro_ce)):
            filas_sin_orden.append({
                'fecha':   inicio_ce + relativedelta(months=j * intervalo),
                'tipo':    'Cuota Extraordinaria',
                'capital': valor_ce,
                'intcte':  Decimal('0'),
                'cuota':   valor_ce,
            })

    # ── Filas de Financiación ───────────────────────────────────────────
    saldo      = ctr.saldo
    tasa       = ctr.tasa
    nro_cuotas = ctr.nro_cuotas_fn
    inicio     = ctr.inicio_fn

    if all([saldo, tasa, nro_cuotas, inicio]):
        saldo      = Decimal(str(saldo))
        tasa       = Decimal(str(tasa))
        nro_cuotas = int(nro_cuotas)

        if tasa > 1:
            tasa = tasa / Decimal('100')

        if tasa == 0:
            cuota_fija = (saldo / nro_cuotas).quantize(Decimal('1'), rounding=ROUND_HALF_UP)
        else:
            factor     = (1 + tasa) ** nro_cuotas
            cuota_fija = (saldo * tasa * factor / (factor - 1)).quantize(Decimal('1'), rounding=ROUND_HALF_UP)

        capital_pendiente = saldo

        for i in range(1, nro_cuotas + 1):
            interes       = (capital_pendiente * tasa).quantize(Decimal('1'), rounding=ROUND_HALF_UP)
            abono_capital = cuota_fija - interes
            fecha         = inicio + relativedelta(months=i - 1)

            if i == nro_cuotas:
                abono_capital = capital_pendiente
                cuota_real    = abono_capital + interes
            else:
                cuota_real = cuota_fija

            capital_pendiente -= abono_capital

            filas_sin_orden.append({
                'fecha':   fecha,
                'tipo':    'Financiación',
                'capital': abono_capital,
                'intcte':  interes,
                'cuota':   cuota_real,
            })

    # ── Ordenar por fecha y calcular saldo_capital acumulado ────────────
    filas_sin_orden.sort(key=lambda r: r['fecha'])

    tabla = []
    for nro, fila in enumerate(filas_sin_orden, start=1):
        saldo_corriente -= fila['capital']
        tabla.append({
            'nrocta':        nro,
            'fecha':         fila['fecha'],
            'tipo':          fila['tipo'],
            'capital':       fila['capital'],
            'intcte':        fila['intcte'],
            'cuota':         fila['cuota'],
            'saldo_capital': saldo_corriente,
        })

    return tabla
