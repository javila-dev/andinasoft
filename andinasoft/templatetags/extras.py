from django import template
from django.conf import settings
from django.core.files.storage import default_storage
from andinasoft.shared_models import titulares_por_adj,Adjudicacion
from andinasoft.models import clientes, asesores

register = template.Library()

@register.filter(name='has_group')
def has_group(user,group_name):
    if not user.is_superuser:
        return user.groups.filter(name=group_name).exists()
    else:
        return False

@register.filter(name='is_cartera')
def is_cartera(user):
    return user.groups.filter(name='Gestor Cartera').exists()

@register.filter(name='titular_adj')
def titular_adj(adj,proyecto):
    obj_adj = titulares_por_adj.objects.using(proyecto).get(adj=adj)
    titular = obj_adj.titular1
    return titular

@register.filter(name='nombre_cliente')
def nombre_cliente(id_cliente):
    obj_cliente = clientes.objects.filter(pk=id_cliente)
    if obj_cliente.exists():
        return obj_cliente[0].nombrecompleto
    return ""

@register.filter(name='nombre_asesor')
def nombre_asesor(id_asesor):
    obj_asesor = asesores.objects.filter(pk=id_asesor)
    if obj_asesor.exists():
        return obj_asesor[0].nombre
    return ""

@register.filter(name='replace_null')
def replace_null(value,replace):
    if value is None:
        return replace
    return value

@register.filter(name='nombre_mes')
def nombre_mes(mes):
    meses={
        1:'Ene',
        2:'Feb',
        3:'Mar',
        4:'Abr',
        5:'May',
        6:'Jun',
        7:'Jul',
        8:'Ago',
        9:'Sep',
        10:'Oct',
        11:'Nov',
        12:'Dic'
    }
    return meses[mes]

@register.filter(name='nombre_numero')
def nombre_numero(numero):
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
    
    valor_letras = valor_letras.replace(' DE ',''
        ).replace('PESOS M/CTE','')
    
    return valor_letras
    

@register.filter(name='dia_en_letras')
def dia_en_letras(dia):
    nombres = {
        1:'uno', 2:'dos', 3:'tres', 4:'cuatro', 5:'cinco',
        6:'seis', 7:'siete', 8:'ocho', 9:'nueve', 10:'diez',
        11:'once', 12:'doce', 13:'trece', 14:'catorce', 15:'quince',
        16:'dieciséis', 17:'diecisiete', 18:'dieciocho', 19:'diecinueve',
        20:'veinte', 21:'veintiuno', 22:'veintidós', 23:'veintitrés',
        24:'veinticuatro', 25:'veinticinco', 26:'veintiséis', 27:'veintisiete',
        28:'veintiocho', 29:'veintinueve', 30:'treinta', 31:'treinta y uno',
    }
    try:
        return nombres.get(int(dia), str(dia))
    except (ValueError, TypeError):
        return str(dia)


@register.filter(name='porcentaje')
def porcentaje(value,total):
    if total==0:
        return '-'
    porcentaje=value*100/total
    porcentaje=f'{porcentaje:.2f}%'
    return porcentaje

@register.filter(name='porcentaje_entero')
def porcentaje_entero(value,total):
    if total==0:
        return '0'
    porcentaje=value*100/total
    porcentaje=f'{porcentaje:.2f}'
    return porcentaje


@register.filter(name='media_url')
def media_url(path):
    if not path:
        return ''
    path = str(path)
    if path.startswith('http://') or path.startswith('https://'):
        return path

    media_url = getattr(settings, 'MEDIA_URL', '/media/') or '/media/'
    normalized = path.strip()

    if media_url and normalized.startswith(media_url):
        normalized = normalized[len(media_url):]
    elif normalized.startswith('/media/'):
        normalized = normalized[len('/media/'):]

    normalized = normalized.lstrip('/').replace('\\', '/')

    if normalized.startswith('static_media/'):
        normalized = normalized[len('static_media/'):]

    try:
        return default_storage.url(normalized)
    except Exception:
        return f'/media/{normalized}'
