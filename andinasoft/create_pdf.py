from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.pdfmetrics import registerFontFamily,stringWidth, getFont
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, Frame, Image, Spacer, SimpleDocTemplate, Table, TableStyle
from reportlab.platypus import PageTemplate, BaseDocTemplate, NextPageTemplate, NextFrameFlowable, FrameBreak, PageBreak
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.pagesizes import A4, LEGAL
from reportlab.lib.units import inch, mm
from reportlab.pdfgen.canvas import Canvas
from datetime import datetime
from andinasoft.utilities import Utilidades
from django.db.models import Max, Sum
import reportlab
import os
import traceback
import locale
from datetime import datetime
from functools import partial
from django.conf import settings

if settings.LIVE:
  locale.setlocale(locale.LC_ALL,'es_CO.UTF-8')
else:
  locale.setlocale(locale.LC_ALL,'es_CO.UTF-8')

class GenerarPDF():
    
    def __init__(self):
        reportlab.rl_config.TTFSearchPath.append('./resources/fonts')
        pdfmetrics.registerFont(TTFont('arial','./resources/fonts/arial.ttf'))
        pdfmetrics.registerFont(TTFont('arialbd','./resources/fonts/arialbd.ttf'))
        pdfmetrics.registerFont(TTFont('ariali','./resources/fonts/ariali.ttf'))
        registerFontFamily('arial',normal='arial',bold='arialbd',italic='ariali')
        pdfmetrics.registerFont(TTFont('centuryG','./resources/fonts/gothic.ttf'))
        pdfmetrics.registerFont(TTFont('centuryGB','./resources/fonts/gothicb.ttf'))
        registerFontFamily('centuryg',normal='centuryG',bold='centuryGB')
        pdfmetrics.registerFont(TTFont('ComicS','./resources/fonts/comic.ttf'))
        pdfmetrics.registerFont(TTFont('ComicSbd','./resources/fonts/comicbd.ttf'))
        pdfmetrics.registerFont(TTFont('ComicSz','./resources/fonts/comicz.ttf'))
        pdfmetrics.registerFont(TTFont('ComicSi','./resources/fonts/comici.ttf'))
        registerFontFamily('comicS',normal='ComicS',bold='ComicSbd',boldItalic='comciSz',italic='ComicSi')
        self.meses=("Enero","Febrero","Marzo","Abril","Mayo","Junio","Julio",
                    "Agosto","Septiembre","Octubre","Noviembre","Diciembre")
        self.logos={
              'Tesoro Escondido':'./resources/Logos/logo-Tesoro-Escondido.png',
              'Vegas de Venecia':'./resources/Logos/logo-vegas-de-venecia.png',
              'Sandville Beach':'./resources/Logos/sandville beach.png',
              'Perla del Mar':'./resources/Logos/Perla del Mar.png',
              'Sandville del Sol':'./resources/Logos/Perla del Mar.png',
              'Sotavento':'./resources/Logos/logo-sotavento.png',
              'Alttum Collection':'',
              'Quadrata Constructores':'./resources/Logos/quadrata.png'
            }

    def ExportOpcionContratoVenecia(self,nro_contrato,nombre_t1,cc_t1,tel_t1,cel_t1,
                                    ofic_t1,cdof_t1,telof_t1,
                                    resid_t1,cdresid_t1,telresid_t1,email_t1,
                                    nombre_t2,cc_t2,tel_t2,cel_t2,
                                    ofic_t2,cdof_t2,telof_t2,
                                    resid_t2,cdresid_t2,telresid_t2,email_t2,
                                    nombre_t3,cc_t3,tel_t3,cel_t3,
                                    ofic_t3,cdof_t3,telof_t3,
                                    resid_t3,cdresid_t3,telresid_t3,email_t3,
                                    nombre_t4,cc_t4,tel_t4,cel_t4,
                                    ofic_t4,cdof_t4,telof_t4,
                                    resid_t4,cdresid_t4,telresid_t4,email_t4,
                                    lote,manzana,area,mtsnorte,colnorte,
                                    mtseste,coleste,mtssur,colsur,
                                    mtsoeste,coloeste,
                                    valor,valor_letras,ci,saldo,
                                    contado_x,credic_x,amort_x,
                                    formaCI,formaFN,obs,
                                    dia_contrato,mes_contrato,año_contrato,ruta):
        
        story=[]
        frames_pag1=[]
     # Imagen base del doc
        frame_base=Frame(0,0,216*mm,356*mm)
        frames_pag1.append(frame_base)
        pagina1=Image('./resources/Contrato de opcion de compra Venecia-1.png',width=214*mm,height=350*mm)
        story.append(pagina1)
        story.append(FrameBreak())
        
        estilo_nro=ParagraphStyle('numero',fontName='centuryg',fontSize=14,textColor='#F78369')
        frame_nro=Frame(143*mm,322*mm,40*mm,20*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_nro)
        story.append(Paragraph('<b>Nº {}</b>'.format(nro_contrato),estilo_nro))
        story.append(FrameBreak())
     # Titulares
        estilo_titulares=ParagraphStyle('estilo',fontName='centuryg',fontSize=9)
        estilo_titulares_peq=ParagraphStyle('estilo',fontName='centuryg',fontSize=8)
      # Titular 1
        frame_nombre1=Frame(30*mm,294*mm,76.5*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_nombre1)
        story.append(Paragraph(nombre_t1,estilo_titulares))
        story.append(FrameBreak())
        
        frame_cc1=Frame(114*mm,294*mm,24.5*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_cc1)
        story.append(Paragraph(cc_t1,estilo_titulares))
        story.append(FrameBreak())
        
        frame_tel1=Frame(144*mm,294*mm,23.2*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_tel1)
        story.append(Paragraph(tel_t1,estilo_titulares_peq))
        story.append(FrameBreak())
        
        frame_cel1=Frame(173*mm,294*mm,26.7*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_cel1)
        story.append(Paragraph(cel_t1,estilo_titulares_peq))
        story.append(FrameBreak())
        
        frame_oficina=Frame(26.5*mm,287*mm,81*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_oficina)
        story.append(Paragraph(ofic_t1,estilo_titulares_peq))
        story.append(FrameBreak())
        
        frame_cdof1=Frame(127*mm,287*mm,30.3*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_cdof1)
        story.append(Paragraph(cdof_t1,estilo_titulares))
        story.append(FrameBreak())
        
        frame_telof1=Frame(171*mm,287*mm,29*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_telof1)
        story.append(Paragraph(telof_t1,estilo_titulares))
        story.append(FrameBreak())
        
        frame_resid=Frame(30.5*mm,279.5*mm,76.5*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_resid)
        story.append(Paragraph(resid_t1[:36],estilo_titulares_peq))
        story.append(FrameBreak())
        
        frame_cdres1=Frame(127*mm,279.5*mm,31*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_cdres1)
        story.append(Paragraph(cdresid_t1[:19],estilo_titulares))
        story.append(FrameBreak())
        
        frame_telres1=Frame(171.5*mm,279.5*mm,29*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_telres1)
        story.append(Paragraph(telresid_t1,estilo_titulares))
        story.append(FrameBreak())
        
        frame_email1=Frame(26*mm,273*mm,81*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_email1)
        story.append(Paragraph(email_t1,estilo_titulares))
        story.append(FrameBreak())
        
      # Titular 2
        distancia=28.7*mm
        frame_nombre2=Frame(30*mm,294*mm-distancia,76.5*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_nombre2)
        story.append(Paragraph(nombre_t2,estilo_titulares))
        story.append(FrameBreak())
        
        frame_cc2=Frame(114*mm,294*mm-distancia,24.5*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_cc2)
        story.append(Paragraph(cc_t2,estilo_titulares))
        story.append(FrameBreak())
        
        frame_tel2=Frame(144*mm,294*mm-distancia,23.2*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_tel2)
        story.append(Paragraph(tel_t2,estilo_titulares_peq))
        story.append(FrameBreak())
        
        frame_cel2=Frame(173*mm,294*mm-distancia,26.7*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_cel2)
        story.append(Paragraph(cel_t2,estilo_titulares_peq))
        story.append(FrameBreak())
        
        frame_oficina2=Frame(26.5*mm,287*mm-distancia,81*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_oficina2)
        story.append(Paragraph(ofic_t2,estilo_titulares))
        story.append(FrameBreak())
        
        frame_cdof2=Frame(127*mm,287*mm-distancia,30.3*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_cdof2)
        story.append(Paragraph(cdof_t2,estilo_titulares))
        story.append(FrameBreak())
        
        frame_telof2=Frame(171*mm,287*mm-distancia,29*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_telof2)
        story.append(Paragraph(telof_t2,estilo_titulares_peq))
        story.append(FrameBreak())
        
        frame_resid2=Frame(30.5*mm,279.5*mm-distancia,76.5*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_resid2)
        story.append(Paragraph(resid_t2,estilo_titulares_peq))
        story.append(FrameBreak())
        
        frame_cdres2=Frame(127*mm,279.5*mm-distancia,31*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_cdres2)
        story.append(Paragraph(cdresid_t2[:19],estilo_titulares))
        story.append(FrameBreak())
        
        frame_telres2=Frame(171.5*mm,279.5*mm-distancia,29*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_telres2)
        story.append(Paragraph(telresid_t2,estilo_titulares))
        story.append(FrameBreak())
        
        frame_email2=Frame(26*mm,273*mm-distancia,81*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_email2)
        story.append(Paragraph(email_t2,estilo_titulares))
        story.append(FrameBreak())
        
      # Titular 3
        distancia=28.7*mm*2
        frame_nombre3=Frame(30*mm,294*mm-distancia,76.5*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_nombre3)
        story.append(Paragraph(nombre_t3,estilo_titulares))
        story.append(FrameBreak())
        
        frame_cc3=Frame(114*mm,294*mm-distancia,24.5*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_cc3)
        story.append(Paragraph(cc_t3,estilo_titulares))
        story.append(FrameBreak())
        
        frame_tel3=Frame(144*mm,294*mm-distancia,23.2*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_tel3)
        story.append(Paragraph(tel_t3,estilo_titulares))
        story.append(FrameBreak())
        
        frame_cel3=Frame(173*mm,294*mm-distancia,26.7*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_cel3)
        story.append(Paragraph(cel_t3,estilo_titulares))
        story.append(FrameBreak())
        
        frame_oficina3=Frame(26.5*mm,287*mm-distancia,81*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_oficina3)
        story.append(Paragraph(ofic_t3,estilo_titulares))
        story.append(FrameBreak())
        
        frame_cdof3=Frame(127*mm,287*mm-distancia,30.3*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_cdof3)
        story.append(Paragraph(cdof_t3,estilo_titulares))
        story.append(FrameBreak())
        
        frame_telof3=Frame(171*mm,287*mm-distancia,29*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_telof3)
        story.append(Paragraph(telof_t3,estilo_titulares))
        story.append(FrameBreak())
        
        frame_resid3=Frame(30.5*mm,279.5*mm-distancia,76.5*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_resid3)
        story.append(Paragraph(resid_t3,estilo_titulares))
        story.append(FrameBreak())
        
        frame_cdres3=Frame(127*mm,279.5*mm-distancia,31*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_cdres3)
        story.append(Paragraph(cdresid_t3[:19],estilo_titulares))
        story.append(FrameBreak())
        
        frame_telres3=Frame(171.5*mm,279.5*mm-distancia,29*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_telres3)
        story.append(Paragraph(telresid_t3,estilo_titulares))
        story.append(FrameBreak())
        
        frame_email3=Frame(26*mm,273*mm-distancia,81*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_email3)
        story.append(Paragraph(email_t3,estilo_titulares))
        story.append(FrameBreak())
      
      # Titular 4
        distancia=28.7*mm*3
        frame_nombre4=Frame(30*mm,294*mm-distancia,76.5*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_nombre4)
        story.append(Paragraph(nombre_t4,estilo_titulares))
        story.append(FrameBreak())
        
        frame_cc4=Frame(114*mm,294*mm-distancia,24.5*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_cc4)
        story.append(Paragraph(cc_t4,estilo_titulares))
        story.append(FrameBreak())
        
        frame_tel4=Frame(144*mm,294*mm-distancia,23.2*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_tel4)
        story.append(Paragraph(tel_t4,estilo_titulares))
        story.append(FrameBreak())
        
        frame_cel4=Frame(173*mm,294*mm-distancia,26.7*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_cel4)
        story.append(Paragraph(cel_t4,estilo_titulares))
        story.append(FrameBreak())
        
        frame_oficina4=Frame(26.5*mm,287*mm-distancia,81*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_oficina4)
        story.append(Paragraph(ofic_t4,estilo_titulares))
        story.append(FrameBreak())
        
        frame_cdof4=Frame(127*mm,287*mm-distancia,30.3*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_cdof4)
        story.append(Paragraph(cdof_t4,estilo_titulares))
        story.append(FrameBreak())
        
        frame_telof4=Frame(171*mm,287*mm-distancia,29*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_telof4)
        story.append(Paragraph(telof_t4,estilo_titulares))
        story.append(FrameBreak())
        
        frame_resid4=Frame(30.5*mm,279.5*mm-distancia,76.5*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_resid4)
        story.append(Paragraph(resid_t4,estilo_titulares))
        story.append(FrameBreak())
        
        frame_cdres4=Frame(127*mm,279.5*mm-distancia,31*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_cdres4)
        story.append(Paragraph(cdresid_t4[:19],estilo_titulares))
        story.append(FrameBreak())
        
        frame_telres4=Frame(171.5*mm,279.5*mm-distancia,29*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_telres4)
        story.append(Paragraph(telresid_t4,estilo_titulares))
        story.append(FrameBreak())
        
        frame_email4=Frame(26*mm,273*mm-distancia,81*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_email4)
        story.append(Paragraph(email_t4,estilo_titulares))
        story.append(FrameBreak())
    
     # Datos Inmueble
        estilo_inmueble=ParagraphStyle('inmueble',fontName='centuryg',fontSize=9,alignment=1)
        frame_lote=Frame(23*mm,153.7*mm,12*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        frames_pag1.append(frame_lote)
        story.append(Paragraph(lote,estilo_inmueble))
        story.append(FrameBreak())
        
        frame_manzana=Frame(48.5*mm,153.7*mm,12*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        frames_pag1.append(frame_manzana)
        story.append(Paragraph(manzana,estilo_inmueble))
        story.append(FrameBreak())
        
        frame_area=Frame(68.6*mm,153.7*mm,12*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        frames_pag1.append(frame_area)
        story.append(Paragraph(area,estilo_inmueble))
        story.append(FrameBreak())
        
        frame_mtsnorte=Frame(32.9*mm,145*mm,22.17*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        frames_pag1.append(frame_mtsnorte)
        story.append(Paragraph(mtsnorte,estilo_inmueble))
        story.append(FrameBreak())
        
        frame_colnorte=Frame(72.6*mm,145*mm,33.7*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        frames_pag1.append(frame_colnorte)
        story.append(Paragraph(colnorte,estilo_inmueble))
        story.append(FrameBreak())
        
        frame_mtseste=Frame(127.8*mm,145*mm,23.55*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        frames_pag1.append(frame_mtseste)
        story.append(Paragraph(mtseste,estilo_inmueble))
        story.append(FrameBreak())
        
        frame_coleste=Frame(170.5*mm,145*mm,31.4*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        frames_pag1.append(frame_coleste)
        story.append(Paragraph(coleste,estilo_inmueble))
        story.append(FrameBreak())
        
        frame_mtssur=Frame(30.5*mm,135.8*mm,24.47*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        frames_pag1.append(frame_mtssur)
        story.append(Paragraph(mtssur,estilo_inmueble))
        story.append(FrameBreak())
        
        frame_colsur=Frame(72.6*mm,135.8*mm,33.7*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        frames_pag1.append(frame_colsur)
        story.append(Paragraph(colsur,estilo_inmueble))
        story.append(FrameBreak())
        
        frame_mtsoeste=Frame(127.8*mm,135.8*mm,23.55*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        frames_pag1.append(frame_mtsoeste)
        story.append(Paragraph(mtsoeste,estilo_inmueble))
        story.append(FrameBreak())
        
        frame_coloeste=Frame(170.5*mm,135.8*mm,31.4*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        frames_pag1.append(frame_coloeste)
        story.append(Paragraph(coloeste,estilo_inmueble))
        story.append(FrameBreak())
        
     # Precio y Forma de pago
        estilo_precio=ParagraphStyle('precio',fontName='centuryg',fontSize=10)
        frame_precio=Frame(142*mm,107*mm,58.3*mm,5.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        frames_pag1.append(frame_precio)
        story.append(Paragraph('<b>{:,}</b>'.format(valor),estilo_precio))
        story.append(FrameBreak())
        
        frame_valorletras=Frame(41*mm,101.42*mm,160*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        frames_pag1.append(frame_valorletras)
        story.append(Paragraph(valor_letras,estilo_titulares))
        story.append(FrameBreak())
        
        frame_ctainicial=Frame(50*mm,89.9*mm,49*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        frames_pag1.append(frame_ctainicial)
        story.append(Paragraph('{:,}'.format(ci),estilo_precio))
        story.append(FrameBreak())
        
        frame_saldo=Frame(148.5*mm,89.9*mm,49*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        frames_pag1.append(frame_saldo)
        story.append(Paragraph('{:,}'.format(saldo),estilo_precio))
        story.append(FrameBreak())
        
        frame_contado=Frame(131*mm,81.5*mm,5.5*mm,4.5*mm,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        frames_pag1.append(frame_contado)
        story.append(Paragraph(contado_x,estilo_precio))
        story.append(FrameBreak())
        
        frame_credic=Frame(150.5*mm,81.5*mm,5.5*mm,4.5*mm,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        frames_pag1.append(frame_credic)
        story.append(Paragraph(credic_x,estilo_precio))
        story.append(FrameBreak())
        
        frame_amort=Frame(178*mm,81.5*mm,5.5*mm,4.5*mm,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        frames_pag1.append(frame_amort)
        story.append(Paragraph(amort_x,estilo_precio))
        story.append(FrameBreak())
        
        estilo_formas=ParagraphStyle('precio',fontName='centuryg',fontSize=7,leading=20,alignment=4)
        estilo_formas_ci=ParagraphStyle('precio',fontName='centuryg',fontSize=5,leading=20,alignment=4)
        
        frame_formaCI=Frame(18*mm,40.2*mm,88.3*mm,37*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        frames_pag1.append(frame_formaCI)
        story.append(Paragraph(formaCI,estilo_formas_ci))
        story.append(FrameBreak())
        
        frame_formaFN=Frame(112.5*mm,50.2*mm,88.3*mm,27*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        frames_pag1.append(frame_formaFN)
        story.append(Paragraph(formaFN,estilo_formas))
        story.append(FrameBreak())
        
        estilo_obs=ParagraphStyle('precio',fontName='centuryg',fontSize=5,leading=10)
        frame_obs2=Frame(18*mm,30.5*mm,186*mm,15*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        frames_pag1.append(frame_obs2)
        story.append(Paragraph('&nbsp '*64+obs,estilo_obs))
        
        
        
     #respaldo
        
        story.append(NextPageTemplate('pagina2'))
        frames_pag2=[]
        frames_pag2.append(frame_base)
        
        
        pagina2=Image('./resources/Contrato de opcion de compra Venecia-2.png',width=214*mm,height=350*mm)
        story.append(pagina2)
        
        estilo_fecha=ParagraphStyle('fecha contrato',fontName='centuryg',fontSize=9,alignment=1)
      # Titular 1
        frame_dia=Frame(104*mm,98.5*mm,10.5*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag2.append(frame_dia)
        story.append(Paragraph(dia_contrato,estilo_fecha))
        story.append(FrameBreak())
        
        frame_mes=Frame(133*mm,98.5*mm,34.6*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag2.append(frame_mes)
        story.append(Paragraph(Utilidades().NombreMes(mes_contrato),estilo_fecha))
        story.append(FrameBreak())
        
        frame_año=Frame(180.5*mm,98.5*mm,14*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag2.append(frame_año)
        story.append(Paragraph(año_contrato,estilo_fecha))
        story.append(FrameBreak())
        
        
        page1=PageTemplate(id='pagina1',frames=frames_pag1)
        page2=PageTemplate(id='pagina2',frames=frames_pag2)
        
        doc=BaseDocTemplate(ruta,pageTemplates=[page1,page2],pagesize=LEGAL)
        
        doc.build(story)
        
    def ExportPromesaSandvilleMar(self,nro_contrato,nombre_t1,cc_t1,tel_t1,cel_t1,
                                    ofic_t1,cdof_t1,telof_t1,
                                    resid_t1,cdresid_t1,telresid_t1,email_t1,
                                    nombre_t2,cc_t2,tel_t2,cel_t2,
                                    ofic_t2,cdof_t2,telof_t2,
                                    resid_t2,cdresid_t2,telresid_t2,email_t2,
                                    nombre_t3,cc_t3,tel_t3,cel_t3,
                                    ofic_t3,cdof_t3,telof_t3,
                                    resid_t3,cdresid_t3,telresid_t3,email_t3,
                                    nombre_t4,cc_t4,tel_t4,cel_t4,
                                    ofic_t4,cdof_t4,telof_t4,
                                    resid_t4,cdresid_t4,telresid_t4,email_t4,
                                    lote,manzana,area,mtsnorte,colnorte,
                                    mtseste,coleste,mtssur,colsur,
                                    mtsoeste,coloeste,
                                    valor,valor_letras,ci,saldo,
                                    contado_x,credic_x,amort_x,
                                    formaCI,formaFN,obs,
                                    fecha_escritura,fecha_entrega,ciudad_entrega,
                                    dia_contrato,mes_contrato,año_contrato,ruta,
                                    nro_condominio,nombre_con,prorroga='360'):
        
        story=[]
        frames_pag1=[]
        grupos=[]
     # Imagen base del doc
        frame_base=Frame(0,0,216*mm,356*mm,id='framebase')
        frames_pag1.append(frame_base)
        pagina1=Image('./resources/Perla del Mar/FORMATO PROMESA PERLA DEL MAR V5 A 10.05.21.png',width=214*mm,height=350*mm)
        story.append(pagina1)
        story.append(FrameBreak())
        
        estilo_nro=ParagraphStyle('numero',alignment=1,fontName='centuryg',fontSize=14,textColor='#F78369',id='numero')
        frame_nro=Frame(185.9*mm,336.6*mm,22*mm,6*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_nro)
        story.append(Paragraph(f'<b>{int(nro_contrato):03d}</b>',estilo_nro))
        story.append(FrameBreak())
     # Titulares
        estilo_titulares=ParagraphStyle('estilo',fontName='centuryg',fontSize=9)
      # Titular 1
        frame_nombre1=Frame(30*mm,293.3*mm,130.5*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,id='nombre1')
        grupos.append((frame_nombre1,nombre_t1))
        
        frame_cc1=Frame(163*mm,293.3*mm,24.5*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,id='cc2')
        grupos.append((frame_cc1,cc_t1))
        
        frame_cel1=Frame(29*mm,274.2*mm,26.7*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,id='cel1')
        grupos.append((frame_cel1,cel_t1))
        
        frame_oficina=Frame(26.5*mm,280.1*mm,81*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,id='odicina1')
        grupos.append((frame_oficina,ofic_t1))
        
        frame_cdof1=Frame(123*mm,280.1*mm,30.3*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,id='cdof1')
        grupos.append((frame_cdof1,cdof_t1))
        
        frame_telof1=Frame(168.5*mm,280.1*mm,29*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,id='telfof1')
        grupos.append((frame_telof1,telof_t1))
        
        frame_resid=Frame(30.5*mm,286.8*mm,76.5*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,id='resid1')
        grupos.append((frame_resid,resid_t1))
        
        frame_cdres1=Frame(123*mm,286.8*mm,30.3*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,id='cdres1')
        grupos.append((frame_cdres1,cdresid_t1))
        
        frame_telres1=Frame(168.5*mm,286.8*mm,29*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,id='telres1')
        grupos.append((frame_telres1,telresid_t1))
        
        frame_email1=Frame(117.5*mm,274.2*mm,81*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,id='email1')
        grupos.append((frame_email1,email_t1))
        
      # Titular 2
        distancia=25.8*mm
        frame_nombre2=Frame(30*mm,293.3*mm-distancia,120.5*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,id='nombre2')
        grupos.append((frame_nombre2,nombre_t2))
        
        frame_cc2=Frame(163*mm,293.3*mm-distancia,24.5*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,id='cc2')
        grupos.append((frame_cc2,cc_t2))
                
        frame_cel2=Frame(29*mm,274.2*mm-distancia,26.7*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,id='cel2')
        grupos.append((frame_cel2,cel_t2))
        
        frame_oficina2=Frame(26.5*mm,280.1*mm-distancia,81*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,id='oficina2')
        grupos.append((frame_oficina2,ofic_t2))
        
        frame_cdof2=Frame(123*mm,280.1*mm-distancia,30.3*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,id='cdof2')
        grupos.append((frame_cdof2,cdof_t2))
        
        frame_telof2=Frame(168.5*mm,280.1*mm-distancia,29*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,id='telof2')
        grupos.append((frame_telof2,telof_t2))
        
        frame_resid2=Frame(30.5*mm,286.8*mm-distancia,76.5*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,id='resid2')
        grupos.append((frame_resid2,resid_t2))
        
        frame_cdres2=Frame(123*mm,286.8*mm-distancia,30.3*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,id='cdres2')
        grupos.append((frame_cdres2,cdresid_t2))
        
        frame_telres2=Frame(171.5*mm,286.8*mm-distancia,29*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,id='telres2')
        grupos.append((frame_telres2,telresid_t2))
        
        frame_email2=Frame(117.5*mm,274.2*mm-distancia,81*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,id='email2')
        grupos.append((frame_email2,email_t2))
      
      # Titular 3
        distancia=25.8*mm*2
        frame_nombre3=Frame(30*mm,293.3*mm-distancia,120.5*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,id='nombre3')
        grupos.append((frame_nombre3,nombre_t3))
        
        frame_cc3=Frame(163*mm,293.3*mm-distancia,24.5*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,id='cc3')
        grupos.append((frame_cc3,cc_t3))
        
        frame_cel3=Frame(29*mm,274.2*mm-distancia,26.7*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,id='cel3')
        grupos.append((frame_cel3,cel_t3))
        
        frame_oficina3=Frame(26.5*mm,280.1*mm-distancia,81*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,id='oficina3')
        grupos.append((frame_oficina3,ofic_t3))
        
        frame_cdof3=Frame(123*mm,280.1*mm-distancia,30.3*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,id='cdof3')
        grupos.append((frame_cdof3,cdof_t3))
        
        frame_telof3=Frame(168.5*mm,280.1*mm-distancia,29*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,id='telof3')
        grupos.append((frame_telof3,telof_t3))
        
        frame_resid3=Frame(30.5*mm,286.8*mm-distancia,76.5*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,id='resid3')
        grupos.append((frame_resid3,resid_t3))
        
        frame_cdres3=Frame(123*mm,286.8*mm-distancia,30.3*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,id='cdres3')
        grupos.append((frame_cdres3,cdresid_t3))
        
        frame_telres3=Frame(171.5*mm,286.8*mm-distancia,29*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,id='telres3')
        grupos.append((frame_telres3,telresid_t3))
        
        frame_email3=Frame(117.5*mm,274.2*mm-distancia,81*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,id='email3')
        grupos.append((frame_email3,email_t3))
        
      # Titular 4
        distancia=25.8*mm*3
        frame_nombre4=Frame(30*mm,293.3*mm-distancia,120.5*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,id='nombre4')
        grupos.append((frame_nombre4,nombre_t4))
                
        frame_cc4=Frame(163*mm,293.3*mm-distancia,24.5*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,id='cc4')
        grupos.append((frame_cc4,cc_t4))
        
        frame_cel4=Frame(29*mm,274.2*mm-distancia,26.7*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,id='cel4')
        grupos.append((frame_cel4,cel_t4))
        
        frame_oficina4=Frame(26.5*mm,280.1*mm-distancia,81*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,id='oficina4')
        grupos.append((frame_oficina4,ofic_t4))
        
        frame_cdof4=Frame(123*mm,280.1*mm-distancia,30.3*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,id='cdof4')
        grupos.append((frame_cdof4,cdof_t4))
        
        frame_telof4=Frame(168.5*mm,280.1*mm-distancia,29*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,id='telof4')
        grupos.append((frame_telof4,telof_t4))
                
        frame_resid4=Frame(30.5*mm,286.8*mm-distancia,76.5*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,id='resid4')
        grupos.append((frame_resid4,resid_t4))
        
        frame_cdres4=Frame(123*mm,286.8*mm-distancia,30.3*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,id='cdres4')
        grupos.append((frame_cdres4,cdresid_t4))
        
        frame_telres4=Frame(171.5*mm,286.8*mm-distancia,29*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,id='telres4')
        grupos.append((frame_telres4,telresid_t4))
        
        frame_email4=Frame(117.5*mm,274.2*mm-distancia,81*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,id='email4')
        grupos.append((frame_email4,email_t4))
    
        for grupo in grupos:
          contenido=grupo[1]
          if contenido!=None and contenido!='None':
            frame=grupo[0]
            fontName='centuryg'
            fontSize=9
            estilo=ParagraphStyle('estilo',fontName=fontName,fontSize=fontSize)
            flowable=Paragraph(contenido,estilo)
            textwidth=stringWidth(contenido,'centuryG',fontSize)
            i=1
            j=1
            while textwidth>frame._aW:
              if fontSize>6:
                fontSize-=i
              else:
                contenido=contenido[:len(contenido)-j]
              estilo=ParagraphStyle('estilo',fontName=fontName,fontSize=fontSize)
              flowable=Paragraph(contenido,estilo)
              textwidth=stringWidth(contenido,'centuryG',fontSize)
              i+=1
              j+=1
            frames_pag1.append(frame)
            story.append(flowable)
            story.append(FrameBreak())
        grupos=[]

     # Datos Inmueble
        estilo_inmueble=ParagraphStyle('inmueble',fontName='centuryg',fontSize=9,alignment=1)
        
        frame_nrocond=Frame(30*mm,170*mm,12*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0,id='lote')
        grupos.append((frame_nrocond,nro_condominio))
        
        frame_nombrecond=Frame(57.5*mm,170*mm,30*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0,id='lote')
        grupos.append((frame_nombrecond,nombre_con))
        
        frame_lote=Frame(21.3*mm,165.5*mm,12*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0,id='lote')
        grupos.append((frame_lote,lote))
                        
        frame_manzana=Frame(45.5*mm,165.5*mm,12*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0,id='manzana')
        grupos.append((frame_manzana,manzana))
        
        frame_area=Frame(62.2*mm,165.5*mm,12*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0,id='area')
        grupos.append((frame_area,area))
        
        frame_mtsnorte=Frame(32.9*mm,160.7*mm,22.17*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0,id='mtsnorte')
        grupos.append((frame_mtsnorte,mtsnorte))
        
        frame_colnorte=Frame(72.6*mm,160.7*mm,33.7*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0,id='colnorte')
        grupos.append((frame_colnorte,colnorte))
        
        frame_mtseste=Frame(127.8*mm,160.7*mm,23.55*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0,id='mtseste')
        grupos.append((frame_mtseste,mtseste))
        
        frame_coleste=Frame(170.5*mm,160.7*mm,31.4*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0,id='coleste')
        grupos.append((frame_coleste,coleste))
        
        frame_mtssur=Frame(30.5*mm,154.9*mm,24.47*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0,id='mtssur')
        grupos.append((frame_mtssur,mtssur))
        
        frame_colsur=Frame(72.6*mm,154.9*mm,33.7*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0,id='colsur')
        grupos.append((frame_colsur,colsur))
        
        frame_mtsoeste=Frame(127.8*mm,154.9*mm,23.55*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0,id='mtsoeste')
        grupos.append((frame_mtsoeste,mtsoeste))
        
        frame_coloeste=Frame(170.5*mm,154.9*mm,31.4*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0,id='coloeste')
        grupos.append((frame_coloeste,coloeste))
        
        frame_valorletras=Frame(10.6*mm,106.4*mm,104.8*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0,id='vrletras')
        grupos.append((frame_valorletras,valor_letras))
        
        for grupo in grupos:
          contenido=grupo[1]
          if contenido!=None and contenido!='None':
            frame=grupo[0]
            fontName='centuryg'
            fontSize=9
            estilo=ParagraphStyle('estilo',fontName=fontName,fontSize=fontSize,alignment=1)
            flowable=Paragraph(contenido,estilo)
            textwidth=stringWidth(contenido,'centuryG',fontSize)
            i=1
            j=1
            while textwidth>frame._aW:
              if fontSize>6:
                fontSize-=i
              else:
                contenido=contenido[:len(contenido)-j]
              estilo=ParagraphStyle('estilo',fontName=fontName,fontSize=fontSize)
              flowable=Paragraph(contenido,estilo)
              textwidth=stringWidth(contenido,'centuryG',fontSize)
              i+=1
              j+=1
            frames_pag1.append(frame)
            story.append(flowable)
            story.append(FrameBreak())
        grupos=[]
          
     # Precio y Forma de pago
        estilo_precio=ParagraphStyle('precio',fontName='centuryg',fontSize=10,alignment=1)
        frame_precio=Frame(119.1*mm,106.3*mm,29.3*mm,5.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0,id='precio')
        frames_pag1.append(frame_precio)
        story.append(Paragraph('<b>{:,}</b>'.format(valor),estilo_precio))
        story.append(FrameBreak())
                
        frame_ctainicial=Frame(54.5*mm,97.6*mm,49*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0,id='ctaini')
        frames_pag1.append(frame_ctainicial)
        story.append(Paragraph('{:,}'.format(ci),estilo_precio))
        story.append(FrameBreak())
        
        frame_saldo=Frame(154*mm,97.6*mm,49*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0,id='saldo')
        frames_pag1.append(frame_saldo)
        story.append(Paragraph('{:,}'.format(saldo),estilo_precio))
        story.append(FrameBreak())
        
        frame_contado=Frame(136.1*mm,92.4*mm,5.5*mm,4.5*mm,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0,id='contado')
        frames_pag1.append(frame_contado)
        story.append(Paragraph(contado_x,estilo_precio))
        story.append(FrameBreak())
        
        frame_credic=Frame(155.3*mm,92.4*mm,5.5*mm,4.5*mm,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0,id='credic')
        frames_pag1.append(frame_credic)
        story.append(Paragraph(credic_x,estilo_precio))
        story.append(FrameBreak())
        
        frame_amort=Frame(181.7*mm,92.4*mm,5.5*mm,4.5*mm,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0,id='amort')
        frames_pag1.append(frame_amort)
        story.append(Paragraph(amort_x,estilo_precio))
        story.append(FrameBreak())
        
        estilo_formas=ParagraphStyle('precio',fontName='centuryg',fontSize=7,leading=20,alignment=4)
        
        frame_formaCI=Frame(12.8*mm,64.7*mm,90*mm,28.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0,id='formaCI')
        frames_pag1.append(frame_formaCI)
        story.append(Paragraph(formaCI,estilo_formas))
        story.append(FrameBreak())
        
        frame_formaFN=Frame(112.5*mm,63.1*mm,90.3*mm,19.9*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0,id='formaFN')
        frames_pag1.append(frame_formaFN)
        aW = 90.3*mm
        aH = 19.9*mm
        p_formaFN = Paragraph(formaFN,estilo_formas)
        w, h = p_formaFN.wrap(aW,aH)
        i=1
        while w>=aW and h>=aH:
          estilo_forma_reducido = ParagraphStyle('precio',fontName='centuryg',fontSize=7-i,leading=20,alignment=4)
          p_formaFN = Paragraph(formaFN,estilo_forma_reducido)
          w, h = p_formaFN.wrap(aW,aH)
          i+=0.5
          
        story.append(p_formaFN)
        story.append(FrameBreak())
        
        
        
        estilo_obs=ParagraphStyle('precio',fontName='centuryg',fontSize=8,leading=20)
        frame_obs2=Frame(12.8*mm,46.8*mm,190*mm,14.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0,id='obs')
        frames_pag1.append(frame_obs2)
        story.append(Paragraph('&nbsp '*37+obs,estilo_obs))
        
     #pag 2
        
        story.append(NextPageTemplate('pagina2'))
        frames_pag2=[]
        frames_pag2.append(frame_base)
        if int(prorroga) == 360:
          pagina2=Image('./resources/Perla del Mar/FORMATO PROMESA PERLA DEL MAR V5 A 10.05.212.png',width=214*mm,height=350*mm)
        elif int(prorroga) == 180:
          pagina2=Image('./resources/Perla del Mar/FORMATO PROMESA PERLA DEL MAR V5 A 10.05.212-180.png',width=214*mm,height=350*mm)
        else:
          pagina2=Image('./resources/Perla del Mar/FORMATO PROMESA PERLA DEL MAR V5 A 10.05.212.png',width=214*mm,height=350*mm)
        story.append(pagina2)
        story.append(FrameBreak())
        
        diaescr=str(fecha_escritura.day)
        mesescr=Utilidades().NombreMes(fecha_escritura.month)
        añoescr=str(fecha_escritura.year)
        
        diaentr=str(fecha_entrega.day)
        mesentr=str(fecha_entrega.month)
        añoentr=str(fecha_entrega.year)
        
        notarias={
          'Monteria':'1',
          'Medellin':'26',
        }
        
        try: notaria=notarias[ciudad_entrega]
        except KeyError: notaria=''
        
        frame_diaescr=Frame(40.2*mm,322.2*mm,10*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,id='diaesc')
        grupos.append((frame_diaescr,diaescr))
        
        frame_mesescr=Frame(76.8*mm,322.2*mm,30*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,id='mesescr')
        grupos.append((frame_mesescr,mesescr))
        
        frame_añoescr=Frame(125.2*mm,322.2*mm,13.3*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,id='añoesc')
        grupos.append((frame_añoescr,añoescr))
        
        frame_notaria=Frame(165.6*mm,322.2*mm,13.8*mm,4.5*mm,id='notaria',showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_notaria,notaria))
        
        frame_ciudad=Frame(190*mm,322.2*mm,13.8*mm,4.5*mm,id='ciudad',showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_ciudad,ciudad_entrega))
        
        frame_diaentr=Frame(75.7*mm,276.6*mm,6.5*mm,4.5*mm,id='diaentrega',showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_diaentr,diaentr))
        
        frame_mesentr=Frame(100.2*mm,276.6*mm,12.6*mm,4.5*mm,id='mesentrega',showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_mesentr,mesentr))
        
        frame_añoentr=Frame(130.1*mm,276.6*mm,12.6*mm,4.5*mm,id='añoentrega',showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_añoentr,añoentr))
        
        group_counter=1
        for grupo in grupos:
          contenido=grupo[1]
          if contenido!=None and contenido!='None':
            frame=grupo[0]
            fontName='centuryg'
            fontSize=9
            estilo=ParagraphStyle('estilo',alignment=1,fontName=fontName,fontSize=fontSize)
            flowable=Paragraph(contenido,estilo)
            textwidth=stringWidth(contenido,'centuryG',fontSize)
            i=1
            j=1
            while textwidth>frame._aW:
              if fontSize>5:
                fontSize-=i
              else:
                contenido=contenido[:len(contenido)-j]
              estilo=ParagraphStyle('estilo',fontName=fontName,fontSize=fontSize)
              flowable=Paragraph(contenido,estilo)
              textwidth=stringWidth(contenido,'centuryG',fontSize)
              i+=1
              j+=1
            frames_pag2.append(frame)
            story.append(flowable)
            if group_counter<len(grupos):
              story.append(FrameBreak())
              group_counter+=1
              
        story.append(NextPageTemplate('pagina3'))
        frames_pag3=[]
        frames_pag3.append(frame_base)
        pagina3=Image('./resources/Perla del Mar/FORMATO PROMESA PERLA DEL MAR V5 A 10.05.213.png',width=214*mm,height=350*mm)
        story.append(pagina3)
        
        estilo_fecha=ParagraphStyle('fecha contrato',fontName='centuryg',fontSize=9,alignment=1)
      
        frame_dia=Frame(115.8*mm,250.8*mm,10.5*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag3.append(frame_dia)
        story.append(Paragraph(dia_contrato,estilo_fecha))
        story.append(FrameBreak())
        
        frame_mes=Frame(137*mm,250.8*mm,34.6*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag3.append(frame_mes)
        story.append(Paragraph(Utilidades().NombreMes(mes_contrato),estilo_fecha))
        story.append(FrameBreak())
        
        frame_año=Frame(175*mm,250.8*mm,14*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag3.append(frame_año)
        story.append(Paragraph(año_contrato,estilo_fecha))
        story.append(FrameBreak())
        
        page1=PageTemplate(id='pagina1',frames=frames_pag1)
        page2=PageTemplate(id='pagina2',frames=frames_pag2)
        page3=PageTemplate(id='pagina3',frames=frames_pag3)
        
        doc=BaseDocTemplate(ruta,pageTemplates=[page1,page2,page3],pagesize=LEGAL)
        
        doc.build(story)
    
    def ExportCBFVegasVenecia(self,nro_contrato,nombre_t1,cc_t1,tel_t1,cel_t1,
                                    ofic_t1,cdof_t1,telof_t1,
                                    resid_t1,cdresid_t1,telresid_t1,email_t1,
                                    nombre_t2,cc_t2,tel_t2,cel_t2,
                                    ofic_t2,cdof_t2,telof_t2,
                                    resid_t2,cdresid_t2,telresid_t2,email_t2,
                                    nombre_t3,cc_t3,tel_t3,cel_t3,
                                    ofic_t3,cdof_t3,telof_t3,
                                    resid_t3,cdresid_t3,telresid_t3,email_t3,
                                    nombre_t4,cc_t4,tel_t4,cel_t4,
                                    ofic_t4,cdof_t4,telof_t4,
                                    resid_t4,cdresid_t4,telresid_t4,email_t4,
                                    lote,manzana,area,mtsnorte,colnorte,
                                    mtseste,coleste,mtssur,colsur,
                                    mtsoeste,coloeste,
                                    valor,valor_letras,ci,saldo,
                                    contado_x,credic_x,amort_x,
                                    formaCI,formaFN,obs,
                                    fecha_escritura,fecha_entrega,ciudad_entrega,
                                    dia_contrato,mes_contrato,año_contrato,ruta,meses_entrega):
        
        story=[]
        frames_pag1=[]
        grupos=[]
     # Imagen base del doc
        frame_base=Frame(0,0,216*mm,356*mm)
        frames_pag1.append(frame_base)
        pagina1=Image('./resources/Perla del Mar/FORMATO PROMESA  BIEN FUTURO PERLA V2  A 09.08.22.png',width=214*mm,height=350*mm)
        story.append(pagina1)
        story.append(FrameBreak())
        
        estilo_nro=ParagraphStyle('numero',alignment=1,fontName='centuryg',fontSize=14,textColor='#F78369')
        frame_nro=Frame(148*mm,336.9*mm,22*mm,6*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_nro)
        story.append(Paragraph(f'<b>Nº {int(nro_contrato):03d}</b>',estilo_nro))
        story.append(FrameBreak())
     # Titulares
        estilo_titulares=ParagraphStyle('estilo',fontName='centuryg',fontSize=9)
      # Titular 1
        frame_nombre1=Frame(30*mm,285.2*mm,120.5*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_nombre1,nombre_t1))
        
        frame_cc1=Frame(163*mm,285.2*mm,24.5*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_cc1,cc_t1))
        
        frame_cel1=Frame(29*mm,266.2*mm,26.7*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_cel1,cel_t1))
        
        frame_oficina=Frame(26.5*mm,272.8*mm,81*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_oficina,ofic_t1))
        
        frame_cdof1=Frame(123*mm,272.8*mm,30.3*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_cdof1,cdof_t1))
        
        frame_telof1=Frame(168.5*mm,272.8*mm,29*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_telof1,telof_t1))
        
        frame_resid=Frame(30.5*mm,279.3*mm,76.5*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_resid,resid_t1))
        
        frame_cdres1=Frame(123*mm,279.3*mm,30.3*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_cdres1,cdresid_t1))
        
        frame_telres1=Frame(168.5*mm,279.3*mm,29*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_telres1,telresid_t1))
        
        frame_email1=Frame(117.5*mm,266.2*mm,81*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_email1,email_t1))
        
      # Titular 2
        distancia=28*mm
        frame_nombre2=Frame(30*mm,285.2*mm-distancia,120.5*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_nombre2,nombre_t2))
        
        frame_cc2=Frame(163*mm,285.2*mm-distancia,24.5*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_cc2,cc_t2))
                
        frame_cel2=Frame(29*mm,266.2*mm-distancia,26.7*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_cel2,cel_t2))
        
        frame_oficina2=Frame(26.5*mm,272.8*mm-distancia,81*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_oficina2,ofic_t2))
        
        frame_cdof2=Frame(123*mm,272.8*mm-distancia,30.3*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_cdof2,cdof_t2))
        
        frame_telof2=Frame(168.5*mm,272.8*mm-distancia,29*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_telof2,telof_t2))
        
        frame_resid2=Frame(30.5*mm,279.3*mm-distancia,76.5*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_resid2,resid_t2))
        
        frame_cdres2=Frame(123*mm,279.3*mm-distancia,30.3*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_cdres2,cdresid_t2))
        
        frame_telres2=Frame(171.5*mm,279.5*mm-distancia,29*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_telres2,telresid_t2))
        
        frame_email2=Frame(117.5*mm,266.2*mm-distancia,81*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_email2,email_t2))
      
      # Titular 3
        distancia=27.5*mm*2
        frame_nombre3=Frame(30*mm,285.2*mm-distancia,120.5*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_nombre3,nombre_t3))
        
        frame_cc3=Frame(163*mm,285.2*mm-distancia,24.5*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_cc3,cc_t3))
        
        frame_cel3=Frame(29*mm,266.2*mm-distancia,26.7*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_cel3,cel_t3))
        
        frame_oficina3=Frame(26.5*mm,272.8*mm-distancia,81*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_oficina3,ofic_t3))
        
        frame_cdof3=Frame(123*mm,272.8*mm-distancia,30.3*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_cdof3,cdof_t3))
        
        frame_telof3=Frame(168.5*mm,272.8*mm-distancia,29*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_telof3,telof_t3))
        
        frame_resid3=Frame(30.5*mm,279.3*mm-distancia,76.5*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_resid3,resid_t3))
        
        frame_cdres3=Frame(123*mm,279.3*mm-distancia,30.3*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_cdres3,cdresid_t3))
        
        frame_telres3=Frame(171.5*mm,279.5*mm-distancia,29*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_telres3,telresid_t3))
        
        frame_email3=Frame(117.5*mm,266.2*mm-distancia,81*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_email3,email_t3))
        
      # Titular 4
        distancia=27.3*mm*3
        frame_nombre4=Frame(30*mm,285.2*mm-distancia,120.5*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_nombre4,nombre_t4))
                
        frame_cc4=Frame(163*mm,285.2*mm-distancia,24.5*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_cc4,cc_t4))
        
        frame_cel4=Frame(29*mm,266.2*mm-distancia,26.7*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_cel4,cel_t4))
        
        frame_oficina4=Frame(26.5*mm,272.8*mm-distancia,81*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_oficina4,ofic_t4))
        
        frame_cdof4=Frame(123*mm,272.8*mm-distancia,30.3*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_cdof4,cdof_t4))
        
        frame_telof4=Frame(168.5*mm,272.8*mm-distancia,29*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_telof4,telof_t4))
                
        frame_resid4=Frame(30.5*mm,279.3*mm-distancia,76.5*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_resid4,resid_t4))
        
        frame_cdres4=Frame(123*mm,279.3*mm-distancia,30.3*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_cdres4,cdresid_t4))
        
        frame_telres4=Frame(171.5*mm,279.5*mm-distancia,29*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_telres4,telresid_t4))
        
        frame_email4=Frame(117.5*mm,266.2*mm-distancia,81*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_email4,email_t4))
    
        for grupo in grupos:
          contenido=grupo[1]
          if contenido!=None and contenido!='None':
            frame=grupo[0]
            fontName='centuryg'
            fontSize=9
            estilo=ParagraphStyle('estilo',fontName=fontName,fontSize=fontSize)
            flowable=Paragraph(contenido,estilo)
            textwidth=stringWidth(contenido,'centuryG',fontSize)
            i=1
            j=1
            while textwidth>frame._aW:
              if fontSize>6:
                fontSize-=i
              else:
                contenido=contenido[:len(contenido)-j]
              estilo=ParagraphStyle('estilo',fontName=fontName,fontSize=fontSize)
              flowable=Paragraph(contenido,estilo)
              textwidth=stringWidth(contenido,'centuryG',fontSize)
              i+=1
              j+=1
            frames_pag1.append(frame)
            story.append(flowable)
            story.append(FrameBreak())
        grupos=[]

     # Datos Inmueble
        estilo_inmueble=ParagraphStyle('inmueble',fontName='centuryg',fontSize=9,alignment=1)
        
        frame_lote=Frame(21.7*mm,107.5*mm,12*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        grupos.append((frame_lote,lote))
                        
        frame_manzana=Frame(47*mm,107.5*mm,12*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        grupos.append((frame_manzana,manzana))
        
        frame_area=Frame(65.2*mm,107.5*mm,12*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        grupos.append((frame_area,area))
        
        frame_mtsnorte=Frame(32.9*mm,97.7*mm,22.17*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        grupos.append((frame_mtsnorte,mtsnorte))
        
        frame_colnorte=Frame(72.6*mm,97.7*mm,33.7*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        grupos.append((frame_colnorte,colnorte))
        
        frame_mtseste=Frame(127.8*mm,97.7*mm,23.55*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        grupos.append((frame_mtseste,mtseste))
        
        frame_coleste=Frame(170.5*mm,97.7*mm,31.4*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        grupos.append((frame_coleste,coleste))
        
        frame_mtssur=Frame(30.5*mm,88.4*mm,24.47*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        grupos.append((frame_mtssur,mtssur))
        
        frame_colsur=Frame(72.6*mm,88.4*mm,33.7*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        grupos.append((frame_colsur,colsur))
        
        frame_mtsoeste=Frame(127.8*mm,88.4*mm,23.55*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        grupos.append((frame_mtsoeste,mtsoeste))
        
        frame_coloeste=Frame(170.5*mm,88.4*mm,31.4*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        grupos.append((frame_coloeste,coloeste))
        
        for grupo in grupos:
          contenido=grupo[1]
          if contenido!=None and contenido!='None':
            frame=grupo[0]
            fontName='centuryg'
            fontSize=9
            estilo=ParagraphStyle('estilo',fontName=fontName,fontSize=fontSize,alignment=1)
            flowable=Paragraph(contenido,estilo)
            textwidth=stringWidth(contenido,'centuryG',fontSize)
            i=1
            j=1
            while textwidth>frame._aW:
              if fontSize>6:
                fontSize-=i
              else:
                contenido=contenido[:len(contenido)-j]
              estilo=ParagraphStyle('estilo',fontName=fontName,fontSize=fontSize)
              flowable=Paragraph(contenido,estilo)
              textwidth=stringWidth(contenido,'centuryG',fontSize)
              i+=1
              j+=1
            frames_pag1.append(frame)
            story.append(flowable)
            if grupos.index(grupo) + 1 < len(grupos):
              story.append(FrameBreak())
        grupos=[]
          
     #pag 2
        
        story.append(NextPageTemplate('pagina2'))
        frames_pag2=[]
        frames_pag2.append(frame_base)
        pagina2=Image('./resources/Perla del Mar/FORMATO PROMESA  BIEN FUTURO PERLA V2  A 09.08.222.png',width=214*mm,height=350*mm)
        story.append(pagina2)
        
        
        # Precio y Forma de pago
        frame_valorletras=Frame(13.1*mm,307.8*mm,93*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        grupos.append((frame_valorletras,valor_letras))
     
        estilo_precio=ParagraphStyle('precio',fontName='centuryg',fontSize=10)
        frame_precio=Frame(140.8*mm,307*mm,58.3*mm,5.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        frames_pag2.append(frame_precio)
        story.append(Paragraph('<b>{:,}</b>'.format(valor),estilo_precio))
        story.append(FrameBreak())
                
        frame_ctainicial=Frame(60.5*mm,297.8*mm,49*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        frames_pag2.append(frame_ctainicial)
        story.append(Paragraph('{:,}'.format(ci),estilo_precio))
        story.append(FrameBreak())
        
        frame_saldo=Frame(154*mm,297.8*mm,49*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        frames_pag2.append(frame_saldo)
        story.append(Paragraph('{:,}'.format(saldo),estilo_precio))
        story.append(FrameBreak())
        
        frame_contado=Frame(137.4*mm,292.9*mm,5.5*mm,4.5*mm,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        frames_pag2.append(frame_contado)
        story.append(Paragraph(contado_x,estilo_precio))
        story.append(FrameBreak())
        
        frame_credic=Frame(156.2*mm,292.9*mm,5.5*mm,4.5*mm,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        frames_pag2.append(frame_credic)
        story.append(Paragraph(credic_x,estilo_precio))
        story.append(FrameBreak())
        
        frame_amort=Frame(182.2*mm,292.9*mm,5.5*mm,4.5*mm,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        frames_pag2.append(frame_amort)
        story.append(Paragraph(amort_x,estilo_precio))
        story.append(FrameBreak())
        
        estilo_formas=ParagraphStyle('precio',fontName='centuryg',fontSize=7,leading=20,alignment=4)
        
        frame_formaCI=Frame(12.8*mm,264.5*mm,90*mm,29*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        frames_pag2.append(frame_formaCI)
        story.append(Paragraph(formaCI,estilo_formas))
        story.append(FrameBreak())
        
        frame_formaFN=Frame(112.5*mm,265*mm,88.3*mm,18.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        frames_pag2.append(frame_formaFN)
        story.append(Paragraph(formaFN,estilo_formas))
        story.append(FrameBreak())
        
        estilo_obs=ParagraphStyle('precio',fontName='centuryg',fontSize=8,leading=20)
        frame_obs2=Frame(12.8*mm,240*mm,190*mm,22.7*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        frames_pag2.append(frame_obs2)
        story.append(Paragraph('&nbsp '*41+obs,estilo_obs))
        story.append(FrameBreak())
        
        
        diaescr=str(fecha_escritura.day)
        mesescr=Utilidades().NombreMes(fecha_escritura.month)
        añoescr=str(fecha_escritura.year)
        
        """ diaentr=str(fecha_entrega.day)
        mesentr=str(fecha_entrega.month)
        añoentr=str(fecha_entrega.year) """
        
        notarias={
          'Monteria':'1',
          'Medellin':'26',
        }
        
        try: notaria=notarias[ciudad_entrega]
        except KeyError: notaria=''
        
        frame_diaescr=Frame(178*mm,184.5*mm,10*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_diaescr,diaescr))
        
        frame_mesescr=Frame(6.6*mm,180.6*mm,30*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_mesescr,mesescr))
        
        frame_añoescr=Frame(39.3*mm,180.6*mm,13.3*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_añoescr,añoescr))
        
        frame_notaria=Frame(75.3*mm,180.6*mm,13.8*mm,4.5*mm,id='notaria',showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_notaria,notaria))
        
        frame_ciudad=Frame(98.6*mm,180.6*mm,13.8*mm,4.5*mm,id='ciudad',showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_ciudad,ciudad_entrega))
        
        frame_meses_entrega=Frame(180.8*mm,74.8*mm,10*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        grupos.append((frame_meses_entrega,meses_entrega))
        
        group_counter=1
        for grupo in grupos:
          contenido=grupo[1]
          if contenido!=None and contenido!='None':
            frame=grupo[0]
            fontName='centuryg'
            fontSize=9
            estilo=ParagraphStyle('estilo',alignment=1,fontName=fontName,fontSize=fontSize)
            flowable=Paragraph(contenido,estilo)
            textwidth=stringWidth(contenido,'centuryG',fontSize)
            i=1
            j=1
            while textwidth>frame._aW:
              if fontSize>5:
                fontSize-=i
              else:
                contenido=contenido[:len(contenido)-j]
              estilo=ParagraphStyle('estilo',fontName=fontName,fontSize=fontSize)
              flowable=Paragraph(contenido,estilo)
              textwidth=stringWidth(contenido,'centuryG',fontSize)
              i+=1
              j+=1
            frames_pag2.append(frame)
            story.append(flowable)
            if group_counter<len(grupos):
              story.append(FrameBreak())
              group_counter+=1
              
        story.append(NextPageTemplate('pagina3'))
        frames_pag3=[]
        frames_pag3.append(frame_base)
        pagina3=Image('./resources/Perla del Mar/FORMATO PROMESA  BIEN FUTURO PERLA V2  A 09.08.223.png',width=214*mm,height=350*mm)
        story.append(pagina3)
        
        story.append(NextPageTemplate('pagina4'))
        frames_pag4=[]
        frames_pag4.append(frame_base)
        pagina4=Image('./resources/Perla del Mar/FORMATO PROMESA  BIEN FUTURO PERLA V2  A 09.08.224.png',width=214*mm,height=350*mm)
        story.append(pagina4)
        
        estilo_fecha=ParagraphStyle('fecha contrato',fontName='centuryg',fontSize=9,alignment=1)
      
        frame_dia=Frame(105.2*mm,238.2*mm,10.5*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag4.append(frame_dia)
        story.append(Paragraph(dia_contrato,estilo_fecha))
        story.append(FrameBreak())
        
        frame_mes=Frame(109.3*mm,238.2*mm,34.6*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag4.append(frame_mes)
        story.append(Paragraph(Utilidades().NombreMes(mes_contrato),estilo_fecha))
        story.append(FrameBreak())
        
        frame_año=Frame(142.9*mm,238.2*mm,14*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag4.append(frame_año)
        story.append(Paragraph(año_contrato,estilo_fecha))
        
        frame_oficina=Frame(170.2*mm,238.2*mm,30*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag4.append(frame_oficina)
        story.append(Paragraph(ciudad_entrega,estilo_fecha))
        
        page1=PageTemplate(id='pagina1',frames=frames_pag1)
        page2=PageTemplate(id='pagina2',frames=frames_pag2)
        page3=PageTemplate(id='pagina3',frames=frames_pag3)
        page4=PageTemplate(id='pagina4',frames=frames_pag4)
        
        doc=BaseDocTemplate(ruta,pageTemplates=[page1,page2,page3,page4],pagesize=LEGAL)
        
        doc.build(story)
    
    
    def ExportCBFCarmeloReservado(self,nro_contrato,nombre_t1,cc_t1,tel_t1,cel_t1,
                                    ofic_t1,cdof_t1,telof_t1,
                                    resid_t1,cdresid_t1,telresid_t1,email_t1,
                                    nombre_t2,cc_t2,tel_t2,cel_t2,
                                    ofic_t2,cdof_t2,telof_t2,
                                    resid_t2,cdresid_t2,telresid_t2,email_t2,
                                    nombre_t3,cc_t3,tel_t3,cel_t3,
                                    ofic_t3,cdof_t3,telof_t3,
                                    resid_t3,cdresid_t3,telresid_t3,email_t3,
                                    nombre_t4,cc_t4,tel_t4,cel_t4,
                                    ofic_t4,cdof_t4,telof_t4,
                                    resid_t4,cdresid_t4,telresid_t4,email_t4,
                                    lote,manzana,area,mtsnorte,colnorte,
                                    mtseste,coleste,mtssur,colsur,
                                    mtsoeste,coloeste,
                                    valor,valor_letras,ci,saldo,
                                    contado_x,credic_x,amort_x,
                                    formaCI,formaFN,obs,
                                    fecha_escritura,fecha_entrega,ciudad_entrega,
                                    dia_contrato,mes_contrato,año_contrato,ruta,meses_entrega):
        
        story=[]
        frames_pag1=[]
        grupos=[]
     # Imagen base del doc
        frame_base=Frame(0,0,216*mm,356*mm)
        frames_pag1.append(frame_base)
        pagina1=Image('./resources/Carmelo Reservado/FORMATO PROMESA EL CARMELO RESERVADO V1 A 29.07.22-1.png',width=214*mm,height=350*mm)
        story.append(pagina1)
        story.append(FrameBreak())
        
        estilo_nro=ParagraphStyle('numero',alignment=1,fontName='centuryg',fontSize=14,textColor='#F78369')
        frame_nro=Frame(100*mm,320.9*mm,22*mm,6*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_nro)
        story.append(Paragraph(f'<b>{int(nro_contrato):03d}</b>',estilo_nro))
        story.append(FrameBreak())
     # Titulares
        estilo_titulares=ParagraphStyle('estilo',fontName='centuryg',fontSize=9)
      # Titular 1
        frame_nombre1=Frame(30*mm,287.4*mm,120.5*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_nombre1,nombre_t1))
        
        frame_cc1=Frame(163*mm,287.4*mm,24.5*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_cc1,cc_t1))
        
        frame_cel1=Frame(29*mm,268.4*mm,26.7*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_cel1,cel_t1))
        
        frame_oficina=Frame(26.5*mm,275.2*mm,81*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_oficina,ofic_t1))
        
        frame_cdof1=Frame(123*mm,275.2*mm,30.3*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_cdof1,cdof_t1))
        
        frame_telof1=Frame(168.5*mm,275.2*mm,29*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_telof1,telof_t1))
        
        frame_resid=Frame(30.5*mm,280.5*mm,76.5*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_resid,resid_t1))
        
        frame_cdres1=Frame(123*mm,280.5*mm,30.3*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_cdres1,cdresid_t1))
        
        frame_telres1=Frame(168.5*mm,280.5*mm,29*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_telres1,telresid_t1))
        
        frame_email1=Frame(117.5*mm,268.4*mm,81*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_email1,email_t1))
        
      # Titular 2
        distancia=24*mm
        frame_nombre2=Frame(30*mm,285.7*mm-distancia,120.5*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_nombre2,nombre_t2))
        
        frame_cc2=Frame(163*mm,285.7*mm-distancia,24.5*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_cc2,cc_t2))
                
        frame_cel2=Frame(29*mm,266.2*mm-distancia,26.7*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_cel2,cel_t2))
        
        frame_oficina2=Frame(26.5*mm,272.8*mm-distancia,81*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_oficina2,ofic_t2))
        
        frame_cdof2=Frame(123*mm,272.8*mm-distancia,30.3*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_cdof2,cdof_t2))
        
        frame_telof2=Frame(168.5*mm,272.8*mm-distancia,29*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_telof2,telof_t2))
        
        frame_resid2=Frame(30.5*mm,279.3*mm-distancia,76.5*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_resid2,resid_t2))
        
        frame_cdres2=Frame(123*mm,279.3*mm-distancia,30.3*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_cdres2,cdresid_t2))
        
        frame_telres2=Frame(171.5*mm,279.5*mm-distancia,29*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_telres2,telresid_t2))
        
        frame_email2=Frame(117.5*mm,266.2*mm-distancia,81*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_email2,email_t2))
      
      # Titular 3
        distancia=24.5*mm*2
        frame_nombre3=Frame(30*mm,285.2*mm-distancia,120.5*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_nombre3,nombre_t3))
        
        frame_cc3=Frame(163*mm,285.2*mm-distancia,24.5*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_cc3,cc_t3))
        
        frame_cel3=Frame(29*mm,266.2*mm-distancia,26.7*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_cel3,cel_t3))
        
        frame_oficina3=Frame(26.5*mm,272.8*mm-distancia,81*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_oficina3,ofic_t3))
        
        frame_cdof3=Frame(123*mm,272.8*mm-distancia,30.3*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_cdof3,cdof_t3))
        
        frame_telof3=Frame(168.5*mm,272.8*mm-distancia,29*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_telof3,telof_t3))
        
        frame_resid3=Frame(30.5*mm,279.3*mm-distancia,76.5*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_resid3,resid_t3))
        
        frame_cdres3=Frame(123*mm,279.3*mm-distancia,30.3*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_cdres3,cdresid_t3))
        
        frame_telres3=Frame(171.5*mm,279.5*mm-distancia,29*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_telres3,telresid_t3))
        
        frame_email3=Frame(117.5*mm,266.2*mm-distancia,81*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_email3,email_t3))
        
      # Titular 4
        distancia=24.6*mm*3
        frame_nombre4=Frame(30*mm,285.2*mm-distancia,120.5*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_nombre4,nombre_t4))
                
        frame_cc4=Frame(163*mm,285.2*mm-distancia,24.5*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_cc4,cc_t4))
        
        frame_cel4=Frame(29*mm,266.2*mm-distancia,26.7*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_cel4,cel_t4))
        
        frame_oficina4=Frame(26.5*mm,272.8*mm-distancia,81*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_oficina4,ofic_t4))
        
        frame_cdof4=Frame(123*mm,272.8*mm-distancia,30.3*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_cdof4,cdof_t4))
        
        frame_telof4=Frame(168.5*mm,272.8*mm-distancia,29*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_telof4,telof_t4))
                
        frame_resid4=Frame(30.5*mm,279.3*mm-distancia,76.5*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_resid4,resid_t4))
        
        frame_cdres4=Frame(123*mm,279.3*mm-distancia,30.3*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_cdres4,cdresid_t4))
        
        frame_telres4=Frame(171.5*mm,279.5*mm-distancia,29*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_telres4,telresid_t4))
        
        frame_email4=Frame(117.5*mm,266.2*mm-distancia,81*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_email4,email_t4))
    
        for grupo in grupos:
          contenido=grupo[1]
          if contenido!=None and contenido!='None':
            frame=grupo[0]
            fontName='centuryg'
            fontSize=9
            estilo=ParagraphStyle('estilo',fontName=fontName,fontSize=fontSize)
            flowable=Paragraph(contenido,estilo)
            textwidth=stringWidth(contenido,'centuryG',fontSize)
            i=1
            j=1
            while textwidth>frame._aW:
              if fontSize>6:
                fontSize-=i
              else:
                contenido=contenido[:len(contenido)-j]
              estilo=ParagraphStyle('estilo',fontName=fontName,fontSize=fontSize)
              flowable=Paragraph(contenido,estilo)
              textwidth=stringWidth(contenido,'centuryG',fontSize)
              i+=1
              j+=1
            frames_pag1.append(frame)
            story.append(flowable)
            story.append(FrameBreak())
        grupos=[]

     # Datos Inmueble
        estilo_inmueble=ParagraphStyle('inmueble',fontName='centuryg',fontSize=9,alignment=1)
        
        frame_lote=Frame(21.7*mm,108.7*mm,12*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        grupos.append((frame_lote,lote))
                        
        frame_manzana=Frame(45*mm,108.7*mm,12*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        grupos.append((frame_manzana,manzana))
        
        frame_area=Frame(62.2*mm,108.7*mm,12*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        grupos.append((frame_area,area))
        
        frame_mtsnorte=Frame(32.9*mm,102.7*mm,22.17*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        grupos.append((frame_mtsnorte,mtsnorte))
        
        frame_colnorte=Frame(72.6*mm,102.7*mm,33.7*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        grupos.append((frame_colnorte,colnorte))
        
        frame_mtseste=Frame(127.8*mm,102.7*mm,23.55*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        grupos.append((frame_mtseste,mtseste))
        
        frame_coleste=Frame(170.5*mm,102.7*mm,31.4*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        grupos.append((frame_coleste,coleste))
        
        frame_mtssur=Frame(30.5*mm,97.4*mm,24.47*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        grupos.append((frame_mtssur,mtssur))
        
        frame_colsur=Frame(72.6*mm,97.4*mm,33.7*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        grupos.append((frame_colsur,colsur))
        
        frame_mtsoeste=Frame(127.8*mm,97.4*mm,23.55*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        grupos.append((frame_mtsoeste,mtsoeste))
        
        frame_coloeste=Frame(170.5*mm,97.4*mm,31.4*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        grupos.append((frame_coloeste,coloeste))
        
        for grupo in grupos:
          contenido=grupo[1]
          if contenido!=None and contenido!='None':
            frame=grupo[0]
            fontName='centuryg'
            fontSize=9
            estilo=ParagraphStyle('estilo',fontName=fontName,fontSize=fontSize,alignment=1)
            flowable=Paragraph(contenido,estilo)
            textwidth=stringWidth(contenido,'centuryG',fontSize)
            i=1
            j=1
            while textwidth>frame._aW:
              if fontSize>6:
                fontSize-=i
              else:
                contenido=contenido[:len(contenido)-j]
              estilo=ParagraphStyle('estilo',fontName=fontName,fontSize=fontSize)
              flowable=Paragraph(contenido,estilo)
              textwidth=stringWidth(contenido,'centuryG',fontSize)
              i+=1
              j+=1
            frames_pag1.append(frame)
            story.append(flowable)
            if grupos.index(grupo) + 1 < len(grupos):
              story.append(FrameBreak())
        grupos=[]
          
     #pag 2
        
        story.append(NextPageTemplate('pagina2'))
        frames_pag2=[]
        frames_pag2.append(frame_base)
        pagina2=Image('./resources/Carmelo Reservado/FORMATO PROMESA EL CARMELO RESERVADO V1 A 29.07.22-2.png',width=214*mm,height=350*mm)
        story.append(pagina2)
        
        
        # Precio y Forma de pago
     
        estilo_precio=ParagraphStyle('precio',fontName='centuryg',fontSize=10)
        frame_valorletras=Frame(10*mm,337.8*mm,120*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        frames_pag2.append(frame_valorletras)
        story.append(Paragraph(valor_letras,estilo_precio))
        story.append(FrameBreak())
        
        frame_precio=Frame(167.5*mm,339.8*mm,40.3*mm,5.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        frames_pag2.append(frame_precio)
        story.append(Paragraph('<b>{:,}</b>'.format(valor),estilo_precio))
        story.append(FrameBreak())
                
        frame_ctainicial=Frame(60.5*mm,326.8*mm,49*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        frames_pag2.append(frame_ctainicial)
        story.append(Paragraph('{:,}'.format(ci),estilo_precio))
        story.append(FrameBreak())
        
        frame_saldo=Frame(154*mm,326.8*mm,49*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        frames_pag2.append(frame_saldo)
        story.append(Paragraph('{:,}'.format(saldo),estilo_precio))
        story.append(FrameBreak())
        
        frame_contado=Frame(111.6*mm,322.2*mm,5.5*mm,4.5*mm,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        frames_pag2.append(frame_contado)
        story.append(Paragraph(contado_x,estilo_precio))
        story.append(FrameBreak())
        
        frame_credic=Frame(141.5*mm,322.2*mm,5.5*mm,4.5*mm,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        frames_pag2.append(frame_credic)
        story.append(Paragraph(credic_x,estilo_precio))
        story.append(FrameBreak())
        
        frame_amort=Frame(178.7*mm,321.9*mm,5.5*mm,4.5*mm,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        frames_pag2.append(frame_amort)
        story.append(Paragraph(amort_x,estilo_precio))
        story.append(FrameBreak())
        
        estilo_formas=ParagraphStyle('precio',fontName='centuryg',fontSize=7,leading=20,alignment=4)
        
        frame_formaCI=Frame(16*mm,293.5*mm,90*mm,29*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        frames_pag2.append(frame_formaCI)
        story.append(Paragraph(formaCI,estilo_formas))
        story.append(FrameBreak())
        
        frame_formaFN=Frame(112.5*mm,296.5*mm,88.3*mm,18.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        frames_pag2.append(frame_formaFN)
        story.append(Paragraph(formaFN,estilo_formas))
        story.append(FrameBreak())
        
        estilo_obs=ParagraphStyle('precio',fontName='centuryg',fontSize=8,leading=20)
        frame_obs2=Frame(16.8*mm,262*mm,183.5*mm,22.7*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        frames_pag2.append(frame_obs2)
        story.append(Paragraph('&nbsp '*40+obs,estilo_obs))
        story.append(FrameBreak())
        
        
        diaescr=str(fecha_escritura.day)
        mesescr=Utilidades().NombreMes(fecha_escritura.month)
        añoescr=str(fecha_escritura.year)
        
        """ diaentr=str(fecha_entrega.day)
        mesentr=str(fecha_entrega.month)
        añoentr=str(fecha_entrega.year) """
        
        notarias={
          'Monteria':'1',
          'Medellin':'26',
        }
        
        try: notaria=notarias[ciudad_entrega]
        except KeyError: notaria=''
        
        frame_diaescr=Frame(51.5*mm,204.6*mm,10*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_diaescr,diaescr))
        
        frame_mesescr=Frame(73.2*mm,204.6*mm,30*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_mesescr,mesescr))
        
        frame_añoescr=Frame(105.9*mm,204.6*mm,13.3*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_añoescr,añoescr))
        
        frame_notaria=Frame(141.9*mm,204.6*mm,13.8*mm,4.5*mm,id='notaria',showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_notaria,notaria))
        
        frame_ciudad=Frame(165.2*mm,204.6*mm,13.8*mm,4.5*mm,id='ciudad',showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_ciudad,ciudad_entrega))
        
        frame_meses_entrega=Frame(79.5*mm,97.3*mm,10*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        grupos.append((frame_meses_entrega,meses_entrega))
        
        group_counter=1
        for grupo in grupos:
          contenido=grupo[1]
          if contenido!=None and contenido!='None':
            frame=grupo[0]
            fontName='centuryg'
            fontSize=9
            estilo=ParagraphStyle('estilo',alignment=1,fontName=fontName,fontSize=fontSize)
            flowable=Paragraph(contenido,estilo)
            textwidth=stringWidth(contenido,'centuryG',fontSize)
            i=1
            j=1
            while textwidth>frame._aW:
              if fontSize>5:
                fontSize-=i
              else:
                contenido=contenido[:len(contenido)-j]
              estilo=ParagraphStyle('estilo',fontName=fontName,fontSize=fontSize)
              flowable=Paragraph(contenido,estilo)
              textwidth=stringWidth(contenido,'centuryG',fontSize)
              i+=1
              j+=1
            frames_pag2.append(frame)
            story.append(flowable)
            if group_counter<len(grupos):
              story.append(FrameBreak())
              group_counter+=1
              
        story.append(NextPageTemplate('pagina3'))
        frames_pag3=[]
        frames_pag3.append(frame_base)
        pagina3=Image('./resources/Carmelo Reservado/FORMATO PROMESA EL CARMELO RESERVADO V1 A 29.07.22-3.png',width=214*mm,height=350*mm)
        story.append(pagina3)
        
        story.append(NextPageTemplate('pagina4'))
        frames_pag4=[]
        frames_pag4.append(frame_base)
        pagina4=Image('./resources/Carmelo Reservado/FORMATO PROMESA EL CARMELO RESERVADO V1 A 29.07.22-4.png',width=214*mm,height=350*mm)
        story.append(pagina4)
        
        estilo_fecha=ParagraphStyle('fecha contrato',fontName='centuryg',fontSize=9,alignment=1)
      
        frame_dia=Frame(107.7*mm,149.2*mm,10.5*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag4.append(frame_dia)
        story.append(Paragraph(dia_contrato,estilo_fecha))
        story.append(FrameBreak())
        
        frame_mes=Frame(109.3*mm,149.2*mm,34.6*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag4.append(frame_mes)
        story.append(Paragraph(Utilidades().NombreMes(mes_contrato),estilo_fecha))
        story.append(FrameBreak())
        
        frame_año=Frame(136.7*mm,149.2*mm,14*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag4.append(frame_año)
        story.append(Paragraph(año_contrato,estilo_fecha))
        
        frame_oficina=Frame(170.2*mm,149.2*mm,30*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag4.append(frame_oficina)
        story.append(Paragraph(ciudad_entrega,estilo_fecha))
        
        page1=PageTemplate(id='pagina1',frames=frames_pag1)
        page2=PageTemplate(id='pagina2',frames=frames_pag2)
        page3=PageTemplate(id='pagina3',frames=frames_pag3)
        page4=PageTemplate(id='pagina4',frames=frames_pag4)
        
        doc=BaseDocTemplate(ruta,pageTemplates=[page1,page2,page3,page4],pagesize=LEGAL)
        
        doc.build(story)
         
    def ExportPromesaSandvilleBeach(self,nro_contrato,nombre_t1,cc_t1,tel_t1,cel_t1,
                                    ofic_t1,cdof_t1,telof_t1,
                                    resid_t1,cdresid_t1,telresid_t1,email_t1,
                                    nombre_t2,cc_t2,tel_t2,cel_t2,
                                    ofic_t2,cdof_t2,telof_t2,
                                    resid_t2,cdresid_t2,telresid_t2,email_t2,
                                    nombre_t3,cc_t3,tel_t3,cel_t3,
                                    ofic_t3,cdof_t3,telof_t3,
                                    resid_t3,cdresid_t3,telresid_t3,email_t3,
                                    nombre_t4,cc_t4,tel_t4,cel_t4,
                                    ofic_t4,cdof_t4,telof_t4,
                                    resid_t4,cdresid_t4,telresid_t4,email_t4,
                                    lote,manzana,area,mtsnorte,colnorte,
                                    mtseste,coleste,mtssur,colsur,
                                    mtsoeste,coloeste,
                                    valor,valor_letras,ci,saldo,
                                    contado_x,credic_x,amort_x,
                                    formaCI,formaFN,obs,
                                    fecha_escritura,fecha_entrega,ciudad_entrega,
                                    dia_contrato,mes_contrato,año_contrato,ruta):
        
        story=[]
        frames_pag1=[]
        grupos=[]
     # Imagen base del doc
        frame_base=Frame(0,0,216*mm,356*mm,id='framebase')
        frames_pag1.append(frame_base)
        pagina1=Image('./resources/Sandville Beach/FORMATO PROMESA SV URB CAMPESTRE BEACH CLUB V7_A 10.05.2021.png',width=214*mm,height=350*mm)
        story.append(pagina1)
        story.append(FrameBreak())
        
        estilo_nro=ParagraphStyle('numero',alignment=1,fontName='centuryg',fontSize=14,textColor='#F78369',id='numero')
        frame_nro=Frame(185.9*mm,336.6*mm,22*mm,6*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_nro)
        story.append(Paragraph(f'<b>{int(nro_contrato):03d}</b>',estilo_nro))
        story.append(FrameBreak())
     # Titulares
        estilo_titulares=ParagraphStyle('estilo',fontName='centuryg',fontSize=9)
      # Titular 1
        frame_nombre1=Frame(30*mm,286.6*mm,130.5*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,id='nombre1')
        grupos.append((frame_nombre1,nombre_t1))
        
        frame_cc1=Frame(163*mm,286.6*mm,24.5*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,id='cc2')
        grupos.append((frame_cc1,cc_t1))
        
        frame_cel1=Frame(29*mm,267.2*mm,26.7*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,id='cel1')
        grupos.append((frame_cel1,cel_t1))
        
        frame_oficina=Frame(26.5*mm,273.8*mm,81*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,id='odicina1')
        grupos.append((frame_oficina,ofic_t1))
        
        frame_cdof1=Frame(123*mm,273.8*mm,30.3*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,id='cdof1')
        grupos.append((frame_cdof1,cdof_t1))
        
        frame_telof1=Frame(168.5*mm,273.8*mm,29*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,id='telfof1')
        grupos.append((frame_telof1,telof_t1))
        
        frame_resid=Frame(30.5*mm,280.3*mm,76.5*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,id='resid1')
        grupos.append((frame_resid,resid_t1))
        
        frame_cdres1=Frame(123*mm,280.3*mm,30.3*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,id='cdres1')
        grupos.append((frame_cdres1,cdresid_t1))
        
        frame_telres1=Frame(168.5*mm,280.3*mm,29*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,id='telres1')
        grupos.append((frame_telres1,telresid_t1))
        
        frame_email1=Frame(117.5*mm,267.2*mm,81*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,id='email1')
        grupos.append((frame_email1,email_t1))
        
      # Titular 2
        distancia=26.3*mm
        frame_nombre2=Frame(30*mm,286.6*mm-distancia,120.5*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,id='nombre2')
        grupos.append((frame_nombre2,nombre_t2))
        
        frame_cc2=Frame(163*mm,286.6*mm-distancia,24.5*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,id='cc2')
        grupos.append((frame_cc2,cc_t2))
                
        frame_cel2=Frame(29*mm,267.2*mm-distancia,26.7*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,id='cel2')
        grupos.append((frame_cel2,cel_t2))
        
        frame_oficina2=Frame(26.5*mm,273.8*mm-distancia,81*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,id='oficina2')
        grupos.append((frame_oficina2,ofic_t2))
        
        frame_cdof2=Frame(123*mm,273.8*mm-distancia,30.3*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,id='cdof2')
        grupos.append((frame_cdof2,cdof_t2))
        
        frame_telof2=Frame(168.5*mm,273.8*mm-distancia,29*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,id='telof2')
        grupos.append((frame_telof2,telof_t2))
        
        frame_resid2=Frame(30.5*mm,280.3*mm-distancia,76.5*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,id='resid2')
        grupos.append((frame_resid2,resid_t2))
        
        frame_cdres2=Frame(123*mm,280.3*mm-distancia,30.3*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,id='cdres2')
        grupos.append((frame_cdres2,cdresid_t2))
        
        frame_telres2=Frame(171.5*mm,280.5*mm-distancia,29*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,id='telres2')
        grupos.append((frame_telres2,telresid_t2))
        
        frame_email2=Frame(117.5*mm,267.2*mm-distancia,81*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,id='email2')
        grupos.append((frame_email2,email_t2))
      
      # Titular 3
        distancia=26.3*mm*2
        frame_nombre3=Frame(30*mm,287*mm-distancia,120.5*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,id='nombre3')
        grupos.append((frame_nombre3,nombre_t3))
        
        frame_cc3=Frame(163*mm,287*mm-distancia,24.5*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,id='cc3')
        grupos.append((frame_cc3,cc_t3))
        
        frame_cel3=Frame(29*mm,267.2*mm-distancia,26.7*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,id='cel3')
        grupos.append((frame_cel3,cel_t3))
        
        frame_oficina3=Frame(26.5*mm,273.8*mm-distancia,81*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,id='oficina3')
        grupos.append((frame_oficina3,ofic_t3))
        
        frame_cdof3=Frame(123*mm,273.8*mm-distancia,30.3*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,id='cdof3')
        grupos.append((frame_cdof3,cdof_t3))
        
        frame_telof3=Frame(168.5*mm,273.8*mm-distancia,29*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,id='telof3')
        grupos.append((frame_telof3,telof_t3))
        
        frame_resid3=Frame(30.5*mm,280.3*mm-distancia,76.5*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,id='resid3')
        grupos.append((frame_resid3,resid_t3))
        
        frame_cdres3=Frame(123*mm,280.3*mm-distancia,30.3*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,id='cdres3')
        grupos.append((frame_cdres3,cdresid_t3))
        
        frame_telres3=Frame(171.5*mm,280.5*mm-distancia,29*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,id='telres3')
        grupos.append((frame_telres3,telresid_t3))
        
        frame_email3=Frame(117.5*mm,267.2*mm-distancia,81*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,id='email3')
        grupos.append((frame_email3,email_t3))
        
      # Titular 4
        distancia=26.3*mm*3
        frame_nombre4=Frame(30*mm,286.2*mm-distancia,120.5*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,id='nombre4')
        grupos.append((frame_nombre4,nombre_t4))
                
        frame_cc4=Frame(163*mm,286.2*mm-distancia,24.5*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,id='cc4')
        grupos.append((frame_cc4,cc_t4))
        
        frame_cel4=Frame(29*mm,267.2*mm-distancia,26.7*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,id='cel4')
        grupos.append((frame_cel4,cel_t4))
        
        frame_oficina4=Frame(26.5*mm,273.8*mm-distancia,81*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,id='oficina4')
        grupos.append((frame_oficina4,ofic_t4))
        
        frame_cdof4=Frame(123*mm,273.8*mm-distancia,30.3*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,id='cdof4')
        grupos.append((frame_cdof4,cdof_t4))
        
        frame_telof4=Frame(168.5*mm,273.8*mm-distancia,29*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,id='telof4')
        grupos.append((frame_telof4,telof_t4))
                
        frame_resid4=Frame(30.5*mm,280.3*mm-distancia,76.5*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,id='resid4')
        grupos.append((frame_resid4,resid_t4))
        
        frame_cdres4=Frame(123*mm,280.3*mm-distancia,30.3*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,id='cdres4')
        grupos.append((frame_cdres4,cdresid_t4))
        
        frame_telres4=Frame(171.5*mm,280.5*mm-distancia,29*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,id='telres4')
        grupos.append((frame_telres4,telresid_t4))
        
        frame_email4=Frame(117.5*mm,267.2*mm-distancia,81*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,id='email4')
        grupos.append((frame_email4,email_t4))
    
        for grupo in grupos:
          contenido=grupo[1]
          if contenido!=None and contenido!='None':
            frame=grupo[0]
            fontName='centuryg'
            fontSize=9
            estilo=ParagraphStyle('estilo',fontName=fontName,fontSize=fontSize)
            flowable=Paragraph(contenido,estilo)
            textwidth=stringWidth(contenido,'centuryG',fontSize)
            i=1
            j=1
            while textwidth>frame._aW:
              if fontSize>6:
                fontSize-=i
              else:
                contenido=contenido[:len(contenido)-j]
              estilo=ParagraphStyle('estilo',fontName=fontName,fontSize=fontSize)
              flowable=Paragraph(contenido,estilo)
              textwidth=stringWidth(contenido,'centuryG',fontSize)
              i+=1
              j+=1
            frames_pag1.append(frame)
            story.append(flowable)
            story.append(FrameBreak())
        grupos=[]

     # Datos Inmueble
        estilo_inmueble=ParagraphStyle('inmueble',fontName='centuryg',fontSize=9,alignment=1)
        
        frame_lote=Frame(19.1*mm,164.5*mm,12*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0,id='lote')
        grupos.append((frame_lote,lote))
                        
        frame_manzana=Frame(43*mm,164.5*mm,12*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0,id='manzana')
        grupos.append((frame_manzana,manzana))
        
        frame_area=Frame(60*mm,164.5*mm,12*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0,id='area')
        grupos.append((frame_area,area))
        
        frame_mtsnorte=Frame(32.9*mm,159.2*mm,22.17*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0,id='mtsnorte')
        grupos.append((frame_mtsnorte,mtsnorte))
        
        frame_colnorte=Frame(72.6*mm,159.2*mm,33.7*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0,id='colnorte')
        grupos.append((frame_colnorte,colnorte))
        
        frame_mtseste=Frame(127.8*mm,159.2*mm,23.55*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0,id='mtseste')
        grupos.append((frame_mtseste,mtseste))
        
        frame_coleste=Frame(170.5*mm,159.2*mm,31.4*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0,id='coleste')
        grupos.append((frame_coleste,coleste))
        
        frame_mtssur=Frame(30.5*mm,153.6*mm,24.47*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0,id='mtssur')
        grupos.append((frame_mtssur,mtssur))
        
        frame_colsur=Frame(72.6*mm,153.6*mm,33.7*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0,id='colsur')
        grupos.append((frame_colsur,colsur))
        
        frame_mtsoeste=Frame(127.8*mm,153.6*mm,23.55*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0,id='mtsoeste')
        grupos.append((frame_mtsoeste,mtsoeste))
        
        frame_coloeste=Frame(170.5*mm,153.6*mm,31.4*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0,id='coloeste')
        grupos.append((frame_coloeste,coloeste))
        
        frame_valorletras=Frame(40.1*mm,104.9*mm,104.8*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0,id='vrletras')
        grupos.append((frame_valorletras,valor_letras))
        
        for grupo in grupos:
          contenido=grupo[1]
          if contenido!=None and contenido!='None':
            frame=grupo[0]
            fontName='centuryg'
            fontSize=9
            estilo=ParagraphStyle('estilo',fontName=fontName,fontSize=fontSize,alignment=1)
            flowable=Paragraph(contenido,estilo)
            textwidth=stringWidth(contenido,'centuryG',fontSize)
            i=1
            j=1
            while textwidth>frame._aW:
              if fontSize>6:
                fontSize-=i
              else:
                contenido=contenido[:len(contenido)-j]
              estilo=ParagraphStyle('estilo',fontName=fontName,fontSize=fontSize)
              flowable=Paragraph(contenido,estilo)
              textwidth=stringWidth(contenido,'centuryG',fontSize)
              i+=1
              j+=1
            frames_pag1.append(frame)
            story.append(flowable)
            story.append(FrameBreak())
        grupos=[]
          
     # Precio y Forma de pago
        estilo_precio=ParagraphStyle('precio',fontName='centuryg',fontSize=10,alignment=1)
        frame_precio=Frame(146.8*mm,104*mm,29.3*mm,5.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0,id='precio')
        frames_pag1.append(frame_precio)
        story.append(Paragraph('<b>{:,}</b>'.format(valor),estilo_precio))
        story.append(FrameBreak())
                
        frame_ctainicial=Frame(54.5*mm,95.1*mm,49*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0,id='ctaini')
        frames_pag1.append(frame_ctainicial)
        story.append(Paragraph('{:,}'.format(ci),estilo_precio))
        story.append(FrameBreak())
        
        frame_saldo=Frame(154*mm,95.1*mm,49*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0,id='saldo')
        frames_pag1.append(frame_saldo)
        story.append(Paragraph('{:,}'.format(saldo),estilo_precio))
        story.append(FrameBreak())
        
        frame_contado=Frame(133.7*mm,90.4*mm,5.5*mm,4.5*mm,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0,id='contado')
        frames_pag1.append(frame_contado)
        story.append(Paragraph(contado_x,estilo_precio))
        story.append(FrameBreak())
        
        frame_credic=Frame(152.7*mm,90.4*mm,5.5*mm,4.5*mm,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0,id='credic')
        frames_pag1.append(frame_credic)
        story.append(Paragraph(credic_x,estilo_precio))
        story.append(FrameBreak())
        
        frame_amort=Frame(178.7*mm,90.4*mm,5.5*mm,4.5*mm,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0,id='amort')
        frames_pag1.append(frame_amort)
        story.append(Paragraph(amort_x,estilo_precio))
        story.append(FrameBreak())
        
        estilo_formas=ParagraphStyle('precio',fontName='centuryg',fontSize=7,leading=20,alignment=4)
        
        frame_formaCI=Frame(12.8*mm,62.2*mm,90*mm,28.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0,id='formaCI')
        frames_pag1.append(frame_formaCI)
        story.append(Paragraph(formaCI,estilo_formas))
        story.append(FrameBreak())
        
        frame_formaFN=Frame(112.5*mm,61.6*mm,90.3*mm,19.9*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0,id='formaFN')
        frames_pag1.append(frame_formaFN)
        aW = 90.3*mm
        aH = 19.9*mm
        p_formaFN = Paragraph(formaFN,estilo_formas)
        w, h = p_formaFN.wrap(aW,aH)
        i=1
        while w>=aW and h>=aH:
          estilo_forma_reducido = ParagraphStyle('precio',fontName='centuryg',fontSize=7-i,leading=20,alignment=4)
          p_formaFN = Paragraph(formaFN,estilo_forma_reducido)
          w, h = p_formaFN.wrap(aW,aH)
          i+=0.5
          
        story.append(p_formaFN)
        story.append(FrameBreak())
        
        
        
        estilo_obs=ParagraphStyle('precio',fontName='centuryg',fontSize=8,leading=20)
        frame_obs2=Frame(12.8*mm,45.8*mm,190*mm,14.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0,id='obs')
        frames_pag1.append(frame_obs2)
        story.append(Paragraph('&nbsp '*37+obs,estilo_obs))
        
     #pag 2
        
        story.append(NextPageTemplate('pagina2'))
        frames_pag2=[]
        frames_pag2.append(frame_base)
        pagina2=Image('./resources/Sandville Beach/FORMATO PROMESA SV URB CAMPESTRE BEACH CLUB V7_A 10.05.20212.png',width=214*mm,height=350*mm)
        story.append(pagina2)
        story.append(FrameBreak())
        
        diaescr=str(fecha_escritura.day)
        mesescr=Utilidades().NombreMes(fecha_escritura.month)
        añoescr=str(fecha_escritura.year)
        
        diaentr=str(fecha_entrega.day)
        mesentr=str(fecha_entrega.month)
        añoentr=str(fecha_entrega.year)
        
        notarias={
          'Monteria':'1',
          'Medellin':'26',
        }
        
        try: notaria=notarias[ciudad_entrega]
        except KeyError: notaria=''
        
        frame_diaescr=Frame(40.2*mm,328.7*mm,10*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,id='diaesc')
        grupos.append((frame_diaescr,diaescr))
        
        frame_mesescr=Frame(76.8*mm,328.7*mm,30*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,id='mesescr')
        grupos.append((frame_mesescr,mesescr))
        
        frame_añoescr=Frame(125.2*mm,328.7*mm,13.3*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,id='añoesc')
        grupos.append((frame_añoescr,añoescr))
        
        frame_notaria=Frame(165.6*mm,328.7*mm,13.8*mm,4.5*mm,id='notaria',showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_notaria,notaria))
        
        frame_ciudad=Frame(190*mm,328.7*mm,13.8*mm,4.5*mm,id='ciudad',showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_ciudad,ciudad_entrega))
        
        frame_diaentr=Frame(75.7*mm,279.1*mm,6.5*mm,4.5*mm,id='diaentrega',showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_diaentr,diaentr))
        
        frame_mesentr=Frame(100.2*mm,279.1*mm,12.6*mm,4.5*mm,id='mesentrega',showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_mesentr,mesentr))
        
        frame_añoentr=Frame(130.1*mm,279.1*mm,12.6*mm,4.5*mm,id='añoentrega',showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_añoentr,añoentr))
        
        group_counter=1
        for grupo in grupos:
          contenido=grupo[1]
          if contenido!=None and contenido!='None':
            frame=grupo[0]
            fontName='centuryg'
            fontSize=9
            estilo=ParagraphStyle('estilo',alignment=1,fontName=fontName,fontSize=fontSize)
            flowable=Paragraph(contenido,estilo)
            textwidth=stringWidth(contenido,'centuryG',fontSize)
            i=1
            j=1
            while textwidth>frame._aW:
              if fontSize>5:
                fontSize-=i
              else:
                contenido=contenido[:len(contenido)-j]
              estilo=ParagraphStyle('estilo',fontName=fontName,fontSize=fontSize)
              flowable=Paragraph(contenido,estilo)
              textwidth=stringWidth(contenido,'centuryG',fontSize)
              i+=1
              j+=1
            frames_pag2.append(frame)
            story.append(flowable)
            if group_counter<len(grupos):
              story.append(FrameBreak())
              group_counter+=1
              
        story.append(NextPageTemplate('pagina3'))
        frames_pag3=[]
        frames_pag3.append(frame_base)
        pagina3=Image('./resources/Sandville Beach/FORMATO PROMESA SV URB CAMPESTRE BEACH CLUB V7_A 10.05.20213.png',width=214*mm,height=350*mm)
        story.append(pagina3)
        
        estilo_fecha=ParagraphStyle('fecha contrato',fontName='centuryg',fontSize=9,alignment=1)
      
        frame_dia=Frame(112*mm,217.8*mm,10.5*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag3.append(frame_dia)
        story.append(Paragraph(dia_contrato,estilo_fecha))
        story.append(FrameBreak())
        
        frame_mes=Frame(128*mm,217.8*mm,34.6*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag3.append(frame_mes)
        story.append(Paragraph(Utilidades().NombreMes(mes_contrato),estilo_fecha))
        story.append(FrameBreak())
        
        frame_año=Frame(159.5*mm,217.8*mm,14*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag3.append(frame_año)
        story.append(Paragraph(año_contrato,estilo_fecha))
        story.append(FrameBreak())
        
        page1=PageTemplate(id='pagina1',frames=frames_pag1)
        page2=PageTemplate(id='pagina2',frames=frames_pag2)
        page3=PageTemplate(id='pagina3',frames=frames_pag3)
        
        doc=BaseDocTemplate(ruta,pageTemplates=[page1,page2,page3],pagesize=LEGAL)
        
        doc.build(story)
    
    def ExportPromesaBugambilias(self,nro_contrato,nombre_t1,cc_t1,tel_t1,cel_t1,
                                    ofic_t1,cdof_t1,telof_t1,
                                    resid_t1,cdresid_t1,telresid_t1,email_t1,
                                    nombre_t2,cc_t2,tel_t2,cel_t2,
                                    ofic_t2,cdof_t2,telof_t2,
                                    resid_t2,cdresid_t2,telresid_t2,email_t2,
                                    nombre_t3,cc_t3,tel_t3,cel_t3,
                                    ofic_t3,cdof_t3,telof_t3,
                                    resid_t3,cdresid_t3,telresid_t3,email_t3,
                                    nombre_t4,cc_t4,tel_t4,cel_t4,
                                    ofic_t4,cdof_t4,telof_t4,
                                    resid_t4,cdresid_t4,telresid_t4,email_t4,
                                    lote,manzana,area,mtsnorte,colnorte,
                                    mtseste,coleste,mtssur,colsur,
                                    mtsoeste,coloeste,
                                    valor,valor_letras,ci,saldo,
                                    contado_x,credic_x,amort_x,
                                    formaCI,formaFN,obs,
                                    fecha_escritura,fecha_entrega,ciudad_entrega,
                                    dia_contrato,mes_contrato,año_contrato,ruta,porcderecho,area_parcela):
        
        story=[]
        frames_pag1=[]
        grupos=[]
     # Imagen base del doc
        frame_base=Frame(0,0,216*mm,356*mm)
        frames_pag1.append(frame_base)
        pagina1=Image('./resources/Bugambilias/1.png',width=214*mm,height=350*mm)
        story.append(pagina1)
        story.append(FrameBreak())
        
        estilo_nro=ParagraphStyle('numero',alignment=1,fontName='centuryg',fontSize=14,textColor='#F78369')
        frame_nro=Frame(100*mm,321*mm,22*mm,6*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_nro)
        story.append(Paragraph('<b>{}</b>'.format(nro_contrato),estilo_nro))
        story.append(FrameBreak())
     # Titulares
        estilo_titulares=ParagraphStyle('estilo',fontName='centuryg',fontSize=9)
      # Titular 1
        frame_nombre1=Frame(30*mm,281.8*mm,120.5*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_nombre1,nombre_t1))
        
        frame_cc1=Frame(163*mm,281.8*mm,24.5*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_cc1,cc_t1))
        
        frame_cel1=Frame(29*mm,262.8*mm,26.7*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_cel1,cel_t1))
        
        frame_oficina=Frame(26.5*mm,269.4*mm,81*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_oficina,ofic_t1))
        
        frame_cdof1=Frame(123*mm,269.4*mm,30.3*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_cdof1,cdof_t1))
        
        frame_telof1=Frame(168.5*mm,269.4*mm,29*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_telof1,telof_t1))
        
        frame_resid=Frame(30.5*mm,275.9*mm,76.5*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_resid,resid_t1))
        
        frame_cdres1=Frame(123*mm,275.9*mm,30.3*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_cdres1,cdresid_t1))
        
        frame_telres1=Frame(168.5*mm,275.9*mm,29*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_telres1,telresid_t1))
        
        frame_email1=Frame(117.5*mm,262.8*mm,81*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_email1,email_t1))
        
      # Titular 2
        distancia=25*mm
        frame_nombre2=Frame(30*mm,281.8*mm-distancia,120.5*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_nombre2,nombre_t2))
        
        frame_cc2=Frame(163*mm,281.8*mm-distancia,24.5*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_cc2,cc_t2))
                
        frame_cel2=Frame(29*mm,262.8*mm-distancia,26.7*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_cel2,cel_t2))
        
        frame_oficina2=Frame(26.5*mm,269.4*mm-distancia,81*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_oficina2,ofic_t2))
        
        frame_cdof2=Frame(123*mm,269.4*mm-distancia,30.3*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_cdof2,cdof_t2))
        
        frame_telof2=Frame(168.5*mm,269.4*mm-distancia,29*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_telof2,telof_t2))
        
        frame_resid2=Frame(30.5*mm,275.9*mm-distancia,76.5*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_resid2,resid_t2))
        
        frame_cdres2=Frame(123*mm,275.9*mm-distancia,30.3*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_cdres2,cdresid_t2))
        
        frame_telres2=Frame(171.5*mm,275.9*mm-distancia,29*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_telres2,telresid_t2))
        
        frame_email2=Frame(117.5*mm,262.8*mm-distancia,81*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_email2,email_t2))
      
      # Titular 3
        distancia=24.9*mm*2
        frame_nombre3=Frame(30*mm,281.8*mm-distancia,120.5*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_nombre3,nombre_t3))
        
        frame_cc3=Frame(163*mm,281.8*mm-distancia,24.5*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_cc3,cc_t3))
        
        frame_cel3=Frame(29*mm,262.8*mm-distancia,26.7*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_cel3,cel_t3))
        
        frame_oficina3=Frame(26.5*mm,269.4*mm-distancia,81*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_oficina3,ofic_t3))
        
        frame_cdof3=Frame(123*mm,269.4*mm-distancia,30.3*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_cdof3,cdof_t3))
        
        frame_telof3=Frame(168.5*mm,269.4*mm-distancia,29*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_telof3,telof_t3))
        
        frame_resid3=Frame(30.5*mm,275.9*mm-distancia,76.5*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_resid3,resid_t3))
        
        frame_cdres3=Frame(123*mm,275.9*mm-distancia,30.3*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_cdres3,cdresid_t3))
        
        frame_telres3=Frame(171.5*mm,275.9*mm-distancia,29*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_telres3,telresid_t3))
        
        frame_email3=Frame(117.5*mm,262.8*mm-distancia,81*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_email3,email_t3))
        
      # Titular 4
        distancia=24.8*mm*3
        frame_nombre4=Frame(30*mm,281.8*mm-distancia,120.5*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_nombre4,nombre_t4))
                
        frame_cc4=Frame(163*mm,281.8*mm-distancia,24.5*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_cc4,cc_t4))
        
        frame_cel4=Frame(29*mm,262.8*mm-distancia,26.7*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_cel4,cel_t4))
        
        frame_oficina4=Frame(26.5*mm,269.4*mm-distancia,81*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_oficina4,ofic_t4))
        
        frame_cdof4=Frame(123*mm,269.4*mm-distancia,30.3*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_cdof4,cdof_t4))
        
        frame_telof4=Frame(168.5*mm,269.4*mm-distancia,29*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_telof4,telof_t4))
                
        frame_resid4=Frame(30.5*mm,275.9*mm-distancia,76.5*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_resid4,resid_t4))
        
        frame_cdres4=Frame(123*mm,275.9*mm-distancia,30.3*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_cdres4,cdresid_t4))
        
        frame_telres4=Frame(171.5*mm,275.9*mm-distancia,29*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_telres4,telresid_t4))
        
        frame_email4=Frame(117.5*mm,262.8*mm-distancia,81*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_email4,email_t4))
    
        for grupo in grupos:
          contenido=grupo[1]
          if contenido!=None and contenido!='None':
            frame=grupo[0]
            fontName='centuryg'
            fontSize=9
            estilo=ParagraphStyle('estilo',fontName=fontName,fontSize=fontSize)
            flowable=Paragraph(contenido,estilo)
            textwidth=stringWidth(contenido,'centuryG',fontSize)
            i=1
            j=1
            while textwidth>frame._aW:
              if fontSize>6:
                fontSize-=i
              else:
                contenido=contenido[:len(contenido)-j]
              estilo=ParagraphStyle('estilo',fontName=fontName,fontSize=fontSize)
              flowable=Paragraph(contenido,estilo)
              textwidth=stringWidth(contenido,'centuryG',fontSize)
              i+=1
              j+=1
            frames_pag1.append(frame)
            story.append(flowable)
            if grupos.index(grupo)<len(grupos)-1:
              story.append(FrameBreak())
        grupos=[]
    
     #respaldo
        
        story.append(NextPageTemplate('pagina2'))
        frames_pag2=[]
        frames_pag2.append(frame_base)
        pagina2=Image('./resources/Bugambilias/2.png',width=214*mm,height=350*mm)
        story.append(pagina2)
        story.append(FrameBreak())
        
         # Datos Inmueble
        estilo_inmueble=ParagraphStyle('inmueble',fontName='centuryg',fontSize=9,alignment=1)
        
        frame_parcelacion=Frame(37.9*mm,311.5*mm,12*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        grupos.append((frame_parcelacion,'1'))
        
        frame_lote=Frame(147.5*mm,311.5*mm,12*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        grupos.append((frame_lote,lote[:-1]))
        
        frame_parcela=Frame(33.5*mm,303.5*mm,12*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        grupos.append((frame_parcela,area_parcela))
        
        frame_porcderecho=Frame(139.7*mm,303.5*mm,12*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        grupos.append((frame_porcderecho,porcderecho))
        
        frame_fraccion=Frame(189.2*mm,303.5*mm,12*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        grupos.append((frame_fraccion,lote[-1]))
        
        frame_manzana=Frame(184*mm,311.5*mm,12*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        grupos.append((frame_manzana,manzana))
        
        frame_area=Frame(78.8*mm,303.5*mm,12*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        grupos.append((frame_area,area))
        
        frame_mtsnorte=Frame(32.9*mm,293*mm,22.17*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        grupos.append((frame_mtsnorte,mtsnorte))
        
        frame_colnorte=Frame(72.6*mm,293*mm,33.7*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        grupos.append((frame_colnorte,colnorte))
        
        frame_mtseste=Frame(127.8*mm,293*mm,23.55*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        grupos.append((frame_mtseste,mtseste))
        
        frame_coleste=Frame(170.5*mm,293*mm,31.4*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        grupos.append((frame_coleste,coleste))
        
        frame_mtssur=Frame(30.5*mm,285.2*mm,24.47*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        grupos.append((frame_mtssur,mtssur))
        
        frame_colsur=Frame(72.6*mm,285.2*mm,33.7*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        grupos.append((frame_colsur,colsur))
        
        frame_mtsoeste=Frame(127.8*mm,285.2*mm,23.55*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        grupos.append((frame_mtsoeste,mtsoeste))
        
        frame_coloeste=Frame(170.5*mm,285.2*mm,31.4*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        grupos.append((frame_coloeste,coloeste))
        
        frame_valorletras=Frame(12*mm,204*mm,99*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        grupos.append((frame_valorletras,valor_letras))
        
        for grupo in grupos:
          contenido=grupo[1]
          if contenido!=None and contenido!='None':
            frame=grupo[0]
            fontName='centuryg'
            fontSize=9
            estilo=ParagraphStyle('estilo',fontName=fontName,fontSize=fontSize,alignment=1)
            flowable=Paragraph(contenido,estilo)
            textwidth=stringWidth(contenido,'centuryG',fontSize)
            i=1
            j=1
            while textwidth>frame._aW:
              if fontSize>6:
                fontSize-=i
              else:
                contenido=contenido[:len(contenido)-j]
              estilo=ParagraphStyle('estilo',fontName=fontName,fontSize=fontSize)
              flowable=Paragraph(contenido,estilo)
              textwidth=stringWidth(contenido,'centuryG',fontSize)
              i+=1
              j+=1
            frames_pag2.append(frame)
            story.append(flowable)
            story.append(FrameBreak())
        grupos=[]
          
     # Precio y Forma de pago
        estilo_precio=ParagraphStyle('precio',fontName='centuryg',fontSize=10)
        frame_precio=Frame(120.8*mm,203*mm,58.3*mm,5.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        frames_pag2.append(frame_precio)
        story.append(Paragraph('<b>{:,}</b>'.format(valor),estilo_precio))
        story.append(FrameBreak())
                
        frame_ctainicial=Frame(70.5*mm,194.6*mm,49*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        frames_pag2.append(frame_ctainicial)
        story.append(Paragraph('{:,}'.format(ci),estilo_precio))
        story.append(FrameBreak())
        
        frame_saldo=Frame(168*mm,194.6*mm,49*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        frames_pag2.append(frame_saldo)
        story.append(Paragraph('{:,}'.format(saldo),estilo_precio))
        story.append(FrameBreak())
        
        frame_contado=Frame(137.5*mm,189.5*mm,5.5*mm,4.5*mm,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        frames_pag2.append(frame_contado)
        story.append(Paragraph(contado_x,estilo_precio))
        story.append(FrameBreak())
        
        frame_credic=Frame(156.4*mm,189.5*mm,5.5*mm,4.5*mm,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        frames_pag2.append(frame_credic)
        story.append(Paragraph(credic_x,estilo_precio))
        story.append(FrameBreak())
        
        frame_amort=Frame(182.1*mm,189.5*mm,5.5*mm,4.5*mm,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        frames_pag2.append(frame_amort)
        story.append(Paragraph(amort_x,estilo_precio))
        story.append(FrameBreak())
        
        estilo_formas=ParagraphStyle('precio',fontName='centuryg',fontSize=7,leading=20,alignment=4)
        
        frame_formaCI=Frame(12*mm,160.9*mm,90.3*mm,28.6*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        frames_pag2.append(frame_formaCI)
        story.append(Paragraph(formaCI,estilo_formas))
        story.append(FrameBreak())
        
        frame_formaFN=Frame(112.5*mm,161*mm,90.3*mm,19.9*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0,id='formaFN')
        frames_pag2.append(frame_formaFN)
        aW = 90.3*mm
        aH = 19.9*mm
        p_formaFN = Paragraph(formaFN,estilo_formas)
        w, h = p_formaFN.wrap(aW,aH)
        i=1
        while w>=aW and h>=aH:
          estilo_forma_reducido = ParagraphStyle('precio',fontName='centuryg',fontSize=7-i,leading=20,alignment=4)
          p_formaFN = Paragraph(formaFN,estilo_forma_reducido)
          w, h = p_formaFN.wrap(aW,aH)
          i+=0.5
          
        story.append(p_formaFN)
        story.append(FrameBreak())
        
        
        estilo_obs=ParagraphStyle('precio',fontName='centuryg',fontSize=8,leading=20)
        frame_obs2=Frame(12.7*mm,140*mm,191.7*mm,19.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        frames_pag2.append(frame_obs2)
        story.append(Paragraph('&nbsp '*38+obs,estilo_obs))
        story.append(FrameBreak())
        
        #####
        diaescr=str(fecha_escritura.day)
        mesescr=Utilidades().NombreMes(fecha_escritura.month)
        añoescr=str(fecha_escritura.year)
        
        diaentr=str(fecha_entrega.day)
        mesentr=str(fecha_entrega.month)
        añoentr=str(fecha_entrega.year)
        
        notarias={
          'Monteria':'1',
          'Medellin':'26',
        }
        
        try: notaria=notarias[ciudad_entrega]
        except KeyError: notaria=''
        
        frame_diaescr=Frame(76.8*mm,107.9*mm,10*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_diaescr,diaescr))
        
        frame_mesescr=Frame(114.3*mm,107.9*mm,30*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_mesescr,mesescr))
        
        frame_añoescr=Frame(164*mm,107.9*mm,13.3*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_añoescr,añoescr))
        
        #frame_notaria=Frame(19.3*mm,259.2*mm,13.8*mm,4.5*mm,id='notaria',showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        #grupos.append((frame_notaria,notaria))
        
        #frame_ciudad=Frame(48*mm,259.2*mm,13.8*mm,4.5*mm,id='ciudad',showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        #grupos.append((frame_ciudad,ciudad_entrega))
        
        frame_diaentr=Frame(152*mm,48.9*mm,6.5*mm,4.5*mm,id='diaentrega',showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_diaentr,diaentr))
        
        frame_mesentr=Frame(176.3*mm,48.9*mm,12.6*mm,4.5*mm,id='mesentrega',showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_mesentr,mesentr))
        
        frame_añoentr=Frame(14.2*mm,45.5*mm,12.6*mm,4.5*mm,id='añoentrega',showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_añoentr,añoentr))
        
        group_counter=1
        for grupo in grupos:
          contenido=grupo[1]
          if contenido!=None and contenido!='None':
            frame=grupo[0]
            fontName='centuryg'
            fontSize=9
            estilo=ParagraphStyle('estilo',alignment=1,fontName=fontName,fontSize=fontSize)
            flowable=Paragraph(contenido,estilo)
            textwidth=stringWidth(contenido,'centuryG',fontSize)
            i=1
            j=1
            while textwidth>frame._aW:
              if fontSize>5:
                fontSize-=i
              else:
                contenido=contenido[:len(contenido)-j]
              estilo=ParagraphStyle('estilo',fontName=fontName,fontSize=fontSize)
              flowable=Paragraph(contenido,estilo)
              textwidth=stringWidth(contenido,'centuryG',fontSize)
              i+=1
              j+=1
            frames_pag2.append(frame)
            story.append(flowable)
            if group_counter<len(grupos):
              story.append(FrameBreak())
              group_counter+=1
              
        story.append(NextPageTemplate('pagina3'))
        frames_pag3=[]
        frames_pag3.append(frame_base)
        pagina3=Image('./resources/Bugambilias/3.png',width=214*mm,height=350*mm)
        story.append(pagina3)
        
        story.append(NextPageTemplate('pagina4'))
        frames_pag4=[]
        frames_pag4.append(frame_base)
        pagina4=Image('./resources/Bugambilias/4.png',width=214*mm,height=350*mm)
        story.append(pagina4)
        
        estilo_fecha=ParagraphStyle('fecha contrato',fontName='centuryg',fontSize=9,alignment=1)
      
        frame_dia=Frame(116.7*mm,219.3*mm,10.5*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag4.append(frame_dia)
        story.append(Paragraph(dia_contrato,estilo_fecha))
        story.append(FrameBreak())
        
        frame_mes=Frame(138.3*mm,219.3*mm,34.6*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag4.append(frame_mes)
        story.append(Paragraph(Utilidades().NombreMes(mes_contrato),estilo_fecha))
        story.append(FrameBreak())
        
        frame_año=Frame(182.2*mm,219.3*mm,14*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag4.append(frame_año)
        story.append(Paragraph(año_contrato,estilo_fecha))
        story.append(FrameBreak())
        
        page1=PageTemplate(id='pagina1',frames=frames_pag1)
        page2=PageTemplate(id='pagina2',frames=frames_pag2)
        page3=PageTemplate(id='pagina3',frames=frames_pag3)
        page4=PageTemplate(id='pagina4',frames=frames_pag4)
        
        doc=BaseDocTemplate(ruta,pageTemplates=[page1,page2,page3,page4],pagesize=LEGAL)
        
        doc.build(story)
    
    def ExportPromesaVegasVenecia(self,nro_contrato,nombre_t1,cc_t1,tel_t1,cel_t1,
                                    ofic_t1,cdof_t1,telof_t1,
                                    resid_t1,cdresid_t1,telresid_t1,email_t1,
                                    nombre_t2,cc_t2,tel_t2,cel_t2,
                                    ofic_t2,cdof_t2,telof_t2,
                                    resid_t2,cdresid_t2,telresid_t2,email_t2,
                                    nombre_t3,cc_t3,tel_t3,cel_t3,
                                    ofic_t3,cdof_t3,telof_t3,
                                    resid_t3,cdresid_t3,telresid_t3,email_t3,
                                    nombre_t4,cc_t4,tel_t4,cel_t4,
                                    ofic_t4,cdof_t4,telof_t4,
                                    resid_t4,cdresid_t4,telresid_t4,email_t4,
                                    lote,manzana,area,mtsnorte,colnorte,
                                    mtseste,coleste,mtssur,colsur,
                                    mtsoeste,coloeste,
                                    valor,valor_letras,ci,saldo,
                                    contado_x,credic_x,amort_x,
                                    formaCI,formaFN,obs,
                                    fecha_escritura,fecha_entrega,ciudad_entrega,
                                    dia_contrato,mes_contrato,año_contrato,ruta):
        
        story=[]
        frames_pag1=[]
        grupos=[]
     # Imagen base del doc
        frame_base=Frame(0,0,216*mm,356*mm)
        frames_pag1.append(frame_base)
        pagina1=Image('./resources/Vegas de Venecia/Promesa de Compraventa V1A6-05-2021-01.png',width=214*mm,height=350*mm)
        story.append(pagina1)
        story.append(FrameBreak())
        
        estilo_nro=ParagraphStyle('numero',alignment=1,fontName='centuryg',fontSize=14,textColor='#F78369')
        frame_nro=Frame(148*mm,336.9*mm,22*mm,6*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_nro)
        story.append(Paragraph(f'<b>Nº {int(nro_contrato):03d}</b>',estilo_nro))
        story.append(FrameBreak())
     # Titulares
        estilo_titulares=ParagraphStyle('estilo',fontName='centuryg',fontSize=9)
      # Titular 1
        frame_nombre1=Frame(30*mm,285.2*mm,120.5*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_nombre1,nombre_t1))
        
        frame_cc1=Frame(163*mm,285.2*mm,24.5*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_cc1,cc_t1))
        
        frame_cel1=Frame(29*mm,266.2*mm,26.7*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_cel1,cel_t1))
        
        frame_oficina=Frame(26.5*mm,272.8*mm,81*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_oficina,ofic_t1))
        
        frame_cdof1=Frame(123*mm,272.8*mm,30.3*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_cdof1,cdof_t1))
        
        frame_telof1=Frame(168.5*mm,272.8*mm,29*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_telof1,telof_t1))
        
        frame_resid=Frame(30.5*mm,279.3*mm,76.5*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_resid,resid_t1))
        
        frame_cdres1=Frame(123*mm,279.3*mm,30.3*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_cdres1,cdresid_t1))
        
        frame_telres1=Frame(168.5*mm,279.3*mm,29*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_telres1,telresid_t1))
        
        frame_email1=Frame(117.5*mm,266.2*mm,81*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_email1,email_t1))
        
      # Titular 2
        distancia=28*mm
        frame_nombre2=Frame(30*mm,285.2*mm-distancia,120.5*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_nombre2,nombre_t2))
        
        frame_cc2=Frame(163*mm,285.2*mm-distancia,24.5*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_cc2,cc_t2))
                
        frame_cel2=Frame(29*mm,266.2*mm-distancia,26.7*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_cel2,cel_t2))
        
        frame_oficina2=Frame(26.5*mm,272.8*mm-distancia,81*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_oficina2,ofic_t2))
        
        frame_cdof2=Frame(123*mm,272.8*mm-distancia,30.3*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_cdof2,cdof_t2))
        
        frame_telof2=Frame(168.5*mm,272.8*mm-distancia,29*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_telof2,telof_t2))
        
        frame_resid2=Frame(30.5*mm,279.3*mm-distancia,76.5*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_resid2,resid_t2))
        
        frame_cdres2=Frame(123*mm,279.3*mm-distancia,30.3*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_cdres2,cdresid_t2))
        
        frame_telres2=Frame(171.5*mm,279.5*mm-distancia,29*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_telres2,telresid_t2))
        
        frame_email2=Frame(117.5*mm,266.2*mm-distancia,81*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_email2,email_t2))
      
      # Titular 3
        distancia=27.5*mm*2
        frame_nombre3=Frame(30*mm,285.2*mm-distancia,120.5*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_nombre3,nombre_t3))
        
        frame_cc3=Frame(163*mm,285.2*mm-distancia,24.5*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_cc3,cc_t3))
        
        frame_cel3=Frame(29*mm,266.2*mm-distancia,26.7*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_cel3,cel_t3))
        
        frame_oficina3=Frame(26.5*mm,272.8*mm-distancia,81*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_oficina3,ofic_t3))
        
        frame_cdof3=Frame(123*mm,272.8*mm-distancia,30.3*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_cdof3,cdof_t3))
        
        frame_telof3=Frame(168.5*mm,272.8*mm-distancia,29*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_telof3,telof_t3))
        
        frame_resid3=Frame(30.5*mm,279.3*mm-distancia,76.5*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_resid3,resid_t3))
        
        frame_cdres3=Frame(123*mm,279.3*mm-distancia,30.3*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_cdres3,cdresid_t3))
        
        frame_telres3=Frame(171.5*mm,279.5*mm-distancia,29*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_telres3,telresid_t3))
        
        frame_email3=Frame(117.5*mm,266.2*mm-distancia,81*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_email3,email_t3))
        
      # Titular 4
        distancia=27.3*mm*3
        frame_nombre4=Frame(30*mm,285.2*mm-distancia,120.5*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_nombre4,nombre_t4))
                
        frame_cc4=Frame(163*mm,285.2*mm-distancia,24.5*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_cc4,cc_t4))
        
        frame_cel4=Frame(29*mm,266.2*mm-distancia,26.7*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_cel4,cel_t4))
        
        frame_oficina4=Frame(26.5*mm,272.8*mm-distancia,81*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_oficina4,ofic_t4))
        
        frame_cdof4=Frame(123*mm,272.8*mm-distancia,30.3*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_cdof4,cdof_t4))
        
        frame_telof4=Frame(168.5*mm,272.8*mm-distancia,29*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_telof4,telof_t4))
                
        frame_resid4=Frame(30.5*mm,279.3*mm-distancia,76.5*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_resid4,resid_t4))
        
        frame_cdres4=Frame(123*mm,279.3*mm-distancia,30.3*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_cdres4,cdresid_t4))
        
        frame_telres4=Frame(171.5*mm,279.5*mm-distancia,29*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_telres4,telresid_t4))
        
        frame_email4=Frame(117.5*mm,266.2*mm-distancia,81*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_email4,email_t4))
    
        for grupo in grupos:
          contenido=grupo[1]
          if contenido!=None and contenido!='None':
            frame=grupo[0]
            fontName='centuryg'
            fontSize=9
            estilo=ParagraphStyle('estilo',fontName=fontName,fontSize=fontSize)
            flowable=Paragraph(contenido,estilo)
            textwidth=stringWidth(contenido,'centuryG',fontSize)
            i=1
            j=1
            while textwidth>frame._aW:
              if fontSize>6:
                fontSize-=i
              else:
                contenido=contenido[:len(contenido)-j]
              estilo=ParagraphStyle('estilo',fontName=fontName,fontSize=fontSize)
              flowable=Paragraph(contenido,estilo)
              textwidth=stringWidth(contenido,'centuryG',fontSize)
              i+=1
              j+=1
            frames_pag1.append(frame)
            story.append(flowable)
            story.append(FrameBreak())
        grupos=[]

     # Datos Inmueble
        estilo_inmueble=ParagraphStyle('inmueble',fontName='centuryg',fontSize=9,alignment=1)
        
        frame_lote=Frame(21.7*mm,155.3*mm,12*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        grupos.append((frame_lote,lote))
                        
        frame_manzana=Frame(47*mm,155.3*mm,12*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        grupos.append((frame_manzana,manzana))
        
        frame_area=Frame(65.2*mm,155.3*mm,12*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        grupos.append((frame_area,area))
        
        frame_mtsnorte=Frame(32.9*mm,148*mm,22.17*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        grupos.append((frame_mtsnorte,mtsnorte))
        
        frame_colnorte=Frame(72.6*mm,148*mm,33.7*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        grupos.append((frame_colnorte,colnorte))
        
        frame_mtseste=Frame(127.8*mm,148*mm,23.55*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        grupos.append((frame_mtseste,mtseste))
        
        frame_coleste=Frame(170.5*mm,148*mm,31.4*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        grupos.append((frame_coleste,coleste))
        
        frame_mtssur=Frame(30.5*mm,138.6*mm,24.47*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        grupos.append((frame_mtssur,mtssur))
        
        frame_colsur=Frame(72.6*mm,138.6*mm,33.7*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        grupos.append((frame_colsur,colsur))
        
        frame_mtsoeste=Frame(127.8*mm,138.6*mm,23.55*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        grupos.append((frame_mtsoeste,mtsoeste))
        
        frame_coloeste=Frame(170.5*mm,138.6*mm,31.4*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        grupos.append((frame_coloeste,coloeste))
        
        frame_valorletras=Frame(13.1*mm,89.8*mm,93*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        grupos.append((frame_valorletras,valor_letras))
        
        for grupo in grupos:
          contenido=grupo[1]
          if contenido!=None and contenido!='None':
            frame=grupo[0]
            fontName='centuryg'
            fontSize=9
            estilo=ParagraphStyle('estilo',fontName=fontName,fontSize=fontSize,alignment=1)
            flowable=Paragraph(contenido,estilo)
            textwidth=stringWidth(contenido,'centuryG',fontSize)
            i=1
            j=1
            while textwidth>frame._aW:
              if fontSize>6:
                fontSize-=i
              else:
                contenido=contenido[:len(contenido)-j]
              estilo=ParagraphStyle('estilo',fontName=fontName,fontSize=fontSize)
              flowable=Paragraph(contenido,estilo)
              textwidth=stringWidth(contenido,'centuryG',fontSize)
              i+=1
              j+=1
            frames_pag1.append(frame)
            story.append(flowable)
            story.append(FrameBreak())
        grupos=[]
          
     # Precio y Forma de pago
        estilo_precio=ParagraphStyle('precio',fontName='centuryg',fontSize=10)
        frame_precio=Frame(113.8*mm,89*mm,58.3*mm,5.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        frames_pag1.append(frame_precio)
        story.append(Paragraph('<b>{:,}</b>'.format(valor),estilo_precio))
        story.append(FrameBreak())
                
        frame_ctainicial=Frame(60.5*mm,79.3*mm,49*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        frames_pag1.append(frame_ctainicial)
        story.append(Paragraph('{:,}'.format(ci),estilo_precio))
        story.append(FrameBreak())
        
        frame_saldo=Frame(154*mm,79.3*mm,49*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        frames_pag1.append(frame_saldo)
        story.append(Paragraph('{:,}'.format(saldo),estilo_precio))
        story.append(FrameBreak())
        
        frame_contado=Frame(137.4*mm,74.4*mm,5.5*mm,4.5*mm,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        frames_pag1.append(frame_contado)
        story.append(Paragraph(contado_x,estilo_precio))
        story.append(FrameBreak())
        
        frame_credic=Frame(156.2*mm,74.4*mm,5.5*mm,4.5*mm,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        frames_pag1.append(frame_credic)
        story.append(Paragraph(credic_x,estilo_precio))
        story.append(FrameBreak())
        
        frame_amort=Frame(182.2*mm,77*mm,5.5*mm,4.5*mm,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        frames_pag1.append(frame_amort)
        story.append(Paragraph(amort_x,estilo_precio))
        story.append(FrameBreak())
        
        estilo_formas=ParagraphStyle('precio',fontName='centuryg',fontSize=7,leading=20,alignment=4)
        
        frame_formaCI=Frame(12.8*mm,46*mm,90*mm,28.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        frames_pag1.append(frame_formaCI)
        story.append(Paragraph(formaCI,estilo_formas))
        story.append(FrameBreak())
        
        frame_formaFN=Frame(112.5*mm,41*mm,88.3*mm,25*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        frames_pag1.append(frame_formaFN)
        story.append(Paragraph(formaFN,estilo_formas))
        story.append(FrameBreak())
        
        estilo_obs=ParagraphStyle('precio',fontName='centuryg',fontSize=8,leading=20)
        frame_obs2=Frame(12.8*mm,29.7*mm,190*mm,14.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        frames_pag1.append(frame_obs2)
        story.append(Paragraph('&nbsp '*41+obs,estilo_obs))
        
     #pag 2
        
        story.append(NextPageTemplate('pagina2'))
        frames_pag2=[]
        frames_pag2.append(frame_base)
        pagina2=Image('./resources/Vegas de Venecia/Promesa de Compraventa V1A6-05-2021-02.png',width=214*mm,height=350*mm)
        story.append(pagina2)
        story.append(FrameBreak())
        
        diaescr=str(fecha_escritura.day)
        mesescr=Utilidades().NombreMes(fecha_escritura.month)
        añoescr=str(fecha_escritura.year)
        
        diaentr=str(fecha_entrega.day)
        mesentr=str(fecha_entrega.month)
        añoentr=str(fecha_entrega.year)
        
        notarias={
          'Monteria':'1',
          'Medellin':'26',
        }
        
        try: notaria=notarias[ciudad_entrega]
        except KeyError: notaria=''
        
        frame_diaescr=Frame(15.7*mm,285.2*mm,10*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_diaescr,diaescr))
        
        frame_mesescr=Frame(50.1*mm,285.2*mm,30*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_mesescr,mesescr))
        
        frame_añoescr=Frame(98.7*mm,285.2*mm,13.3*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_añoescr,añoescr))
        
        frame_notaria=Frame(135.1*mm,285.2*mm,13.8*mm,4.5*mm,id='notaria',showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_notaria,notaria))
        
        frame_ciudad=Frame(157.8*mm,285.2*mm,13.8*mm,4.5*mm,id='ciudad',showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_ciudad,ciudad_entrega))
        
        frame_diaentr=Frame(138*mm,245.2*mm,6.5*mm,4.5*mm,id='diaentrega',showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_diaentr,diaentr))
        
        frame_mesentr=Frame(160*mm,245.2*mm,12.6*mm,4.5*mm,id='mesentrega',showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_mesentr,mesentr))
        
        frame_añoentr=Frame(189.3*mm,245.2*mm,12.6*mm,4.5*mm,id='añoentrega',showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_añoentr,añoentr))
        
        group_counter=1
        for grupo in grupos:
          contenido=grupo[1]
          if contenido!=None and contenido!='None':
            frame=grupo[0]
            fontName='centuryg'
            fontSize=9
            estilo=ParagraphStyle('estilo',alignment=1,fontName=fontName,fontSize=fontSize)
            flowable=Paragraph(contenido,estilo)
            textwidth=stringWidth(contenido,'centuryG',fontSize)
            i=1
            j=1
            while textwidth>frame._aW:
              if fontSize>5:
                fontSize-=i
              else:
                contenido=contenido[:len(contenido)-j]
              estilo=ParagraphStyle('estilo',fontName=fontName,fontSize=fontSize)
              flowable=Paragraph(contenido,estilo)
              textwidth=stringWidth(contenido,'centuryG',fontSize)
              i+=1
              j+=1
            frames_pag2.append(frame)
            story.append(flowable)
            if group_counter<len(grupos):
              story.append(FrameBreak())
              group_counter+=1
              
        story.append(NextPageTemplate('pagina3'))
        frames_pag3=[]
        frames_pag3.append(frame_base)
        pagina3=Image('./resources/Vegas de Venecia/Promesa de Compraventa V1A6-05-2021-03.png',width=214*mm,height=350*mm)
        story.append(pagina3)
        
        estilo_fecha=ParagraphStyle('fecha contrato',fontName='centuryg',fontSize=9,alignment=1)
      
        frame_dia=Frame(105.2*mm,214.2*mm,10.5*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag3.append(frame_dia)
        story.append(Paragraph(dia_contrato,estilo_fecha))
        story.append(FrameBreak())
        
        frame_mes=Frame(134.3*mm,214.2*mm,34.6*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag3.append(frame_mes)
        story.append(Paragraph(Utilidades().NombreMes(mes_contrato),estilo_fecha))
        story.append(FrameBreak())
        
        frame_año=Frame(180.2*mm,214.2*mm,14*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag3.append(frame_año)
        story.append(Paragraph(año_contrato,estilo_fecha))
        story.append(FrameBreak())
        
        page1=PageTemplate(id='pagina1',frames=frames_pag1)
        page2=PageTemplate(id='pagina2',frames=frames_pag2)
        page3=PageTemplate(id='pagina3',frames=frames_pag3)
        
        doc=BaseDocTemplate(ruta,pageTemplates=[page1,page2,page3],pagesize=LEGAL)
        
        doc.build(story)
    
    def ExportCBFVegasVenecia(self,nro_contrato,nombre_t1,cc_t1,tel_t1,cel_t1,
                                    ofic_t1,cdof_t1,telof_t1,
                                    resid_t1,cdresid_t1,telresid_t1,email_t1,
                                    nombre_t2,cc_t2,tel_t2,cel_t2,
                                    ofic_t2,cdof_t2,telof_t2,
                                    resid_t2,cdresid_t2,telresid_t2,email_t2,
                                    nombre_t3,cc_t3,tel_t3,cel_t3,
                                    ofic_t3,cdof_t3,telof_t3,
                                    resid_t3,cdresid_t3,telresid_t3,email_t3,
                                    nombre_t4,cc_t4,tel_t4,cel_t4,
                                    ofic_t4,cdof_t4,telof_t4,
                                    resid_t4,cdresid_t4,telresid_t4,email_t4,
                                    lote,manzana,area,mtsnorte,colnorte,
                                    mtseste,coleste,mtssur,colsur,
                                    mtsoeste,coloeste,
                                    valor,valor_letras,ci,saldo,
                                    contado_x,credic_x,amort_x,
                                    formaCI,formaFN,obs,
                                    fecha_escritura,fecha_entrega,ciudad_entrega,
                                    dia_contrato,mes_contrato,año_contrato,ruta,meses_entrega):
        
        story=[]
        frames_pag1=[]
        grupos=[]
     # Imagen base del doc
        frame_base=Frame(0,0,216*mm,356*mm)
        frames_pag1.append(frame_base)
        pagina1=Image('./resources/Vegas de Venecia/FORMATO PROMESA COMPRAVENTA BIEN FUTURO VEGAS DE VENECIA A 18.04.2022_V3-1.png',width=214*mm,height=350*mm)
        story.append(pagina1)
        story.append(FrameBreak())
        
        estilo_nro=ParagraphStyle('numero',alignment=1,fontName='centuryg',fontSize=14,textColor='#F78369')
        frame_nro=Frame(148*mm,336.9*mm,22*mm,6*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_nro)
        story.append(Paragraph(f'<b>Nº {int(nro_contrato):03d}</b>',estilo_nro))
        story.append(FrameBreak())
     # Titulares
        estilo_titulares=ParagraphStyle('estilo',fontName='centuryg',fontSize=9)
      # Titular 1
        frame_nombre1=Frame(30*mm,285.2*mm,120.5*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_nombre1,nombre_t1))
        
        frame_cc1=Frame(163*mm,285.2*mm,24.5*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_cc1,cc_t1))
        
        frame_cel1=Frame(29*mm,266.2*mm,26.7*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_cel1,cel_t1))
        
        frame_oficina=Frame(26.5*mm,272.8*mm,81*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_oficina,ofic_t1))
        
        frame_cdof1=Frame(123*mm,272.8*mm,30.3*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_cdof1,cdof_t1))
        
        frame_telof1=Frame(168.5*mm,272.8*mm,29*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_telof1,telof_t1))
        
        frame_resid=Frame(30.5*mm,279.3*mm,76.5*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_resid,resid_t1))
        
        frame_cdres1=Frame(123*mm,279.3*mm,30.3*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_cdres1,cdresid_t1))
        
        frame_telres1=Frame(168.5*mm,279.3*mm,29*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_telres1,telresid_t1))
        
        frame_email1=Frame(117.5*mm,266.2*mm,81*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_email1,email_t1))
        
      # Titular 2
        distancia=28*mm
        frame_nombre2=Frame(30*mm,285.2*mm-distancia,120.5*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_nombre2,nombre_t2))
        
        frame_cc2=Frame(163*mm,285.2*mm-distancia,24.5*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_cc2,cc_t2))
                
        frame_cel2=Frame(29*mm,266.2*mm-distancia,26.7*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_cel2,cel_t2))
        
        frame_oficina2=Frame(26.5*mm,272.8*mm-distancia,81*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_oficina2,ofic_t2))
        
        frame_cdof2=Frame(123*mm,272.8*mm-distancia,30.3*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_cdof2,cdof_t2))
        
        frame_telof2=Frame(168.5*mm,272.8*mm-distancia,29*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_telof2,telof_t2))
        
        frame_resid2=Frame(30.5*mm,279.3*mm-distancia,76.5*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_resid2,resid_t2))
        
        frame_cdres2=Frame(123*mm,279.3*mm-distancia,30.3*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_cdres2,cdresid_t2))
        
        frame_telres2=Frame(171.5*mm,279.5*mm-distancia,29*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_telres2,telresid_t2))
        
        frame_email2=Frame(117.5*mm,266.2*mm-distancia,81*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_email2,email_t2))
      
      # Titular 3
        distancia=27.5*mm*2
        frame_nombre3=Frame(30*mm,285.2*mm-distancia,120.5*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_nombre3,nombre_t3))
        
        frame_cc3=Frame(163*mm,285.2*mm-distancia,24.5*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_cc3,cc_t3))
        
        frame_cel3=Frame(29*mm,266.2*mm-distancia,26.7*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_cel3,cel_t3))
        
        frame_oficina3=Frame(26.5*mm,272.8*mm-distancia,81*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_oficina3,ofic_t3))
        
        frame_cdof3=Frame(123*mm,272.8*mm-distancia,30.3*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_cdof3,cdof_t3))
        
        frame_telof3=Frame(168.5*mm,272.8*mm-distancia,29*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_telof3,telof_t3))
        
        frame_resid3=Frame(30.5*mm,279.3*mm-distancia,76.5*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_resid3,resid_t3))
        
        frame_cdres3=Frame(123*mm,279.3*mm-distancia,30.3*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_cdres3,cdresid_t3))
        
        frame_telres3=Frame(171.5*mm,279.5*mm-distancia,29*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_telres3,telresid_t3))
        
        frame_email3=Frame(117.5*mm,266.2*mm-distancia,81*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_email3,email_t3))
        
      # Titular 4
        distancia=27.3*mm*3
        frame_nombre4=Frame(30*mm,285.2*mm-distancia,120.5*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_nombre4,nombre_t4))
                
        frame_cc4=Frame(163*mm,285.2*mm-distancia,24.5*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_cc4,cc_t4))
        
        frame_cel4=Frame(29*mm,266.2*mm-distancia,26.7*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_cel4,cel_t4))
        
        frame_oficina4=Frame(26.5*mm,272.8*mm-distancia,81*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_oficina4,ofic_t4))
        
        frame_cdof4=Frame(123*mm,272.8*mm-distancia,30.3*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_cdof4,cdof_t4))
        
        frame_telof4=Frame(168.5*mm,272.8*mm-distancia,29*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_telof4,telof_t4))
                
        frame_resid4=Frame(30.5*mm,279.3*mm-distancia,76.5*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_resid4,resid_t4))
        
        frame_cdres4=Frame(123*mm,279.3*mm-distancia,30.3*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_cdres4,cdresid_t4))
        
        frame_telres4=Frame(171.5*mm,279.5*mm-distancia,29*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_telres4,telresid_t4))
        
        frame_email4=Frame(117.5*mm,266.2*mm-distancia,81*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_email4,email_t4))
    
        for grupo in grupos:
          contenido=grupo[1]
          if contenido!=None and contenido!='None':
            frame=grupo[0]
            fontName='centuryg'
            fontSize=9
            estilo=ParagraphStyle('estilo',fontName=fontName,fontSize=fontSize)
            flowable=Paragraph(contenido,estilo)
            textwidth=stringWidth(contenido,'centuryG',fontSize)
            i=1
            j=1
            while textwidth>frame._aW:
              if fontSize>6:
                fontSize-=i
              else:
                contenido=contenido[:len(contenido)-j]
              estilo=ParagraphStyle('estilo',fontName=fontName,fontSize=fontSize)
              flowable=Paragraph(contenido,estilo)
              textwidth=stringWidth(contenido,'centuryG',fontSize)
              i+=1
              j+=1
            frames_pag1.append(frame)
            story.append(flowable)
            story.append(FrameBreak())
        grupos=[]

     # Datos Inmueble
        estilo_inmueble=ParagraphStyle('inmueble',fontName='centuryg',fontSize=9,alignment=1)
        
        frame_lote=Frame(21.7*mm,107.5*mm,12*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        grupos.append((frame_lote,lote))
                        
        frame_manzana=Frame(47*mm,107.5*mm,12*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        grupos.append((frame_manzana,manzana))
        
        frame_area=Frame(65.2*mm,107.5*mm,12*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        grupos.append((frame_area,area))
        
        frame_mtsnorte=Frame(32.9*mm,97.7*mm,22.17*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        grupos.append((frame_mtsnorte,mtsnorte))
        
        frame_colnorte=Frame(72.6*mm,97.7*mm,33.7*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        grupos.append((frame_colnorte,colnorte))
        
        frame_mtseste=Frame(127.8*mm,97.7*mm,23.55*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        grupos.append((frame_mtseste,mtseste))
        
        frame_coleste=Frame(170.5*mm,97.7*mm,31.4*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        grupos.append((frame_coleste,coleste))
        
        frame_mtssur=Frame(30.5*mm,88.4*mm,24.47*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        grupos.append((frame_mtssur,mtssur))
        
        frame_colsur=Frame(72.6*mm,88.4*mm,33.7*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        grupos.append((frame_colsur,colsur))
        
        frame_mtsoeste=Frame(127.8*mm,88.4*mm,23.55*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        grupos.append((frame_mtsoeste,mtsoeste))
        
        frame_coloeste=Frame(170.5*mm,88.4*mm,31.4*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        grupos.append((frame_coloeste,coloeste))
        
        for grupo in grupos:
          contenido=grupo[1]
          if contenido!=None and contenido!='None':
            frame=grupo[0]
            fontName='centuryg'
            fontSize=9
            estilo=ParagraphStyle('estilo',fontName=fontName,fontSize=fontSize,alignment=1)
            flowable=Paragraph(contenido,estilo)
            textwidth=stringWidth(contenido,'centuryG',fontSize)
            i=1
            j=1
            while textwidth>frame._aW:
              if fontSize>6:
                fontSize-=i
              else:
                contenido=contenido[:len(contenido)-j]
              estilo=ParagraphStyle('estilo',fontName=fontName,fontSize=fontSize)
              flowable=Paragraph(contenido,estilo)
              textwidth=stringWidth(contenido,'centuryG',fontSize)
              i+=1
              j+=1
            frames_pag1.append(frame)
            story.append(flowable)
            if grupos.index(grupo) + 1 < len(grupos):
              story.append(FrameBreak())
        grupos=[]
          
     #pag 2
        
        story.append(NextPageTemplate('pagina2'))
        frames_pag2=[]
        frames_pag2.append(frame_base)
        pagina2=Image('./resources/Vegas de Venecia/FORMATO PROMESA COMPRAVENTA BIEN FUTURO VEGAS DE VENECIA A 18.04.2022_V3-2.png',width=214*mm,height=350*mm)
        story.append(pagina2)
        
        
        # Precio y Forma de pago
        frame_valorletras=Frame(13.1*mm,307.8*mm,93*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        grupos.append((frame_valorletras,valor_letras))
     
        estilo_precio=ParagraphStyle('precio',fontName='centuryg',fontSize=10)
        frame_precio=Frame(140.8*mm,307*mm,58.3*mm,5.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        frames_pag2.append(frame_precio)
        story.append(Paragraph('<b>{:,}</b>'.format(valor),estilo_precio))
        story.append(FrameBreak())
                
        frame_ctainicial=Frame(60.5*mm,297.8*mm,49*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        frames_pag2.append(frame_ctainicial)
        story.append(Paragraph('{:,}'.format(ci),estilo_precio))
        story.append(FrameBreak())
        
        frame_saldo=Frame(154*mm,297.8*mm,49*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        frames_pag2.append(frame_saldo)
        story.append(Paragraph('{:,}'.format(saldo),estilo_precio))
        story.append(FrameBreak())
        
        frame_contado=Frame(137.4*mm,292.9*mm,5.5*mm,4.5*mm,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        frames_pag2.append(frame_contado)
        story.append(Paragraph(contado_x,estilo_precio))
        story.append(FrameBreak())
        
        frame_credic=Frame(156.2*mm,292.9*mm,5.5*mm,4.5*mm,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        frames_pag2.append(frame_credic)
        story.append(Paragraph(credic_x,estilo_precio))
        story.append(FrameBreak())
        
        frame_amort=Frame(182.2*mm,292.9*mm,5.5*mm,4.5*mm,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        frames_pag2.append(frame_amort)
        story.append(Paragraph(amort_x,estilo_precio))
        story.append(FrameBreak())
        
        estilo_formas=ParagraphStyle('precio',fontName='centuryg',fontSize=7,leading=20,alignment=4)
        
        frame_formaCI=Frame(12.8*mm,264.5*mm,90*mm,29*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        frames_pag2.append(frame_formaCI)
        story.append(Paragraph(formaCI,estilo_formas))
        story.append(FrameBreak())
        
        frame_formaFN=Frame(112.5*mm,265*mm,88.3*mm,18.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        frames_pag2.append(frame_formaFN)
        story.append(Paragraph(formaFN,estilo_formas))
        story.append(FrameBreak())
        
        estilo_obs=ParagraphStyle('precio',fontName='centuryg',fontSize=8,leading=20)
        frame_obs2=Frame(12.8*mm,240*mm,190*mm,22.7*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        frames_pag2.append(frame_obs2)
        story.append(Paragraph('&nbsp '*41+obs,estilo_obs))
        story.append(FrameBreak())
        
        
        diaescr=str(fecha_escritura.day)
        mesescr=Utilidades().NombreMes(fecha_escritura.month)
        añoescr=str(fecha_escritura.year)
        
        """ diaentr=str(fecha_entrega.day)
        mesentr=str(fecha_entrega.month)
        añoentr=str(fecha_entrega.year) """
        
        notarias={
          'Monteria':'1',
          'Medellin':'26',
        }
        
        try: notaria=notarias[ciudad_entrega]
        except KeyError: notaria=''
        
        frame_diaescr=Frame(178*mm,184.5*mm,10*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_diaescr,diaescr))
        
        frame_mesescr=Frame(6.6*mm,180.6*mm,30*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_mesescr,mesescr))
        
        frame_añoescr=Frame(39.3*mm,180.6*mm,13.3*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_añoescr,añoescr))
        
        frame_notaria=Frame(75.3*mm,180.6*mm,13.8*mm,4.5*mm,id='notaria',showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_notaria,notaria))
        
        frame_ciudad=Frame(98.6*mm,180.6*mm,13.8*mm,4.5*mm,id='ciudad',showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        grupos.append((frame_ciudad,ciudad_entrega))
        
        frame_meses_entrega=Frame(180.8*mm,74.8*mm,10*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        grupos.append((frame_meses_entrega,meses_entrega))
        
        group_counter=1
        for grupo in grupos:
          contenido=grupo[1]
          if contenido!=None and contenido!='None':
            frame=grupo[0]
            fontName='centuryg'
            fontSize=9
            estilo=ParagraphStyle('estilo',alignment=1,fontName=fontName,fontSize=fontSize)
            flowable=Paragraph(contenido,estilo)
            textwidth=stringWidth(contenido,'centuryG',fontSize)
            i=1
            j=1
            while textwidth>frame._aW:
              if fontSize>5:
                fontSize-=i
              else:
                contenido=contenido[:len(contenido)-j]
              estilo=ParagraphStyle('estilo',fontName=fontName,fontSize=fontSize)
              flowable=Paragraph(contenido,estilo)
              textwidth=stringWidth(contenido,'centuryG',fontSize)
              i+=1
              j+=1
            frames_pag2.append(frame)
            story.append(flowable)
            if group_counter<len(grupos):
              story.append(FrameBreak())
              group_counter+=1
              
        story.append(NextPageTemplate('pagina3'))
        frames_pag3=[]
        frames_pag3.append(frame_base)
        pagina3=Image('./resources/Vegas de Venecia/FORMATO PROMESA COMPRAVENTA BIEN FUTURO VEGAS DE VENECIA A 18.04.2022_V3-3.png',width=214*mm,height=350*mm)
        story.append(pagina3)
        
        story.append(NextPageTemplate('pagina4'))
        frames_pag4=[]
        frames_pag4.append(frame_base)
        pagina4=Image('./resources/Vegas de Venecia/FORMATO PROMESA COMPRAVENTA BIEN FUTURO VEGAS DE VENECIA A 18.04.2022_V3-4.png',width=214*mm,height=350*mm)
        story.append(pagina4)
        
        estilo_fecha=ParagraphStyle('fecha contrato',fontName='centuryg',fontSize=9,alignment=1)
      
        frame_dia=Frame(105.2*mm,238.2*mm,10.5*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag4.append(frame_dia)
        story.append(Paragraph(dia_contrato,estilo_fecha))
        story.append(FrameBreak())
        
        frame_mes=Frame(109.3*mm,238.2*mm,34.6*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag4.append(frame_mes)
        story.append(Paragraph(Utilidades().NombreMes(mes_contrato),estilo_fecha))
        story.append(FrameBreak())
        
        frame_año=Frame(142.9*mm,238.2*mm,14*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag4.append(frame_año)
        story.append(Paragraph(año_contrato,estilo_fecha))
        
        frame_oficina=Frame(170.2*mm,238.2*mm,30*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag4.append(frame_oficina)
        story.append(Paragraph(ciudad_entrega,estilo_fecha))
        
        page1=PageTemplate(id='pagina1',frames=frames_pag1)
        page2=PageTemplate(id='pagina2',frames=frames_pag2)
        page3=PageTemplate(id='pagina3',frames=frames_pag3)
        page4=PageTemplate(id='pagina4',frames=frames_pag4)
        
        doc=BaseDocTemplate(ruta,pageTemplates=[page1,page2,page3,page4],pagesize=LEGAL)
        
        doc.build(story)
      
    def PagareQuadrata(self,nroPagare,nombreT1,ccT1,nombreT2,ccT2,nombreT3,ccT3,nombreT4,ccT4,diaPagare,mesPagare,añoPagare,ciudad,ruta):
      story=[]
      titulares=nombreT1
      if nombreT2!='': titulares+=f', {nombreT2}'
      if nombreT3!='': titulares+=f', {nombreT3}'
      if nombreT4!='': titulares+=f', {nombreT4}'
      frames_pag1=[]
     # Imagen base del doc
      frame_base=Frame(0,0,216*mm,356*mm)
      frames_pag1.append(frame_base)
      pagina1=Image('./resources/Pagare Quadrata.png',width=214*mm,height=350*mm)
      story.append(pagina1)
      story.append(FrameBreak())
      
      estilo_nro=ParagraphStyle('numero',fontName='centuryg',fontSize=14,textColor='#F78369')
      frame_nro=Frame(107.2*mm,325*mm,21.5*mm,6.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_nro)
      story.append(Paragraph('<b>{} - 1</b>'.format(nroPagare),estilo_nro))
      story.append(FrameBreak())
      
      estilo_deudores=ParagraphStyle('deudores',fontName='centuryg',fontSize=12,alignment=4,leading=20)
      frame_deudores=Frame(13*mm,278*mm,190*mm,19.3*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_deudores)
      story.append(Paragraph('{}{}'.format('&nbsp '*20,titulares),estilo_deudores))
      story.append(FrameBreak())
      
      estilo_fechas=ParagraphStyle('fechas',fontName='centuryg',fontSize=9,alignment=1)
      frame_dia=Frame(115*mm,142.6*mm,19*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_dia)
      story.append(Paragraph(diaPagare,estilo_fechas))
      story.append(FrameBreak())
      
      frame_mes=Frame(155*mm,142.6*mm,17*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_mes)
      story.append(Paragraph(mesPagare,estilo_fechas))
      story.append(FrameBreak())
      
      frame_año=Frame(183*mm,142.6*mm,10.2*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_año)
      story.append(Paragraph(añoPagare,estilo_fechas))
      story.append(FrameBreak())
      
      frame_ciudad=Frame(27.5*mm,138*mm,27.7*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_ciudad)
      story.append(Paragraph(ciudad,estilo_fechas))
      story.append(FrameBreak())
      
      estilo_firmas=ParagraphStyle('firmas',fontName='centuryg',fontSize=7,alignment=1)
      frame_titular1=Frame(25.8*mm,113*mm,57*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_titular1)
      story.append(Paragraph(nombreT1,estilo_firmas))
      story.append(FrameBreak())
      
      frame_cc1=Frame(25.8*mm,105*mm,57*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_cc1)
      story.append(Paragraph(ccT1,estilo_firmas))
      story.append(FrameBreak())
      
      frame_titular2=Frame(126.3*mm,113*mm,57*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_titular2)
      story.append(Paragraph(nombreT2,estilo_firmas))
      story.append(FrameBreak())
      
      frame_cc2=Frame(126.3*mm,105*mm,57*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_cc2)
      story.append(Paragraph(ccT2,estilo_firmas))
      story.append(FrameBreak())
      
      frame_titular3=Frame(25.8*mm,83.7*mm,57*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_titular3)
      story.append(Paragraph(nombreT3,estilo_firmas))
      story.append(FrameBreak())
      
      frame_cc3=Frame(25.8*mm,75.2*mm,57*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_cc3)
      story.append(Paragraph(ccT3,estilo_firmas))
      story.append(FrameBreak())
      
      frame_titular4=Frame(126.3*mm,83.7*mm,57*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_titular4)
      story.append(Paragraph(nombreT4,estilo_firmas))
      story.append(FrameBreak())
      
      frame_cc4=Frame(126.3*mm,75.2*mm,57*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_cc4)
      story.append(Paragraph(ccT4,estilo_firmas))
      
      story.append(NextPageTemplate('pagina2'))
      frames_pag2=[]
      frames_pag2.append(frame_base)
      
      
      pagina2=Image('./resources/Carta intrucciones Quadrata.png',width=200*mm,height=250*mm)
      story.append(pagina2)
      story.append(FrameBreak())
      
      frame_nroC=Frame(164.2*mm,288.5*mm,31.6*mm,8*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag2.append(frame_nroC)
      story.append(Paragraph(nroPagare+' - 1',estilo_deudores))
      story.append(FrameBreak())
      
      frame_deudC=Frame(19.3*mm,269*mm,176.7*mm,19.7*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag2.append(frame_deudC)
      story.append(Paragraph('{}{}'.format('&nbsp '*9,titulares),estilo_deudores))
      story.append(FrameBreak())
      
      frame_diaC=Frame(145.2*mm,209.3*mm,12*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag2.append(frame_diaC)
      story.append(Paragraph(diaPagare,estilo_firmas))
      story.append(FrameBreak())
      
      frame_mesC=Frame(180.5*mm,209.3*mm,12.3*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag2.append(frame_mesC)
      story.append(Paragraph(mesPagare,estilo_firmas))
      story.append(FrameBreak())
      
      frame_añoC=Frame(24.8*mm,206.2*mm,12*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag2.append(frame_añoC)
      story.append(Paragraph(añoPagare,estilo_firmas))
      story.append(FrameBreak())
      
      frame_ciudadC=Frame(63.5*mm,206.2*mm,27.7*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag2.append(frame_ciudadC)
      story.append(Paragraph(ciudad,estilo_firmas))
      story.append(FrameBreak())
      
      estilo_firmas=ParagraphStyle('firmas',fontName='centuryg',fontSize=7,alignment=1)
      frame_titular1C=Frame(31.9*mm,176*mm,52*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag2.append(frame_titular1C)
      story.append(Paragraph(nombreT1[:27],estilo_firmas))
      story.append(FrameBreak())
      
      frame_cc1C=Frame(31.9*mm,168*mm,52*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag2.append(frame_cc1C)
      story.append(Paragraph(ccT1,estilo_firmas))
      story.append(FrameBreak())
      
      frame_titular2C=Frame(125.53*mm,176*mm,52*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag2.append(frame_titular2C)
      story.append(Paragraph(nombreT2[:27],estilo_firmas))
      story.append(FrameBreak())
      
      frame_cc2C=Frame(125.53*mm,168*mm,52*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag2.append(frame_cc2C)
      story.append(Paragraph(ccT2,estilo_firmas))
      story.append(FrameBreak())
      
      frame_titular3C=Frame(31.9*mm,143*mm,52*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag2.append(frame_titular3C)
      story.append(Paragraph(nombreT3[:27],estilo_firmas))
      story.append(FrameBreak())
      
      frame_cc3C=Frame(31.9*mm,135*mm,52*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag2.append(frame_cc3C)
      story.append(Paragraph(ccT3,estilo_firmas))
      story.append(FrameBreak())
      
      frame_titular4C=Frame(125.53*mm,143*mm,52*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag2.append(frame_titular4C)
      story.append(Paragraph(nombreT4[:27],estilo_firmas))
      story.append(FrameBreak())
      
      frame_cc4C=Frame(125.53*mm,135*mm,52*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag2.append(frame_cc4C)
      story.append(Paragraph(ccT4,estilo_firmas))
      
      page1=PageTemplate(id='pagina1',frames=frames_pag1)
      page2=PageTemplate(id='pagina2',frames=frames_pag2)
      
      doc=BaseDocTemplate(ruta,pageTemplates=[page1,page2],pagesize=LEGAL)
      
      doc.build(story)
      
    def VerificacionQuadrata(self,ruta,nombreT1,nombreT2,nombreT3,nombreT4,
                             ccTitular1,ccTitular2,ccTitular3,ccTitular4,
                             lote,manzana,area,valor,ci,formaci,saldo,formasaldo,
                             fechaEntrega,fechaEscritura,
                             diactr,mesctr,anioctr,ciudad,meses_entrega=36):
      story=[]
      
      frames_pag1=[]
     # Imagen base del doc
      frame_base=Frame(0,0,216*mm,356*mm)
      frames_pag1.append(frame_base)
      pagina1=Image('./resources/Vegas de Venecia/Verificacion-Contrato_Vegas-de-Venecia-V2.png',width=214*mm,height=350*mm)
      story.append(pagina1)
      story.append(FrameBreak())
      
      estilo_titulares=ParagraphStyle('titulares',fontName='centuryg',fontSize=12)
      frame_titular1=Frame(28.5*mm,288.2*mm,133*mm,5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_titular1)
      story.append(Paragraph(nombreT1,estilo_titulares))
      story.append(FrameBreak())
      
      frame_cctitular1=Frame(150*mm,288.2*mm,52*mm,5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_cctitular1)
      story.append(Paragraph(ccTitular1,estilo_titulares))
      story.append(FrameBreak())
      
      frame_titular2=Frame(28.5*mm,282.2*mm,133*mm,5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_titular2)
      story.append(Paragraph(nombreT2,estilo_titulares))
      story.append(FrameBreak())
      
      frame_cctitular2=Frame(150*mm,282.2*mm,52*mm,5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_cctitular2)
      story.append(Paragraph(ccTitular2,estilo_titulares))
      story.append(FrameBreak())
      
      frame_titular3=Frame(28.5*mm,276.2*mm,133*mm,5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_titular3)
      story.append(Paragraph(nombreT3,estilo_titulares))
      story.append(FrameBreak())
      
      frame_cctitular3=Frame(150*mm,276.2*mm,52*mm,5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_cctitular3)
      story.append(Paragraph(ccTitular3,estilo_titulares))
      story.append(FrameBreak())
      
      frame_titular4=Frame(28.5*mm,269.2*mm,133*mm,5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_titular4)
      story.append(Paragraph(nombreT4,estilo_titulares))
      story.append(FrameBreak())
      
      frame_cctitular4=Frame(150*mm,269.2*mm,52*mm,5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_cctitular4)
      story.append(Paragraph(ccTitular4,estilo_titulares))
      story.append(FrameBreak())
      
      estilo_detalle=ParagraphStyle('detalle',fontName='centuryg',fontSize=10,alignment=1)
      frame_lote=Frame(64*mm,245*mm,36*mm,5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_lote)
      story.append(Paragraph(lote,estilo_detalle))
      story.append(FrameBreak())
      
      frame_manzana=Frame(100.2*mm,245*mm,41.8*mm,5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_manzana)
      story.append(Paragraph(manzana,estilo_detalle))
      story.append(FrameBreak())
      
      frame_area=Frame(129.1*mm,245*mm,55.7*mm,5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_area)
      story.append(Paragraph(area,estilo_detalle))
      story.append(FrameBreak())
      
      frame_valor=Frame(71*mm,236.6*mm,30.2*mm,5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_valor)
      story.append(Paragraph(f'{int(valor):,}',estilo_detalle))
      story.append(FrameBreak())
      
      frame_ci=Frame(49.7*mm,221.2*mm,55*mm,5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_ci)
      story.append(Paragraph(f'{int(ci):,}',estilo_detalle))
      story.append(FrameBreak())
      
      estilo_formas=ParagraphStyle('formas',fontName='centuryg',fontSize=8,alignment=4,leading=14)
      
      frame_formaci=Frame(12.5*mm,206.5*mm,191*mm,17.6*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_formaci)
      story.append(Paragraph('&nbsp '*75+formaci,estilo_formas))
      story.append(FrameBreak())
      
      estilo_valores=ParagraphStyle('formas',fontName='centuryg',fontSize=10)
      
      frame_saldo=Frame(49.7*mm,202*mm,55*mm,5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_saldo)
      story.append(Paragraph(f'{int(saldo):,}',estilo_valores))
      story.append(FrameBreak())
      
      frame_formasaldo=Frame(12.5*mm,188.6*mm,191*mm,17.6*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_formasaldo)
      story.append(Paragraph('&nbsp '*75+formasaldo,estilo_formas))
      story.append(FrameBreak())
      
      frame_fechaentrega=Frame(81.2*mm,128.2*mm,35.7*mm,5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_fechaentrega)
      entrega = str(meses_entrega)
      story.append(Paragraph(entrega,estilo_detalle))
      story.append(FrameBreak())
      
      frame_fechaescrit=Frame(117.6*mm,156.7*mm,63.1*mm,5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_fechaescrit)
      story.append(Paragraph(fechaEscritura,estilo_detalle))
      story.append(FrameBreak())
      
      
      
      frame_diaC=Frame(74.5*mm,86.9*mm,22.9*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_diaC)
      story.append(Paragraph(diactr,estilo_detalle))
      story.append(FrameBreak())
      
      frame_mesC=Frame(125.1*mm,86.9*mm,22.9*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_mesC)
      mes = Utilidades().NombreMes(int(mesctr))
      story.append(Paragraph(mes,estilo_detalle))
      story.append(FrameBreak())
      
      frame_añoC=Frame(163.6*mm,86.9*mm,19.5*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_añoC)
      story.append(Paragraph(anioctr,estilo_detalle))
      story.append(FrameBreak())
      
      frame_ciudadC=Frame(29*mm,86.9*mm,36*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_ciudadC)
      story.append(Paragraph(ciudad,estilo_detalle))
      story.append(FrameBreak())
      
      frame_Autotitular1=Frame(35.8*mm,64.5*mm,92*mm,5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_Autotitular1)
      story.append(Paragraph(nombreT1,estilo_titulares))
      story.append(FrameBreak())
      
      frame_Autocctitular1=Frame(26.6*mm,59*mm,54.5*mm,5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_Autocctitular1)
      story.append(Paragraph(ccTitular1,estilo_titulares))
      story.append(FrameBreak())
      
      frame_Autotitular2=Frame(139*mm,64.5*mm,133*mm,5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_Autotitular2)
      story.append(Paragraph(nombreT2,estilo_titulares))
      story.append(FrameBreak())
      
      frame_Autocctitular2=Frame(129.3*mm,59*mm,54.5*mm,5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_Autocctitular2)
      story.append(Paragraph(ccTitular2,estilo_titulares))
      story.append(FrameBreak())
      
      frame_Autotitular3=Frame(35.8*mm,42.8*mm,133*mm,5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_Autotitular3)
      story.append(Paragraph(nombreT3,estilo_titulares))
      story.append(FrameBreak())
      
      frame_Autocctitular3=Frame(26.6*mm,37.3*mm,52*mm,5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_Autocctitular3)
      story.append(Paragraph(ccTitular3,estilo_titulares))
      story.append(FrameBreak())
      
      frame_Autotitular4=Frame(139*mm,42.8*mm,133*mm,5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_Autotitular4)
      story.append(Paragraph(nombreT4,estilo_titulares))
      story.append(FrameBreak())
      
      frame_Autocctitular4=Frame(129.3*mm,37.3*mm,52*mm,5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_Autocctitular4)
      story.append(Paragraph(ccTitular4,estilo_titulares))
      story.append(FrameBreak())
      
      page1=PageTemplate(id='pagina1',frames=frames_pag1)
      doc=BaseDocTemplate(ruta,pageTemplates=page1,pagesize=LEGAL)
      doc.build(story)
      
    def Recibovegas(self,ruta,nroRecibo,titular1,fecha,concepto,valor,direccion,
                    ciudad,telefono,formapag):
      
      story=[]
      frames_pag1=[]
     # Imagen base del doc
      frame_base=Frame(0,0,210*mm,297*mm)
      frames_pag1.append(frame_base)
      pagina1=Image('./resources/Recibo-de-Caja-Vegas-Status.png',width=210*mm,height=150*mm)
      story.append(pagina1)
      story.append(FrameBreak())
      
      estilo_nro=ParagraphStyle('numero',fontName='centuryg',fontSize=14,textColor='#F78369',alignment=1)
      frame_nro=Frame(110*mm,261.8*mm,29*mm,7*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_nro)
      story.append(Paragraph('<b>{}</b>'.format(nroRecibo),estilo_nro))
      story.append(FrameBreak())
      
      estilo_detalle=ParagraphStyle('detalle',fontName='centuryg',fontSize=10)
      frame_tit1=Frame(34*mm,251.8*mm,99*mm,5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_tit1)
      story.append(Paragraph(titular1,estilo_detalle))
      story.append(FrameBreak())
      
      frame_fecha=Frame(149*mm,251.8*mm,48*mm,5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_fecha)
      story.append(Paragraph(fecha,estilo_detalle))
      story.append(FrameBreak())
      
      frame_concepto=Frame(33*mm,245*mm,99*mm,5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_concepto)
      story.append(Paragraph(concepto,estilo_detalle))
      story.append(FrameBreak())
      
      frame_valor=Frame(149*mm,245*mm,60*mm,5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_valor)
      story.append(Paragraph('{:,}'.format(valor),estilo_detalle))
      story.append(FrameBreak())
      
      frame_direccion=Frame(33*mm,238.2*mm,56*mm,5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_direccion)
      story.append(Paragraph(direccion,estilo_detalle))
      story.append(FrameBreak())
      
      frame_ciudad=Frame(101.2*mm,238.2*mm,40*mm,5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_ciudad)
      story.append(Paragraph(ciudad,estilo_detalle))
      story.append(FrameBreak())
      
      frame_telefono=Frame(149*mm,238.2*mm,40*mm,5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_telefono)
      story.append(Paragraph(telefono,estilo_detalle))
      story.append(FrameBreak())
      
      estilo_pago=ParagraphStyle('pago',fontName='centuryg',fontSize=10,alignment=1)
      frame_formapag=Frame(19*mm,210*mm,99*mm,5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_formapag)
      story.append(Paragraph(formapag,estilo_pago))
      story.append(FrameBreak())
      
      frame_valorpag=Frame(121*mm,210*mm,71.3*mm,5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_valorpag)
      story.append(Paragraph('${:,}'.format(valor),estilo_pago))
      story.append(FrameBreak())
      
      frame_total=Frame(121*mm,202.3*mm,71.3*mm,5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_total)
      story.append(Paragraph('<b>${:,}</b>'.format(valor),estilo_pago))
      story.append(FrameBreak())
      
      page1=PageTemplate(id='pagina1',frames=frames_pag1)
      
      doc=BaseDocTemplate(ruta,pageTemplates=page1,pagesize=A4)
      
      doc.build(story)

    def ExportOpcionTamarindos(self,nro_contrato,nombre_t1,cc_t1,tel_t1,cel_t1,
                                    ofic_t1,cdof_t1,telof_t1,
                                    resid_t1,cdresid_t1,telresid_t1,email_t1,
                                    nombre_t2,cc_t2,tel_t2,cel_t2,
                                    ofic_t2,cdof_t2,telof_t2,
                                    resid_t2,cdresid_t2,telresid_t2,email_t2,
                                    nombre_t3,cc_t3,tel_t3,cel_t3,
                                    ofic_t3,cdof_t3,telof_t3,
                                    resid_t3,cdresid_t3,telresid_t3,email_t3,
                                    nombre_t4,cc_t4,tel_t4,cel_t4,
                                    ofic_t4,cdof_t4,telof_t4,
                                    resid_t4,cdresid_t4,telresid_t4,email_t4,
                                    lote,manzana,area,mtsnorte,colnorte,
                                    mtseste,coleste,mtssur,colsur,
                                    mtsoeste,coloeste,
                                    valor,valor_letras,ci,saldo,
                                    contado_x,credic_x,amort_x,
                                    formaCI,formaFN,obs,
                                    dia_contrato,mes_contrato,año_contrato,ruta,
                                    parcelacion,porcDerecho,fraccion):
        
        story=[]
        frames_pag1=[]
     # Imagen base del doc
        frame_base=Frame(0,0,216*mm,356*mm)
        frames_pag1.append(frame_base)
        pagina1=Image('./resources/Opcion Tamarindos.png',width=214*mm,height=350*mm)
        story.append(pagina1)
        story.append(FrameBreak())
        
        estilo_nro=ParagraphStyle('numero',fontName='centuryg',fontSize=14,textColor='#F78369')
        frame_nro=Frame(157*mm,304*mm,40*mm,20*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_nro)
        story.append(Paragraph('<b>Nº {}</b>'.format(nro_contrato),estilo_nro))
        story.append(FrameBreak())
     # Titulares
        estilo_titulares=ParagraphStyle('estilo',fontName='centuryg',fontSize=9)
        estilo_titulares_peq=ParagraphStyle('estilo',fontName='centuryg',fontSize=7)
      # Titular 1
        frame_nombre1=Frame(30*mm,300*mm,76.5*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_nombre1)
        story.append(Paragraph(nombre_t1[:33],estilo_titulares))
        story.append(FrameBreak())
        
        frame_cc1=Frame(114*mm,300*mm,24.5*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_cc1)
        story.append(Paragraph(cc_t1,estilo_titulares))
        story.append(FrameBreak())
        
        frame_tel1=Frame(144*mm,300*mm,23.2*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_tel1)
        story.append(Paragraph(tel_t1,estilo_titulares))
        story.append(FrameBreak())
        
        frame_cel1=Frame(173*mm,300*mm,26.7*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_cel1)
        story.append(Paragraph(cel_t1,estilo_titulares))
        story.append(FrameBreak())
        
        frame_oficina=Frame(26.5*mm,293*mm,81*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_oficina)
        story.append(Paragraph(ofic_t1,estilo_titulares))
        story.append(FrameBreak())
        
        frame_cdof1=Frame(127*mm,293*mm,30.3*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_cdof1)
        story.append(Paragraph(cdof_t1,estilo_titulares))
        story.append(FrameBreak())
        
        frame_telof1=Frame(171*mm,293*mm,29*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_telof1)
        story.append(Paragraph(telof_t1,estilo_titulares))
        story.append(FrameBreak())
        
        frame_resid=Frame(30.5*mm,285.5*mm,76.5*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_resid)
        story.append(Paragraph(resid_t1,estilo_titulares))
        story.append(FrameBreak())
        
        frame_cdres1=Frame(127*mm,285.5*mm,32*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_cdres1)
        story.append(Paragraph(cdresid_t1[:19],estilo_titulares))
        story.append(FrameBreak())
        
        frame_telres1=Frame(171.5*mm,285.5*mm,29*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_telres1)
        story.append(Paragraph(telresid_t1,estilo_titulares))
        story.append(FrameBreak())
        
        frame_email1=Frame(26*mm,279*mm,81*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_email1)
        story.append(Paragraph(email_t1,estilo_titulares))
        story.append(FrameBreak())
        
      # Titular 2
        distancia=28.7*mm
        frame_nombre2=Frame(30*mm,300*mm-distancia,76.5*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_nombre2)
        story.append(Paragraph(nombre_t2,estilo_titulares))
        story.append(FrameBreak())
        
        frame_cc2=Frame(114*mm,300*mm-distancia,24.5*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_cc2)
        story.append(Paragraph(cc_t2,estilo_titulares))
        story.append(FrameBreak())
        
        frame_tel2=Frame(144*mm,300*mm-distancia,23.2*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_tel2)
        story.append(Paragraph(tel_t2,estilo_titulares_peq))
        story.append(FrameBreak())
        
        frame_cel2=Frame(173*mm,300*mm-distancia,26.7*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_cel2)
        story.append(Paragraph(cel_t2,estilo_titulares))
        story.append(FrameBreak())
        
        frame_oficina2=Frame(26.5*mm,293*mm-distancia,81*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_oficina2)
        story.append(Paragraph(ofic_t2,estilo_titulares))
        story.append(FrameBreak())
        
        frame_cdof2=Frame(127*mm,293*mm-distancia,30.3*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_cdof2)
        story.append(Paragraph(cdof_t2,estilo_titulares))
        story.append(FrameBreak())
        
        frame_telof2=Frame(171*mm,293*mm-distancia,29*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_telof2)
        story.append(Paragraph(telof_t2,estilo_titulares))
        story.append(FrameBreak())
        
        frame_resid2=Frame(30.5*mm,285.5*mm-distancia,76.5*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_resid2)
        story.append(Paragraph(resid_t2[:25],estilo_titulares_peq))
        story.append(FrameBreak())
        
        frame_cdres2=Frame(127*mm,285.5*mm-distancia,32*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_cdres2)
        story.append(Paragraph(cdresid_t2[:19],estilo_titulares))
        story.append(FrameBreak())
        
        frame_telres2=Frame(171.5*mm,285.5*mm-distancia,29*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_telres2)
        story.append(Paragraph(telresid_t2,estilo_titulares))
        story.append(FrameBreak())
        
        frame_email2=Frame(26*mm,279*mm-distancia,81*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_email2)
        story.append(Paragraph(email_t2,estilo_titulares))
        story.append(FrameBreak())
        
      # Titular 3
        distancia=(28.7-0.77)*mm*2
        frame_nombre3=Frame(30*mm,300*mm-distancia,76.5*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_nombre3)
        story.append(Paragraph(nombre_t3,estilo_titulares))
        story.append(FrameBreak())
        
        frame_cc3=Frame(114*mm,300*mm-distancia,24.5*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_cc3)
        story.append(Paragraph(cc_t3,estilo_titulares))
        story.append(FrameBreak())
        
        frame_tel3=Frame(144*mm,300*mm-distancia,23.2*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_tel3)
        story.append(Paragraph(tel_t3,estilo_titulares))
        story.append(FrameBreak())
        
        frame_cel3=Frame(173*mm,300*mm-distancia,26.7*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_cel3)
        story.append(Paragraph(cel_t3,estilo_titulares))
        story.append(FrameBreak())
        
        frame_oficina3=Frame(26.5*mm,293*mm-distancia,81*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_oficina3)
        story.append(Paragraph(ofic_t3,estilo_titulares))
        story.append(FrameBreak())
        
        frame_cdof3=Frame(127*mm,293*mm-distancia,30.3*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_cdof3)
        story.append(Paragraph(cdof_t3,estilo_titulares))
        story.append(FrameBreak())
        
        frame_telof3=Frame(171*mm,293*mm-distancia,29*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_telof3)
        story.append(Paragraph(telof_t3,estilo_titulares))
        story.append(FrameBreak())
        
        frame_resid3=Frame(30.5*mm,285.5*mm-distancia,76.5*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_resid3)
        story.append(Paragraph(resid_t3,estilo_titulares))
        story.append(FrameBreak())
        
        frame_cdres3=Frame(127*mm,285.5*mm-distancia,32*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_cdres3)
        story.append(Paragraph(cdresid_t3[:19],estilo_titulares))
        story.append(FrameBreak())
        
        frame_telres3=Frame(171.5*mm,285.5*mm-distancia,29*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_telres3)
        story.append(Paragraph(telresid_t3,estilo_titulares))
        story.append(FrameBreak())
        
        frame_email3=Frame(26*mm,279*mm-distancia,81*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_email3)
        story.append(Paragraph(email_t3,estilo_titulares))
        story.append(FrameBreak())
      
      # Titular 4
        distancia=(28.7-0.87)*mm*3
        frame_nombre4=Frame(30*mm,300*mm-distancia,76.5*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_nombre4)
        story.append(Paragraph(nombre_t4,estilo_titulares))
        story.append(FrameBreak())
        
        frame_cc4=Frame(114*mm,300*mm-distancia,24.5*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_cc4)
        story.append(Paragraph(cc_t4,estilo_titulares))
        story.append(FrameBreak())
        
        frame_tel4=Frame(144*mm,300*mm-distancia,23.2*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_tel4)
        story.append(Paragraph(tel_t4,estilo_titulares))
        story.append(FrameBreak())
        
        frame_cel4=Frame(173*mm,300*mm-distancia,26.7*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_cel4)
        story.append(Paragraph(cel_t4,estilo_titulares))
        story.append(FrameBreak())
        
        frame_oficina4=Frame(26.5*mm,293*mm-distancia,81*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_oficina4)
        story.append(Paragraph(ofic_t4,estilo_titulares))
        story.append(FrameBreak())
        
        frame_cdof4=Frame(127*mm,293*mm-distancia,30.3*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_cdof4)
        story.append(Paragraph(cdof_t4,estilo_titulares))
        story.append(FrameBreak())
        
        frame_telof4=Frame(171*mm,293*mm-distancia,29*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_telof4)
        story.append(Paragraph(telof_t4,estilo_titulares))
        story.append(FrameBreak())
        
        frame_resid4=Frame(30.5*mm,285.5*mm-distancia,76.5*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_resid4)
        story.append(Paragraph(resid_t4,estilo_titulares))
        story.append(FrameBreak())
        
        frame_cdres4=Frame(127*mm,285.5*mm-distancia,32*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_cdres4)
        story.append(Paragraph(cdresid_t4[:19],estilo_titulares))
        story.append(FrameBreak())
        
        frame_telres4=Frame(171.5*mm,285.5*mm-distancia,29*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_telres4)
        story.append(Paragraph(telresid_t4,estilo_titulares))
        story.append(FrameBreak())
        
        frame_email4=Frame(26*mm,279*mm-distancia,81*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_email4)
        story.append(Paragraph(email_t4,estilo_titulares))
        story.append(FrameBreak())
    
     # Datos Inmueble
        estilo_inmueble=ParagraphStyle('inmueble',fontName='centuryg',fontSize=9,alignment=1)
        estilo_inmueble_peq=ParagraphStyle('inmueble',fontName='centuryg',fontSize=7,alignment=1)
        frame_lote=Frame(152.1*mm,171.55*mm,12*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        frames_pag1.append(frame_lote)
        story.append(Paragraph(lote,estilo_inmueble))
        story.append(FrameBreak())
        
        frame_manzana=Frame(126.98*mm,171.55*mm,12*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        frames_pag1.append(frame_manzana)
        story.append(Paragraph(manzana,estilo_inmueble))
        story.append(FrameBreak())
        
        frame_area=Frame(26.5*mm,166.52*mm,12*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        frames_pag1.append(frame_area)
        story.append(Paragraph(area,estilo_inmueble))
        story.append(FrameBreak())
        
        frame_parcelacion=Frame(32.5*mm,171.55*mm,7.2*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        frames_pag1.append(frame_parcelacion)
        story.append(Paragraph(parcelacion,estilo_inmueble))
        story.append(FrameBreak())
        
        frame_porcDerecho=Frame(183*mm,171.55*mm,10*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        frames_pag1.append(frame_porcDerecho)
        story.append(Paragraph(porcDerecho,estilo_inmueble_peq))
        story.append(FrameBreak())
        
        frame_fraccion=Frame(47.7*mm,166.52*mm,12*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        frames_pag1.append(frame_fraccion)
        story.append(Paragraph(fraccion,estilo_inmueble))
        story.append(FrameBreak())
        
        frame_mtsnorte=Frame(27.9*mm,160.26*mm,22.17*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        frames_pag1.append(frame_mtsnorte)
        story.append(Paragraph(mtsnorte,estilo_inmueble))
        story.append(FrameBreak())
        
        frame_colnorte=Frame(67.6*mm,160.26*mm,33.7*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        frames_pag1.append(frame_colnorte)
        story.append(Paragraph(colnorte,estilo_inmueble))
        story.append(FrameBreak())
        
        frame_mtseste=Frame(122.8*mm,160.26*mm,23.55*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        frames_pag1.append(frame_mtseste)
        story.append(Paragraph(mtseste,estilo_inmueble))
        story.append(FrameBreak())
        
        frame_coleste=Frame(165.5*mm,160.26*mm,31.4*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        frames_pag1.append(frame_coleste)
        story.append(Paragraph(coleste,estilo_inmueble))
        story.append(FrameBreak())
        
        frame_mtssur=Frame(25.5*mm,154.92*mm,24.47*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        frames_pag1.append(frame_mtssur)
        story.append(Paragraph(mtssur,estilo_inmueble))
        story.append(FrameBreak())
        
        frame_colsur=Frame(67.6*mm,154.92*mm,33.7*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        frames_pag1.append(frame_colsur)
        story.append(Paragraph(colsur,estilo_inmueble))
        story.append(FrameBreak())
        
        frame_mtsoeste=Frame(122.8*mm,154.92*mm,23.55*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        frames_pag1.append(frame_mtsoeste)
        story.append(Paragraph(mtsoeste,estilo_inmueble))
        story.append(FrameBreak())
        
        frame_coloeste=Frame(165.5*mm,154.92*mm,31.4*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        frames_pag1.append(frame_coloeste)
        story.append(Paragraph(coloeste,estilo_inmueble))
        story.append(FrameBreak())
        
     # Precio y Forma de pago
        estilo_precio=ParagraphStyle('precio',fontName='centuryg',fontSize=8)
        frame_precio=Frame(142*mm,109.3*mm,68.3*mm,5.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        frames_pag1.append(frame_precio)
        story.append(Paragraph('<b>{:,}</b>'.format(valor),estilo_precio))
        story.append(FrameBreak())
        
        frame_valorletras=Frame(41*mm,104.9*mm,180*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        frames_pag1.append(frame_valorletras)
        story.append(Paragraph(valor_letras,estilo_titulares_peq))
        story.append(FrameBreak())
        
        frame_ctainicial=Frame(69.2*mm,100.5*mm,49*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        frames_pag1.append(frame_ctainicial)
        story.append(Paragraph('{:,}'.format(ci),estilo_precio))
        story.append(FrameBreak())
        
        frame_saldo=Frame(159.5*mm,100.5*mm,49*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        frames_pag1.append(frame_saldo)
        story.append(Paragraph('{:,}'.format(saldo),estilo_precio))
        story.append(FrameBreak())
        
        frame_contado=Frame(129.7*mm,94.1*mm,5.5*mm,4.5*mm,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        frames_pag1.append(frame_contado)
        story.append(Paragraph(contado_x,estilo_precio))
        story.append(FrameBreak())
        
        frame_credic=Frame(149.2*mm,94.1*mm,5.5*mm,4.5*mm,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        frames_pag1.append(frame_credic)
        story.append(Paragraph(credic_x,estilo_precio))
        story.append(FrameBreak())
        
        frame_amort=Frame(176.7*mm,94.1*mm,5.5*mm,4.5*mm,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        frames_pag1.append(frame_amort)
        story.append(Paragraph(amort_x,estilo_precio))
        story.append(FrameBreak())
        
        estilo_formas=ParagraphStyle('precio',fontName='centuryg',fontSize=8,leading=20,alignment=4)
        
        frame_formaCI=Frame(18*mm,49.37*mm,88.3*mm,40*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        frames_pag1.append(frame_formaCI)
        story.append(Paragraph(formaCI,estilo_formas))
        story.append(FrameBreak())
        
        frame_formaFN=Frame(112.5*mm,62.37*mm,88.3*mm,27*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        frames_pag1.append(frame_formaFN)
        story.append(Paragraph(formaFN,estilo_formas))
        story.append(FrameBreak())
        
        estilo_obs=ParagraphStyle('precio',fontName='centuryg',fontSize=7,leading=19)
        frame_obs2=Frame(17.5*mm,33.23*mm,183*mm,28.38*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        frames_pag1.append(frame_obs2)
        story.append(Paragraph('&nbsp '*41+obs,estilo_obs))
        
        
     #respaldo
        
        story.append(NextPageTemplate('pagina2'))
        frames_pag2=[]
        frames_pag2.append(frame_base)
        
        
        pagina2=Image('./resources/Opcion Tamarindos 2.png',width=214*mm,height=350*mm)
        story.append(pagina2)
        
        estilo_fecha=ParagraphStyle('fecha contrato',fontName='centuryg',fontSize=9,alignment=1)
      
        frame_dia=Frame(104*mm,95*mm,10.5*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag2.append(frame_dia)
        story.append(Paragraph(dia_contrato,estilo_fecha))
        story.append(FrameBreak())
        
        frame_mes=Frame(133*mm,95*mm,34.6*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag2.append(frame_mes)
        story.append(Paragraph(Utilidades().NombreMes(mes_contrato),estilo_fecha))
        story.append(FrameBreak())
        
        frame_año=Frame(180.5*mm,95*mm,14*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag2.append(frame_año)
        story.append(Paragraph(año_contrato,estilo_fecha))
        story.append(FrameBreak())
        
        page1=PageTemplate(id='pagina1',frames=frames_pag1)
        page2=PageTemplate(id='pagina2',frames=frames_pag2)
        
        doc=BaseDocTemplate(ruta,pageTemplates=[page1,page2],pagesize=LEGAL)
        
        doc.build(story)

    def ExportOpcionAraza(self,nro_contrato,nombre_t1,cc_t1,tel_t1,cel_t1,
                                    ofic_t1,cdof_t1,telof_t1,
                                    resid_t1,cdresid_t1,telresid_t1,email_t1,
                                    nombre_t2,cc_t2,tel_t2,cel_t2,
                                    ofic_t2,cdof_t2,telof_t2,
                                    resid_t2,cdresid_t2,telresid_t2,email_t2,
                                    nombre_t3,cc_t3,tel_t3,cel_t3,
                                    ofic_t3,cdof_t3,telof_t3,
                                    resid_t3,cdresid_t3,telresid_t3,email_t3,
                                    nombre_t4,cc_t4,tel_t4,cel_t4,
                                    ofic_t4,cdof_t4,telof_t4,
                                    resid_t4,cdresid_t4,telresid_t4,email_t4,
                                    lote,manzana,area,mtsnorte,colnorte,
                                    mtseste,coleste,mtssur,colsur,
                                    mtsoeste,coloeste,
                                    valor,valor_letras,ci,saldo,
                                    contado_x,credic_x,amort_x,
                                    formaCI,formaFN,obs,
                                    dia_contrato,mes_contrato,año_contrato,ruta,
                                    parcelacion,porcDerecho,fraccion):
        
        story=[]
        frames_pag1=[]
     # Imagen base del doc
        frame_base=Frame(0,0,216*mm,356*mm)
        frames_pag1.append(frame_base)
        pagina1=Image('./resources/Opcion Araza.png',width=214*mm,height=350*mm)
        story.append(pagina1)
        story.append(FrameBreak())
        
        estilo_nro=ParagraphStyle('numero',fontName='centuryg',fontSize=14,textColor='#F78369')
        frame_nro=Frame(157*mm,304*mm,40*mm,20*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_nro)
        story.append(Paragraph('<b>Nº {}</b>'.format(nro_contrato),estilo_nro))
        story.append(FrameBreak())
     # Titulares
        estilo_titulares=ParagraphStyle('estilo',fontName='centuryg',fontSize=9)
        estilo_titulares_peq=ParagraphStyle('estilo',fontName='centuryg',fontSize=7)
      # Titular 1
        frame_nombre1=Frame(30*mm,300*mm,76.5*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_nombre1)
        story.append(Paragraph(nombre_t1[:33],estilo_titulares))
        story.append(FrameBreak())
        
        frame_cc1=Frame(114*mm,300*mm,24.5*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_cc1)
        story.append(Paragraph(cc_t1,estilo_titulares))
        story.append(FrameBreak())
        
        frame_tel1=Frame(144*mm,300*mm,23.2*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_tel1)
        story.append(Paragraph(tel_t1,estilo_titulares))
        story.append(FrameBreak())
        
        frame_cel1=Frame(173*mm,300*mm,26.7*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_cel1)
        story.append(Paragraph(cel_t1,estilo_titulares))
        story.append(FrameBreak())
        
        frame_oficina=Frame(26.5*mm,293*mm,81*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_oficina)
        story.append(Paragraph(ofic_t1,estilo_titulares))
        story.append(FrameBreak())
        
        frame_cdof1=Frame(127*mm,293*mm,30.3*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_cdof1)
        story.append(Paragraph(cdof_t1,estilo_titulares))
        story.append(FrameBreak())
        
        frame_telof1=Frame(171*mm,293*mm,29*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_telof1)
        story.append(Paragraph(telof_t1,estilo_titulares))
        story.append(FrameBreak())
        
        frame_resid=Frame(30.5*mm,285.5*mm,76.5*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_resid)
        story.append(Paragraph(resid_t1,estilo_titulares))
        story.append(FrameBreak())
        
        frame_cdres1=Frame(127*mm,285.5*mm,32*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_cdres1)
        story.append(Paragraph(cdresid_t1[:19],estilo_titulares))
        story.append(FrameBreak())
        
        frame_telres1=Frame(171.5*mm,285.5*mm,29*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_telres1)
        story.append(Paragraph(telresid_t1,estilo_titulares))
        story.append(FrameBreak())
        
        frame_email1=Frame(26*mm,279*mm,81*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_email1)
        story.append(Paragraph(email_t1,estilo_titulares))
        story.append(FrameBreak())
        
      # Titular 2
        distancia=28.7*mm
        frame_nombre2=Frame(30*mm,300*mm-distancia,76.5*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_nombre2)
        story.append(Paragraph(nombre_t2,estilo_titulares))
        story.append(FrameBreak())
        
        frame_cc2=Frame(114*mm,300*mm-distancia,24.5*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_cc2)
        story.append(Paragraph(cc_t2,estilo_titulares))
        story.append(FrameBreak())
        
        frame_tel2=Frame(144*mm,300*mm-distancia,23.2*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_tel2)
        story.append(Paragraph(tel_t2,estilo_titulares_peq))
        story.append(FrameBreak())
        
        frame_cel2=Frame(173*mm,300*mm-distancia,26.7*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_cel2)
        story.append(Paragraph(cel_t2,estilo_titulares))
        story.append(FrameBreak())
        
        frame_oficina2=Frame(26.5*mm,293*mm-distancia,81*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_oficina2)
        story.append(Paragraph(ofic_t2,estilo_titulares))
        story.append(FrameBreak())
        
        frame_cdof2=Frame(127*mm,293*mm-distancia,30.3*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_cdof2)
        story.append(Paragraph(cdof_t2,estilo_titulares))
        story.append(FrameBreak())
        
        frame_telof2=Frame(171*mm,293*mm-distancia,29*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_telof2)
        story.append(Paragraph(telof_t2,estilo_titulares))
        story.append(FrameBreak())
        
        frame_resid2=Frame(30.5*mm,285.5*mm-distancia,76.5*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_resid2)
        story.append(Paragraph(resid_t2[:25],estilo_titulares_peq))
        story.append(FrameBreak())
        
        frame_cdres2=Frame(127*mm,285.5*mm-distancia,32*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_cdres2)
        story.append(Paragraph(cdresid_t2[:19],estilo_titulares))
        story.append(FrameBreak())
        
        frame_telres2=Frame(171.5*mm,285.5*mm-distancia,29*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_telres2)
        story.append(Paragraph(telresid_t2,estilo_titulares))
        story.append(FrameBreak())
        
        frame_email2=Frame(26*mm,279*mm-distancia,81*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_email2)
        story.append(Paragraph(email_t2,estilo_titulares))
        story.append(FrameBreak())
        
      # Titular 3
        distancia=(28.7-0.77)*mm*2
        frame_nombre3=Frame(30*mm,300*mm-distancia,76.5*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_nombre3)
        story.append(Paragraph(nombre_t3,estilo_titulares))
        story.append(FrameBreak())
        
        frame_cc3=Frame(114*mm,300*mm-distancia,24.5*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_cc3)
        story.append(Paragraph(cc_t3,estilo_titulares))
        story.append(FrameBreak())
        
        frame_tel3=Frame(144*mm,300*mm-distancia,23.2*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_tel3)
        story.append(Paragraph(tel_t3,estilo_titulares))
        story.append(FrameBreak())
        
        frame_cel3=Frame(173*mm,300*mm-distancia,26.7*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_cel3)
        story.append(Paragraph(cel_t3,estilo_titulares))
        story.append(FrameBreak())
        
        frame_oficina3=Frame(26.5*mm,293*mm-distancia,81*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_oficina3)
        story.append(Paragraph(ofic_t3,estilo_titulares))
        story.append(FrameBreak())
        
        frame_cdof3=Frame(127*mm,293*mm-distancia,30.3*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_cdof3)
        story.append(Paragraph(cdof_t3,estilo_titulares))
        story.append(FrameBreak())
        
        frame_telof3=Frame(171*mm,293*mm-distancia,29*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_telof3)
        story.append(Paragraph(telof_t3,estilo_titulares))
        story.append(FrameBreak())
        
        frame_resid3=Frame(30.5*mm,285.5*mm-distancia,76.5*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_resid3)
        story.append(Paragraph(resid_t3,estilo_titulares))
        story.append(FrameBreak())
        
        frame_cdres3=Frame(127*mm,285.5*mm-distancia,32*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_cdres3)
        story.append(Paragraph(cdresid_t3[:19],estilo_titulares))
        story.append(FrameBreak())
        
        frame_telres3=Frame(171.5*mm,285.5*mm-distancia,29*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_telres3)
        story.append(Paragraph(telresid_t3,estilo_titulares))
        story.append(FrameBreak())
        
        frame_email3=Frame(26*mm,279*mm-distancia,81*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_email3)
        story.append(Paragraph(email_t3,estilo_titulares))
        story.append(FrameBreak())
      
      # Titular 4
        distancia=(28.7-0.87)*mm*3
        frame_nombre4=Frame(30*mm,300*mm-distancia,76.5*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_nombre4)
        story.append(Paragraph(nombre_t4,estilo_titulares))
        story.append(FrameBreak())
        
        frame_cc4=Frame(114*mm,300*mm-distancia,24.5*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_cc4)
        story.append(Paragraph(cc_t4,estilo_titulares))
        story.append(FrameBreak())
        
        frame_tel4=Frame(144*mm,300*mm-distancia,23.2*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_tel4)
        story.append(Paragraph(tel_t4,estilo_titulares))
        story.append(FrameBreak())
        
        frame_cel4=Frame(173*mm,300*mm-distancia,26.7*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_cel4)
        story.append(Paragraph(cel_t4,estilo_titulares))
        story.append(FrameBreak())
        
        frame_oficina4=Frame(26.5*mm,293*mm-distancia,81*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_oficina4)
        story.append(Paragraph(ofic_t4,estilo_titulares))
        story.append(FrameBreak())
        
        frame_cdof4=Frame(127*mm,293*mm-distancia,30.3*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_cdof4)
        story.append(Paragraph(cdof_t4,estilo_titulares))
        story.append(FrameBreak())
        
        frame_telof4=Frame(171*mm,293*mm-distancia,29*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_telof4)
        story.append(Paragraph(telof_t4,estilo_titulares))
        story.append(FrameBreak())
        
        frame_resid4=Frame(30.5*mm,285.5*mm-distancia,76.5*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_resid4)
        story.append(Paragraph(resid_t4,estilo_titulares))
        story.append(FrameBreak())
        
        frame_cdres4=Frame(127*mm,285.5*mm-distancia,32*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_cdres4)
        story.append(Paragraph(cdresid_t4[:19],estilo_titulares))
        story.append(FrameBreak())
        
        frame_telres4=Frame(171.5*mm,285.5*mm-distancia,29*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_telres4)
        story.append(Paragraph(telresid_t4,estilo_titulares))
        story.append(FrameBreak())
        
        frame_email4=Frame(26*mm,279*mm-distancia,81*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_email4)
        story.append(Paragraph(email_t4,estilo_titulares))
        story.append(FrameBreak())
    
     # Datos Inmueble
        estilo_inmueble=ParagraphStyle('inmueble',fontName='centuryg',fontSize=9,alignment=1)
        estilo_inmueble_peq=ParagraphStyle('inmueble',fontName='centuryg',fontSize=7,alignment=1)
        frame_lote=Frame(152.1*mm,171.55*mm,12*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        frames_pag1.append(frame_lote)
        story.append(Paragraph(lote,estilo_inmueble))
        story.append(FrameBreak())
        
        frame_manzana=Frame(126.98*mm,171.55*mm,12*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        frames_pag1.append(frame_manzana)
        story.append(Paragraph(manzana,estilo_inmueble))
        story.append(FrameBreak())
        
        frame_area=Frame(26.5*mm,166.52*mm,12*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        frames_pag1.append(frame_area)
        story.append(Paragraph(area,estilo_inmueble))
        story.append(FrameBreak())
        
        frame_parcelacion=Frame(32.5*mm,171.55*mm,7.2*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        frames_pag1.append(frame_parcelacion)
        story.append(Paragraph(parcelacion,estilo_inmueble))
        story.append(FrameBreak())
        
        frame_porcDerecho=Frame(183*mm,171.55*mm,10*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        frames_pag1.append(frame_porcDerecho)
        story.append(Paragraph(porcDerecho,estilo_inmueble_peq))
        story.append(FrameBreak())
        
        frame_fraccion=Frame(47.7*mm,166.52*mm,12*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        frames_pag1.append(frame_fraccion)
        story.append(Paragraph(fraccion,estilo_inmueble))
        story.append(FrameBreak())
        
        frame_mtsnorte=Frame(27.9*mm,160.26*mm,22.17*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        frames_pag1.append(frame_mtsnorte)
        story.append(Paragraph(mtsnorte,estilo_inmueble))
        story.append(FrameBreak())
        
        frame_colnorte=Frame(67.6*mm,160.26*mm,33.7*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        frames_pag1.append(frame_colnorte)
        story.append(Paragraph(colnorte,estilo_inmueble))
        story.append(FrameBreak())
        
        frame_mtseste=Frame(122.8*mm,160.26*mm,23.55*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        frames_pag1.append(frame_mtseste)
        story.append(Paragraph(mtseste,estilo_inmueble))
        story.append(FrameBreak())
        
        frame_coleste=Frame(165.5*mm,160.26*mm,31.4*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        frames_pag1.append(frame_coleste)
        story.append(Paragraph(coleste,estilo_inmueble))
        story.append(FrameBreak())
        
        frame_mtssur=Frame(25.5*mm,154.92*mm,24.47*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        frames_pag1.append(frame_mtssur)
        story.append(Paragraph(mtssur,estilo_inmueble))
        story.append(FrameBreak())
        
        frame_colsur=Frame(67.6*mm,154.92*mm,33.7*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        frames_pag1.append(frame_colsur)
        story.append(Paragraph(colsur,estilo_inmueble))
        story.append(FrameBreak())
        
        frame_mtsoeste=Frame(122.8*mm,154.92*mm,23.55*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        frames_pag1.append(frame_mtsoeste)
        story.append(Paragraph(mtsoeste,estilo_inmueble))
        story.append(FrameBreak())
        
        frame_coloeste=Frame(165.5*mm,154.92*mm,31.4*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        frames_pag1.append(frame_coloeste)
        story.append(Paragraph(coloeste,estilo_inmueble))
        story.append(FrameBreak())
        
     # Precio y Forma de pago
        estilo_precio=ParagraphStyle('precio',fontName='centuryg',fontSize=8)
        frame_precio=Frame(142*mm,109.3*mm,68.3*mm,5.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        frames_pag1.append(frame_precio)
        story.append(Paragraph('<b>{:,}</b>'.format(valor),estilo_precio))
        story.append(FrameBreak())
        
        frame_valorletras=Frame(41*mm,104.9*mm,180*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        frames_pag1.append(frame_valorletras)
        story.append(Paragraph(valor_letras,estilo_titulares_peq))
        story.append(FrameBreak())
        
        frame_ctainicial=Frame(69.2*mm,100.5*mm,49*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        frames_pag1.append(frame_ctainicial)
        story.append(Paragraph('{:,}'.format(ci),estilo_precio))
        story.append(FrameBreak())
        
        frame_saldo=Frame(159.5*mm,100.5*mm,49*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        frames_pag1.append(frame_saldo)
        story.append(Paragraph('{:,}'.format(saldo),estilo_precio))
        story.append(FrameBreak())
        
        frame_contado=Frame(129.7*mm,94.1*mm,5.5*mm,4.5*mm,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        frames_pag1.append(frame_contado)
        story.append(Paragraph(contado_x,estilo_precio))
        story.append(FrameBreak())
        
        frame_credic=Frame(149.2*mm,94.1*mm,5.5*mm,4.5*mm,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        frames_pag1.append(frame_credic)
        story.append(Paragraph(credic_x,estilo_precio))
        story.append(FrameBreak())
        
        frame_amort=Frame(176.7*mm,94.1*mm,5.5*mm,4.5*mm,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        frames_pag1.append(frame_amort)
        story.append(Paragraph(amort_x,estilo_precio))
        story.append(FrameBreak())
        
        estilo_formas=ParagraphStyle('precio',fontName='centuryg',fontSize=8,leading=20,alignment=4)
        
        frame_formaCI=Frame(18*mm,49.37*mm,88.3*mm,40*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        frames_pag1.append(frame_formaCI)
        story.append(Paragraph(formaCI,estilo_formas))
        story.append(FrameBreak())
        
        frame_formaFN=Frame(112.5*mm,62.37*mm,88.3*mm,27*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        frames_pag1.append(frame_formaFN)
        story.append(Paragraph(formaFN,estilo_formas))
        story.append(FrameBreak())
        
        estilo_obs=ParagraphStyle('precio',fontName='centuryg',fontSize=7,leading=19)
        frame_obs2=Frame(17.5*mm,33.23*mm,183*mm,28.38*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        frames_pag1.append(frame_obs2)
        story.append(Paragraph('&nbsp '*41+obs,estilo_obs))
        
        
     #respaldo
        
        story.append(NextPageTemplate('pagina2'))
        frames_pag2=[]
        frames_pag2.append(frame_base)
        
        
        pagina2=Image('./resources/Opcion Araza 2.png',width=214*mm,height=350*mm)
        story.append(pagina2)
        
        estilo_fecha=ParagraphStyle('fecha contrato',fontName='centuryg',fontSize=9,alignment=1)
      
        frame_dia=Frame(104*mm,95*mm,10.5*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag2.append(frame_dia)
        story.append(Paragraph(dia_contrato,estilo_fecha))
        story.append(FrameBreak())
        
        frame_mes=Frame(133*mm,95*mm,34.6*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag2.append(frame_mes)
        story.append(Paragraph(Utilidades().NombreMes(mes_contrato),estilo_fecha))
        story.append(FrameBreak())
        
        frame_año=Frame(180.5*mm,95*mm,14*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag2.append(frame_año)
        story.append(Paragraph(año_contrato,estilo_fecha))
        story.append(FrameBreak())
        
        page1=PageTemplate(id='pagina1',frames=frames_pag1)
        page2=PageTemplate(id='pagina2',frames=frames_pag2)
        
        doc=BaseDocTemplate(ruta,pageTemplates=[page1,page2],pagesize=LEGAL)
        
        doc.build(story)

    def ExportOpcionTesoro(self,nro_contrato,nombre_t1,cc_t1,tel_t1,cel_t1,
                                    ofic_t1,cdof_t1,telof_t1,
                                    resid_t1,cdresid_t1,telresid_t1,email_t1,
                                    nombre_t2,cc_t2,tel_t2,cel_t2,
                                    ofic_t2,cdof_t2,telof_t2,
                                    resid_t2,cdresid_t2,telresid_t2,email_t2,
                                    nombre_t3,cc_t3,tel_t3,cel_t3,
                                    ofic_t3,cdof_t3,telof_t3,
                                    resid_t3,cdresid_t3,telresid_t3,email_t3,
                                    nombre_t4,cc_t4,tel_t4,cel_t4,
                                    ofic_t4,cdof_t4,telof_t4,
                                    resid_t4,cdresid_t4,telresid_t4,email_t4,
                                    lote,manzana,area,mtsnorte,colnorte,
                                    mtseste,coleste,mtssur,colsur,
                                    mtsoeste,coloeste,
                                    valor,valor_letras,ci,saldo,
                                    contado_x,credic_x,amort_x,
                                    formaCI,formaFN,obs,
                                    dia_contrato,mes_contrato,año_contrato,ruta,
                                    parcelacion,porcDerecho,fraccion,meses_entrega):
        
        story=[]
        frames_pag1=[]
     # Imagen base del doc
        frame_base=Frame(0,0,216*mm,356*mm)
        frames_pag1.append(frame_base)
        pagina1=Image('./resources/Contrato de opcion de compra - Tesoro Escondido1 -1.png',width=214*mm,height=350*mm)
        story.append(pagina1)
        story.append(FrameBreak())
        
        estilo_nro=ParagraphStyle('numero',fontName='centuryg',fontSize=14,textColor='#F78369')
        frame_nro=Frame(157*mm,304*mm,40*mm,20*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_nro)
        story.append(Paragraph('<b>Nº {}</b>'.format(nro_contrato),estilo_nro))
        story.append(FrameBreak())
     # Titulares
        estilo_titulares=ParagraphStyle('estilo',fontName='centuryg',fontSize=9)
        estilo_titulares_peq=ParagraphStyle('estilo',fontName='centuryg',fontSize=7)
      # Titular 1
        frame_nombre1=Frame(30*mm,300*mm,76.5*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_nombre1)
        story.append(Paragraph(nombre_t1[:33],estilo_titulares))
        story.append(FrameBreak())
        
        frame_cc1=Frame(114*mm,300*mm,24.5*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_cc1)
        story.append(Paragraph(cc_t1,estilo_titulares))
        story.append(FrameBreak())
        
        frame_tel1=Frame(144*mm,300*mm,23.2*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_tel1)
        story.append(Paragraph(tel_t1,estilo_titulares))
        story.append(FrameBreak())
        
        frame_cel1=Frame(173*mm,300*mm,26.7*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_cel1)
        story.append(Paragraph(cel_t1,estilo_titulares))
        story.append(FrameBreak())
        
        frame_oficina=Frame(26.5*mm,293*mm,81*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_oficina)
        story.append(Paragraph(ofic_t1,estilo_titulares))
        story.append(FrameBreak())
        
        frame_cdof1=Frame(127*mm,293*mm,30.3*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_cdof1)
        story.append(Paragraph(cdof_t1,estilo_titulares))
        story.append(FrameBreak())
        
        frame_telof1=Frame(171*mm,293*mm,29*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_telof1)
        story.append(Paragraph(telof_t1,estilo_titulares))
        story.append(FrameBreak())
        
        frame_resid=Frame(30.5*mm,285.5*mm,76.5*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_resid)
        story.append(Paragraph(resid_t1,estilo_titulares))
        story.append(FrameBreak())
        
        frame_cdres1=Frame(127*mm,285.5*mm,32*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_cdres1)
        story.append(Paragraph(cdresid_t1[:19],estilo_titulares))
        story.append(FrameBreak())
        
        frame_telres1=Frame(171.5*mm,285.5*mm,29*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_telres1)
        story.append(Paragraph(telresid_t1,estilo_titulares))
        story.append(FrameBreak())
        
        frame_email1=Frame(26*mm,279*mm,81*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_email1)
        story.append(Paragraph(email_t1,estilo_titulares))
        story.append(FrameBreak())
        
      # Titular 2
        distancia=28.7*mm
        frame_nombre2=Frame(30*mm,300*mm-distancia,76.5*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_nombre2)
        story.append(Paragraph(nombre_t2,estilo_titulares))
        story.append(FrameBreak())
        
        frame_cc2=Frame(114*mm,300*mm-distancia,24.5*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_cc2)
        story.append(Paragraph(cc_t2,estilo_titulares))
        story.append(FrameBreak())
        
        frame_tel2=Frame(144*mm,300*mm-distancia,23.2*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_tel2)
        story.append(Paragraph(tel_t2,estilo_titulares_peq))
        story.append(FrameBreak())
        
        frame_cel2=Frame(173*mm,300*mm-distancia,26.7*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_cel2)
        story.append(Paragraph(cel_t2,estilo_titulares))
        story.append(FrameBreak())
        
        frame_oficina2=Frame(26.5*mm,293*mm-distancia,81*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_oficina2)
        story.append(Paragraph(ofic_t2,estilo_titulares))
        story.append(FrameBreak())
        
        frame_cdof2=Frame(127*mm,293*mm-distancia,30.3*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_cdof2)
        story.append(Paragraph(cdof_t2,estilo_titulares))
        story.append(FrameBreak())
        
        frame_telof2=Frame(171*mm,293*mm-distancia,29*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_telof2)
        story.append(Paragraph(telof_t2,estilo_titulares))
        story.append(FrameBreak())
        
        frame_resid2=Frame(30.5*mm,285.5*mm-distancia,76.5*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_resid2)
        story.append(Paragraph(resid_t2[:25],estilo_titulares_peq))
        story.append(FrameBreak())
        
        frame_cdres2=Frame(127*mm,285.5*mm-distancia,32*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_cdres2)
        story.append(Paragraph(cdresid_t2[:19],estilo_titulares))
        story.append(FrameBreak())
        
        frame_telres2=Frame(171.5*mm,285.5*mm-distancia,29*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_telres2)
        story.append(Paragraph(telresid_t2,estilo_titulares))
        story.append(FrameBreak())
        
        frame_email2=Frame(26*mm,279*mm-distancia,81*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_email2)
        story.append(Paragraph(email_t2,estilo_titulares))
        story.append(FrameBreak())
        
      # Titular 3
        distancia=(28.7-0.77)*mm*2
        frame_nombre3=Frame(30*mm,300*mm-distancia,76.5*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_nombre3)
        story.append(Paragraph(nombre_t3,estilo_titulares))
        story.append(FrameBreak())
        
        frame_cc3=Frame(114*mm,300*mm-distancia,24.5*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_cc3)
        story.append(Paragraph(cc_t3,estilo_titulares))
        story.append(FrameBreak())
        
        frame_tel3=Frame(144*mm,300*mm-distancia,23.2*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_tel3)
        story.append(Paragraph(tel_t3,estilo_titulares))
        story.append(FrameBreak())
        
        frame_cel3=Frame(173*mm,300*mm-distancia,26.7*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_cel3)
        story.append(Paragraph(cel_t3,estilo_titulares))
        story.append(FrameBreak())
        
        frame_oficina3=Frame(26.5*mm,293*mm-distancia,81*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_oficina3)
        story.append(Paragraph(ofic_t3,estilo_titulares))
        story.append(FrameBreak())
        
        frame_cdof3=Frame(127*mm,293*mm-distancia,30.3*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_cdof3)
        story.append(Paragraph(cdof_t3,estilo_titulares))
        story.append(FrameBreak())
        
        frame_telof3=Frame(171*mm,293*mm-distancia,29*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_telof3)
        story.append(Paragraph(telof_t3,estilo_titulares))
        story.append(FrameBreak())
        
        frame_resid3=Frame(30.5*mm,285.5*mm-distancia,76.5*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_resid3)
        story.append(Paragraph(resid_t3,estilo_titulares))
        story.append(FrameBreak())
        
        frame_cdres3=Frame(127*mm,285.5*mm-distancia,32*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_cdres3)
        story.append(Paragraph(cdresid_t3[:19],estilo_titulares))
        story.append(FrameBreak())
        
        frame_telres3=Frame(171.5*mm,285.5*mm-distancia,29*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_telres3)
        story.append(Paragraph(telresid_t3,estilo_titulares))
        story.append(FrameBreak())
        
        frame_email3=Frame(26*mm,279*mm-distancia,81*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_email3)
        story.append(Paragraph(email_t3,estilo_titulares))
        story.append(FrameBreak())
      
      # Titular 4
        distancia=(28.7-0.87)*mm*3
        frame_nombre4=Frame(30*mm,300*mm-distancia,76.5*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_nombre4)
        story.append(Paragraph(nombre_t4,estilo_titulares))
        story.append(FrameBreak())
        
        frame_cc4=Frame(114*mm,300*mm-distancia,24.5*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_cc4)
        story.append(Paragraph(cc_t4,estilo_titulares))
        story.append(FrameBreak())
        
        frame_tel4=Frame(144*mm,300*mm-distancia,23.2*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_tel4)
        story.append(Paragraph(tel_t4,estilo_titulares))
        story.append(FrameBreak())
        
        frame_cel4=Frame(173*mm,300*mm-distancia,26.7*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_cel4)
        story.append(Paragraph(cel_t4,estilo_titulares))
        story.append(FrameBreak())
        
        frame_oficina4=Frame(26.5*mm,293*mm-distancia,81*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_oficina4)
        story.append(Paragraph(ofic_t4,estilo_titulares))
        story.append(FrameBreak())
        
        frame_cdof4=Frame(127*mm,293*mm-distancia,30.3*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_cdof4)
        story.append(Paragraph(cdof_t4,estilo_titulares))
        story.append(FrameBreak())
        
        frame_telof4=Frame(171*mm,293*mm-distancia,29*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_telof4)
        story.append(Paragraph(telof_t4,estilo_titulares))
        story.append(FrameBreak())
        
        frame_resid4=Frame(30.5*mm,285.5*mm-distancia,76.5*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_resid4)
        story.append(Paragraph(resid_t4,estilo_titulares))
        story.append(FrameBreak())
        
        frame_cdres4=Frame(127*mm,285.5*mm-distancia,32*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_cdres4)
        story.append(Paragraph(cdresid_t4[:19],estilo_titulares))
        story.append(FrameBreak())
        
        frame_telres4=Frame(171.5*mm,285.5*mm-distancia,29*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_telres4)
        story.append(Paragraph(telresid_t4,estilo_titulares))
        story.append(FrameBreak())
        
        frame_email4=Frame(26*mm,279*mm-distancia,81*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_email4)
        story.append(Paragraph(email_t4,estilo_titulares))
        story.append(FrameBreak())
    
     # Datos Inmueble
        estilo_inmueble=ParagraphStyle('inmueble',fontName='centuryg',fontSize=9,alignment=1)
        estilo_inmueble_peq=ParagraphStyle('inmueble',fontName='centuryg',fontSize=7,alignment=1)
        frame_lote=Frame(152.1*mm,171.55*mm,12*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        frames_pag1.append(frame_lote)
        story.append(Paragraph(lote,estilo_inmueble))
        story.append(FrameBreak())
        
        frame_manzana=Frame(126.98*mm,171.55*mm,12*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        frames_pag1.append(frame_manzana)
        story.append(Paragraph(manzana,estilo_inmueble))
        story.append(FrameBreak())
        
        frame_area=Frame(26.5*mm,166.52*mm,12*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        frames_pag1.append(frame_area)
        story.append(Paragraph(area,estilo_inmueble))
        story.append(FrameBreak())
        
        frame_parcelacion=Frame(32.5*mm,171.55*mm,7.2*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        frames_pag1.append(frame_parcelacion)
        story.append(Paragraph(parcelacion,estilo_inmueble))
        story.append(FrameBreak())
        
        frame_porcDerecho=Frame(183*mm,171.55*mm,10*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        frames_pag1.append(frame_porcDerecho)
        story.append(Paragraph(porcDerecho,estilo_inmueble_peq))
        story.append(FrameBreak())
        
        frame_fraccion=Frame(47.7*mm,166.52*mm,12*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        frames_pag1.append(frame_fraccion)
        story.append(Paragraph(fraccion,estilo_inmueble))
        story.append(FrameBreak())
        
        frame_mtsnorte=Frame(27.9*mm,160.26*mm,22.17*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        frames_pag1.append(frame_mtsnorte)
        story.append(Paragraph(mtsnorte,estilo_inmueble))
        story.append(FrameBreak())
        
        frame_colnorte=Frame(67.6*mm,160.26*mm,33.7*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        frames_pag1.append(frame_colnorte)
        story.append(Paragraph(colnorte,estilo_inmueble))
        story.append(FrameBreak())
        
        frame_mtseste=Frame(122.8*mm,160.26*mm,23.55*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        frames_pag1.append(frame_mtseste)
        story.append(Paragraph(mtseste,estilo_inmueble))
        story.append(FrameBreak())
        
        frame_coleste=Frame(165.5*mm,160.26*mm,31.4*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        frames_pag1.append(frame_coleste)
        story.append(Paragraph(coleste,estilo_inmueble))
        story.append(FrameBreak())
        
        frame_mtssur=Frame(25.5*mm,154.92*mm,24.47*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        frames_pag1.append(frame_mtssur)
        story.append(Paragraph(mtssur,estilo_inmueble))
        story.append(FrameBreak())
        
        frame_colsur=Frame(67.6*mm,154.92*mm,33.7*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        frames_pag1.append(frame_colsur)
        story.append(Paragraph(colsur,estilo_inmueble))
        story.append(FrameBreak())
        
        frame_mtsoeste=Frame(122.8*mm,154.92*mm,23.55*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        frames_pag1.append(frame_mtsoeste)
        story.append(Paragraph(mtsoeste,estilo_inmueble))
        story.append(FrameBreak())
        
        frame_coloeste=Frame(165.5*mm,154.92*mm,31.4*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        frames_pag1.append(frame_coloeste)
        story.append(Paragraph(coloeste,estilo_inmueble))
        story.append(FrameBreak())
        
     # Precio y Forma de pago
        estilo_precio=ParagraphStyle('precio',fontName='centuryg',fontSize=8)
        frame_precio=Frame(142*mm,109.3*mm,68.3*mm,5.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        frames_pag1.append(frame_precio)
        story.append(Paragraph('<b>{:,}</b>'.format(valor),estilo_precio))
        story.append(FrameBreak())
        
        frame_valorletras=Frame(41*mm,104.9*mm,180*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        frames_pag1.append(frame_valorletras)
        story.append(Paragraph(valor_letras,estilo_titulares_peq))
        story.append(FrameBreak())
        
        frame_ctainicial=Frame(69.2*mm,100.5*mm,49*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        frames_pag1.append(frame_ctainicial)
        story.append(Paragraph('{:,}'.format(ci),estilo_precio))
        story.append(FrameBreak())
        
        frame_saldo=Frame(159.5*mm,100.5*mm,49*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        frames_pag1.append(frame_saldo)
        story.append(Paragraph('{:,}'.format(saldo),estilo_precio))
        story.append(FrameBreak())
        
        frame_contado=Frame(125.8*mm,93.4*mm,5.5*mm,4.5*mm,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        frames_pag1.append(frame_contado)
        story.append(Paragraph(contado_x,estilo_precio))
        story.append(FrameBreak())
        
        frame_credic=Frame(147.8*mm,93.4*mm,5.5*mm,4.5*mm,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        frames_pag1.append(frame_credic)
        story.append(Paragraph(credic_x,estilo_precio))
        story.append(FrameBreak())
        
        frame_amort=Frame(176.7*mm,93.4*mm,5.5*mm,4.5*mm,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        frames_pag1.append(frame_amort)
        story.append(Paragraph(amort_x,estilo_precio))
        story.append(FrameBreak())
        
        estilo_formas=ParagraphStyle('precio',fontName='centuryg',fontSize=8,leading=20,alignment=4)
        estilo_formas_CI=ParagraphStyle('precio',fontName='centuryg',fontSize=6,leading=20,alignment=4)
        
        frame_formaCI=Frame(18*mm,49.37*mm,88.3*mm,40*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        frames_pag1.append(frame_formaCI)
        story.append(Paragraph(formaCI,estilo_formas_CI))
        story.append(FrameBreak())
        
        frame_formaFN=Frame(112.5*mm,62.37*mm,88.3*mm,27*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        frames_pag1.append(frame_formaFN)
        story.append(Paragraph(formaFN,estilo_formas))
        story.append(FrameBreak())
        
        estilo_obs=ParagraphStyle('precio',fontName='centuryg',fontSize=7,leading=19)
        frame_obs2=Frame(17.5*mm,33.23*mm,183*mm,28.38*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
        frames_pag1.append(frame_obs2)
        story.append(Paragraph('&nbsp '*41+obs,estilo_obs))
        
        
     #respaldo
        
        story.append(NextPageTemplate('pagina2'))
        frames_pag2=[]
        frames_pag2.append(frame_base)
        
        
        pagina2=Image('./resources/Contrato de opcion de compra - Tesoro Escondido1 -2.png',width=214*mm,height=350*mm)
        story.append(pagina2)
        
        estilo_fecha=ParagraphStyle('fecha contrato',fontName='centuryg',fontSize=9,alignment=1)
        estilo_fecha_peq=ParagraphStyle('fecha contrato',fontName='centuryg',fontSize=7,alignment=1)
        
        frame_meses_entrega=Frame(170.5*mm,288.3*mm,10*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag2.append(frame_meses_entrega)
        story.append(Paragraph(meses_entrega,estilo_fecha_peq))
        story.append(FrameBreak())
        
        frame_dia=Frame(104*mm,95*mm,10.5*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag2.append(frame_dia)
        story.append(Paragraph(dia_contrato,estilo_fecha))
        story.append(FrameBreak())
        
        frame_mes=Frame(133*mm,95*mm,34.6*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag2.append(frame_mes)
        story.append(Paragraph(Utilidades().NombreMes(mes_contrato),estilo_fecha))
        story.append(FrameBreak())
        
        frame_año=Frame(180.5*mm,95*mm,14*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag2.append(frame_año)
        story.append(Paragraph(año_contrato,estilo_fecha))
        story.append(FrameBreak())
        
        page1=PageTemplate(id='pagina1',frames=frames_pag1)
        page2=PageTemplate(id='pagina2',frames=frames_pag2)
        
        doc=BaseDocTemplate(ruta,pageTemplates=[page1,page2],pagesize=LEGAL)
        
        doc.build(story)

    def ExportOpcionSotavento(self,nro_contrato,nombre_t1,cc_t1,tel_t1,cel_t1,
                                    ofic_t1,cdof_t1,telof_t1,
                                    resid_t1,cdresid_t1,telresid_t1,email_t1,
                                    nombre_t2,cc_t2,tel_t2,cel_t2,
                                    ofic_t2,cdof_t2,telof_t2,
                                    resid_t2,cdresid_t2,telresid_t2,email_t2,
                                    nombre_t3,cc_t3,tel_t3,cel_t3,
                                    ofic_t3,cdof_t3,telof_t3,
                                    resid_t3,cdresid_t3,telresid_t3,email_t3,
                                    nombre_t4,cc_t4,tel_t4,cel_t4,
                                    ofic_t4,cdof_t4,telof_t4,
                                    resid_t4,cdresid_t4,telresid_t4,email_t4,
                                    lote,manzana,area,mtsnorte,colnorte,
                                    mtseste,coleste,mtssur,colsur,
                                    mtsoeste,coloeste,
                                    valor,valor_letras,ci,saldo,
                                    contado_x,credic_x,amort_x,
                                    formaCI,formaFN,obs,meses_entrega,
                                    dia_contrato,mes_contrato,año_contrato,ruta):
        
      story=[]
      frames_pag1=[]
      grupos=[]
      # Imagen base del doc
      frame_base=Frame(0,0,216*mm,356*mm)
      frames_pag1.append(frame_base)
      pagina1=Image('./resources/Sotavento/Contrato de opcion de compra V1 -pag 1.png',width=214*mm,height=350*mm)
      story.append(pagina1)
      story.append(FrameBreak())
      
      estilo_nro=ParagraphStyle('numero',fontName='centuryg',fontSize=14,textColor='#F78369')
      frame_nro=Frame(184.5*mm,307.2*mm,40*mm,20*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_nro)
      story.append(Paragraph('<b>Nº {}</b>'.format(nro_contrato),estilo_nro))
      story.append(FrameBreak())
      # Titulares
      estilo_titulares=ParagraphStyle('estilo',fontName='centuryg',fontSize=9)
      # Titular 1
      frame_nombre1=Frame(31*mm,294.5*mm,76.5*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      grupos.append((frame_nombre1,nombre_t1))
      
      frame_cc1=Frame(114*mm,294.5*mm,24.5*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      grupos.append((frame_cc1,cc_t1))
      
      frame_tel1=Frame(144*mm,294.5*mm,23.2*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      grupos.append((frame_tel1,tel_t1))
      
      frame_cel1=Frame(173*mm,294.5*mm,26.7*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      grupos.append((frame_cel1,cel_t1))
      
      frame_oficina=Frame(26.5*mm,287.6*mm,81*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      grupos.append((frame_oficina,ofic_t1))
      
      frame_cdof1=Frame(127*mm,287.6*mm,30.3*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      grupos.append((frame_cdof1,cdof_t1))
      
      frame_telof1=Frame(171*mm,287.6*mm,29*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      grupos.append((frame_telof1,telof_t1))
      
      frame_resid=Frame(30.5*mm,280.4*mm,76.5*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      grupos.append((frame_resid,resid_t1))
      
      frame_cdres1=Frame(127*mm,280.4*mm,30.3*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      grupos.append((frame_cdres1,cdresid_t1))
      
      frame_telres1=Frame(171.5*mm,280.4*mm,29*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      grupos.append((frame_telres1,telresid_t1))
      
      frame_email1=Frame(26*mm,273.6*mm,81*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      grupos.append((frame_email1,email_t1))
      
      # Titular 2
      distancia=27.7*mm
      frame_nombre2=Frame(31*mm,294.5*mm-distancia,76.5*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      grupos.append((frame_nombre2,nombre_t2))
      
      frame_cc2=Frame(114*mm,294.5*mm-distancia,24.5*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      grupos.append((frame_cc2,cc_t2))
      
      frame_tel2=Frame(144*mm,294.5*mm-distancia,23.2*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      grupos.append((frame_tel2,tel_t2))
      
      frame_cel2=Frame(173*mm,294.5*mm-distancia,26.7*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      grupos.append((frame_cel2,cel_t2))
      
      frame_oficina2=Frame(26.5*mm,287.6*mm-distancia,81*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      grupos.append((frame_oficina2,ofic_t2))
      
      frame_cdof2=Frame(127*mm,287.6*mm-distancia,30.3*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      grupos.append((frame_cdof2,cdof_t2))
      
      frame_telof2=Frame(171*mm,287.6*mm-distancia,29*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      grupos.append((frame_telof2,telof_t2))
      
      frame_resid2=Frame(30.5*mm,280.4*mm-distancia,76.5*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      grupos.append((frame_resid2,resid_t2))
      
      frame_cdres2=Frame(127*mm,280.4*mm-distancia,30.3*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      grupos.append((frame_cdres2,cdresid_t2))
      
      frame_telres2=Frame(171.5*mm,280.4*mm-distancia,29*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      grupos.append((frame_telres2,telresid_t2))
      
      frame_email2=Frame(26*mm,273.6*mm-distancia,81*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      grupos.append((frame_email2,email_t2))
    
     # Titular 3
      distancia=27.7*mm*2
      frame_nombre3=Frame(31*mm,294.5*mm-distancia,76.5*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      grupos.append((frame_nombre3,nombre_t3))
      
      frame_cc3=Frame(114*mm,294.5*mm-distancia,24.5*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      grupos.append((frame_cc3,cc_t3))
      
      frame_tel3=Frame(144*mm,294.5*mm-distancia,23.2*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      grupos.append((frame_tel3,tel_t3))
      
      frame_cel3=Frame(173*mm,294.5*mm-distancia,26.7*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      grupos.append((frame_cel3,cel_t3))
      
      frame_oficina3=Frame(26.5*mm,287.6*mm-distancia,81*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      grupos.append((frame_oficina3,ofic_t3))
      
      frame_cdof3=Frame(127*mm,287.6*mm-distancia,30.3*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      grupos.append((frame_cdof3,cdof_t3))
      
      frame_telof3=Frame(171*mm,287.6*mm-distancia,29*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      grupos.append((frame_telof3,telof_t3))
      
      frame_resid3=Frame(30.5*mm,280.4*mm-distancia,76.5*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      grupos.append((frame_resid3,resid_t3))
      
      frame_cdres3=Frame(127*mm,280.4*mm-distancia,30.3*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      grupos.append((frame_cdres3,cdresid_t3))
      
      frame_telres3=Frame(171.5*mm,280.4*mm-distancia,29*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      grupos.append((frame_telres3,telresid_t3))
      
      frame_email3=Frame(26*mm,273.6*mm-distancia,81*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      grupos.append((frame_email3,email_t3))
      
     # Titular 4
      distancia=27.7*mm*3
      frame_nombre4=Frame(31*mm,294.5*mm-distancia,76.5*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      grupos.append((frame_nombre4,nombre_t4))
              
      frame_cc4=Frame(114*mm,294.5*mm-distancia,24.5*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      grupos.append((frame_cc4,cc_t4))
      
      frame_tel4=Frame(144*mm,294.5*mm-distancia,23.2*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      grupos.append((frame_tel4,tel_t4))
      
      frame_cel4=Frame(173*mm,294.5*mm-distancia,26.7*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      grupos.append((frame_cel4,cel_t4))
      
      frame_oficina4=Frame(26.5*mm,287.6*mm-distancia,81*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      grupos.append((frame_oficina4,ofic_t4))
      
      frame_cdof4=Frame(127*mm,287.6*mm-distancia,30.3*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      grupos.append((frame_cdof4,cdof_t4))
      
      frame_telof4=Frame(171*mm,287.6*mm-distancia,29*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      grupos.append((frame_telof4,telof_t4))
              
      frame_resid4=Frame(30.5*mm,280.4*mm-distancia,76.5*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      grupos.append((frame_resid4,resid_t4))
      
      frame_cdres4=Frame(127*mm,280.4*mm-distancia,30.3*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      grupos.append((frame_cdres4,cdresid_t4))
      
      frame_telres4=Frame(171.5*mm,280.4*mm-distancia,29*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      grupos.append((frame_telres4,telresid_t4))
      
      frame_email4=Frame(26*mm,273.6*mm-distancia,81*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      grupos.append((frame_email4,email_t4))
  
      for grupo in grupos:
        contenido=grupo[1]
        if contenido!=None and contenido!='None':
          frame=grupo[0]
          fontName='centuryg'
          fontSize=9
          estilo=ParagraphStyle('estilo',fontName=fontName,fontSize=fontSize)
          flowable=Paragraph(contenido,estilo)
          textwidth=stringWidth(contenido,'centuryG',fontSize)
          i=1
          j=1
          while textwidth>frame._aW:
            if fontSize>6:
              fontSize-=i
            else:
              contenido=contenido[:len(contenido)-j]
            estilo=ParagraphStyle('estilo',fontName=fontName,fontSize=fontSize)
            flowable=Paragraph(contenido,estilo)
            textwidth=stringWidth(contenido,'centuryG',fontSize)
            i+=1
            j+=1
          frames_pag1.append(frame)
          story.append(flowable)
          story.append(FrameBreak())
      grupos=[]

     # Datos Inmueble
      estilo_inmueble=ParagraphStyle('inmueble',fontName='centuryg',fontSize=9,alignment=1)
      frame_lote=Frame(19.5*mm,164.2*mm,12*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
      grupos.append((frame_lote,lote))
      
      frame_manzana=Frame(42.3*mm,164.2*mm,12*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
      grupos.append((frame_manzana,manzana))
      
      frame_area=Frame(61*mm,164.2*mm,11*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
      grupos.append((frame_area,area))
      
      frame_mtsnorte=Frame(28.8*mm,159.1*mm,22.17*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
      grupos.append((frame_mtsnorte,mtsnorte))
      
      frame_colnorte=Frame(68.4*mm,159.1*mm,33.7*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
      grupos.append((frame_colnorte,colnorte))
      
      frame_mtseste=Frame(123.6*mm,159.1*mm,23.55*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
      grupos.append((frame_mtseste,mtseste))
      
      frame_coleste=Frame(166.3*mm,159.1*mm,31.4*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
      grupos.append((frame_coleste,coleste))
      
      frame_mtssur=Frame(26.3*mm,153.3*mm,24.47*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
      grupos.append((frame_mtssur,mtssur))
      
      frame_colsur=Frame(68.4*mm,153.3*mm,33.7*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
      grupos.append((frame_colsur,colsur))
      
      frame_mtsoeste=Frame(123.6*mm,153.3*mm,23.55*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
      grupos.append((frame_mtsoeste,mtsoeste))
      
      frame_coloeste=Frame(166.3*mm,153.3*mm,31.4*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
      grupos.append((frame_coloeste,coloeste))
      
      for grupo in grupos:
        contenido=grupo[1]
        if contenido!=None and contenido!='None':
          frame=grupo[0]
          fontName='centuryg'
          fontSize=9
          estilo=ParagraphStyle('estilo',fontName=fontName,fontSize=fontSize,alignment=1)
          flowable=Paragraph(contenido,estilo)
          textwidth=stringWidth(contenido,'centuryG',fontSize)
          i=1
          j=1
          while textwidth>frame._aW:
            if fontSize>6:
              fontSize-=i
            else:
              contenido=contenido[:len(contenido)-j]
            estilo=ParagraphStyle('estilo',fontName=fontName,fontSize=fontSize)
            flowable=Paragraph(contenido,estilo)
            textwidth=stringWidth(contenido,'centuryG',fontSize)
            i+=1
            j+=1
          frames_pag1.append(frame)
          story.append(flowable)
          story.append(FrameBreak())
      grupos=[]
        
     # Precio y Forma de pago
      estilo_precio=ParagraphStyle('precio',fontName='centuryg',fontSize=10)
      estilo_precio_peq=ParagraphStyle('precio',fontName='centuryg',fontSize=8)
      frame_precio=Frame(124.28*mm,135.2*mm,58.3*mm,5.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
      frames_pag1.append(frame_precio)
      story.append(Paragraph('<b>{:,}</b>'.format(valor),estilo_precio))
      story.append(FrameBreak())
      
      frame_valorletras=Frame(40*mm,131.7*mm,170*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
      frames_pag1.append(frame_valorletras)
      story.append(Paragraph(valor_letras,estilo_precio_peq))
      story.append(FrameBreak())
      
      frame_ctainicial=Frame(78.6*mm,128.3*mm,49*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
      frames_pag1.append(frame_ctainicial)
      story.append(Paragraph('{:,}'.format(ci),estilo_precio))
      story.append(FrameBreak())
      
      frame_saldo=Frame(168.6*mm,128.3*mm,49*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
      frames_pag1.append(frame_saldo)
      story.append(Paragraph('{:,}'.format(saldo),estilo_precio))
      story.append(FrameBreak())
      
      frame_contado=Frame(125.5*mm,121.8*mm,5.5*mm,4.5*mm,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
      frames_pag1.append(frame_contado)
      story.append(Paragraph(contado_x,estilo_precio))
      story.append(FrameBreak())
      
      frame_credic=Frame(147.5*mm,121.8*mm,5.5*mm,4.5*mm,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
      frames_pag1.append(frame_credic)
      story.append(Paragraph(credic_x,estilo_precio))
      story.append(FrameBreak())
      
      frame_amort=Frame(176.5*mm,121.8*mm,5.5*mm,4.5*mm,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
      frames_pag1.append(frame_amort)
      story.append(Paragraph(amort_x,estilo_precio))
      story.append(FrameBreak())
      
      estilo_forma_ci=ParagraphStyle('precio',fontName='centuryg',fontSize=5,leading=20,alignment=4)
      estilo_forma_fn=ParagraphStyle('precio',fontName='centuryg',fontSize=7,leading=20,alignment=4)
      
      frame_formaCI=Frame(18*mm,88.6*mm,88.3*mm,28*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
      frames_pag1.append(frame_formaCI)
      story.append(Paragraph(formaCI,estilo_forma_ci))
      story.append(FrameBreak())
      
      frame_formaFN=Frame(112.5*mm,88.6*mm,88.3*mm,28*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
      frames_pag1.append(frame_formaFN)
      story.append(Paragraph(formaFN,estilo_forma_fn))
      story.append(FrameBreak())
      
      estilo_obs=ParagraphStyle('precio',fontName='centuryg',fontSize=8,leading=18)
      frame_obs2=Frame(17.5*mm,65.6*mm,183*mm,23.7*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,rightPadding=0)
      frames_pag1.append(frame_obs2)
      story.append(Paragraph('&nbsp '*37+obs,estilo_obs))
            
     #respaldo
      
      story.append(NextPageTemplate('pagina2'))
      frames_pag2=[]
      frames_pag2.append(frame_base)
      pagina2=Image('./resources/Sotavento/Contrato de opcion de compra V1 -pag 2.png',width=214*mm,height=350*mm)
      story.append(pagina2)
      
      estilo_fecha=ParagraphStyle('fecha contrato',fontName='centuryg',fontSize=9,alignment=1)
      estilo_fecha_peq=ParagraphStyle('fecha contrato',fontName='centuryg',fontSize=7,alignment=1)
      frame_meses_entrega=Frame(170.5*mm,297.6*mm,20*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag2.append(frame_meses_entrega)
      story.append(Paragraph(f'{meses_entrega} meses',estilo_fecha_peq))
      story.append(FrameBreak())
     
      frame_dia=Frame(104.1*mm,108.4*mm,10.5*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag2.append(frame_dia)
      story.append(Paragraph(dia_contrato,estilo_fecha))
      story.append(FrameBreak())
      
      frame_mes=Frame(135.3*mm,108.4*mm,34.6*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag2.append(frame_mes)
      story.append(Paragraph(Utilidades().NombreMes(mes_contrato),estilo_fecha))
      story.append(FrameBreak())
      
      frame_año=Frame(179.7*mm,108.4*mm,14*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag2.append(frame_año)
      story.append(Paragraph(año_contrato,estilo_fecha))
      story.append(FrameBreak())
      
      page1=PageTemplate(id='pagina1',frames=frames_pag1)
      page2=PageTemplate(id='pagina2',frames=frames_pag2)
      
      doc=BaseDocTemplate(ruta,pageTemplates=[page1,page2],pagesize=LEGAL)
      
      doc.build(story)
    
    def PagareTesoro(self,nroPagare,nombreT1,ccT1,nombreT2,ccT2,nombreT3,ccT3,nombreT4,ccT4,diaPagare,mesPagare,añoPagare,ciudad,ruta):
      story=[]
      titulares=nombreT1
      if nombreT2!='': titulares+=f', {nombreT2}'
      if nombreT3!='': titulares+=f', {nombreT3}'
      if nombreT4!='': titulares+=f', {nombreT4}'
      frames_pag1=[]
     # Imagen base del doc
      frame_base=Frame(0,0,216*mm,356*mm)
      frames_pag1.append(frame_base)
      pagina1=Image('./resources/Pagare Terranova-Tesoro1.png',width=214*mm,height=350*mm)
      story.append(pagina1)
      story.append(FrameBreak())
      
      estilo_nro=ParagraphStyle('numero',fontName='centuryg',fontSize=14,textColor='#F78369')
      frame_nro=Frame(179.9*mm,320.3*mm,21.5*mm,6.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_nro)
      story.append(Paragraph('<b>{} - 1</b>'.format(nroPagare),estilo_nro))
      story.append(FrameBreak())
      
      estilo_deudores=ParagraphStyle('deudores',fontName='centuryg',fontSize=12,alignment=4,leading=20)
      frame_deudores=Frame(13*mm,278*mm,190*mm,19.3*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_deudores)
      story.append(Paragraph('{}{}'.format('&nbsp '*19,titulares),estilo_deudores))
      story.append(FrameBreak())
      
      estilo_fechas=ParagraphStyle('fechas',fontName='centuryg',fontSize=9,alignment=1)
      frame_dia=Frame(115*mm,142.6*mm,19*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_dia)
      story.append(Paragraph(diaPagare,estilo_fechas))
      story.append(FrameBreak())
      
      frame_mes=Frame(155*mm,142.6*mm,17*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_mes)
      story.append(Paragraph(mesPagare,estilo_fechas))
      story.append(FrameBreak())
      
      frame_año=Frame(183*mm,142.6*mm,10.2*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_año)
      story.append(Paragraph(añoPagare,estilo_fechas))
      story.append(FrameBreak())
      
      frame_ciudad=Frame(27.5*mm,138*mm,27.7*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_ciudad)
      story.append(Paragraph(ciudad,estilo_fechas))
      story.append(FrameBreak())
      
      estilo_firmas=ParagraphStyle('firmas',fontName='centuryg',fontSize=7,alignment=1)
      frame_titular1=Frame(25.8*mm,113*mm,57*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_titular1)
      story.append(Paragraph(nombreT1,estilo_firmas))
      story.append(FrameBreak())
      
      frame_cc1=Frame(25.8*mm,105*mm,57*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_cc1)
      story.append(Paragraph(ccT1,estilo_firmas))
      story.append(FrameBreak())
      
      frame_titular2=Frame(126.3*mm,113*mm,57*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_titular2)
      story.append(Paragraph(nombreT2,estilo_firmas))
      story.append(FrameBreak())
      
      frame_cc2=Frame(126.3*mm,105*mm,57*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_cc2)
      story.append(Paragraph(ccT2,estilo_firmas))
      story.append(FrameBreak())
      
      frame_titular3=Frame(25.8*mm,83.7*mm,57*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_titular3)
      story.append(Paragraph(nombreT3,estilo_firmas))
      story.append(FrameBreak())
      
      frame_cc3=Frame(25.8*mm,75.2*mm,57*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_cc3)
      story.append(Paragraph(ccT3,estilo_firmas))
      story.append(FrameBreak())
      
      frame_titular4=Frame(126.3*mm,83.7*mm,57*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_titular4)
      story.append(Paragraph(nombreT4,estilo_firmas))
      story.append(FrameBreak())
      
      frame_cc4=Frame(126.3*mm,75.2*mm,57*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_cc4)
      story.append(Paragraph(ccT4,estilo_firmas))
      
      
      story.append(NextPageTemplate('pagina2'))
      frames_pag2=[]
      frames_pag2.append(frame_base)
      
      
      pagina2=Image('./resources/Carta instrucciones Terranova Tesoro 1.png',width=200*mm,height=250*mm)
      story.append(pagina2)
      story.append(FrameBreak())
      
      frame_nroC=Frame(164.2*mm,288.5*mm,31.6*mm,8*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag2.append(frame_nroC)
      story.append(Paragraph(nroPagare+' - 1',estilo_deudores))
      story.append(FrameBreak())
      
      frame_deudC=Frame(19.3*mm,269*mm,176.7*mm,19.7*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag2.append(frame_deudC)
      story.append(Paragraph('{}{}'.format('&nbsp '*9,titulares),estilo_deudores))
      story.append(FrameBreak())
      
      frame_diaC=Frame(145.2*mm,209.3*mm,12*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag2.append(frame_diaC)
      story.append(Paragraph(diaPagare,estilo_firmas))
      story.append(FrameBreak())
      
      frame_mesC=Frame(180.5*mm,209.3*mm,12.3*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag2.append(frame_mesC)
      story.append(Paragraph(mesPagare,estilo_firmas))
      story.append(FrameBreak())
      
      frame_añoC=Frame(24.8*mm,206.2*mm,12*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag2.append(frame_añoC)
      story.append(Paragraph(añoPagare,estilo_firmas))
      story.append(FrameBreak())
      
      frame_ciudadC=Frame(63.5*mm,206.2*mm,27.7*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag2.append(frame_ciudadC)
      story.append(Paragraph(ciudad,estilo_firmas))
      story.append(FrameBreak())
      
      estilo_firmas=ParagraphStyle('firmas',fontName='centuryg',fontSize=7,alignment=1)
      frame_titular1C=Frame(31.9*mm,176*mm,52*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag2.append(frame_titular1C)
      story.append(Paragraph(nombreT1[:27],estilo_firmas))
      story.append(FrameBreak())
      
      frame_cc1C=Frame(31.9*mm,168*mm,52*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag2.append(frame_cc1C)
      story.append(Paragraph(ccT1,estilo_firmas))
      story.append(FrameBreak())
      
      frame_titular2C=Frame(125.53*mm,176*mm,52*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag2.append(frame_titular2C)
      story.append(Paragraph(nombreT2[:27],estilo_firmas))
      story.append(FrameBreak())
      
      frame_cc2C=Frame(125.53*mm,168*mm,52*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag2.append(frame_cc2C)
      story.append(Paragraph(ccT2,estilo_firmas))
      story.append(FrameBreak())
      
      frame_titular3C=Frame(31.9*mm,143*mm,52*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag2.append(frame_titular3C)
      story.append(Paragraph(nombreT3[:27],estilo_firmas))
      story.append(FrameBreak())
      
      frame_cc3C=Frame(31.9*mm,135*mm,52*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag2.append(frame_cc3C)
      story.append(Paragraph(ccT3,estilo_firmas))
      story.append(FrameBreak())
      
      frame_titular4C=Frame(125.53*mm,143*mm,52*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag2.append(frame_titular4C)
      story.append(Paragraph(nombreT4[:27],estilo_firmas))
      story.append(FrameBreak())
      
      frame_cc4C=Frame(125.53*mm,135*mm,52*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag2.append(frame_cc4C)
      story.append(Paragraph(ccT4,estilo_firmas))
      
      page1=PageTemplate(id='pagina1',frames=frames_pag1)
      page2=PageTemplate(id='pagina2',frames=frames_pag2)
      
      doc=BaseDocTemplate(ruta,pageTemplates=[page1,page2],pagesize=LEGAL)
      
      doc.build(story)

    def PagareSotavento(self,nroPagare,nombreT1,ccT1,nombreT2,ccT2,nombreT3,ccT3,nombreT4,ccT4,diaPagare,mesPagare,añoPagare,ciudad,ruta):
      story=[]
      titulares=nombreT1
      if nombreT2!='': titulares+=f', {nombreT2}'
      if nombreT3!='': titulares+=f', {nombreT3}'
      if nombreT4!='': titulares+=f', {nombreT4}'
      frames_pag1=[]
     # Imagen base del doc
      frame_base=Frame(0,0,216*mm,356*mm)
      frames_pag1.append(frame_base)
      pagina1=Image('./resources/Sotavento/Pagare-Sotavento-Quadrata.png',width=214*mm,height=350*mm)
      story.append(pagina1)
      story.append(FrameBreak())
      
      estilo_nro=ParagraphStyle('numero',fontName='centuryg',fontSize=14,textColor='#F78369')
      frame_nro=Frame(108.9*mm,323.6*mm,21.5*mm,6.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_nro)
      story.append(Paragraph('<b>{} - 1</b>'.format(nroPagare),estilo_nro))
      story.append(FrameBreak())
      
      estilo_deudores=ParagraphStyle('deudores',fontName='centuryg',fontSize=12,alignment=4,leading=20)
      frame_deudores=Frame(13*mm,278*mm,190*mm,19.3*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_deudores)
      story.append(Paragraph('{}{}'.format('&nbsp '*19,titulares),estilo_deudores))
      story.append(FrameBreak())
      
      estilo_fechas=ParagraphStyle('fechas',fontName='centuryg',fontSize=9,alignment=1)
      frame_dia=Frame(115*mm,142.6*mm,19*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_dia)
      story.append(Paragraph(diaPagare,estilo_fechas))
      story.append(FrameBreak())
      
      frame_mes=Frame(155*mm,142.6*mm,17*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_mes)
      story.append(Paragraph(mesPagare,estilo_fechas))
      story.append(FrameBreak())
      
      frame_año=Frame(183*mm,142.6*mm,10.2*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_año)
      story.append(Paragraph(añoPagare,estilo_fechas))
      story.append(FrameBreak())
      
      frame_ciudad=Frame(27.5*mm,138*mm,27.7*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_ciudad)
      story.append(Paragraph(ciudad,estilo_fechas))
      story.append(FrameBreak())
      
      estilo_firmas=ParagraphStyle('firmas',fontName='centuryg',fontSize=7,alignment=1)
      frame_titular1=Frame(25.8*mm,113*mm,57*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_titular1)
      story.append(Paragraph(nombreT1,estilo_firmas))
      story.append(FrameBreak())
      
      frame_cc1=Frame(25.8*mm,105*mm,57*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_cc1)
      story.append(Paragraph(ccT1,estilo_firmas))
      story.append(FrameBreak())
      
      frame_titular2=Frame(126.3*mm,113*mm,57*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_titular2)
      story.append(Paragraph(nombreT2,estilo_firmas))
      story.append(FrameBreak())
      
      frame_cc2=Frame(126.3*mm,105*mm,57*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_cc2)
      story.append(Paragraph(ccT2,estilo_firmas))
      story.append(FrameBreak())
      
      frame_titular3=Frame(25.8*mm,83.7*mm,57*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_titular3)
      story.append(Paragraph(nombreT3,estilo_firmas))
      story.append(FrameBreak())
      
      frame_cc3=Frame(25.8*mm,75.2*mm,57*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_cc3)
      story.append(Paragraph(ccT3,estilo_firmas))
      story.append(FrameBreak())
      
      frame_titular4=Frame(126.3*mm,83.7*mm,57*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_titular4)
      story.append(Paragraph(nombreT4,estilo_firmas))
      story.append(FrameBreak())
      
      frame_cc4=Frame(126.3*mm,75.2*mm,57*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_cc4)
      story.append(Paragraph(ccT4,estilo_firmas))
      
      
      story.append(NextPageTemplate('pagina2'))
      frames_pag2=[]
      frames_pag2.append(frame_base)
      
      
      pagina2=Image('./resources/Sotavento/Carta-instrucciones-Pagare-Sotavento.png',width=200*mm,height=250*mm)
      story.append(pagina2)
      story.append(FrameBreak())
      
      frame_nroC=Frame(164.2*mm,288.5*mm,31.6*mm,8*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag2.append(frame_nroC)
      story.append(Paragraph(nroPagare+' - 1',estilo_deudores))
      story.append(FrameBreak())
      
      frame_deudC=Frame(19.3*mm,269*mm,176.7*mm,19.7*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag2.append(frame_deudC)
      story.append(Paragraph('{}{}'.format('&nbsp '*9,titulares),estilo_deudores))
      story.append(FrameBreak())
      
      frame_diaC=Frame(145.2*mm,209.3*mm,12*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag2.append(frame_diaC)
      story.append(Paragraph(diaPagare,estilo_firmas))
      story.append(FrameBreak())
      
      frame_mesC=Frame(180.5*mm,209.3*mm,12.3*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag2.append(frame_mesC)
      story.append(Paragraph(mesPagare,estilo_firmas))
      story.append(FrameBreak())
      
      frame_añoC=Frame(24.8*mm,206.2*mm,12*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag2.append(frame_añoC)
      story.append(Paragraph(añoPagare,estilo_firmas))
      story.append(FrameBreak())
      
      frame_ciudadC=Frame(63.5*mm,206.2*mm,27.7*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag2.append(frame_ciudadC)
      story.append(Paragraph(ciudad,estilo_firmas))
      story.append(FrameBreak())
      
      estilo_firmas=ParagraphStyle('firmas',fontName='centuryg',fontSize=7,alignment=1)
      frame_titular1C=Frame(31.9*mm,176*mm,52*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag2.append(frame_titular1C)
      story.append(Paragraph(nombreT1[:27],estilo_firmas))
      story.append(FrameBreak())
      
      frame_cc1C=Frame(31.9*mm,168*mm,52*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag2.append(frame_cc1C)
      story.append(Paragraph(ccT1,estilo_firmas))
      story.append(FrameBreak())
      
      frame_titular2C=Frame(125.53*mm,176*mm,52*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag2.append(frame_titular2C)
      story.append(Paragraph(nombreT2[:27],estilo_firmas))
      story.append(FrameBreak())
      
      frame_cc2C=Frame(125.53*mm,168*mm,52*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag2.append(frame_cc2C)
      story.append(Paragraph(ccT2,estilo_firmas))
      story.append(FrameBreak())
      
      frame_titular3C=Frame(31.9*mm,143*mm,52*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag2.append(frame_titular3C)
      story.append(Paragraph(nombreT3[:27],estilo_firmas))
      story.append(FrameBreak())
      
      frame_cc3C=Frame(31.9*mm,135*mm,52*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag2.append(frame_cc3C)
      story.append(Paragraph(ccT3,estilo_firmas))
      story.append(FrameBreak())
      
      frame_titular4C=Frame(125.53*mm,143*mm,52*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag2.append(frame_titular4C)
      story.append(Paragraph(nombreT4[:27],estilo_firmas))
      story.append(FrameBreak())
      
      frame_cc4C=Frame(125.53*mm,135*mm,52*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag2.append(frame_cc4C)
      story.append(Paragraph(ccT4,estilo_firmas))
      
      page1=PageTemplate(id='pagina1',frames=frames_pag1)
      page2=PageTemplate(id='pagina2',frames=frames_pag2)
      
      doc=BaseDocTemplate(ruta,pageTemplates=[page1,page2],pagesize=LEGAL)
      
      doc.build(story)

    def PagareCarmelo(self,nroPagare,nombreT1,ccT1,nombreT2,ccT2,nombreT3,ccT3,nombreT4,ccT4,diaPagare,mesPagare,añoPagare,ciudad,ruta):
      story=[]
      titulares=nombreT1
      if nombreT2!='': titulares+=f', {nombreT2}'
      if nombreT3!='': titulares+=f', {nombreT3}'
      if nombreT4!='': titulares+=f', {nombreT4}'
      frames_pag1=[]
     # Imagen base del doc
      frame_base=Frame(0,0,216*mm,356*mm)
      frames_pag1.append(frame_base)
      pagina1=Image('./resources/Carmelo Reservado/Pagare.png',width=214*mm,height=350*mm)
      story.append(pagina1)
      story.append(FrameBreak())
      
      estilo_nro=ParagraphStyle('numero',fontName='centuryg',fontSize=14,textColor='#F78369')
      frame_nro=Frame(108.9*mm,323.6*mm,21.5*mm,6.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_nro)
      story.append(Paragraph('<b>{} - 1</b>'.format(nroPagare),estilo_nro))
      story.append(FrameBreak())
      
      estilo_deudores=ParagraphStyle('deudores',fontName='centuryg',fontSize=12,alignment=4,leading=20)
      frame_deudores=Frame(13*mm,278*mm,190*mm,19.3*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_deudores)
      story.append(Paragraph('{}{}'.format('&nbsp '*19,titulares),estilo_deudores))
      story.append(FrameBreak())
      
      estilo_fechas=ParagraphStyle('fechas',fontName='centuryg',fontSize=9,alignment=1)
      frame_dia=Frame(115*mm,142.6*mm,19*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_dia)
      story.append(Paragraph(diaPagare,estilo_fechas))
      story.append(FrameBreak())
      
      frame_mes=Frame(155*mm,142.6*mm,17*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_mes)
      story.append(Paragraph(mesPagare,estilo_fechas))
      story.append(FrameBreak())
      
      frame_año=Frame(183*mm,142.6*mm,10.2*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_año)
      story.append(Paragraph(añoPagare,estilo_fechas))
      story.append(FrameBreak())
      
      frame_ciudad=Frame(27.5*mm,138*mm,27.7*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_ciudad)
      story.append(Paragraph(ciudad,estilo_fechas))
      story.append(FrameBreak())
      
      estilo_firmas=ParagraphStyle('firmas',fontName='centuryg',fontSize=7,alignment=1)
      frame_titular1=Frame(25.8*mm,113*mm,57*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_titular1)
      story.append(Paragraph(nombreT1,estilo_firmas))
      story.append(FrameBreak())
      
      frame_cc1=Frame(25.8*mm,105*mm,57*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_cc1)
      story.append(Paragraph(ccT1,estilo_firmas))
      story.append(FrameBreak())
      
      frame_titular2=Frame(126.3*mm,113*mm,57*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_titular2)
      story.append(Paragraph(nombreT2,estilo_firmas))
      story.append(FrameBreak())
      
      frame_cc2=Frame(126.3*mm,105*mm,57*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_cc2)
      story.append(Paragraph(ccT2,estilo_firmas))
      story.append(FrameBreak())
      
      frame_titular3=Frame(25.8*mm,83.7*mm,57*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_titular3)
      story.append(Paragraph(nombreT3,estilo_firmas))
      story.append(FrameBreak())
      
      frame_cc3=Frame(25.8*mm,75.2*mm,57*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_cc3)
      story.append(Paragraph(ccT3,estilo_firmas))
      story.append(FrameBreak())
      
      frame_titular4=Frame(126.3*mm,83.7*mm,57*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_titular4)
      story.append(Paragraph(nombreT4,estilo_firmas))
      story.append(FrameBreak())
      
      frame_cc4=Frame(126.3*mm,75.2*mm,57*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_cc4)
      story.append(Paragraph(ccT4,estilo_firmas))
      
      
      story.append(NextPageTemplate('pagina2'))
      frames_pag2=[]
      frames_pag2.append(frame_base)
      
      
      pagina2=Image('./resources/Carmelo Reservado/Carta de instrucciones.png',width=200*mm,height=250*mm)
      story.append(pagina2)
      story.append(FrameBreak())
      
      frame_nroC=Frame(164.2*mm,288.5*mm,31.6*mm,8*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag2.append(frame_nroC)
      story.append(Paragraph(nroPagare+' - 1',estilo_deudores))
      story.append(FrameBreak())
      
      frame_deudC=Frame(19.3*mm,269*mm,176.7*mm,19.7*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag2.append(frame_deudC)
      story.append(Paragraph('{}{}'.format('&nbsp '*9,titulares),estilo_deudores))
      story.append(FrameBreak())
      
      frame_diaC=Frame(145.2*mm,209.3*mm,12*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag2.append(frame_diaC)
      story.append(Paragraph(diaPagare,estilo_firmas))
      story.append(FrameBreak())
      
      frame_mesC=Frame(180.5*mm,209.3*mm,12.3*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag2.append(frame_mesC)
      story.append(Paragraph(mesPagare,estilo_firmas))
      story.append(FrameBreak())
      
      frame_añoC=Frame(24.8*mm,206.2*mm,12*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag2.append(frame_añoC)
      story.append(Paragraph(añoPagare,estilo_firmas))
      story.append(FrameBreak())
      
      frame_ciudadC=Frame(63.5*mm,206.2*mm,27.7*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag2.append(frame_ciudadC)
      story.append(Paragraph(ciudad,estilo_firmas))
      story.append(FrameBreak())
      
      estilo_firmas=ParagraphStyle('firmas',fontName='centuryg',fontSize=7,alignment=1)
      frame_titular1C=Frame(31.9*mm,176*mm,52*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag2.append(frame_titular1C)
      story.append(Paragraph(nombreT1[:27],estilo_firmas))
      story.append(FrameBreak())
      
      frame_cc1C=Frame(31.9*mm,168*mm,52*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag2.append(frame_cc1C)
      story.append(Paragraph(ccT1,estilo_firmas))
      story.append(FrameBreak())
      
      frame_titular2C=Frame(125.53*mm,176*mm,52*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag2.append(frame_titular2C)
      story.append(Paragraph(nombreT2[:27],estilo_firmas))
      story.append(FrameBreak())
      
      frame_cc2C=Frame(125.53*mm,168*mm,52*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag2.append(frame_cc2C)
      story.append(Paragraph(ccT2,estilo_firmas))
      story.append(FrameBreak())
      
      frame_titular3C=Frame(31.9*mm,143*mm,52*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag2.append(frame_titular3C)
      story.append(Paragraph(nombreT3[:27],estilo_firmas))
      story.append(FrameBreak())
      
      frame_cc3C=Frame(31.9*mm,135*mm,52*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag2.append(frame_cc3C)
      story.append(Paragraph(ccT3,estilo_firmas))
      story.append(FrameBreak())
      
      frame_titular4C=Frame(125.53*mm,143*mm,52*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag2.append(frame_titular4C)
      story.append(Paragraph(nombreT4[:27],estilo_firmas))
      story.append(FrameBreak())
      
      frame_cc4C=Frame(125.53*mm,135*mm,52*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag2.append(frame_cc4C)
      story.append(Paragraph(ccT4,estilo_firmas))
      
      page1=PageTemplate(id='pagina1',frames=frames_pag1)
      page2=PageTemplate(id='pagina2',frames=frames_pag2)
      
      doc=BaseDocTemplate(ruta,pageTemplates=[page1,page2],pagesize=LEGAL)
      
      doc.build(story)

    def PagareCasasdeVerano(self,nroPagare,nombreT1,ccT1,nombreT2,ccT2,nombreT3,ccT3,nombreT4,ccT4,diaPagare,mesPagare,añoPagare,ciudad,ruta):
      story=[]
      titulares=nombreT1
      if nombreT2!='': titulares+=f', {nombreT2}'
      if nombreT3!='': titulares+=f', {nombreT3}'
      if nombreT4!='': titulares+=f', {nombreT4}'
      frames_pag1=[]
     # Imagen base del doc
      frame_base=Frame(0,0,216*mm,356*mm)
      frames_pag1.append(frame_base)
      pagina1=Image('./resources/Casas de Verano/Pagare.png',width=214*mm,height=350*mm)
      story.append(pagina1)
      story.append(FrameBreak())
      
      estilo_nro=ParagraphStyle('numero',fontName='centuryg',fontSize=14,textColor='#F78369')
      frame_nro=Frame(108.9*mm,323.6*mm,21.5*mm,6.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_nro)
      story.append(Paragraph('<b>{} - 1</b>'.format(nroPagare),estilo_nro))
      story.append(FrameBreak())
      
      estilo_deudores=ParagraphStyle('deudores',fontName='centuryg',fontSize=12,alignment=4,leading=20)
      frame_deudores=Frame(13*mm,278*mm,190*mm,19.3*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_deudores)
      story.append(Paragraph('{}{}'.format('&nbsp '*19,titulares),estilo_deudores))
      story.append(FrameBreak())
      
      estilo_fechas=ParagraphStyle('fechas',fontName='centuryg',fontSize=9,alignment=1)
      frame_dia=Frame(115*mm,142.6*mm,19*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_dia)
      story.append(Paragraph(diaPagare,estilo_fechas))
      story.append(FrameBreak())
      
      frame_mes=Frame(155*mm,142.6*mm,17*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_mes)
      story.append(Paragraph(mesPagare,estilo_fechas))
      story.append(FrameBreak())
      
      frame_año=Frame(183*mm,142.6*mm,10.2*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_año)
      story.append(Paragraph(añoPagare,estilo_fechas))
      story.append(FrameBreak())
      
      frame_ciudad=Frame(27.5*mm,138*mm,27.7*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_ciudad)
      story.append(Paragraph(ciudad,estilo_fechas))
      story.append(FrameBreak())
      
      estilo_firmas=ParagraphStyle('firmas',fontName='centuryg',fontSize=7,alignment=1)
      frame_titular1=Frame(25.8*mm,113*mm,57*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_titular1)
      story.append(Paragraph(nombreT1,estilo_firmas))
      story.append(FrameBreak())
      
      frame_cc1=Frame(25.8*mm,105*mm,57*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_cc1)
      story.append(Paragraph(ccT1,estilo_firmas))
      story.append(FrameBreak())
      
      frame_titular2=Frame(126.3*mm,113*mm,57*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_titular2)
      story.append(Paragraph(nombreT2,estilo_firmas))
      story.append(FrameBreak())
      
      frame_cc2=Frame(126.3*mm,105*mm,57*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_cc2)
      story.append(Paragraph(ccT2,estilo_firmas))
      story.append(FrameBreak())
      
      frame_titular3=Frame(25.8*mm,83.7*mm,57*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_titular3)
      story.append(Paragraph(nombreT3,estilo_firmas))
      story.append(FrameBreak())
      
      frame_cc3=Frame(25.8*mm,75.2*mm,57*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_cc3)
      story.append(Paragraph(ccT3,estilo_firmas))
      story.append(FrameBreak())
      
      frame_titular4=Frame(126.3*mm,83.7*mm,57*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_titular4)
      story.append(Paragraph(nombreT4,estilo_firmas))
      story.append(FrameBreak())
      
      frame_cc4=Frame(126.3*mm,75.2*mm,57*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_cc4)
      story.append(Paragraph(ccT4,estilo_firmas))
      
      
      story.append(NextPageTemplate('pagina2'))
      frames_pag2=[]
      frames_pag2.append(frame_base)
      
      
      pagina2=Image('./resources/Casas de Verano/Carta de instrucciones.png',width=200*mm,height=250*mm)
      story.append(pagina2)
      story.append(FrameBreak())
      
      frame_nroC=Frame(164.2*mm,288.5*mm,31.6*mm,8*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag2.append(frame_nroC)
      story.append(Paragraph(nroPagare+' - 1',estilo_deudores))
      story.append(FrameBreak())
      
      frame_deudC=Frame(19.3*mm,269*mm,176.7*mm,19.7*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag2.append(frame_deudC)
      story.append(Paragraph('{}{}'.format('&nbsp '*9,titulares),estilo_deudores))
      story.append(FrameBreak())
      
      frame_diaC=Frame(145.2*mm,209.3*mm,12*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag2.append(frame_diaC)
      story.append(Paragraph(diaPagare,estilo_firmas))
      story.append(FrameBreak())
      
      frame_mesC=Frame(180.5*mm,209.3*mm,12.3*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag2.append(frame_mesC)
      story.append(Paragraph(mesPagare,estilo_firmas))
      story.append(FrameBreak())
      
      frame_añoC=Frame(24.8*mm,206.2*mm,12*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag2.append(frame_añoC)
      story.append(Paragraph(añoPagare,estilo_firmas))
      story.append(FrameBreak())
      
      frame_ciudadC=Frame(63.5*mm,206.2*mm,27.7*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag2.append(frame_ciudadC)
      story.append(Paragraph(ciudad,estilo_firmas))
      story.append(FrameBreak())
      
      estilo_firmas=ParagraphStyle('firmas',fontName='centuryg',fontSize=7,alignment=1)
      frame_titular1C=Frame(31.9*mm,176*mm,52*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag2.append(frame_titular1C)
      story.append(Paragraph(nombreT1[:27],estilo_firmas))
      story.append(FrameBreak())
      
      frame_cc1C=Frame(31.9*mm,168*mm,52*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag2.append(frame_cc1C)
      story.append(Paragraph(ccT1,estilo_firmas))
      story.append(FrameBreak())
      
      frame_titular2C=Frame(125.53*mm,176*mm,52*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag2.append(frame_titular2C)
      story.append(Paragraph(nombreT2[:27],estilo_firmas))
      story.append(FrameBreak())
      
      frame_cc2C=Frame(125.53*mm,168*mm,52*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag2.append(frame_cc2C)
      story.append(Paragraph(ccT2,estilo_firmas))
      story.append(FrameBreak())
      
      frame_titular3C=Frame(31.9*mm,143*mm,52*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag2.append(frame_titular3C)
      story.append(Paragraph(nombreT3[:27],estilo_firmas))
      story.append(FrameBreak())
      
      frame_cc3C=Frame(31.9*mm,135*mm,52*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag2.append(frame_cc3C)
      story.append(Paragraph(ccT3,estilo_firmas))
      story.append(FrameBreak())
      
      frame_titular4C=Frame(125.53*mm,143*mm,52*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag2.append(frame_titular4C)
      story.append(Paragraph(nombreT4[:27],estilo_firmas))
      story.append(FrameBreak())
      
      frame_cc4C=Frame(125.53*mm,135*mm,52*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag2.append(frame_cc4C)
      story.append(Paragraph(ccT4,estilo_firmas))
      
      page1=PageTemplate(id='pagina1',frames=frames_pag1)
      page2=PageTemplate(id='pagina2',frames=frames_pag2)
      
      doc=BaseDocTemplate(ruta,pageTemplates=[page1,page2],pagesize=LEGAL)
      
      doc.build(story)

    
    def PagareSandvilleMar(self,nroPagare,nombreT1,ccT1,nombreT2,ccT2,nombreT3,ccT3,nombreT4,ccT4,diaPagare,mesPagare,añoPagare,ciudad,ruta):
      story=[]
      titulares=nombreT1
      if nombreT2!='': titulares+=f', {nombreT2}'
      if nombreT3!='': titulares+=f', {nombreT3}'
      if nombreT4!='': titulares+=f', {nombreT4}'
      frames_pag1=[]
     # Imagen base del doc
      frame_base=Frame(0,0,216*mm,356*mm)
      frames_pag1.append(frame_base)
      pagina1=Image('./resources/Pagare Promotora Sandville.png',width=214*mm,height=350*mm)
      story.append(pagina1)
      story.append(FrameBreak())
      
      estilo_nro=ParagraphStyle('numero',fontName='centuryg',fontSize=14,textColor='#F78369')
      frame_nro=Frame(106.3*mm,323.3*mm,21.5*mm,6.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_nro)
      story.append(Paragraph('<b>{} - 1</b>'.format(nroPagare),estilo_nro))
      story.append(FrameBreak())
      
      estilo_deudores=ParagraphStyle('deudores',fontName='centuryg',fontSize=12,alignment=4,leading=20)
      frame_deudores=Frame(13*mm,278*mm,190*mm,19.3*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_deudores)
      story.append(Paragraph('{}{}'.format('&nbsp '*19,titulares),estilo_deudores))
      story.append(FrameBreak())
      
      estilo_fechas=ParagraphStyle('fechas',fontName='centuryg',fontSize=9,alignment=1)
      frame_dia=Frame(115*mm,142.6*mm,19*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_dia)
      story.append(Paragraph(diaPagare,estilo_fechas))
      story.append(FrameBreak())
      
      frame_mes=Frame(155*mm,142.6*mm,17*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_mes)
      story.append(Paragraph(mesPagare,estilo_fechas))
      story.append(FrameBreak())
      
      frame_año=Frame(183*mm,142.6*mm,10.2*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_año)
      story.append(Paragraph(añoPagare,estilo_fechas))
      story.append(FrameBreak())
      
      frame_ciudad=Frame(27.5*mm,138*mm,27.7*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_ciudad)
      story.append(Paragraph(ciudad,estilo_fechas))
      story.append(FrameBreak())
      
      estilo_firmas=ParagraphStyle('firmas',fontName='centuryg',fontSize=7,alignment=1)
      frame_titular1=Frame(25.8*mm,113*mm,57*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_titular1)
      story.append(Paragraph(nombreT1,estilo_firmas))
      story.append(FrameBreak())
      
      frame_cc1=Frame(25.8*mm,105*mm,57*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_cc1)
      story.append(Paragraph(ccT1,estilo_firmas))
      story.append(FrameBreak())
      
      frame_titular2=Frame(126.3*mm,113*mm,57*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_titular2)
      story.append(Paragraph(nombreT2,estilo_firmas))
      story.append(FrameBreak())
      
      frame_cc2=Frame(126.3*mm,105*mm,57*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_cc2)
      story.append(Paragraph(ccT2,estilo_firmas))
      story.append(FrameBreak())
      
      frame_titular3=Frame(25.8*mm,83.7*mm,57*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_titular3)
      story.append(Paragraph(nombreT3,estilo_firmas))
      story.append(FrameBreak())
      
      frame_cc3=Frame(25.8*mm,75.2*mm,57*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_cc3)
      story.append(Paragraph(ccT3,estilo_firmas))
      story.append(FrameBreak())
      
      frame_titular4=Frame(126.3*mm,83.7*mm,57*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_titular4)
      story.append(Paragraph(nombreT4,estilo_firmas))
      story.append(FrameBreak())
      
      frame_cc4=Frame(126.3*mm,75.2*mm,57*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_cc4)
      story.append(Paragraph(ccT4,estilo_firmas))
      
      
      story.append(NextPageTemplate('pagina2'))
      frames_pag2=[]
      frames_pag2.append(frame_base)
      
      
      pagina2=Image('./resources/Carta de instrucciones Promotora Sandville.png',width=200*mm,height=250*mm)
      story.append(pagina2)
      story.append(FrameBreak())
      
      frame_nroC=Frame(164.2*mm,288.5*mm,31.6*mm,8*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag2.append(frame_nroC)
      story.append(Paragraph(nroPagare+' - 1',estilo_deudores))
      story.append(FrameBreak())
      
      frame_deudC=Frame(19.3*mm,269*mm,176.7*mm,19.7*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag2.append(frame_deudC)
      story.append(Paragraph('{}{}'.format('&nbsp '*9,titulares),estilo_deudores))
      story.append(FrameBreak())
      
      frame_diaC=Frame(145.2*mm,209.3*mm,12*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag2.append(frame_diaC)
      story.append(Paragraph(diaPagare,estilo_firmas))
      story.append(FrameBreak())
      
      frame_mesC=Frame(180.5*mm,209.3*mm,12.3*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag2.append(frame_mesC)
      story.append(Paragraph(mesPagare,estilo_firmas))
      story.append(FrameBreak())
      
      frame_añoC=Frame(24.8*mm,206.2*mm,12*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag2.append(frame_añoC)
      story.append(Paragraph(añoPagare,estilo_firmas))
      story.append(FrameBreak())
      
      frame_ciudadC=Frame(63.5*mm,206.2*mm,27.7*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag2.append(frame_ciudadC)
      story.append(Paragraph(ciudad,estilo_firmas))
      story.append(FrameBreak())
      
      estilo_firmas=ParagraphStyle('firmas',fontName='centuryg',fontSize=7,alignment=1)
      frame_titular1C=Frame(31.9*mm,176*mm,52*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag2.append(frame_titular1C)
      story.append(Paragraph(nombreT1[:27],estilo_firmas))
      story.append(FrameBreak())
      
      frame_cc1C=Frame(31.9*mm,168*mm,52*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag2.append(frame_cc1C)
      story.append(Paragraph(ccT1,estilo_firmas))
      story.append(FrameBreak())
      
      frame_titular2C=Frame(125.53*mm,176*mm,52*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag2.append(frame_titular2C)
      story.append(Paragraph(nombreT2[:27],estilo_firmas))
      story.append(FrameBreak())
      
      frame_cc2C=Frame(125.53*mm,168*mm,52*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag2.append(frame_cc2C)
      story.append(Paragraph(ccT2,estilo_firmas))
      story.append(FrameBreak())
      
      frame_titular3C=Frame(31.9*mm,143*mm,52*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag2.append(frame_titular3C)
      story.append(Paragraph(nombreT3[:27],estilo_firmas))
      story.append(FrameBreak())
      
      frame_cc3C=Frame(31.9*mm,135*mm,52*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag2.append(frame_cc3C)
      story.append(Paragraph(ccT3,estilo_firmas))
      story.append(FrameBreak())
      
      frame_titular4C=Frame(125.53*mm,143*mm,52*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag2.append(frame_titular4C)
      story.append(Paragraph(nombreT4[:27],estilo_firmas))
      story.append(FrameBreak())
      
      frame_cc4C=Frame(125.53*mm,135*mm,52*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag2.append(frame_cc4C)
      story.append(Paragraph(ccT4,estilo_firmas))
      
      page1=PageTemplate(id='pagina1',frames=frames_pag1)
      page2=PageTemplate(id='pagina2',frames=frames_pag2)
      
      doc=BaseDocTemplate(ruta,pageTemplates=[page1,page2],pagesize=LEGAL)
      
      doc.build(story)

    def PagareSandvilleBeach(self,nroPagare,nombreT1,ccT1,nombreT2,ccT2,nombreT3,ccT3,nombreT4,ccT4,diaPagare,mesPagare,añoPagare,ciudad,ruta):
      story=[]
      titulares=nombreT1
      if nombreT2!='': titulares+=f', {nombreT2}'
      if nombreT3!='': titulares+=f', {nombreT3}'
      if nombreT4!='': titulares+=f', {nombreT4}'
      frames_pag1=[]
     # Imagen base del doc
      frame_base=Frame(0,0,216*mm,356*mm)
      frames_pag1.append(frame_base)
      pagina1=Image('./resources/Pagare Terranova-Beach.png',width=214*mm,height=350*mm)
      story.append(pagina1)
      story.append(FrameBreak())
      
      estilo_nro=ParagraphStyle('numero',fontName='centuryg',fontSize=14,textColor='#F78369')
      frame_nro=Frame(179.9*mm,320.3*mm,21.5*mm,6.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_nro)
      story.append(Paragraph('<b>{} - 1</b>'.format(nroPagare),estilo_nro))
      story.append(FrameBreak())
      
      estilo_deudores=ParagraphStyle('deudores',fontName='centuryg',fontSize=12,alignment=4,leading=20)
      frame_deudores=Frame(13*mm,278*mm,190*mm,19.3*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_deudores)
      story.append(Paragraph('{}{}'.format('&nbsp '*19,titulares),estilo_deudores))
      story.append(FrameBreak())
      
      estilo_fechas=ParagraphStyle('fechas',fontName='centuryg',fontSize=9,alignment=1)
      frame_dia=Frame(115*mm,142.6*mm,19*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_dia)
      story.append(Paragraph(diaPagare,estilo_fechas))
      story.append(FrameBreak())
      
      frame_mes=Frame(155*mm,142.6*mm,17*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_mes)
      story.append(Paragraph(mesPagare,estilo_fechas))
      story.append(FrameBreak())
      
      frame_año=Frame(183*mm,142.6*mm,10.2*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_año)
      story.append(Paragraph(añoPagare,estilo_fechas))
      story.append(FrameBreak())
      
      frame_ciudad=Frame(27.5*mm,138*mm,27.7*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_ciudad)
      story.append(Paragraph(ciudad,estilo_fechas))
      story.append(FrameBreak())
      
      estilo_firmas=ParagraphStyle('firmas',fontName='centuryg',fontSize=7,alignment=1)
      frame_titular1=Frame(25.8*mm,113*mm,57*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_titular1)
      story.append(Paragraph(nombreT1,estilo_firmas))
      story.append(FrameBreak())
      
      frame_cc1=Frame(25.8*mm,105*mm,57*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_cc1)
      story.append(Paragraph(ccT1,estilo_firmas))
      story.append(FrameBreak())
      
      frame_titular2=Frame(126.3*mm,113*mm,57*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_titular2)
      story.append(Paragraph(nombreT2,estilo_firmas))
      story.append(FrameBreak())
      
      frame_cc2=Frame(126.3*mm,105*mm,57*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_cc2)
      story.append(Paragraph(ccT2,estilo_firmas))
      story.append(FrameBreak())
      
      frame_titular3=Frame(25.8*mm,83.7*mm,57*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_titular3)
      story.append(Paragraph(nombreT3,estilo_firmas))
      story.append(FrameBreak())
      
      frame_cc3=Frame(25.8*mm,75.2*mm,57*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_cc3)
      story.append(Paragraph(ccT3,estilo_firmas))
      story.append(FrameBreak())
      
      frame_titular4=Frame(126.3*mm,83.7*mm,57*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_titular4)
      story.append(Paragraph(nombreT4,estilo_firmas))
      story.append(FrameBreak())
      
      frame_cc4=Frame(126.3*mm,75.2*mm,57*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_cc4)
      story.append(Paragraph(ccT4,estilo_firmas))
      
      
      story.append(NextPageTemplate('pagina2'))
      frames_pag2=[]
      frames_pag2.append(frame_base)
      
      
      pagina2=Image('./resources/Carta instrucciones Terranova beach.png',width=200*mm,height=250*mm)
      story.append(pagina2)
      story.append(FrameBreak())
      
      frame_nroC=Frame(164.2*mm,288.5*mm,31.6*mm,8*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag2.append(frame_nroC)
      story.append(Paragraph(nroPagare+' - 1',estilo_deudores))
      story.append(FrameBreak())
      
      frame_deudC=Frame(19.3*mm,269*mm,176.7*mm,19.7*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag2.append(frame_deudC)
      story.append(Paragraph('{}{}'.format('&nbsp '*9,titulares),estilo_deudores))
      story.append(FrameBreak())
      
      frame_diaC=Frame(145.2*mm,209.3*mm,12*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag2.append(frame_diaC)
      story.append(Paragraph(diaPagare,estilo_firmas))
      story.append(FrameBreak())
      
      frame_mesC=Frame(180.5*mm,209.3*mm,12.3*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag2.append(frame_mesC)
      story.append(Paragraph(mesPagare,estilo_firmas))
      story.append(FrameBreak())
      
      frame_añoC=Frame(24.8*mm,206.2*mm,12*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag2.append(frame_añoC)
      story.append(Paragraph(añoPagare,estilo_firmas))
      story.append(FrameBreak())
      
      frame_ciudadC=Frame(63.5*mm,206.2*mm,27.7*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag2.append(frame_ciudadC)
      story.append(Paragraph(ciudad,estilo_firmas))
      story.append(FrameBreak())
      
      estilo_firmas=ParagraphStyle('firmas',fontName='centuryg',fontSize=7,alignment=1)
      frame_titular1C=Frame(31.9*mm,176*mm,52*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag2.append(frame_titular1C)
      story.append(Paragraph(nombreT1[:27],estilo_firmas))
      story.append(FrameBreak())
      
      frame_cc1C=Frame(31.9*mm,168*mm,52*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag2.append(frame_cc1C)
      story.append(Paragraph(ccT1,estilo_firmas))
      story.append(FrameBreak())
      
      frame_titular2C=Frame(125.53*mm,176*mm,52*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag2.append(frame_titular2C)
      story.append(Paragraph(nombreT2[:27],estilo_firmas))
      story.append(FrameBreak())
      
      frame_cc2C=Frame(125.53*mm,168*mm,52*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag2.append(frame_cc2C)
      story.append(Paragraph(ccT2,estilo_firmas))
      story.append(FrameBreak())
      
      frame_titular3C=Frame(31.9*mm,143*mm,52*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag2.append(frame_titular3C)
      story.append(Paragraph(nombreT3[:27],estilo_firmas))
      story.append(FrameBreak())
      
      frame_cc3C=Frame(31.9*mm,135*mm,52*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag2.append(frame_cc3C)
      story.append(Paragraph(ccT3,estilo_firmas))
      story.append(FrameBreak())
      
      frame_titular4C=Frame(125.53*mm,143*mm,52*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag2.append(frame_titular4C)
      story.append(Paragraph(nombreT4[:27],estilo_firmas))
      story.append(FrameBreak())
      
      frame_cc4C=Frame(125.53*mm,135*mm,52*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag2.append(frame_cc4C)
      story.append(Paragraph(ccT4,estilo_firmas))
      
      page1=PageTemplate(id='pagina1',frames=frames_pag1)
      page2=PageTemplate(id='pagina2',frames=frames_pag2)
      
      doc=BaseDocTemplate(ruta,pageTemplates=[page1,page2],pagesize=LEGAL)
      
      doc.build(story)
          
    def Recibo_caja(self,proyecto,ruta,nroRecibo,titular1,fecha,concepto,valor,direccion,
                    ciudad,telefono,formapag,user):
      
      proyecto_dict={'Sandville Beach':'./resources/Recibo-de-Caja-SandVille.png',
                     'Perla del Mar':'./resources/Recibo-de-Caja-SandVille-mar.png',
                     'Sandville del Sol':'./resources/Recibo-de-Caja-Vegas-Status.png',
                     'Tesoro Escondido':'./resources/Recibo Tesoro1.png',
                     'Vegas de Venecia':'./resources/Recibo-de-Caja-Vegas-Status.png',
                     'Alttum Collection':'',
                     'Sotavento':'./resources/Sotavento/Recibo-de-Caja-Sotavento.png',
                     'Carmelo Reservado':'./resources/Carmelo Reservado/recibo de caja.png',
                     'Casas de Verano':'./resources/Casas de Verano/recibo de caja.png'}
      story=[]
      frames_pag1=[]
     # Imagen base del doc
      frame_base=Frame(0,0,210*mm,297*mm)
      frames_pag1.append(frame_base)
      pagina1=Image(proyecto_dict[proyecto],width=210*mm,height=150*mm)
      story.append(pagina1)
      story.append(FrameBreak())
      
      estilo_nro=ParagraphStyle('numero',fontName='centuryg',fontSize=14,textColor='#F78369',alignment=1)
      frame_nro=Frame(110*mm,257.3*mm,29*mm,7*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_nro)
      story.append(Paragraph('<b>{}</b>'.format(nroRecibo),estilo_nro))
      story.append(FrameBreak())
      
      estilo_detalle=ParagraphStyle('detalle',fontName='centuryg',fontSize=10)
      frame_tit1=Frame(40.7*mm,248.7*mm,99*mm,5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_tit1)
      story.append(Paragraph(titular1,estilo_detalle))
      story.append(FrameBreak())
      
      frame_fecha=Frame(149*mm,248.7*mm,48*mm,5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_fecha)
      story.append(Paragraph(fecha,estilo_detalle))
      story.append(FrameBreak())
      
      frame_concepto=Frame(40.7*mm,241.9*mm,99*mm,5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_concepto)
      story.append(Paragraph(concepto,estilo_detalle))
      story.append(FrameBreak())
      
      frame_valor=Frame(149*mm,241.9*mm,60*mm,5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_valor)
      story.append(Paragraph('{:,}'.format(valor),estilo_detalle))
      story.append(FrameBreak())
      
      estilo_direccion=ParagraphStyle('detalle',fontName='centuryg',fontSize=7)
      frame_direccion=Frame(38.7*mm,236.2*mm,58*mm,5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_direccion)
      story.append(Paragraph(direccion[:33],estilo_direccion))
      story.append(FrameBreak())
      
      if ciudad:
        frame_ciudad=Frame(102.9*mm,236.2*mm,45*mm,5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_ciudad)
        story.append(Paragraph(ciudad[:25],estilo_direccion))
        story.append(FrameBreak())
      
      frame_telefono=Frame(149*mm,236.2*mm,40*mm,5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_telefono)
      story.append(Paragraph(telefono,estilo_direccion))
      story.append(FrameBreak())
      
      estilo_pago=ParagraphStyle('pago',fontName='centuryg',fontSize=10,alignment=1)
      frame_formapag=Frame(19*mm,210*mm,99*mm,5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_formapag)
      story.append(Paragraph(formapag,estilo_pago))
      story.append(FrameBreak())
      
      frame_valorpag=Frame(121*mm,210*mm,71.3*mm,5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_valorpag)
      story.append(Paragraph('${:,}'.format(valor),estilo_pago))
      story.append(FrameBreak())
      
      frame_total=Frame(121*mm,202.3*mm,71.3*mm,5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_total)
      story.append(Paragraph('<b>${:,}</b>'.format(valor),estilo_pago))
      story.append(FrameBreak())
      
      if user!='None' and user!=None:
        estilo_firma=ParagraphStyle('firma',fontName='centuryg',fontSize=12,alignment=1)
        frame_nombre=Frame(24.7*mm,174.3*mm,67.6*mm,7*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_nombre)
        nombre=f'{user}'.upper()
        story.append(Paragraph(nombre,estilo_firma))
        story.append(FrameBreak())
        frame_firma=Frame(120*mm,175.3*mm,60*mm,15*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
        frames_pag1.append(frame_firma)
        try:
          firma=Image(f'./resources/Firmas/{user}.png',width=40*mm,height=15*mm)
          story.append(firma)
        except:
          pass
        story.append(FrameBreak())
      
      
      
      page1=PageTemplate(id='pagina1',frames=frames_pag1)
      
      doc=BaseDocTemplate(ruta,pageTemplates=page1,pagesize=A4)
      
      doc.build(story)

    def VerificacionTerranova(self,ruta,nombreT1,nombreT2,nombreT3,nombreT4,
                             ccTitular1,ccTitular2,ccTitular3,ccTitular4,
                             lote,manzana,area,valor,ci,formaci,saldo,formasaldo,
                             fechaEntrega,fechaEscritura):
      story=[]
      
      frames_pag1=[]
     # Imagen base del doc
      frame_base=Frame(0,0,216*mm,356*mm)
      frames_pag1.append(frame_base)
      pagina1=Image('./resources/Verificacion-Contrato_Tesoro-Escondido.png',width=214*mm,height=350*mm)
      story.append(pagina1)
      story.append(FrameBreak())
      
      estilo_titulares=ParagraphStyle('titulares',fontName='centuryg',fontSize=12)
      frame_titular1=Frame(12.5*mm,299*mm,133*mm,5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_titular1)
      story.append(Paragraph(nombreT1,estilo_titulares))
      story.append(FrameBreak())
      
      frame_cctitular1=Frame(153*mm,299*mm,52*mm,5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_cctitular1)
      story.append(Paragraph(ccTitular1,estilo_titulares))
      story.append(FrameBreak())
      
      frame_titular2=Frame(12.5*mm,292.8*mm,133*mm,5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_titular2)
      story.append(Paragraph(nombreT2,estilo_titulares))
      story.append(FrameBreak())
      
      frame_cctitular2=Frame(153*mm,292.8*mm,52*mm,5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_cctitular2)
      story.append(Paragraph(ccTitular2,estilo_titulares))
      story.append(FrameBreak())
      
      frame_titular3=Frame(12.5*mm,286.6*mm,133*mm,5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_titular3)
      story.append(Paragraph(nombreT3,estilo_titulares))
      story.append(FrameBreak())
      
      frame_cctitular3=Frame(153*mm,286.6*mm,52*mm,5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_cctitular3)
      story.append(Paragraph(ccTitular3,estilo_titulares))
      story.append(FrameBreak())
      
      frame_titular4=Frame(12.5*mm,280.4*mm,133*mm,5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_titular4)
      story.append(Paragraph(nombreT4,estilo_titulares))
      story.append(FrameBreak())
      
      frame_cctitular4=Frame(153*mm,280.4*mm,52*mm,5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_cctitular4)
      story.append(Paragraph(ccTitular4,estilo_titulares))
      story.append(FrameBreak())
      
      estilo_detalle=ParagraphStyle('detalle',fontName='centuryg',fontSize=10,alignment=1)
      estilo_detalle_peq=ParagraphStyle('detalle',fontName='centuryg',fontSize=8)
      frame_lote=Frame(23.4*mm,262.8*mm,36*mm,5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_lote)
      story.append(Paragraph(lote,estilo_detalle))
      story.append(FrameBreak())
      
      frame_manzana=Frame(70.5*mm,262.8*mm,41.8*mm,5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_manzana)
      story.append(Paragraph(manzana,estilo_detalle))
      story.append(FrameBreak())
      
      frame_area=Frame(124.1*mm,262.8*mm,55.7*mm,5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_area)
      story.append(Paragraph(area,estilo_detalle))
      story.append(FrameBreak())
      
      frame_valor=Frame(13.9*mm,257.8*mm,170.2*mm,5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_valor)
      story.append(Paragraph(valor,estilo_detalle))
      story.append(FrameBreak())
      
      frame_ci=Frame(16.7*mm,245.1*mm,104*mm,5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_ci)
      story.append(Paragraph('&nbsp '*25+ci,estilo_detalle))
      story.append(FrameBreak())
      
      estilo_formas=ParagraphStyle('formas',fontName='centuryg',fontSize=8,alignment=4,leading=14)
      
      frame_formaci=Frame(16.7*mm,229.3*mm,166.6*mm,15.6*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_formaci)
      story.append(Paragraph('&nbsp '*15+formaci,estilo_formas))
      story.append(FrameBreak())
      
      estilo_valores=ParagraphStyle('formas',fontName='centuryg',fontSize=10)
      
      frame_saldo=Frame(84.4*mm,231*mm,97.6*mm,5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_saldo)
      story.append(Paragraph(saldo,estilo_valores))
      story.append(FrameBreak())
      
      frame_formasaldo=Frame(16.7*mm,220.5*mm,166.6*mm,10*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_formasaldo)
      story.append(Paragraph('&nbsp '*15+formasaldo,estilo_formas))
      story.append(FrameBreak())
      
      frame_fechaentrega=Frame(93.6*mm,199.2*mm,83.1*mm,5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_fechaentrega)
      story.append(Paragraph(fechaEntrega,estilo_detalle_peq))
      story.append(FrameBreak())
      
      frame_fechaescrit=Frame(117.6*mm,156.7*mm,63.1*mm,5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_fechaescrit)
      story.append(Paragraph(fechaEscritura,estilo_detalle))
      story.append(FrameBreak())
      
      frame_Autotitular1=Frame(22.8*mm,142.5*mm,92*mm,5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_Autotitular1)
      story.append(Paragraph(nombreT1,estilo_titulares))
      story.append(FrameBreak())
      
      frame_Autocctitular1=Frame(145.6*mm,142.5*mm,54.5*mm,5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_Autocctitular1)
      story.append(Paragraph(ccTitular1,estilo_titulares))
      story.append(FrameBreak())
      
      frame_Autotitular2=Frame(22.8*mm,136.5*mm,133*mm,5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_Autotitular2)
      story.append(Paragraph(nombreT2,estilo_titulares))
      story.append(FrameBreak())
      
      frame_Autocctitular2=Frame(145.6*mm,136.5*mm,54.5*mm,5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_Autocctitular2)
      story.append(Paragraph(ccTitular2,estilo_titulares))
      story.append(FrameBreak())
      
      frame_Autotitular3=Frame(22.8*mm,129.5*mm,133*mm,5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_Autotitular3)
      story.append(Paragraph(nombreT3,estilo_titulares))
      story.append(FrameBreak())
      
      frame_Autocctitular3=Frame(145.6*mm,129.5*mm,52*mm,5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_Autocctitular3)
      story.append(Paragraph(ccTitular3,estilo_titulares))
      story.append(FrameBreak())
      
      frame_Autotitular4=Frame(22.8*mm,122.5*mm,133*mm,5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_Autotitular4)
      story.append(Paragraph(nombreT4,estilo_titulares))
      story.append(FrameBreak())
      
      frame_Autocctitular4=Frame(145.6*mm,122.5*mm,52*mm,5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_Autocctitular4)
      story.append(Paragraph(ccTitular4,estilo_titulares))
      story.append(FrameBreak())
      
      page1=PageTemplate(id='pagina1',frames=frames_pag1)
      doc=BaseDocTemplate(ruta,pageTemplates=page1,pagesize=LEGAL)
      doc.build(story)

    def VerificacionSotavento(self,ruta,nombreT1,nombreT2,nombreT3,nombreT4,
                             ccTitular1,ccTitular2,ccTitular3,ccTitular4,
                             lote,manzana,area,valor,ci,formaci,saldo,formasaldo,
                             fechaEntrega,fechaEscritura):
      story=[]
      
      frames_pag1=[]
     # Imagen base del doc
      frame_base=Frame(0,0,216*mm,356*mm)
      frames_pag1.append(frame_base)
      pagina1=Image('./resources/Sotavento/Verificacion-Contrato-sotavento.png',width=214*mm,height=350*mm)
      story.append(pagina1)
      story.append(FrameBreak())
      
      estilo_titulares=ParagraphStyle('titulares',fontName='centuryg',fontSize=12)
      frame_titular1=Frame(12.5*mm,299*mm,133*mm,5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_titular1)
      story.append(Paragraph(nombreT1,estilo_titulares))
      story.append(FrameBreak())
      
      frame_cctitular1=Frame(153*mm,299*mm,52*mm,5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_cctitular1)
      story.append(Paragraph(ccTitular1,estilo_titulares))
      story.append(FrameBreak())
      
      frame_titular2=Frame(12.5*mm,292.8*mm,133*mm,5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_titular2)
      story.append(Paragraph(nombreT2,estilo_titulares))
      story.append(FrameBreak())
      
      frame_cctitular2=Frame(153*mm,292.8*mm,52*mm,5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_cctitular2)
      story.append(Paragraph(ccTitular2,estilo_titulares))
      story.append(FrameBreak())
      
      frame_titular3=Frame(12.5*mm,286.6*mm,133*mm,5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_titular3)
      story.append(Paragraph(nombreT3,estilo_titulares))
      story.append(FrameBreak())
      
      frame_cctitular3=Frame(153*mm,286.6*mm,52*mm,5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_cctitular3)
      story.append(Paragraph(ccTitular3,estilo_titulares))
      story.append(FrameBreak())
      
      frame_titular4=Frame(12.5*mm,280.4*mm,133*mm,5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_titular4)
      story.append(Paragraph(nombreT4,estilo_titulares))
      story.append(FrameBreak())
      
      frame_cctitular4=Frame(153*mm,280.4*mm,52*mm,5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_cctitular4)
      story.append(Paragraph(ccTitular4,estilo_titulares))
      story.append(FrameBreak())
      
      estilo_detalle=ParagraphStyle('detalle',fontName='centuryg',fontSize=10,alignment=1)
      estilo_detalle_peq=ParagraphStyle('detalle',fontName='centuryg',fontSize=8)
      frame_lote=Frame(23.4*mm,262.8*mm,36*mm,5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_lote)
      story.append(Paragraph(lote,estilo_detalle))
      story.append(FrameBreak())
      
      frame_manzana=Frame(70.5*mm,262.8*mm,41.8*mm,5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_manzana)
      story.append(Paragraph(manzana,estilo_detalle))
      story.append(FrameBreak())
      
      frame_area=Frame(124.1*mm,262.8*mm,55.7*mm,5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_area)
      story.append(Paragraph(area,estilo_detalle))
      story.append(FrameBreak())
      
      frame_valor=Frame(13.9*mm,257.8*mm,170.2*mm,5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_valor)
      story.append(Paragraph(valor,estilo_detalle))
      story.append(FrameBreak())
      
      frame_ci=Frame(16.7*mm,245.1*mm,104*mm,5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_ci)
      story.append(Paragraph('&nbsp '*25+ci,estilo_detalle))
      story.append(FrameBreak())
      
      estilo_formas=ParagraphStyle('formas',fontName='centuryg',fontSize=8,alignment=4,leading=14)
      
      frame_formaci=Frame(16.7*mm,229.3*mm,166.6*mm,15.6*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_formaci)
      story.append(Paragraph('&nbsp '*15+formaci,estilo_formas))
      story.append(FrameBreak())
      
      estilo_valores=ParagraphStyle('formas',fontName='centuryg',fontSize=10)
      
      frame_saldo=Frame(84.4*mm,231*mm,97.6*mm,5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_saldo)
      story.append(Paragraph(saldo,estilo_valores))
      story.append(FrameBreak())
      
      frame_formasaldo=Frame(16.7*mm,220.5*mm,166.6*mm,10*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_formasaldo)
      story.append(Paragraph('&nbsp '*15+formasaldo,estilo_formas))
      story.append(FrameBreak())
      
      frame_fechaentrega=Frame(93.6*mm,199.2*mm,83.1*mm,5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_fechaentrega)
      story.append(Paragraph(fechaEntrega,estilo_detalle_peq))
      story.append(FrameBreak())
      
      frame_fechaescrit=Frame(117.6*mm,156.7*mm,63.1*mm,5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_fechaescrit)
      story.append(Paragraph(fechaEscritura,estilo_detalle))
      story.append(FrameBreak())
      
      frame_Autotitular1=Frame(22.8*mm,160.5*mm,92*mm,5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_Autotitular1)
      story.append(Paragraph(nombreT1,estilo_titulares))
      story.append(FrameBreak())
      
      frame_Autocctitular1=Frame(145.6*mm,160.5*mm,54.5*mm,5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_Autocctitular1)
      story.append(Paragraph(ccTitular1,estilo_titulares))
      story.append(FrameBreak())
      
      frame_Autotitular2=Frame(22.8*mm,154.5*mm,133*mm,5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_Autotitular2)
      story.append(Paragraph(nombreT2,estilo_titulares))
      story.append(FrameBreak())
      
      frame_Autocctitular2=Frame(145.6*mm,154.5*mm,54.5*mm,5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_Autocctitular2)
      story.append(Paragraph(ccTitular2,estilo_titulares))
      story.append(FrameBreak())
      
      frame_Autotitular3=Frame(22.8*mm,148.5*mm,133*mm,5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_Autotitular3)
      story.append(Paragraph(nombreT3,estilo_titulares))
      story.append(FrameBreak())
      
      frame_Autocctitular3=Frame(145.6*mm,148.5*mm,52*mm,5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_Autocctitular3)
      story.append(Paragraph(ccTitular3,estilo_titulares))
      story.append(FrameBreak())
      
      frame_Autotitular4=Frame(22.8*mm,142.5*mm,133*mm,5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_Autotitular4)
      story.append(Paragraph(nombreT4,estilo_titulares))
      story.append(FrameBreak())
      
      frame_Autocctitular4=Frame(145.6*mm,142.5*mm,52*mm,5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_Autocctitular4)
      story.append(Paragraph(ccTitular4,estilo_titulares))
      story.append(FrameBreak())
      
      page1=PageTemplate(id='pagina1',frames=frames_pag1)
      doc=BaseDocTemplate(ruta,pageTemplates=page1,pagesize=LEGAL)
      doc.build(story)
    
    def VerificacionPerla(self,ruta,nombreT1,nombreT2,nombreT3,nombreT4,
                             ccTitular1,ccTitular2,ccTitular3,ccTitular4,
                             lote,manzana,area,valor,ci,formaci,saldo,formasaldo,
                             fechaEntrega,fechaEscritura):
      story=[]
      
      frames_pag1=[]
     # Imagen base del doc
      frame_base=Frame(0,0,216*mm,356*mm)
      frames_pag1.append(frame_base)
      pagina1=Image('./resources/Verificacion Perla-del-Mar.png',width=214*mm,height=350*mm)
      story.append(pagina1)
      story.append(FrameBreak())
      
      estilo_titulares=ParagraphStyle('titulares',fontName='centuryg',fontSize=12)
      frame_titular1=Frame(12.5*mm,299*mm,133*mm,5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_titular1)
      story.append(Paragraph(nombreT1,estilo_titulares))
      story.append(FrameBreak())
      
      frame_cctitular1=Frame(153*mm,299*mm,52*mm,5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_cctitular1)
      story.append(Paragraph(ccTitular1,estilo_titulares))
      story.append(FrameBreak())
      
      frame_titular2=Frame(12.5*mm,292.8*mm,133*mm,5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_titular2)
      story.append(Paragraph(nombreT2,estilo_titulares))
      story.append(FrameBreak())
      
      frame_cctitular2=Frame(153*mm,292.8*mm,52*mm,5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_cctitular2)
      story.append(Paragraph(ccTitular2,estilo_titulares))
      story.append(FrameBreak())
      
      frame_titular3=Frame(12.5*mm,286.6*mm,133*mm,5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_titular3)
      story.append(Paragraph(nombreT3,estilo_titulares))
      story.append(FrameBreak())
      
      frame_cctitular3=Frame(153*mm,286.6*mm,52*mm,5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_cctitular3)
      story.append(Paragraph(ccTitular3,estilo_titulares))
      story.append(FrameBreak())
      
      frame_titular4=Frame(12.5*mm,280.4*mm,133*mm,5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_titular4)
      story.append(Paragraph(nombreT4,estilo_titulares))
      story.append(FrameBreak())
      
      frame_cctitular4=Frame(153*mm,280.4*mm,52*mm,5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_cctitular4)
      story.append(Paragraph(ccTitular4,estilo_titulares))
      story.append(FrameBreak())
      
      estilo_detalle=ParagraphStyle('detalle',fontName='centuryg',fontSize=10,alignment=1)
      estilo_detalle_peq=ParagraphStyle('detalle',fontName='centuryg',fontSize=8)
      frame_lote=Frame(23.4*mm,262.8*mm,36*mm,5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_lote)
      story.append(Paragraph(lote,estilo_detalle))
      story.append(FrameBreak())
      
      frame_manzana=Frame(70.5*mm,262.8*mm,41.8*mm,5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_manzana)
      story.append(Paragraph(manzana,estilo_detalle))
      story.append(FrameBreak())
      
      frame_area=Frame(124.1*mm,262.8*mm,55.7*mm,5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_area)
      story.append(Paragraph(area,estilo_detalle))
      story.append(FrameBreak())
      
      frame_valor=Frame(13.9*mm,257.8*mm,170.2*mm,5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_valor)
      story.append(Paragraph(valor,estilo_detalle))
      story.append(FrameBreak())
      
      frame_ci=Frame(16.7*mm,245.1*mm,104*mm,5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_ci)
      story.append(Paragraph('&nbsp '*25+ci,estilo_detalle))
      story.append(FrameBreak())
      
      estilo_formas=ParagraphStyle('formas',fontName='centuryg',fontSize=8,alignment=4,leading=14)
      
      frame_formaci=Frame(16.7*mm,229.3*mm,166.6*mm,15.6*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_formaci)
      story.append(Paragraph('&nbsp '*15+formaci,estilo_formas))
      story.append(FrameBreak())
      
      estilo_valores=ParagraphStyle('formas',fontName='centuryg',fontSize=10)
      
      frame_saldo=Frame(84.4*mm,231*mm,97.6*mm,5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_saldo)
      story.append(Paragraph(saldo,estilo_valores))
      story.append(FrameBreak())
      
      frame_formasaldo=Frame(16.7*mm,220.5*mm,166.6*mm,10*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_formasaldo)
      story.append(Paragraph('&nbsp '*15+formasaldo,estilo_formas))
      story.append(FrameBreak())
      
      frame_fechaentrega=Frame(93.6*mm,199.2*mm,83.1*mm,5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_fechaentrega)
      story.append(Paragraph(fechaEntrega,estilo_detalle_peq))
      story.append(FrameBreak())
      
      frame_fechaescrit=Frame(117.6*mm,156.7*mm,63.1*mm,5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_fechaescrit)
      story.append(Paragraph(fechaEscritura,estilo_detalle))
      story.append(FrameBreak())
      
      frame_Autotitular1=Frame(22.8*mm,185*mm,92*mm,5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_Autotitular1)
      story.append(Paragraph(nombreT1,estilo_titulares))
      story.append(FrameBreak())
      
      frame_Autocctitular1=Frame(145.6*mm,185*mm,54.5*mm,5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_Autocctitular1)
      story.append(Paragraph(ccTitular1,estilo_titulares))
      story.append(FrameBreak())
      
      frame_Autotitular2=Frame(22.8*mm,178.5*mm,133*mm,5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_Autotitular2)
      story.append(Paragraph(nombreT2,estilo_titulares))
      story.append(FrameBreak())
      
      frame_Autocctitular2=Frame(145.6*mm,178.5*mm,54.5*mm,5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_Autocctitular2)
      story.append(Paragraph(ccTitular2,estilo_titulares))
      story.append(FrameBreak())
      
      frame_Autotitular3=Frame(22.8*mm,173*mm,133*mm,5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_Autotitular3)
      story.append(Paragraph(nombreT3,estilo_titulares))
      story.append(FrameBreak())
      
      frame_Autocctitular3=Frame(145.6*mm,173*mm,52*mm,5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_Autocctitular3)
      story.append(Paragraph(ccTitular3,estilo_titulares))
      story.append(FrameBreak())
      
      frame_Autotitular4=Frame(22.8*mm,167*mm,133*mm,5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_Autotitular4)
      story.append(Paragraph(nombreT4,estilo_titulares))
      story.append(FrameBreak())
      
      frame_Autocctitular4=Frame(145.6*mm,167*mm,52*mm,5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_Autocctitular4)
      story.append(Paragraph(ccTitular4,estilo_titulares))
      story.append(FrameBreak())
      
      page1=PageTemplate(id='pagina1',frames=frames_pag1)
      doc=BaseDocTemplate(ruta,pageTemplates=page1,pagesize=LEGAL)
      doc.build(story)
    
    def VerificacionCarmeloReservado(self,ctr,ruta,nombreT1,nombreT2,nombreT3,nombreT4,
                             ccTitular1,ccTitular2,ccTitular3,ccTitular4,
                             lote,manzana,area,valor,ci,formaci,saldo,formasaldo,
                             fechaEntrega,fechaEscritura,fechactr):
      story=[]
      
      frames_pag1=[]
     # Imagen base del doc
      frame_base=Frame(0,0,216*mm,356*mm)
      frames_pag1.append(frame_base)
      pagina1=Image('./resources/Carmelo Reservado/Verificacion Contrato - Carmelo Reservado-1.png',width=214*mm,height=350*mm)
      story.append(pagina1)
      story.append(FrameBreak())
      
      frame_nro_ctro=Frame(82.6*mm,312*mm,10*mm,5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_nro_ctro)
      story.append(Paragraph(f'<b>{ctr}</b>',
                             ParagraphStyle('nro',fontName='centuryg',fontSize=12,align=1,textColor='#F78369'))
      )
      story.append(FrameBreak())
      
      frame_fecha_ctro=Frame(112.6*mm,312*mm,33*mm,5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_fecha_ctro)
      story.append(Paragraph(f'<b>{fechactr}</b>',
                             ParagraphStyle('fecha',fontName='centuryg',fontSize=12,align=1,textColor='#F78369'))
      )
      story.append(FrameBreak())
    
      
      
      estilo_titulares=ParagraphStyle('titulares',fontName='centuryg',fontSize=12)
      frame_titular1=Frame(29.5*mm,291*mm,133*mm,5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_titular1)
      story.append(Paragraph(nombreT1,estilo_titulares))
      story.append(FrameBreak())
      
      frame_cctitular1=Frame(153*mm,291*mm,52*mm,5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_cctitular1)
      story.append(Paragraph(ccTitular1,estilo_titulares))
      story.append(FrameBreak())
      
      frame_titular2=Frame(29.5*mm,284.8*mm,133*mm,5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_titular2)
      story.append(Paragraph(nombreT2,estilo_titulares))
      story.append(FrameBreak())
      
      frame_cctitular2=Frame(153*mm,284.8*mm,52*mm,5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_cctitular2)
      story.append(Paragraph(ccTitular2,estilo_titulares))
      story.append(FrameBreak())
      
      frame_titular3=Frame(29.5*mm,278.6*mm,133*mm,5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_titular3)
      story.append(Paragraph(nombreT3,estilo_titulares))
      story.append(FrameBreak())
      
      frame_cctitular3=Frame(153*mm,278.6*mm,52*mm,5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_cctitular3)
      story.append(Paragraph(ccTitular3,estilo_titulares))
      story.append(FrameBreak())
      
      frame_titular4=Frame(29.5*mm,272.4*mm,133*mm,5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_titular4)
      story.append(Paragraph(nombreT4,estilo_titulares))
      story.append(FrameBreak())
      
      frame_cctitular4=Frame(153*mm,272.4*mm,52*mm,5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_cctitular4)
      story.append(Paragraph(ccTitular4,estilo_titulares))
      story.append(FrameBreak())
      
      estilo_detalle=ParagraphStyle('detalle',fontName='centuryg',fontSize=10,alignment=1)
      estilo_detalle_peq=ParagraphStyle('detalle',fontName='centuryg',fontSize=8)
      
      frame_lote=Frame(71.8*mm,250.3*mm,36*mm,5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_lote)
      story.append(Paragraph(lote,estilo_detalle))
      story.append(FrameBreak())
      
      frame_manzana=Frame(105*mm,250.3*mm,41.8*mm,5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_manzana)
      story.append(Paragraph(manzana,estilo_detalle))
      story.append(FrameBreak())
      
      frame_area=Frame(137.1*mm,250.3*mm,55.7*mm,5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_area)
      story.append(Paragraph(area,estilo_detalle))
      story.append(FrameBreak())
      
      frame_valor=Frame(76*mm,241.7*mm,100*mm,5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_valor)
      story.append(Paragraph(f'{int(valor):,}',estilo_detalle))
      story.append(FrameBreak())
      
      frame_ci=Frame(58.5*mm,230.2*mm,36*mm,5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_ci)
      story.append(Paragraph(f'{int(ci):,}',estilo_detalle))
      story.append(FrameBreak())
      
      estilo_formas=ParagraphStyle('formas',fontName='centuryg',fontSize=8,alignment=4,leading=14)
      
      frame_formaci=Frame(97*mm,195.7*mm,108*mm,38.4*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_formaci)
      story.append(Paragraph('&nbsp '*14+formaci,
                             ParagraphStyle('detalle',fontName='centuryg',fontSize=7,alignment=4,leading=14)))
      story.append(FrameBreak())
      
      estilo_valores=ParagraphStyle('formas',fontName='centuryg',fontSize=10)
      
      frame_saldo=Frame(58.8*mm,215*mm,36*mm,5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_saldo)
      story.append(Paragraph(f'{int(saldo):,}',estilo_detalle))
      story.append(FrameBreak())
      
      frame_formasaldo=Frame(97*mm,200.2*mm,93*mm,18.4*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_formasaldo)
      story.append(Paragraph('&nbsp '*15+formasaldo,
                             ParagraphStyle('detalle',fontName='centuryg',fontSize=7,alignment=4,leading=14)))
      story.append(FrameBreak())
      
      frame_fechaentrega=Frame(27.7*mm,137*mm,28.4*mm,5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_fechaentrega)
      story.append(Paragraph(fechaEntrega,estilo_detalle_peq))
      story.append(FrameBreak())
      
            
      frame_titular1_2=Frame(22*mm,128*mm,112*mm,5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_titular1_2)
      story.append(Paragraph(nombreT1,estilo_titulares))
      story.append(FrameBreak())
      
      frame_cctitular1_2=Frame(142*mm,128*mm,52*mm,5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_cctitular1_2)
      story.append(Paragraph(ccTitular1,estilo_titulares))
      story.append(FrameBreak())
      
      frame_titular2_2=Frame(18*mm,122.2*mm,112*mm,5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_titular2_2)
      story.append(Paragraph(nombreT2,estilo_titulares))
      story.append(FrameBreak())
      
      frame_cctitular2_2=Frame(142*mm,122.2*mm,52*mm,5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_cctitular2_2)
      story.append(Paragraph(ccTitular2,estilo_titulares))
      story.append(FrameBreak())
      
      frame_titular3_2=Frame(18*mm,117*mm,133*mm,5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_titular3_2)
      story.append(Paragraph(nombreT3,estilo_titulares))
      story.append(FrameBreak())
      
      frame_cctitular3_2=Frame(142*mm,117*mm,52*mm,5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_cctitular3_2)
      story.append(Paragraph(ccTitular3,estilo_titulares))
      story.append(FrameBreak())
      
      frame_titular4_2=Frame(18*mm,111.1*mm,133*mm,5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_titular4_2)
      story.append(Paragraph(nombreT4,estilo_titulares))
      story.append(FrameBreak())
      
      frame_cctitular4_2=Frame(142*mm,111.1*mm,52*mm,5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag1.append(frame_cctitular4_2)
      story.append(Paragraph(ccTitular4,estilo_titulares))
      #story.append(FrameBreak())
      
      
      story.append(NextPageTemplate('pagina2'))
      frames_pag2=[]
      frames_pag2.append(frame_base)
      
      
      pagina2=Image('./resources/Carmelo Reservado/Verificacion Contrato - Carmelo Reservado-2.png',width=214*mm,height=350*mm)
      story.append(pagina2)
      story.append(FrameBreak())
      
      estilo_fechas=ParagraphStyle('formas',fontName='centuryg',fontSize=10, align=1)
      
      frame_diaC=Frame(135*mm,287.5*mm,20*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag2.append(frame_diaC)
      story.append(Paragraph(str(fechactr.day),estilo_fechas))
      story.append(FrameBreak())
      
      frame_mesC=Frame(174.5*mm,287.5*mm,22.3*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag2.append(frame_mesC)
      mes = Utilidades().NombreMes(fechactr.month)
      story.append(Paragraph(mes,estilo_fechas))
      story.append(FrameBreak())
      
      frame_añoC=Frame(17.5*mm,283.5*mm,17*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag2.append(frame_añoC)
      story.append(Paragraph(str(fechactr.year),estilo_fechas))
      story.append(FrameBreak())
      
      frame_ciudadC=Frame(96*mm,287.5 *mm,30.4*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames_pag2.append(frame_ciudadC)
      story.append(Paragraph('Medellin',estilo_fechas))
      story.append(FrameBreak())
      
      
      page1=PageTemplate(id='pagina1',frames=frames_pag1)
      page2=PageTemplate(id='pagina2',frames=frames_pag2)
      
      doc=BaseDocTemplate(ruta,pageTemplates=[page1,page2],pagesize=LEGAL)
      doc.build(story)
    
        
    def Conciliacion(self,empresa,cuenta_banco,cuenta_cont,saldo_banco,saldo_cont,
                     fecha_conciliacion,mvto_contable,mvto_banco,ruta,user,
                     conciliacion):
      
      frame=Frame(8*mm,8*mm,200*mm,285*mm)
      story=[]
      
      dictLogos={'900993044':"resources/Logos/Andina-Conceptos.png",
                 '901132949':"resources/Logos/Promotora West.png",
                 '901004733':'resources/Logos/quadrata.png',
                 '901018375':'resources/Logos/status-comercializadora.png',
                 '900712229':'resources/Logos/Terranova.png'}

      logo=Image(dictLogos[empresa.pk],width=50*mm,height=20*mm)
      story.append(logo)
      
      
      estilo_titulo1=ParagraphStyle('titulo',alignment=1,fontSize=12,fontName='centuryg')
      story.append(Paragraph('<b>CONCILIACION BANCARIA</b>',estilo_titulo1))
      story.append(Paragraph(f'<b>{empresa.nombre.upper()}</b>',estilo_titulo1))
      
      
      dia=datetime.today().day
      mes=Utilidades().NombreMes(datetime.today().month)
      año=datetime.today().year

      estilo_titulo2=ParagraphStyle('titulo',alignment=1,fontSize=10,fontName='centuryg')
      story.append(Paragraph(f'<b>Conciliacion a: </b>{fecha_conciliacion}',estilo_titulo2))
      story.append(Spacer(0,10))
      estilo_encabezados=ParagraphStyle('titulo',alignment=0,fontSize=10,fontName='centuryg')
      story.append(Paragraph(f'<b>CUENTA BANCARIA: </b> {cuenta_banco}',estilo_encabezados))
      story.append(Paragraph(f'<b>CUENTA CONTABLE: </b> {cuenta_cont}',estilo_encabezados))
      
      story.append(Spacer(0,20))
            
      story.append(Paragraph(f'<b>Saldo en Libros: </b> {saldo_cont:,}',estilo_encabezados))
      
      story.append(Spacer(0,10))
     
     #Tabla ingresos contables NC
      story.append(Paragraph('<b>(-) Comprobantes de ingreso no registrados en extracto:</b>',estilo_encabezados))
      story.append(Spacer(0,10))
      
      estructura_tabla=[]
      estilo_encabezado_tabla=ParagraphStyle('encabezado tabla',alignment=1,fontSize=10,fontName='centuryg')
      encabezados_tabla=(Paragraph('<b>Fecha</b>',estilo_encabezado_tabla),
                            Paragraph('<b>Comprobante</b>',estilo_encabezado_tabla),
                            Paragraph('<b>Descripcion</b>',estilo_encabezado_tabla),
                            Paragraph('<b>Valor</b>',estilo_encabezado_tabla))
      estructura_tabla.append(encabezados_tabla)
      
      ingresos_nc_cont = mvto_contable.filter(valor__gte=0,
                            ).values_list('fecha','comprobante','descripcion','valor')
      total_ing_nc_cont = mvto_contable.filter(valor__gte=0,
                            ).aggregate(Sum('valor'))['valor__sum']
      if total_ing_nc_cont == None: total_ing_nc_cont = 0
      egresos_nc_cont = mvto_contable.filter(valor__lt=0,
                            ).values_list('fecha','comprobante','descripcion','valor')
      total_egr_nc_cont = mvto_contable.filter(valor__lt=0,
                            ).aggregate(Sum('valor'))['valor__sum']
      if total_egr_nc_cont == None: total_egr_nc_cont = 0
      contenido=ingresos_nc_cont
      
      estilo_detalle_tabla=ParagraphStyle('encabezado tabla',alignment=1,fontSize=8,fontName='centuryg')
      
      for fila in contenido:
          fila_format=[]
          for celda in fila:
              fila_format.append(Paragraph(str(celda),estilo_detalle_tabla))
          estructura_tabla.append(fila_format)
      totales=[Paragraph('<b>TOTAL</b>',estilo_detalle_tabla),
               Paragraph('',estilo_detalle_tabla),Paragraph('',estilo_detalle_tabla)
               ]
      totales.append(Paragraph(f'<b>{total_ing_nc_cont:,}</b>',estilo_detalle_tabla))
      
      estructura_tabla.append(totales)
      
      tabla=Table(estructura_tabla,colWidths=[60,120,230,80])
      tabla.setStyle([('ALIGNMENT',(0,0),(-1,0),'CENTER'),
                     ('BACKGROUND',(0,0),(-1,0),colors.lightblue),
                      ('GRID',(0,0),(-1,-1),1,'#6D6D6D'),
                      ('VALIGN',(0,0),(-1,-1),'MIDDLE'),
                      ('SPAN',(0,-1),(2,-1))])
      story.append(tabla)
      
      story.append(Spacer(0,10))
     
     #Tabla egresos contables NC
      story.append(Paragraph('<b>(+) Comprobantes de egreso no registrados en extracto:</b>',estilo_encabezados))
      story.append(Spacer(0,10))
      
      estructura_tabla=[]
      estilo_encabezado_tabla=ParagraphStyle('encabezado tabla',alignment=1,fontSize=10,fontName='centuryg')
      encabezados_tabla=(Paragraph('<b>Fecha</b>',estilo_encabezado_tabla),
                            Paragraph('<b>Comprobante</b>',estilo_encabezado_tabla),
                            Paragraph('<b>Descripcion</b>',estilo_encabezado_tabla),
                            Paragraph('<b>Valor</b>',estilo_encabezado_tabla))
      estructura_tabla.append(encabezados_tabla)
      
      contenido=egresos_nc_cont
      
      estilo_detalle_tabla=ParagraphStyle('encabezado tabla',alignment=1,fontSize=8,fontName='centuryg')
      
      for fila in contenido:
          fila_format=[]
          for celda in fila:
              fila_format.append(Paragraph(str(celda),estilo_detalle_tabla))
          estructura_tabla.append(fila_format)
      totales=[Paragraph('<b>TOTAL</b>',estilo_detalle_tabla),
               Paragraph('',estilo_detalle_tabla),Paragraph('',estilo_detalle_tabla)
               ]
      totales.append(Paragraph(f'<b>{total_egr_nc_cont:,}</b>',estilo_detalle_tabla))
      
      estructura_tabla.append(totales)
      
      tabla=Table(estructura_tabla,colWidths=[60,120,230,80])
      tabla.setStyle([('ALIGNMENT',(0,0),(-1,-1),'CENTER'),
                      ('BACKGROUND',(0,0),(-1,0),colors.lightblue),
                          ('GRID',(0,0),(-1,-1),1,'#6D6D6D'),
                          ('VALIGN',(0,0),(-1,-1),'MIDDLE'),
                          ('SPAN',(0,-1),(2,-1))])
      story.append(tabla)
      story.append(Spacer(0,10))
     
     #Tabla ingresos bancarios NC
      story.append(Paragraph('<b>(+) Ingresos en extracto no registrados en contabilidad:</b>',estilo_encabezados))
      story.append(Spacer(0,10))
      
      estructura_tabla=[]
      estilo_encabezado_tabla=ParagraphStyle('encabezado tabla',alignment=1,fontSize=10,fontName='centuryg')
      encabezados_tabla=(Paragraph('<b>Fecha</b>',estilo_encabezado_tabla),
                            Paragraph('<b>Descripcion</b>',estilo_encabezado_tabla),
                            Paragraph('<b>Referencia</b>',estilo_encabezado_tabla),
                            Paragraph('<b>Valor</b>',estilo_encabezado_tabla))
      estructura_tabla.append(encabezados_tabla)
      
      ingresos_nc_banco = mvto_banco.filter(valor__gte=0,
                            ).values_list('fecha','descripcion','referencia','valor')
      total_ing_nc_banco = mvto_banco.filter(valor__gte=0,
                            ).aggregate(Sum('valor'))['valor__sum']
      if total_ing_nc_banco == None: total_ing_nc_banco = 0
      egresos_nc_banco = mvto_banco.filter(valor__lt=0,
                            ).values_list('fecha','descripcion','referencia','valor')
      total_egr_nc_banco = mvto_banco.filter(valor__lt=0,
                            ).aggregate(Sum('valor'))['valor__sum']
      if total_egr_nc_banco == None: total_egr_nc_banco = 0
      contenido=ingresos_nc_banco
      
      estilo_detalle_tabla=ParagraphStyle('encabezado tabla',alignment=1,fontSize=8,fontName='centuryg')
      
      for fila in contenido:
          fila_format=[]
          for celda in fila:
              fila_format.append(Paragraph(str(celda),estilo_detalle_tabla))
          estructura_tabla.append(fila_format)
      totales=[Paragraph('<b>TOTAL</b>',estilo_detalle_tabla),
               Paragraph('',estilo_detalle_tabla),Paragraph('',estilo_detalle_tabla)
               ]
      totales.append(Paragraph(f'<b>{total_ing_nc_banco:,}</b>',estilo_detalle_tabla))
      
      estructura_tabla.append(totales)
      
      tabla=Table(estructura_tabla,colWidths=[60,230,120,80])
      tabla.setStyle([('ALIGNMENT',(0,0),(-1,-1),'CENTER'),
                          ('GRID',(0,0),(-1,-1),1,'#6D6D6D'),
                          ('VALIGN',(0,0),(-1,-1),'MIDDLE'),
                          ('BACKGROUND',(0,0),(-1,0),colors.lightblue),
                          ('SPAN',(0,-1),(2,-1))])
      story.append(tabla)
      story.append(Spacer(0,10))
      
     #Tabla egresos bancarios NC
      story.append(Paragraph('<b>(-) Egresos en extracto no registrados en contabilidad:</b>',estilo_encabezados))
      story.append(Spacer(0,10))
      
      estructura_tabla=[]
      estilo_encabezado_tabla=ParagraphStyle('encabezado tabla',alignment=1,fontSize=10,fontName='centuryg')
      encabezados_tabla=(Paragraph('<b>Fecha</b>',estilo_encabezado_tabla),
                            Paragraph('<b>Descripcion</b>',estilo_encabezado_tabla),
                            Paragraph('<b>Referencia</b>',estilo_encabezado_tabla),
                            Paragraph('<b>Valor</b>',estilo_encabezado_tabla))
      estructura_tabla.append(encabezados_tabla)
      
      contenido=egresos_nc_banco
      
      estilo_detalle_tabla=ParagraphStyle('encabezado tabla',alignment=1,fontSize=8,fontName='centuryg')
      
      for fila in contenido:
          fila_format=[]
          for celda in fila:
              fila_format.append(Paragraph(str(celda),estilo_detalle_tabla))
          estructura_tabla.append(fila_format)
      totales=[Paragraph('<b>TOTAL</b>',estilo_detalle_tabla),
               Paragraph('',estilo_detalle_tabla),Paragraph('',estilo_detalle_tabla)
               ]
      totales.append(Paragraph(f'<b>{total_egr_nc_banco:,}</b>',estilo_detalle_tabla))
      
      estructura_tabla.append(totales)
      
      tabla=Table(estructura_tabla,colWidths=[60,230,120,80])
      tabla.setStyle([('ALIGNMENT',(0,0),(-1,-1),'CENTER'),
                          ('GRID',(0,0),(-1,-1),1,'#6D6D6D'),
                          ('VALIGN',(0,0),(-1,-1),'MIDDLE'),
                          ('BACKGROUND',(0,0),(-1,0),colors.lightblue),
                          ('SPAN',(0,-1),(2,-1))])
      story.append(tabla)
      saldo_conciliado = saldo_cont - total_ing_nc_cont - total_egr_nc_cont + total_ing_nc_banco + total_egr_nc_banco
      diferencia = saldo_banco - saldo_conciliado
     #pie
      story.append(Spacer(0,10))
      story.append(Paragraph(f'<b>(=) Saldo Conciliado: </b> {saldo_conciliado:,}',estilo_encabezados))
      story.append(Paragraph(f'<b>Saldo en Bancos: </b> {saldo_banco:,}',estilo_encabezados))
      story.append(Paragraph(f'<b>Diferencia: </b> {diferencia:,}',estilo_encabezados))
      story.append(Spacer(0,10))
      story.append(Paragraph('Elaboró:',estilo_encabezados))
      story.append(Spacer(0,30))
      story.append(Paragraph('_'*30,estilo_encabezados))
      story.append(Paragraph(f'<b>Nombre:</b> {user.first_name} {user.last_name}',estilo_encabezados))
      story.append(Spacer(0,20))
      story.append(Paragraph('Aprobó:',estilo_encabezados))
      story.append(Spacer(0,30))
      story.append(Paragraph('_'*30,estilo_encabezados))
      story.append(Paragraph(f'<b>Nombre:</b>',estilo_encabezados))
      story.append(Spacer(0,40))
      story.append(Paragraph(f'Generado el {datetime.now()} por <b>{user}</b>. ID conciliacion <b>{conciliacion.pk}</b> realizada el {conciliacion.fecha_crea}',estilo_encabezados))
      page=PageTemplate(id='pagina1',frames=frame)
      doc=BaseDocTemplate(ruta,pageTemplates=page)
      doc.build(story)

    def pazysalvo(self,empresa,nit_empresa,nombre_cliente,cc_cliente,tipo_contrato,
                  nro_contrato,mz,lt,fecha_ctr,valor_ctr,proyecto,ruta):
        ubicacion_proyecto="Departamento de Antioquia"
        vr_letras=Utilidades().numeros_letras(valor_ctr)
        story=[]
        
        frame1=Frame(0*mm,0*mm,210*mm,297*mm)
        frame2=Frame(26*mm,26*mm,170*mm,225*mm)
        frames=(frame1,frame2)
        image_base=Image('./resources/membrete andina.png',width=210*mm,height=290*mm)
        story.append(image_base)
        story.append(FrameBreak())
        estilo_titulo=ParagraphStyle('titulares',fontName='centuryg',fontSize=16,alignment=1)
        estilo_titulares=ParagraphStyle('titulares',fontName='centuryg',fontSize=14,alignment=1)
        estilo_cuerpo=ParagraphStyle('titulares',fontName='centuryg',fontSize=12,alignment=4)
        story.append(Spacer(0,30))
        story.append(Paragraph(f'<strong>{empresa}</strong>',estilo_titulo))
        story.append(Spacer(0,5))
        story.append(Paragraph(f'<strong>{nit_empresa}</strong>',estilo_titulo))
        story.append(Spacer(0,40))
        story.append(Paragraph(f'<strong>CERTIFICA QUE:</strong>',estilo_titulares))
        story.append(Spacer(0,20))
        story.append(Paragraph(f'''El(la) señor(a) <b>{nombre_cliente.upper()}</b> identificado(a) con cedula 
                               de ciudadania Nº {cc_cliente} suscribió contrato de {tipo_contrato} de compraventa 
                               Nº {nro_contrato} sobre el lote {lt} manzana {mz} el {fecha_ctr} por un valor de {vr_letras} 
                               (${valor_ctr}), el lote en referencia hace parte del proyecto urbainístico, denominado {proyecto},
                               ubicado en el {ubicacion_proyecto}, el cual fue cancelado en su totalidad quedando a paz y salvo por todo concepto.<br/>
                               <br/>La presente certificación de paz y salvo se expide a solicitud del interesado en la ciudad de 
                               Medellín – Antioquia, a los nueve {datetime.today().day} días del mes {datetime.today().month} de {datetime.today().year}.
                               ''',estilo_cuerpo))
        story.append(Spacer(0,80))
        story.append(Paragraph('<strong>__________________________</strong><br/>',estilo_titulares))
        story.append(Spacer(0,5))
        story.append(Paragraph('<strong>JORGE MARIO AVILA</strong>',estilo_titulares))
        story.append(Paragraph('<strong>GERENTE ADMINISTRATIVO</strong>',estilo_titulares))
        story.append(Paragraph(f'<strong>{empresa.upper()}</strong>',estilo_titulares))
        story.append(Paragraph(f'<strong>NIT. {nit_empresa}</strong>',estilo_titulares))
        
        page=PageTemplate(id='pagina1',frames=frames)
        doc=BaseDocTemplate(ruta,pageTemplates=page)
        doc.build(story)
    
    def estado_de_cuenta(self,ruta,fecha,adj,nombre,proyecto,direccion,inmueble,telefono,
                         valor_contrato,
                         vr_ci,rcdo_ci,saldo_ci,
                         vr_fn,rcdo_fn,saldo_fn,
                         ctas_fn,vr_cta_fn,tasa,
                         vr_ce,ctas_ce,rcdo_ce,saldo_ce,
                         vr_co,rcdo_co,saldo_co,
                         rcdo_total,saldo_total,saldo_mora,
                         ctas_vencidas,saldo_vencido,dias_mora,
                         cuotas_pendientes,cuotas_pagadas):
      image_base={
        'Vegas de Venecia':'./resources/base_ec_Vegas.png',
        'Tesoro Escondido':'./resources/base_ec_tesoro.png',
        'Sandville Beach':'./resources/base_ec_sandville.png',
        'Perla del Mar':'./resources/base_ec_sandville.png',
        'Sandville del Sol':'./resources/base_ec_sandville.png',
        'Sotavento':'./resources/base_ec_sotavento.png',
        'Carmelo Reservado': './resources/Carmelo Reservado/membrete.png',
        'Alttum Collection':''
      }
      
      formato='./resources/Formato-de-estado-de-cuenta-lotes.png'
      base=image_base[proyecto]
      story=[]
      frames_pag1=[]
     # Imagen base del doc
      frame_base=Frame(0,0,210*mm,269*mm,id='pagina1',leftPadding=0,rightPadding=0)
      frames_pag1.append(frame_base)
      pagina1=Image(formato,width=210*mm,height=257*mm)
      story.append(pagina1)
      story.append(FrameBreak())
      
      Estilo_peq=ParagraphStyle('titulares',fontName='centuryg',fontSize=8)
      Estilo_med=ParagraphStyle('titulares',fontName='centuryg',fontSize=10)
      Estilo_med_centrado=ParagraphStyle('titulares',alignment=1,fontName='centuryg',fontSize=10)
      
      ajuste_v=10*mm
      
      frame_fecha=Frame(76.5*mm,261.6*mm+ajuste_v,60*mm,5*mm,id='fecha',showBoundary=0,topPadding=0,leftPadding=0,bottomPadding=0,rightPadding=0)
      frames_pag1.append(frame_fecha)
      story.append(Paragraph('<strong>Fecha y Hora: </strong>'+fecha,Estilo_peq))
      story.append(FrameBreak())
      
      frame_adj=Frame(20.7*mm,233*mm+ajuste_v,40*mm,5*mm,id='adj',showBoundary=0,topPadding=0,leftPadding=0,bottomPadding=0,rightPadding=0)
      frames_pag1.append(frame_adj)
      story.append(Paragraph(adj,Estilo_med))
      story.append(FrameBreak())
      
      frame_nombre=Frame(73*mm,233*mm+ajuste_v,60*mm,5*mm,id='nombre',showBoundary=0,topPadding=0,leftPadding=0,bottomPadding=0,rightPadding=0)
      frames_pag1.append(frame_nombre)
      story.append(Paragraph(nombre[:24],Estilo_med))
      story.append(FrameBreak())
      
      frame_proyecto=Frame(147*mm,233*mm+ajuste_v,53.4*mm,5*mm,id='proyecto',showBoundary=0,topPadding=0,leftPadding=0,bottomPadding=0,rightPadding=0)
      frames_pag1.append(frame_proyecto)
      story.append(Paragraph(proyecto,Estilo_med))
      story.append(FrameBreak())
      
      frame_direccion=Frame(29.2*mm,225*mm+ajuste_v,71*mm,5*mm,id='direccion',showBoundary=0,topPadding=0,leftPadding=0,bottomPadding=0,rightPadding=0)
      frames_pag1.append(frame_direccion)
      story.append(Paragraph(direccion[:36],Estilo_peq))
      story.append(FrameBreak())
      
      frame_Inmueble=Frame(114*mm,225*mm+ajuste_v,39*mm,5*mm,id='inmueble',showBoundary=0,topPadding=0,leftPadding=0,bottomPadding=0,rightPadding=0)
      frames_pag1.append(frame_Inmueble)
      story.append(Paragraph(inmueble,Estilo_med))
      story.append(FrameBreak())
      
      frame_telefono=Frame(166.5*mm,224*mm+ajuste_v,33*mm,5*mm,id='telefono',showBoundary=0,topPadding=0,leftPadding=0,bottomPadding=0,rightPadding=0)
      frames_pag1.append(frame_telefono)
      story.append(Paragraph(telefono[:20],Estilo_peq))
      story.append(FrameBreak())
      
      frame_valor=Frame(40*mm,205.5*mm+ajuste_v,150*mm,5*mm,id='valor',showBoundary=0,topPadding=0,leftPadding=0,bottomPadding=0,rightPadding=0)
      frames_pag1.append(frame_valor)
      story.append(Paragraph(f'${valor_contrato:,}',Estilo_med))
      story.append(FrameBreak())
      
      frame_ci=Frame(37.7*mm,195*mm+ajuste_v,31*mm,5*mm,id='valor_ci',showBoundary=0,topPadding=0,leftPadding=0,bottomPadding=0,rightPadding=0)
      frames_pag1.append(frame_ci)
      story.append(Paragraph(f'${vr_ci:,}',Estilo_med))
      story.append(FrameBreak())
      
      frame_rcd_ci=Frame(97.2*mm,195*mm+ajuste_v,31*mm,5*mm,id='rcd_ci',showBoundary=0,topPadding=0,leftPadding=0,bottomPadding=0,rightPadding=0)
      frames_pag1.append(frame_rcd_ci)
      story.append(Paragraph(f'${rcdo_ci:,}',Estilo_med))
      story.append(FrameBreak())
      
      frame_sdo_ci=Frame(148*mm,195*mm+ajuste_v,51*mm,5*mm,id='sdo_ci',showBoundary=0,topPadding=0,leftPadding=0,bottomPadding=0,rightPadding=0)
      frames_pag1.append(frame_sdo_ci)
      story.append(Paragraph(f'${saldo_ci:,}',Estilo_med))
      story.append(FrameBreak())
      
      frame_fn=Frame(37.7*mm,184*mm+ajuste_v,31*mm,5*mm,id='valor_fn',showBoundary=0,topPadding=0,leftPadding=0,bottomPadding=0,rightPadding=0)
      frames_pag1.append(frame_fn)
      story.append(Paragraph(f'${vr_fn:,}',Estilo_med))
      story.append(FrameBreak())
      
      frame_rcd_fn=Frame(107*mm,184*mm+ajuste_v,26*mm,5*mm,id='rcd_fn',showBoundary=0,topPadding=0,leftPadding=0,bottomPadding=0,rightPadding=0)
      frames_pag1.append(frame_rcd_fn)
      story.append(Paragraph(f'${rcdo_fn:,}',Estilo_med))
      story.append(FrameBreak())
      
      frame_sdo_fn=Frame(169*mm,184*mm+ajuste_v,31*mm,5*mm,id='sdo_fn',showBoundary=0,topPadding=0,leftPadding=0,bottomPadding=0,rightPadding=0)
      frames_pag1.append(frame_sdo_fn)
      story.append(Paragraph(f'${saldo_fn:,}',Estilo_med))
      story.append(FrameBreak())
      
      frame_nro_fn=Frame(36*mm,173*mm+ajuste_v,31*mm,5*mm,id='nro_fn',showBoundary=0,topPadding=0,leftPadding=0,bottomPadding=0,rightPadding=0)
      frames_pag1.append(frame_nro_fn)
      story.append(Paragraph(str(ctas_fn),Estilo_med))
      story.append(FrameBreak())
      
      frame_vrcta_fn=Frame(99*mm,173*mm+ajuste_v,31*mm,5*mm,id='vrcta_fn',showBoundary=0,topPadding=0,leftPadding=0,bottomPadding=0,rightPadding=0)
      frames_pag1.append(frame_vrcta_fn)
      story.append(Paragraph(f'${vr_cta_fn:,}',Estilo_med))
      story.append(FrameBreak())
      
      frame_tasa_fn=Frame(164*mm,173*mm+ajuste_v,31*mm,5*mm,id='tasa_fn',showBoundary=0,topPadding=0,leftPadding=0,bottomPadding=0,rightPadding=0)
      frames_pag1.append(frame_tasa_fn)
      story.append(Paragraph(f'{tasa}% M.V',Estilo_med))
      story.append(FrameBreak())
      
      frame_vr_ce=Frame(34*mm,161.5*mm+ajuste_v,31*mm,5*mm,id='vr_ce',showBoundary=0,topPadding=0,leftPadding=0,bottomPadding=0,rightPadding=0)
      frames_pag1.append(frame_vr_ce)
      story.append(Paragraph(f'${vr_ce:,}',Estilo_med))
      story.append(FrameBreak())
      
      frame_nro_ce=Frame(80*mm,161.5*mm+ajuste_v,11*mm,5*mm,id='nro_ce',showBoundary=0,topPadding=0,leftPadding=0,bottomPadding=0,rightPadding=0)
      frames_pag1.append(frame_nro_ce)
      story.append(Paragraph(str(ctas_ce),Estilo_med))
      story.append(FrameBreak())
      
      frame_rcd_ce=Frame(123*mm,161.5*mm+ajuste_v,22.5*mm,5*mm,id='rcd_ce',showBoundary=0,topPadding=0,leftPadding=0,bottomPadding=0,rightPadding=0)
      frames_pag1.append(frame_rcd_ce)
      story.append(Paragraph(f'${rcdo_ce:,}'[:11],Estilo_med))
      story.append(FrameBreak())
      
      frame_sdo_ce=Frame(173*mm,161.5*mm+ajuste_v,30*mm,5*mm,id='sdo_ce',showBoundary=0,topPadding=0,leftPadding=0,bottomPadding=0,rightPadding=0)
      frames_pag1.append(frame_sdo_ce)
      story.append(Paragraph(f'${saldo_ce:,}',Estilo_med))
      story.append(FrameBreak())
      
      frame_vr_co=Frame(25.6*mm,150*mm+ajuste_v,43*mm,5*mm,id='vr_co',showBoundary=0,topPadding=0,leftPadding=0,bottomPadding=0,rightPadding=0)
      frames_pag1.append(frame_vr_co)
      story.append(Paragraph(f'${vr_co:,}',Estilo_med))
      story.append(FrameBreak())
      
      frame_rcd_co=Frame(94.5*mm,150*mm+ajuste_v,30*mm,5*mm,id='rcd_co',showBoundary=0,topPadding=0,leftPadding=0,bottomPadding=0,rightPadding=0)
      frames_pag1.append(frame_rcd_co)
      story.append(Paragraph(f'${rcdo_co:,}',Estilo_med))
      story.append(FrameBreak())
      
      frame_sdo_co=Frame(147*mm,150*mm+ajuste_v,51*mm,5*mm,id='sdo_co',showBoundary=0,topPadding=0,leftPadding=0,bottomPadding=0,rightPadding=0)
      frames_pag1.append(frame_sdo_co)
      story.append(Paragraph(f'${saldo_co:,}',Estilo_med))
      story.append(FrameBreak())
      
      frame_rcdo_total=Frame(33.6*mm,139.5*mm+ajuste_v,35.5*mm,5*mm,id='rcd_total',showBoundary=0,topPadding=0,leftPadding=0,bottomPadding=0,rightPadding=0)
      frames_pag1.append(frame_rcdo_total)
      story.append(Paragraph(f'${rcdo_total:,}',Estilo_med))
      story.append(FrameBreak())
      
      frame_sdo_total=Frame(100*mm,139.5*mm+ajuste_v,34.7*mm,5*mm,id='sdo_total',showBoundary=0,topPadding=0,leftPadding=0,bottomPadding=0,rightPadding=0)
      frames_pag1.append(frame_sdo_total)
      story.append(Paragraph(f'${saldo_total:,}',Estilo_med))
      story.append(FrameBreak())
      
      frame_mora=Frame(166*mm,139.5*mm+ajuste_v,34.7*mm,5*mm,id='mora',showBoundary=0,topPadding=0,leftPadding=0,bottomPadding=0,rightPadding=0)
      frames_pag1.append(frame_mora)
      story.append(Paragraph(f'${saldo_mora:,}',Estilo_med))
      story.append(FrameBreak())
      
      frame_ctas_venc=Frame(36.5*mm,128.8*mm+ajuste_v,32.5*mm,5*mm,id='ctas_venc',showBoundary=0,topPadding=0,leftPadding=0,bottomPadding=0,rightPadding=0)
      frames_pag1.append(frame_ctas_venc)
      story.append(Paragraph(str(ctas_vencidas),Estilo_med))
      story.append(FrameBreak())
      
      frame_sdo_vencido=Frame(89.6*mm,128.8*mm+ajuste_v,34.7*mm,5*mm,id='sdo_vencido',showBoundary=0,topPadding=0,leftPadding=0,bottomPadding=0,rightPadding=0)
      frames_pag1.append(frame_sdo_vencido)
      if saldo_vencido==None: saldo_vencido=0
      story.append(Paragraph(f'${saldo_vencido:,}',Estilo_med))
      story.append(FrameBreak())
      
      frame_dias_mora=Frame(153*mm,128.8*mm+ajuste_v,34.7*mm,5*mm,id='dias_mora',showBoundary=0,topPadding=0,leftPadding=0,bottomPadding=0,rightPadding=0)
      frames_pag1.append(frame_dias_mora)
      story.append(Paragraph(str(dias_mora),Estilo_med))
      story.append(FrameBreak())
      
      story.append(Paragraph('<strong>Cuotas Pendientes de Pago</strong>',Estilo_med_centrado))
      story.append(Spacer(0,10))
      frame_ctas_pendientes=Frame(11.8*mm,21*mm+ajuste_v,186*mm,98*mm,id='det_ctas_pend',showBoundary=0,topPadding=0,leftPadding=0,bottomPadding=0,rightPadding=0)
      frames_pag1.append(frame_ctas_pendientes)
      
      
      
      estructura_tabla=[]
      estilo_encabezado_tabla=ParagraphStyle('encabezado tabla',alignment=1,fontSize=10,fontName='centuryg')
      encabezados_tabla=(Paragraph('<b>Fecha</b>',estilo_encabezado_tabla),
                            Paragraph('<b>Nº Cta</b>',estilo_encabezado_tabla),
                            Paragraph('<b>Dias Mora</b>',estilo_encabezado_tabla),
                            Paragraph('<b>Cuota</b>',estilo_encabezado_tabla),
                            Paragraph('<b>Interes Mora</b>',estilo_encabezado_tabla),
                            Paragraph('<b>Total</b>',estilo_encabezado_tabla))
      estructura_tabla.append(encabezados_tabla)
      contenido=cuotas_pendientes
      
      estilo_detalle_tabla=ParagraphStyle('encabezado tabla',alignment=1,fontSize=8,fontName='centuryg')
      total_cta=0
      total_mora=0
      total_pendt=0
      for fila in contenido:
        fila_format=[]
        fecha=fila.fecha
        fila_format.append(Paragraph(str(fecha)[:11],estilo_detalle_tabla))
        ncta=fila.idcta[:4]
        fila_format.append(Paragraph(str(ncta),estilo_detalle_tabla))
        diasmora=fila.diasmora
        fila_format.append(Paragraph(str(diasmora),estilo_detalle_tabla))
        cuota=fila.saldocuota
        total_cta+=fila.saldocuota
        fila_format.append(Paragraph(f'${cuota:,}',estilo_detalle_tabla))
        intmora=fila.saldomora
        total_mora+=fila.saldomora
        fila_format.append(Paragraph(f'${intmora:,}',estilo_detalle_tabla))
        total=cuota+intmora
        total_pendt+=total
        fila_format.append(Paragraph(f'${total:,}',estilo_detalle_tabla))
        estructura_tabla.append(fila_format)
        
      totales=[Paragraph('<b>TOTAL</b>',estilo_detalle_tabla),
               Paragraph('',estilo_detalle_tabla),Paragraph('',estilo_detalle_tabla)
               ]
      totales.append(Paragraph(f'<b>{total_cta:,}</b>',estilo_detalle_tabla))
      totales.append(Paragraph(f'<b>{total_mora:,}</b>',estilo_detalle_tabla))
      totales.append(Paragraph(f'<b>{total_pendt:,}</b>',estilo_detalle_tabla))
      
      estructura_tabla.append(totales)
      
      tabla=Table(estructura_tabla)
      tabla.setStyle([('ALIGNMENT',(0,0),(-1,-1),'CENTER'),
                          ('GRID',(0,0),(-1,-1),1,'#C9C9C9'),
                          ('VALIGN',(0,0),(-1,-1),'MIDDLE'),
                          ('SPAN',(0,-1),(2,-1))])
      story.append(tabla)
      story.append(Spacer(0,10))
      
      
      """ story.append(PageBreak())
      
      frame_2=Frame(0,0,210*mm,297*mm,id='pagina2',leftPadding=0,rightPadding=0)
      frames_pag1.append(frame_2) """
      
      
      
      pagina2=Image(base,width=210*mm,height=295*mm)
      page1=PageTemplate(id='pagina1',frames=frames_pag1,onPage=partial(header, content=pagina2))
      doc=BaseDocTemplate(ruta,pageTemplates=(page1))
      
      doc.build(story)

    def resumen_pagos(self,ruta,fecha,adj,nombre,proyecto,direccion,inmueble,telefono,
                            valor_contrato,
                            vr_ci,rcdo_ci,saldo_ci,
                            vr_fn,rcdo_fn,saldo_fn,
                            ctas_fn,vr_cta_fn,tasa,
                            vr_ce,ctas_ce,rcdo_ce,saldo_ce,
                            vr_co,rcdo_co,saldo_co,
                            rcdo_total,saldo_total,saldo_mora,
                            ctas_vencidas,saldo_vencido,dias_mora,
                            cuotas_pendientes,cuotas_pagadas):
          image_base={
            'Vegas de Venecia':'./resources/base_ec_Vegas.png',
            'Tesoro Escondido':'./resources/base_ec_tesoro.png',
            'Sandville Beach':'./resources/base_ec_sandville.png',
            'Perla del Mar':'./resources/base_ec_sandville.png',
            'Sandville del Sol':'./resources/base_ec_sandville.png',
            'Sotavento':'./resources/base_ec_sotavento.png',
            'Carmelo Reservado': './resources/Carmelo Reservado/membrete.png',
            'Alttum Collection':''
          }
          
          formato='./resources/Formato-de-estado-de-cuenta-lotes.png'
          base=image_base[proyecto]
          story=[]
          frames_pag1=[]
        # Imagen base del doc
          frame_base=Frame(0,0,210*mm,269*mm,id='pagina1',leftPadding=0,rightPadding=0)
          frames_pag1.append(frame_base)
          pagina1=Image(formato,width=210*mm,height=257*mm)
          story.append(pagina1)
          story.append(FrameBreak())
          
          Estilo_peq=ParagraphStyle('titulares',fontName='centuryg',fontSize=8)
          Estilo_med=ParagraphStyle('titulares',fontName='centuryg',fontSize=10)
          Estilo_med_centrado=ParagraphStyle('titulares',alignment=1,fontName='centuryg',fontSize=10)
          
          ajuste_v=10*mm
          
          frame_fecha=Frame(76.5*mm,261.6*mm+ajuste_v,60*mm,5*mm,id='fecha',showBoundary=0,topPadding=0,leftPadding=0,bottomPadding=0,rightPadding=0)
          frames_pag1.append(frame_fecha)
          story.append(Paragraph('<strong>Fecha y Hora: </strong>'+fecha,Estilo_peq))
          story.append(FrameBreak())
          
          frame_adj=Frame(20.7*mm,233*mm+ajuste_v,40*mm,5*mm,id='adj',showBoundary=0,topPadding=0,leftPadding=0,bottomPadding=0,rightPadding=0)
          frames_pag1.append(frame_adj)
          story.append(Paragraph(adj,Estilo_med))
          story.append(FrameBreak())
          
          frame_nombre=Frame(73*mm,233*mm+ajuste_v,60*mm,5*mm,id='nombre',showBoundary=0,topPadding=0,leftPadding=0,bottomPadding=0,rightPadding=0)
          frames_pag1.append(frame_nombre)
          story.append(Paragraph(nombre[:24],Estilo_med))
          story.append(FrameBreak())
          
          frame_proyecto=Frame(147*mm,233*mm+ajuste_v,53.4*mm,5*mm,id='proyecto',showBoundary=0,topPadding=0,leftPadding=0,bottomPadding=0,rightPadding=0)
          frames_pag1.append(frame_proyecto)
          story.append(Paragraph(proyecto,Estilo_med))
          story.append(FrameBreak())
          
          frame_direccion=Frame(29.2*mm,225*mm+ajuste_v,71*mm,5*mm,id='direccion',showBoundary=0,topPadding=0,leftPadding=0,bottomPadding=0,rightPadding=0)
          frames_pag1.append(frame_direccion)
          story.append(Paragraph(direccion[:36],Estilo_peq))
          story.append(FrameBreak())
          
          frame_Inmueble=Frame(114*mm,225*mm+ajuste_v,39*mm,5*mm,id='inmueble',showBoundary=0,topPadding=0,leftPadding=0,bottomPadding=0,rightPadding=0)
          frames_pag1.append(frame_Inmueble)
          story.append(Paragraph(inmueble,Estilo_med))
          story.append(FrameBreak())
          
          frame_telefono=Frame(166.5*mm,224*mm+ajuste_v,33*mm,5*mm,id='telefono',showBoundary=0,topPadding=0,leftPadding=0,bottomPadding=0,rightPadding=0)
          frames_pag1.append(frame_telefono)
          story.append(Paragraph(telefono[:20],Estilo_peq))
          story.append(FrameBreak())
          
          frame_valor=Frame(40*mm,205.5*mm+ajuste_v,150*mm,5*mm,id='valor',showBoundary=0,topPadding=0,leftPadding=0,bottomPadding=0,rightPadding=0)
          frames_pag1.append(frame_valor)
          story.append(Paragraph(f'${valor_contrato:,}',Estilo_med))
          story.append(FrameBreak())
          
          frame_ci=Frame(37.7*mm,195*mm+ajuste_v,31*mm,5*mm,id='valor_ci',showBoundary=0,topPadding=0,leftPadding=0,bottomPadding=0,rightPadding=0)
          frames_pag1.append(frame_ci)
          story.append(Paragraph(f'${vr_ci:,}',Estilo_med))
          story.append(FrameBreak())
          
          frame_rcd_ci=Frame(97.2*mm,195*mm+ajuste_v,31*mm,5*mm,id='rcd_ci',showBoundary=0,topPadding=0,leftPadding=0,bottomPadding=0,rightPadding=0)
          frames_pag1.append(frame_rcd_ci)
          story.append(Paragraph(f'${rcdo_ci:,}',Estilo_med))
          story.append(FrameBreak())
          
          frame_sdo_ci=Frame(148*mm,195*mm+ajuste_v,51*mm,5*mm,id='sdo_ci',showBoundary=0,topPadding=0,leftPadding=0,bottomPadding=0,rightPadding=0)
          frames_pag1.append(frame_sdo_ci)
          story.append(Paragraph(f'${saldo_ci:,}',Estilo_med))
          story.append(FrameBreak())
          
          frame_fn=Frame(37.7*mm,184*mm+ajuste_v,31*mm,5*mm,id='valor_fn',showBoundary=0,topPadding=0,leftPadding=0,bottomPadding=0,rightPadding=0)
          frames_pag1.append(frame_fn)
          story.append(Paragraph(f'${vr_fn:,}',Estilo_med))
          story.append(FrameBreak())
          
          frame_rcd_fn=Frame(107*mm,184*mm+ajuste_v,26*mm,5*mm,id='rcd_fn',showBoundary=0,topPadding=0,leftPadding=0,bottomPadding=0,rightPadding=0)
          frames_pag1.append(frame_rcd_fn)
          story.append(Paragraph(f'${rcdo_fn:,}',Estilo_med))
          story.append(FrameBreak())
          
          frame_sdo_fn=Frame(169*mm,184*mm+ajuste_v,31*mm,5*mm,id='sdo_fn',showBoundary=0,topPadding=0,leftPadding=0,bottomPadding=0,rightPadding=0)
          frames_pag1.append(frame_sdo_fn)
          story.append(Paragraph(f'${saldo_fn:,}',Estilo_med))
          story.append(FrameBreak())
          
          frame_nro_fn=Frame(36*mm,173*mm+ajuste_v,31*mm,5*mm,id='nro_fn',showBoundary=0,topPadding=0,leftPadding=0,bottomPadding=0,rightPadding=0)
          frames_pag1.append(frame_nro_fn)
          story.append(Paragraph(str(ctas_fn),Estilo_med))
          story.append(FrameBreak())
          
          frame_vrcta_fn=Frame(99*mm,173*mm+ajuste_v,31*mm,5*mm,id='vrcta_fn',showBoundary=0,topPadding=0,leftPadding=0,bottomPadding=0,rightPadding=0)
          frames_pag1.append(frame_vrcta_fn)
          story.append(Paragraph(f'${vr_cta_fn:,}',Estilo_med))
          story.append(FrameBreak())
          
          frame_tasa_fn=Frame(164*mm,173*mm+ajuste_v,31*mm,5*mm,id='tasa_fn',showBoundary=0,topPadding=0,leftPadding=0,bottomPadding=0,rightPadding=0)
          frames_pag1.append(frame_tasa_fn)
          story.append(Paragraph(f'{tasa}% M.V',Estilo_med))
          story.append(FrameBreak())
          
          frame_vr_ce=Frame(34*mm,161.5*mm+ajuste_v,31*mm,5*mm,id='vr_ce',showBoundary=0,topPadding=0,leftPadding=0,bottomPadding=0,rightPadding=0)
          frames_pag1.append(frame_vr_ce)
          story.append(Paragraph(f'${vr_ce:,}',Estilo_med))
          story.append(FrameBreak())
          
          frame_nro_ce=Frame(80*mm,161.5*mm+ajuste_v,11*mm,5*mm,id='nro_ce',showBoundary=0,topPadding=0,leftPadding=0,bottomPadding=0,rightPadding=0)
          frames_pag1.append(frame_nro_ce)
          story.append(Paragraph(str(ctas_ce),Estilo_med))
          story.append(FrameBreak())
          
          frame_rcd_ce=Frame(123*mm,161.5*mm+ajuste_v,22.5*mm,5*mm,id='rcd_ce',showBoundary=0,topPadding=0,leftPadding=0,bottomPadding=0,rightPadding=0)
          frames_pag1.append(frame_rcd_ce)
          story.append(Paragraph(f'${rcdo_ce:,}'[:11],Estilo_med))
          story.append(FrameBreak())
          
          frame_sdo_ce=Frame(173*mm,161.5*mm+ajuste_v,25*mm,5*mm,id='sdo_ce',showBoundary=0,topPadding=0,leftPadding=0,bottomPadding=0,rightPadding=0)
          frames_pag1.append(frame_sdo_ce)
          story.append(Paragraph(f'${saldo_ce:,}',Estilo_med))
          story.append(FrameBreak())
          
          frame_vr_co=Frame(25.6*mm,150*mm+ajuste_v,43*mm,5*mm,id='vr_co',showBoundary=0,topPadding=0,leftPadding=0,bottomPadding=0,rightPadding=0)
          frames_pag1.append(frame_vr_co)
          story.append(Paragraph(f'${vr_co:,}',Estilo_med))
          story.append(FrameBreak())
          
          frame_rcd_co=Frame(94.5*mm,150*mm+ajuste_v,30*mm,5*mm,id='rcd_co',showBoundary=0,topPadding=0,leftPadding=0,bottomPadding=0,rightPadding=0)
          frames_pag1.append(frame_rcd_co)
          story.append(Paragraph(f'${rcdo_co:,}',Estilo_med))
          story.append(FrameBreak())
          
          frame_sdo_co=Frame(147*mm,150*mm+ajuste_v,51*mm,5*mm,id='sdo_co',showBoundary=0,topPadding=0,leftPadding=0,bottomPadding=0,rightPadding=0)
          frames_pag1.append(frame_sdo_co)
          story.append(Paragraph(f'${saldo_co:,}',Estilo_med))
          story.append(FrameBreak())
          
          frame_rcdo_total=Frame(33.6*mm,139.5*mm+ajuste_v,35.5*mm,5*mm,id='rcd_total',showBoundary=0,topPadding=0,leftPadding=0,bottomPadding=0,rightPadding=0)
          frames_pag1.append(frame_rcdo_total)
          story.append(Paragraph(f'${rcdo_total:,}',Estilo_med))
          story.append(FrameBreak())
          
          frame_sdo_total=Frame(100*mm,139.5*mm+ajuste_v,34.7*mm,5*mm,id='sdo_total',showBoundary=0,topPadding=0,leftPadding=0,bottomPadding=0,rightPadding=0)
          frames_pag1.append(frame_sdo_total)
          story.append(Paragraph(f'${saldo_total:,}',Estilo_med))
          story.append(FrameBreak())
          
          frame_mora=Frame(166*mm,139.5*mm+ajuste_v,34.7*mm,5*mm,id='mora',showBoundary=0,topPadding=0,leftPadding=0,bottomPadding=0,rightPadding=0)
          frames_pag1.append(frame_mora)
          story.append(Paragraph(f'${saldo_mora:,}',Estilo_med))
          story.append(FrameBreak())
          
          frame_ctas_venc=Frame(36.5*mm,128.8*mm+ajuste_v,32.5*mm,5*mm,id='ctas_venc',showBoundary=0,topPadding=0,leftPadding=0,bottomPadding=0,rightPadding=0)
          frames_pag1.append(frame_ctas_venc)
          story.append(Paragraph(str(ctas_vencidas),Estilo_med))
          story.append(FrameBreak())
          
          frame_sdo_vencido=Frame(89.6*mm,128.8*mm+ajuste_v,34.7*mm,5*mm,id='sdo_vencido',showBoundary=0,topPadding=0,leftPadding=0,bottomPadding=0,rightPadding=0)
          frames_pag1.append(frame_sdo_vencido)
          if saldo_vencido==None: saldo_vencido=0
          story.append(Paragraph(f'${saldo_vencido:,}',Estilo_med))
          story.append(FrameBreak())
          
          frame_dias_mora=Frame(153*mm,128.8*mm+ajuste_v,34.7*mm,5*mm,id='dias_mora',showBoundary=0,topPadding=0,leftPadding=0,bottomPadding=0,rightPadding=0)
          frames_pag1.append(frame_dias_mora)
          story.append(Paragraph(str(dias_mora),Estilo_med))
          story.append(FrameBreak())
          
          story.append(Paragraph('<strong>Cuotas Pagadas</strong>',Estilo_med_centrado))
          story.append(Spacer(0,10))
          frame_ctas_pendientes=Frame(11.8*mm,21*mm+ajuste_v,186*mm,98*mm,id='det_ctas_pend',showBoundary=0,topPadding=0,leftPadding=0,bottomPadding=0,rightPadding=0)
          frames_pag1.append(frame_ctas_pendientes)
          
          estructura_tabla=[]
          estilo_encabezado_tabla=ParagraphStyle('encabezado tabla',alignment=1,fontSize=10,fontName='centuryg')
          encabezados_tabla=(Paragraph('<b>Fecha</b>',estilo_encabezado_tabla),
                                Paragraph('<b>Nº Cta</b>',estilo_encabezado_tabla),
                                Paragraph('<b>Recibo</b>',estilo_encabezado_tabla),
                                Paragraph('<b>Cuota</b>',estilo_encabezado_tabla),
                                Paragraph('<b>Interes Mora</b>',estilo_encabezado_tabla),
                                Paragraph('<b>Total</b>',estilo_encabezado_tabla))
          estructura_tabla.append(encabezados_tabla)
          contenido=cuotas_pagadas
          
          estilo_detalle_tabla=ParagraphStyle('encabezado tabla',alignment=1,fontSize=8,fontName='centuryg')
          i=0
          for fila in contenido:
            fila_format=[]
            fecha=fila.fecha
            fila_format.append(Paragraph(str(fecha)[:11],estilo_detalle_tabla))
            ncta=fila.idcta[:4]
            if ncta[3]=='A': ncta=ncta[:3]
            fila_format.append(Paragraph(str(ncta),estilo_detalle_tabla))
            recibo=fila.recibo
            fila_format.append(Paragraph(str(recibo),estilo_detalle_tabla))
            cuota=fila.capital+fila.interescte
            fila_format.append(Paragraph(f'${cuota:,}',estilo_detalle_tabla))
            intmora=fila.interesmora
            fila_format.append(Paragraph(f'{intmora:,}',estilo_detalle_tabla))
            total=cuota+intmora
            fila_format.append(Paragraph(f'{total:,}',estilo_detalle_tabla))
            estructura_tabla.append(fila_format)
            if i==51: break
            i+=1
          
          tabla=Table(estructura_tabla)
          tabla.setStyle([('ALIGNMENT',(0,0),(-1,-1),'CENTER'),
                              ('GRID',(0,0),(-1,-1),1,'#C9C9C9'),
                              ('VALIGN',(0,0),(-1,-1),'MIDDLE'),
                              ])
          story.append(tabla)
          
          frames_pag2=[]
          frame_2=Frame(11.8*mm,12*mm,186*mm,254.5*mm,id='frame_page2',showBoundary=0,leftPadding=0,rightPadding=0)
          frames_pag2.append(frame_2)
          
          estructura_tabla=[]
          contenido=cuotas_pagadas
          estilo_detalle_tabla=ParagraphStyle('encabezado tabla',alignment=1,fontSize=8,fontName='centuryg')
          
          i=0
          for fila in contenido:
            if i>51:
              fila_format=[]
              fecha=fila.fecha
              fila_format.append(Paragraph(str(fecha)[:11],estilo_detalle_tabla))
              ncta=fila.idcta[:4]
              if ncta[3]=='A': ncta=ncta[:3]
              fila_format.append(Paragraph(str(ncta),estilo_detalle_tabla))
              recibo=fila.recibo
              fila_format.append(Paragraph(str(recibo),estilo_detalle_tabla))
              cuota=fila.capital+fila.interescte
              fila_format.append(Paragraph(f'${cuota:,}',estilo_detalle_tabla))
              intmora=fila.interesmora
              fila_format.append(Paragraph(f'{intmora:,}',estilo_detalle_tabla))
              total=cuota+intmora
              fila_format.append(Paragraph(f'{total:,}',estilo_detalle_tabla))
              estructura_tabla.append(fila_format)
            i+=1
            
          if len(contenido)>52:
            story.append(NextPageTemplate('pagina2'))
            story.append(PageBreak())
            
            tabla2=Table(estructura_tabla,colWidths=[31*mm]*6)
            tabla2.setStyle([('ALIGNMENT',(0,0),(-1,-1),'CENTER'),
                                ('GRID',(0,0),(-1,-1),1,'#C9C9C9'),
                                ('VALIGN',(0,0),(-1,-1),'MIDDLE'),
                                ])
            story.append(tabla2)
          
          content_base=Image(base,width=210*mm,height=295*mm)
          page1=PageTemplate(id='pagina1',frames=frames_pag1,onPage=partial(header, content=content_base))
          page2=PageTemplate(id='pagina2',frames=frames_pag2,onPage=partial(header, content=content_base))
          doc=BaseDocTemplate(ruta,pageTemplates=[page1,page2])
          
          doc.build(story)

    def portada_adj(self,ruta,proyecto,adj,fecha,inmueble,tipodoc,nrocontrato,
                    titular1,titular2,titular3,titular4,valor,ci,saldo,formapago,
                    planpagos,ctafn,ctace,escala:list):
      logos={
        'Tesoro Escondido':'./resources/Logos/logo-Tesoro-Escondido.png',
        'Vegas de Venecia':'./resources/Logos/logo-vegas-de-venecia.png',
        'Sandville Beach':'./resources/Logos/sandville beach.png',
        'Perla del Mar':'./resources/Logos/Perla del Mar.png',
        'Sandville del Sol':'./resources/Logos/Perla del Mar.png',
        'Sotavento':'./resources/Logos/logo-sotavento.png',
        'Carmelo Reservado': './resources/Carmelo Reservado/logo.png',
        'Casas de Verano':'./resources/Casas de Verano/logo.png',
        'Alttum Collection':''
      }
      story=[]
      frames=[]
      
      frame_logo=Frame(23*mm,245*mm,37*mm,31*mm,id='pagina1',rightPadding=0,topPadding=0,leftPadding=0,bottomPadding=0)
      frames.append(frame_logo)
      logo=Image(logos[proyecto],width=36*mm,height=25*mm)
      story.append(logo)
      story.append(FrameBreak())
      
      Estilo_peq=ParagraphStyle('titulares',fontName='centuryg',fontSize=8)
      Estilo_med=ParagraphStyle('titulares',fontName='centuryg',fontSize=10)
      Estilo_xl=ParagraphStyle('titulares',fontName='centuryg',fontSize=16,alignment=1)
      Estilo_portada=ParagraphStyle('titulares',fontName='centuryg',fontSize=24,alignment=1)
      Estilo_portada.leading= 20
      Estilo_med_centrado=ParagraphStyle('titulares',alignment=1,fontName='centuryg',fontSize=10)
      
      ajuste_v=0*mm
      
      frame_adj=Frame(177*mm,254.5*mm,21*mm,6*mm,id='adj',showBoundary=0,topPadding=0,leftPadding=0,bottomPadding=0,rightPadding=0)
      frames.append(frame_adj)
      story.append(Paragraph(f'<strong>{adj}</strong>',Estilo_xl))
      story.append(FrameBreak())
      
      frame_fecha=Frame(33*mm,231*mm,35.2*mm,5*mm,id='fecha',showBoundary=0,topPadding=0,leftPadding=0,bottomPadding=0,rightPadding=0)
      frames.append(frame_fecha)
      story.append(Paragraph(fecha,Estilo_peq))
      story.append(FrameBreak())
      
      frame_inmueble=Frame(88.2*mm,231*mm,25*mm,5*mm,id='inmueble',showBoundary=0,topPadding=0,leftPadding=0,bottomPadding=0,rightPadding=0)
      frames.append(frame_inmueble)
      story.append(Paragraph(inmueble,Estilo_peq))
      story.append(FrameBreak())
      
      frame_tipodoc=Frame(131*mm,231*mm,30*mm,5*mm,id='tipodoc',showBoundary=0,topPadding=0,leftPadding=0,bottomPadding=0,rightPadding=0)
      frames.append(frame_tipodoc)
      if tipodoc==None: tipodoc=''
      story.append(Paragraph(tipodoc.split(' ')[0],Estilo_peq))
      story.append(FrameBreak())
      
      frame_nrocontrato=Frame(176*mm,231*mm,18.5*mm,5*mm,id='nrocontrato',showBoundary=0,topPadding=0,leftPadding=0,bottomPadding=0,rightPadding=0)
      frames.append(frame_nrocontrato)
      if nrocontrato==None: nrocontrato=''
      story.append(Paragraph(nrocontrato,Estilo_peq))
      story.append(FrameBreak())
      
      frame_titular1=Frame(38*mm,216*mm,35*mm,10*mm,id='titular1',showBoundary=0,topPadding=0,leftPadding=0,bottomPadding=0,rightPadding=0)
      frames.append(frame_titular1)
      if titular1==None: titular1=''
      story.append(Paragraph(titular1[:25],Estilo_peq))
      story.append(FrameBreak())
      
      frame_titular2=Frame(86.5*mm,216*mm,26.5*mm,10*mm,id='titular2',showBoundary=0,topPadding=0,leftPadding=0,bottomPadding=0,rightPadding=0)
      frames.append(frame_titular2)
      if titular2==None: titular2=''
      story.append(Paragraph(titular2[:20],Estilo_peq))
      story.append(FrameBreak())
      
      frame_titular3=Frame(129.4*mm,216*mm,25*mm,10*mm,id='titular3',showBoundary=0,topPadding=0,leftPadding=0,bottomPadding=0,rightPadding=0)
      frames.append(frame_titular3)
      if titular3==None: titular3=''
      story.append(Paragraph(titular3[:20],Estilo_peq))
      story.append(FrameBreak())
      
      frame_titular4=Frame(170*mm,216*mm,27*mm,10*mm,id='titular4',showBoundary=0,topPadding=0,leftPadding=0,bottomPadding=0,rightPadding=0)
      frames.append(frame_titular4)
      if titular4==None: titular4=''
      story.append(Paragraph(titular4[:22],Estilo_peq))
      story.append(FrameBreak())
      
      frame_valor=Frame(43.5*mm,210.5*mm,26*mm,6*mm,id='valor',showBoundary=0,topPadding=0,leftPadding=0,bottomPadding=0,rightPadding=0)
      frames.append(frame_valor)
      story.append(Paragraph(f'{valor:,}',Estilo_peq))
      story.append(FrameBreak())
      
      frame_ci=Frame(93.6*mm,210.5*mm,20.5*mm,6*mm,id='ci',showBoundary=0,topPadding=0,leftPadding=0,bottomPadding=0,rightPadding=0)
      frames.append(frame_ci)
      story.append(Paragraph(f'{ci:,}',Estilo_peq))
      story.append(FrameBreak())
      
      frame_saldo=Frame(124.9*mm,210.5*mm,28*mm,6*mm,id='saldo',showBoundary=0,topPadding=0,leftPadding=0,bottomPadding=0,rightPadding=0)
      frames.append(frame_saldo)
      story.append(Paragraph(f'{saldo:,}',Estilo_peq))
      story.append(FrameBreak())
      
      frame_formapago=Frame(175.6*mm,210.5*mm,21*mm,6*mm,id='formapago',showBoundary=0,topPadding=0,leftPadding=0,bottomPadding=0,rightPadding=0)
      frames.append(frame_formapago)
      if formapago==None: formapago=''
      story.append(Paragraph(formapago[:15],Estilo_peq))
      story.append(FrameBreak())
      
      frame_planpagos=Frame(47*mm,200.5*mm,22*mm,6*mm,id='planpagos',showBoundary=0,topPadding=0,leftPadding=0,bottomPadding=0,rightPadding=0)
      frames.append(frame_planpagos)
      if planpagos==None: planpagos=''
      story.append(Paragraph(planpagos,Estilo_peq))
      story.append(FrameBreak())
      
      frame_ctafn=Frame(88*mm,200.5*mm,25.5*mm,6*mm,id='ctafn',showBoundary=0,topPadding=0,leftPadding=0,bottomPadding=0,rightPadding=0)
      frames.append(frame_ctafn)
      story.append(Paragraph(f'{ctafn:,}',Estilo_peq))
      story.append(FrameBreak())
      
      frame_ctace=Frame(131*mm,200.5*mm,40*mm,6*mm,id='ctace',showBoundary=0,topPadding=0,leftPadding=0,bottomPadding=0,rightPadding=0)
      frames.append(frame_ctace)
      story.append(Paragraph(f'{ctace:,}',Estilo_peq))
      story.append(FrameBreak())
      
      frame_escala=Frame(13.6*mm,125*mm,185*mm,65*mm,id='escala',showBoundary=0,topPadding=0,leftPadding=0,bottomPadding=0,rightPadding=0)
      frames.append(frame_escala)
      estructura_tabla=[]
      estilo_encabezado_tabla=ParagraphStyle('encabezado tabla',alignment=1,fontSize=10,fontName='centuryg')
      encabezados_tabla=(Paragraph('<b>Cargo</b>',estilo_encabezado_tabla),
                            Paragraph('<b>Gestor</b>',estilo_encabezado_tabla),
                            Paragraph('<b>% Comision</b>',estilo_encabezado_tabla)
                            )
      estructura_tabla.append(encabezados_tabla)
      contenido=escala
      
      estilo_detalle_tabla=ParagraphStyle('encabezado tabla',alignment=1,fontSize=8,fontName='centuryg')
      estilo_detalle_tabla=ParagraphStyle('encabezado tabla',alignment=1,fontSize=8,fontName='centuryg')
      i=0
      for fila in contenido:
        fila_format=[]
        cargo=fila.cargo
        fila_format.append(Paragraph(str(cargo),estilo_detalle_tabla))
        gestor=fila.gestor
        fila_format.append(Paragraph(str(gestor).upper(),estilo_detalle_tabla))
        comision=fila.comision
        fila_format.append(Paragraph(f'{comision}%',estilo_detalle_tabla))
        estructura_tabla.append(fila_format)
        i+=1
        if i==8: break
        
      tabla=Table(estructura_tabla)
      tabla.setStyle([('ALIGNMENT',(0,0),(-1,-1),'CENTER'),
                          ('GRID',(0,0),(-1,-1),1,'#C9C9C9'),
                          ('VALIGN',(0,0),(-1,-1),'MIDDLE')])
      story.append(tabla)
      story.append(FrameBreak())
      
      frame_logo2=Frame(23.3*mm,43*mm,40.8*mm,39.5*mm,id='logo2',showBoundary=0,topPadding=0,leftPadding=0,bottomPadding=0,rightPadding=0)
      frames.append(frame_logo2)
      logo2=Image(logos[proyecto],width=36*mm,height=25*mm)
      story.append(logo2)
      story.append(FrameBreak())
      
      frame_nombre2=Frame(69*mm,69*mm,117.5*mm,20*mm,id='nombre2',showBoundary=0,topPadding=0,leftPadding=0,bottomPadding=0,rightPadding=0)
      frames.append(frame_nombre2)
      if titular1==None: titular1=''
      story.append(Paragraph(titular1[:35],Estilo_portada))
      story.append(FrameBreak())
      
      frame_inmueble2=Frame(69*mm,53*mm,117.5*mm,14*mm,id='inmueble2',showBoundary=0,topPadding=0,leftPadding=0,bottomPadding=0,rightPadding=0)
      frames.append(frame_inmueble2)
      story.append(Paragraph(inmueble,Estilo_portada))
      story.append(FrameBreak())
      
      base=Image('./resources/portada_adj.png',width=210*mm,height=295*mm)
      page=PageTemplate(id='pagina1',frames=frames,onPage=partial(header, content=base))
      doc=BaseDocTemplate(ruta,pageTemplates=(page))
      
      doc.build(story)

    def gtt(self,ruta,proyecto,desde,hasta,contenido,crea,aprueba):
      logos={
        'Tesoro Escondido':'./resources/Logos/logo-Tesoro-Escondido.png',
        'Vegas de Venecia':'./resources/Logos/logo-vegas-de-venecia.png',
        'Sandville Beach':'./resources/Logos/sandville beach.png',
        'Perla del Mar':'./resources/Logos/Perla del Mar.png',
        'Sandville del Sol':'./resources/Logos/Perla del Mar.png',
        'Sotavento':'./resources/Logos/logo-sotavento.png',
        'Carmelo Reservado': './resources/Carmelo Reservado/logo.png',
        'Alttum Collection':'',
        'Fractal':'/static_files/img/fractal450x.png'
      }
      story=[]
      frames=[]
      
      frame_logo=Frame(23*mm,245*mm,37*mm,31*mm,id='logo',rightPadding=0,topPadding=0,leftPadding=0,bottomPadding=0)
      frames.append(frame_logo)
      logo=Image(logos[proyecto],width=36*mm,height=25*mm)
      story.append(logo)
      story.append(FrameBreak())
      
      Estilo_xl_center=ParagraphStyle('titulares',fontName='centuryg',fontSize=14,alignment=1)
      Estilo_med=ParagraphStyle('titulares',fontName='centuryg',fontSize=10,alignment=1)
      frame_titulo=Frame(70*mm,240*mm,107*mm,31*mm,id='titulo',rightPadding=0,topPadding=0,leftPadding=0,bottomPadding=0)
      content=f'GTT {proyecto.upper()}'
      frames.append(frame_titulo)
      story.append(Paragraph(f'<strong>{content}</strong>',Estilo_xl_center))
      content=f'Semana del <strong>{desde}</strong> hasta <strong>{hasta}</strong>'
      story.append(Spacer(0,10))
      story.append(Paragraph(content,Estilo_med))
      story.append(FrameBreak())
      
      frame_escala=Frame(13.6*mm,45*mm,185*mm,200*mm,id='escala',showBoundary=0,topPadding=0,leftPadding=0,bottomPadding=0,rightPadding=0)
      frames.append(frame_escala)
      estructura_tabla=[]
      estilo_encabezado_tabla=ParagraphStyle('encabezado tabla',alignment=1,fontSize=10,fontName='centuryg')
      encabezados_tabla=(Paragraph('<b>CEDULA</b>',estilo_encabezado_tabla),
                            Paragraph('<b>GESTOR</b>',estilo_encabezado_tabla),
                            Paragraph('<b>VALOR</b>',estilo_encabezado_tabla)
                            )
      estructura_tabla.append(encabezados_tabla)
      
      estilo_detalle_tabla=ParagraphStyle('encabezado tabla',alignment=1,fontSize=8,fontName='centuryg')
      i=0
      for fila in contenido:
        fila_format=[]
        id_asesor=fila.asesor.pk
        nombre_asesor=fila.asesor.nombre
        valor=fila.valor
        if valor > 0:
          fila_format.append(Paragraph(str(id_asesor),estilo_detalle_tabla))
          fila_format.append(Paragraph(str(nombre_asesor).upper(),estilo_detalle_tabla))
          fila_format.append(Paragraph(f'${valor:,}',estilo_detalle_tabla))
          estructura_tabla.append(fila_format)
        
      tabla=Table(estructura_tabla)
      tabla.setStyle([('ALIGNMENT',(0,0),(-1,-1),'CENTER'),
                          ('GRID',(0,0),(-1,-1),1,'#C9C9C9'),
                          ('VALIGN',(0,0),(-1,-1),'MIDDLE')])
      story.append(tabla)
      story.append(FrameBreak())
      
      estilo_firma=ParagraphStyle('firma',fontName='centuryg',fontSize=12,alignment=1)
      frame_nombre=Frame(24.7*mm,10*mm,67.6*mm,7*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames.append(frame_nombre)
      nombre=f'<strong>Elaboró:</strong> {crea}'.upper()
      story.append(Paragraph(nombre,estilo_firma))
      story.append(FrameBreak())
      frame_firma=Frame(24.7*mm,18*mm,67.6*mm,15*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames.append(frame_firma)
      try:
        firma=Image(f'./resources/Firmas/{crea}.png',width=40*mm,height=15*mm)
        story.append(firma)
      except:
        pass
      story.append(FrameBreak())
      
      frame_nombre=Frame(119*mm,10*mm,67.6*mm,7*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames.append(frame_nombre)
      nombre=f'<strong>Aprobó:</strong> {aprueba}'.upper()
      story.append(Paragraph(nombre,estilo_firma))
      story.append(FrameBreak())
      frame_firma=Frame(119*mm,18*mm,67.6*mm,15*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames.append(frame_firma)
      try:
        firma=Image(f'./resources/Firmas/{aprueba}.png',width=40*mm,height=15*mm)
        story.append(firma)
      except:
        pass
      story.append(FrameBreak())
      
      page=PageTemplate(id='pagina1',frames=frames,pagesize=A4)
      
      doc=BaseDocTemplate(ruta,pageTemplates=(page))
      doc.build(story)
      
    def comisiones(self,ruta,proyecto,desde,hasta,contenido,crea):
      logos={
        'Tesoro Escondido':'./resources/Logos/logo-Tesoro-Escondido.png',
        'Vegas de Venecia':'./resources/Logos/logo-vegas-de-venecia.png',
        'Sandville Beach':'./resources/Logos/sandville beach.png',
        'Perla del Mar':'./resources/Logos/Perla del Mar.png',
        'Sandville del Sol':'./resources/Logos/Perla del Mar.png',
        'Sotavento':'./resources/Logos/logo-sotavento.png',
        'Carmelo Reservado': './resources/Carmelo Reservado/logo.png',
        'Casas de Verano':'./resources/Casas de Verano/logo.png',
        'Alttum Collection':''
      }
      story=[]
      frames=[]
      
      frame_logo=Frame(23*mm,245*mm,37*mm,31*mm,id='logo',rightPadding=0,topPadding=0,leftPadding=0,bottomPadding=0)
      frames.append(frame_logo)
      logo=Image(logos[proyecto],width=36*mm,height=25*mm)
      story.append(logo)
      story.append(FrameBreak())
      
      Estilo_xl_center=ParagraphStyle('titulares',fontName='centuryg',fontSize=14,alignment=1)
      Estilo_med=ParagraphStyle('titulares',fontName='centuryg',fontSize=10,alignment=1)
      frame_titulo=Frame(70*mm,240*mm,107*mm,31*mm,id='titulo',rightPadding=0,topPadding=0,leftPadding=0,bottomPadding=0)
      content=f'COMISIONES {proyecto.upper()}'
      frames.append(frame_titulo)
      story.append(Paragraph(f'<strong>{content}</strong>',Estilo_xl_center))
      content=f'Corte del <strong>{desde}</strong> hasta <strong>{hasta}</strong>'
      story.append(Spacer(0,10))
      story.append(Paragraph(content,Estilo_med))
      story.append(FrameBreak())
      
      frame_detalle=Frame(13.6*mm,15*mm,185*mm,230*mm,id='detalle',showBoundary=0,topPadding=0,leftPadding=0,bottomPadding=0,rightPadding=0)
      frames.append(frame_detalle)
      estructura_tabla=[]
      estilo_encabezado_tabla=ParagraphStyle('encabezado tabla',alignment=1,fontSize=10,fontName='centuryg')
      encabezados_tabla=(Paragraph('<b>CEDULA</b>',estilo_encabezado_tabla),
                            Paragraph('<b>GESTOR</b>',estilo_encabezado_tabla),
                            Paragraph('<b>COMISION</b>',estilo_encabezado_tabla),
                            Paragraph('<b>PROVISION</b>',estilo_encabezado_tabla),
                            Paragraph('<b>NETO</b>',estilo_encabezado_tabla)
                            )
      estructura_tabla.append(encabezados_tabla)
      
      estilo_detalle_tabla=ParagraphStyle('encabezado tabla',alignment=1,fontSize=8,fontName='centuryg')
      i=0
      for fila in contenido:
        fila_format=[]
        id_asesor=fila.idgestor
        nombre_asesor=fila.nombre
        valor=fila.comision
        provision=fila.provision
        neto=fila.pagoneto
        fila_format.append(Paragraph(str(id_asesor),estilo_detalle_tabla))
        fila_format.append(Paragraph(str(nombre_asesor).upper(),estilo_detalle_tabla))
        fila_format.append(Paragraph(f'${valor:,}',estilo_detalle_tabla))
        fila_format.append(Paragraph(f'${provision:,}',estilo_detalle_tabla))
        fila_format.append(Paragraph(f'${neto:,}',estilo_detalle_tabla))
        estructura_tabla.append(fila_format)
        
      tabla=Table(estructura_tabla,colWidths=["15%","40%","15%","15%","15%"])
      tabla.setStyle([('ALIGNMENT',(0,0),(-1,-1),'CENTER'),
                      ('ALIGNMENT',(1,2),(-1,2),'LEFT'),
                          ('GRID',(0,0),(-1,-1),1,'#C9C9C9'),
                          ('VALIGN',(0,0),(-1,-1),'MIDDLE')])
      story.append(tabla)
      story.append(FrameBreak())
      
      estilo_firma=ParagraphStyle('firma',fontName='centuryg',fontSize=6,alignment=1)
      frame_nombre=Frame(10*mm,5.5*mm,193*mm,7*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      frames.append(frame_nombre)
      nombre=f'<strong>Reporte generado por:</strong> {crea} el {datetime.now()}'
      story.append(Paragraph(nombre,estilo_firma))
      story.append(FrameBreak())
      
      page=PageTemplate(id='pagina1',frames=frames,pagesize=A4)
      
      doc=BaseDocTemplate(ruta,pageTemplates=(page))
      doc.build(story)
      
    def ordenCompra(self,object_contrato,items_contrato,ruta): 
      story = []
      frames = []
      
      frame_detalle=Frame(13.6*mm,15*mm,185*mm,268*mm,id='detalle',showBoundary=0,topPadding=0,leftPadding=0,bottomPadding=0,rightPadding=0)
      frames.append(frame_detalle)
      estructura_tabla=[]
      headerStyle=ParagraphStyle('encabezado tabla',alignment=0,fontSize=10,fontName='centuryg')
      headerStyle_center=ParagraphStyle('encabezado tabla',alignment=1,fontSize=10,fontName='centuryg')
      HdataStyle = ParagraphStyle('encabezado tabla',alignment=0,fontSize=8,fontName='centuryg')
      logo_path = self.logos['Quadrata Constructores']
      logo = Image(f'{settings.MEDIA_ROOT}/{object_contrato.empresa_contrata.logo}',width=50*mm,height=13*mm)
      
      data_table =[
        [logo,'','','',Paragraph('<b>ORDEN</b>',headerStyle_center),'',f'Nº {object_contrato.pk}'],
        ['','','','','','','',],
        ['','','','','Fecha Orden',object_contrato.fecha_creacion,''],
        ['','','','','','','',],
        [Paragraph('<b>Empresa</b>',headerStyle),Paragraph(object_contrato.empresa_contrata.nombre,headerStyle),'','',Paragraph('<b>Proyecto</b>',headerStyle),object_contrato.proyecto.proyecto.upper(),''],
        [Paragraph('<b>Nit.</b>',headerStyle),object_contrato.empresa_contrata.pk,'','','','',''],
        [Paragraph('<b>PROVEEDOR</b>',headerStyle_center),'','','',Paragraph('<b>DESCRIPCION</b>',headerStyle_center),'',''],
        [Paragraph('<b>Nombre</b>',headerStyle),Paragraph(object_contrato.proveedor.nombre,HdataStyle),'','',Paragraph(object_contrato.descripcion,HdataStyle),'',''],
        [Paragraph('<b>Nit</b>',headerStyle),Paragraph(object_contrato.proveedor.pk,HdataStyle),'','','','',''],
        [Paragraph('<b>Direccion</b>',headerStyle),Paragraph(object_contrato.proveedor.direccion,HdataStyle),'','','','',''],
        [Paragraph('<b>Telefono</b>',headerStyle),Paragraph(object_contrato.proveedor.telefono,HdataStyle),'','','','',''],
      ]
      styles=[
        ('GRID',(0,0),(-1,-1),0.5,colors.grey),
        ('VALIGN',(0,0),(-1,-1),'MIDDLE'),
        ('SPAN',(0,0),(3,3)),
        ('ALIGN',(0,0),(3,3),'CENTER'),
        ('BACKGROUND',(4,0),(5,1),colors.palegreen),
        ('SPAN',(4,0),(5,1)),
        ('ALIGN',(4,0),(5,1),'CENTER'),
        ('ALIGN',(6,0),(6,0),'CENTER'),
        ('ALIGN',(5,2),(6,2),'CENTER'),
        ('SPAN',(6,0),(6,1)),
        ('BACKGROUND',(4,2),(4,2),colors.palegreen),
        ('SPAN',(5,2),(6,2)),
        ('BACKGROUND',(4,3),(6,3),colors.palegreen),
        ('SPAN',(4,3),(6,3)),#Termina la parte de logo
        ('BACKGROUND',(0,4),(0,4),colors.palegreen),
        ('SPAN',(1,4),(3,4)),
        ('BACKGROUND',(4,4),(4,5),colors.palegreen),
        ('SPAN',(5,4),(6,5)),
        ('SPAN',(4,4),(4,5)),
        ('BACKGROUND',(0,5),(0,5),colors.palegreen),
        ('SPAN',(1,5),(3,5)),
        ('BACKGROUND',(0,6),(6,6),colors.palegreen),
        ('ALIGN',(0,6),(6,6),'CENTER'),
        ('SPAN',(0,6),(3,6)),
        ('SPAN',(4,6),(6,6)),
        ('BACKGROUND',(0,7),(0,11),colors.palegreen),
        ('SPAN',(1,7),(3,7)),
        ('SPAN',(1,8),(3,8)),
        ('SPAN',(1,9),(3,9)),
        ('SPAN',(1,10),(3,10)),
        ('SPAN',(4,7),(6,10)),
        ('VALIGN',(4,7),(6,10),'TOP'),
      ]
      tabla=Table(data_table,
                  colWidths=["12.5%","12.5%","12.5%","12.5%","16.6%","16.7%","16.7%"],
                  style=styles
      )
      tabla._argH[2]=7*mm
      tabla._argH[3]=4*mm
      story.append(tabla)
      
      story.append(Spacer(0,10))
      detailStyle = ParagraphStyle('encabezado tabla',alignment=0,fontSize=7,fontName='centuryg')
      detailStyle_c = ParagraphStyle('encabezado tabla',alignment=1,fontSize=7,fontName='centuryg')
      data_table=[
        [Paragraph('<b>Item</b>',headerStyle_center),Paragraph('<b>Descripcion</b>',headerStyle_center),
         Paragraph('<b>Unidad</b>',headerStyle_center),Paragraph('<b>Cantidad</b>',headerStyle_center),
         Paragraph('<b>Vr Unitario</b>',headerStyle_center),Paragraph('<b>Total<br></br><small>(IVA incluido)</small></b>',headerStyle_center)
         ]
      ]
      styles=[
        ('BACKGROUND',(0,0),(5,0),colors.palegreen),
        ('GRID',(0,0),(-1,-1),0.5,colors.grey),
        ('VALIGN',(0,0),(-1,-1),'MIDDLE'),
      ]
      tabla=Table(data_table,
                  colWidths=["8%","42%","10%","15%","17%","17%"],
                  style=styles
      )
      story.append(tabla)
      
      
      obras=[]
      styles=[
        ('BACKGROUND',(0,0),(5,0),colors.lightgrey),
        ('GRID',(0,0),(-1,-1),0.5,colors.grey),
        ('VALIGN',(0,0),(-1,-1),'MIDDLE'),
        ('SPAN',(0,0),(5,0))
      ]
      colWidths=["8%","42%","10%","15%","17%","17%"]
      for i in items_contrato:
        data_table=[]
        if i.tipo_obra.nombre_tipo not in obras:
          obras.append(i.tipo_obra.nombre_tipo)
          data_table.append(
            [Paragraph(f'<strong>Obra: </strong>{i.tipo_obra.nombre_tipo}',detailStyle),'','','','','']
          )
          for item in items_contrato.filter(tipo_obra=i.tipo_obra.pk):
            data_table.append(
              [Paragraph(str(item.item.pk),detailStyle_c),Paragraph(item.item.nombre,detailStyle),
              Paragraph(item.item.unidad.nombre,detailStyle_c),Paragraph(str(item.cantidad),detailStyle_c),
              Paragraph(f'{item.valor:,.02f}',detailStyle_c),Paragraph(f'{item.total:,.02f}',detailStyle_c),]
            )
          tabla=Table(data_table,
                  colWidths=colWidths,
                  style=styles
            )
          story.append(tabla)
        
      
      story.append(Spacer(0,10))
      detailStyle = ParagraphStyle('encabezado tabla',alignment=0,fontSize=8,fontName='centuryg')
      detailStyle_c = ParagraphStyle('encabezado tabla',alignment=1,fontSize=8,fontName='centuryg')
      detailStyle_r = ParagraphStyle('encabezado tabla',alignment=2,fontSize=10,fontName='centuryg')
      vr_anticipo = object_contrato.total_costo*object_contrato.anticipo/100
      vr_canje = object_contrato.valor*object_contrato.porcentaje_canje/100
      vr_aiu = object_contrato.aiu*object_contrato.valor/100
      vr_retefte = (object_contrato.valor+vr_aiu)*(object_contrato.retencion.valor)/100
      if vr_aiu == 0: vr_iva = object_contrato.valor*object_contrato.iva/100
      else: vr_iva = vr_aiu*object_contrato.iva/100
      
      vr_efect = float(object_contrato.valor) + float(vr_iva) - float(vr_canje) -float(vr_retefte)
      data_table=[
        ['','','','','',
         Paragraph('<b>SUBTOTAL</b>',headerStyle),Paragraph(f'${object_contrato.valor:,.02f}',detailStyle_r)],
        ['','','','','',
         Paragraph(f'AIU ({object_contrato.aiu}%)',headerStyle),Paragraph(f'${vr_aiu:,.02f}',detailStyle_r)],
        ['','','','','',
         Paragraph(f'IVA ({object_contrato.iva}%)',headerStyle),Paragraph(f'${vr_iva:,.02f}',detailStyle_r)],
        ['','','','','',
         Paragraph('<b>TOTAL ORDEN</b>',headerStyle),Paragraph(f'${object_contrato.total_costo:,.02f}',detailStyle_r)],
        ['','','','','',
         Paragraph(f'CANJE ({object_contrato.porcentaje_canje}%)',headerStyle),Paragraph(f'${vr_canje:,.02f}',detailStyle_r)],
        ['','','','','',
         Paragraph(f'RTEFTE ({object_contrato.retencion.valor}%)',headerStyle),Paragraph(f'${vr_retefte:,.02f}',detailStyle_r)],
        ['','','','','',
         Paragraph('<b>EFECTIVO</b>',headerStyle),Paragraph(f'${vr_efect:,.02f}',detailStyle_r)],
        ['','','','','',
         Paragraph(f'<b>ANTICIPO</b> ({object_contrato.anticipo}%)',headerStyle),Paragraph(f'${vr_anticipo:,.02f}',detailStyle_r)],
        [Paragraph('<b>FORMA DE PAGO</b>',headerStyle_center),'','','','','',''],
        [Paragraph('<b>Anticipado</b>',headerStyle_center),'',Paragraph('<b>Avance</b>',headerStyle_center),'','',Paragraph('<b>Contraentrega</b>',headerStyle_center),'']
      ]
      styles=[
        ('BACKGROUND',(0,8),(6,8),colors.palegreen),
        ('BACKGROUND',(5,0),(5,7),colors.palegreen),
        ('BACKGROUND',(0,9),(0,9),colors.palegreen),
        ('BACKGROUND',(2,9),(2,9),colors.palegreen),
        ('BACKGROUND',(5,9),(5,9),colors.palegreen),
        ('GRID',(0,0),(-1,-1),0.5,colors.grey),
        ('VALIGN',(0,0),(-1,-1),'MIDDLE'),
        ('SPAN',(0,8),(6,8)),
        ('SPAN',(0,0),(4,7)),
        ('SPAN',(3,9),(4,9)),
      ]
      tabla=Table(data_table,
                  colWidths=["20%","10%","15%","10%","1%","24%","20%"],
                  style=styles
      )
      story.append(tabla)
      footStyle = ParagraphStyle('encabezado tabla',alignment=4,fontSize=7,fontName='centuryg')
      firmStyle = ParagraphStyle('encabezado tabla',alignment=1,fontSize=11,fontName='centuryg')
      vr_anticipo = object_contrato.valor* (1 - object_contrato.anticipo/100)
      vr_canje = object_contrato.valor*object_contrato.porcentaje_canje/100
      vr_efect = float(object_contrato.valor) - float(vr_canje) - float(vr_anticipo)
      data_table=[
        [Paragraph(f'''<b>{object_contrato.empresa_contrata.nombre}</b> se reserva el derecho de recibir o rechazar total o parcialmente 
                   los productos y/o servicios suministrados si considera que no coumplen con las caracteristicas especificadas en esta orden
                   de compra o de servicio.  Enviar factura electronica notificaciones@somosandina.co''',footStyle),''],
        [Paragraph(f'<b>{object_contrato.proveedor.nombre.upper()}</b>',firmStyle),Paragraph(f'<b>{object_contrato.empresa_contrata.nombre.upper()}</b>',firmStyle)]
      ]
      styles=[
        ('SPAN',(0,0),(1,0)),
        ('GRID',(0,0),(-1,-1),0.5,colors.grey),
      ]
      tabla=Table(data_table,
                  colWidths=["50%","50%"],
                  style=styles
      )
      tabla._argH[1]=25*mm
      story.append(tabla)
      
      elaboro = Paragraph
      
      page=PageTemplate(id='pagina1',frames=frames,pagesize=A4)
      doc=BaseDocTemplate(ruta,pageTemplates=(page))
      doc.build(story)
    
    def actaRecibido(self,object_contrato,obj_acta,items_recibidos,ruta):
      story = []
      frames = []
      
      frame_detalle=Frame(13.6*mm,15*mm,185*mm,268*mm,id='detalle',showBoundary=0,topPadding=0,leftPadding=0,bottomPadding=0,rightPadding=0)
      frames.append(frame_detalle)
      estructura_tabla=[]
      headerStyle=ParagraphStyle('encabezado tabla',alignment=0,fontSize=10,fontName='centuryg')
      headerStyle_center=ParagraphStyle('encabezado tabla',alignment=1,fontSize=10,fontName='centuryg')
      HdataStyle = ParagraphStyle('encabezado tabla',alignment=0,fontSize=8,fontName='centuryg')
      HdataStyle_c = ParagraphStyle('encabezado tabla',alignment=1,fontSize=8,fontName='centuryg')
      logo_path = self.logos['Quadrata Constructores']
      logo = Image(f'{settings.MEDIA_ROOT}/{object_contrato.empresa_contrata.logo}',width=50*mm,height=13*mm)
      
      data_table =[
        [logo,'','','',Paragraph('<b>ACTA DE RECIBIDO</b>',headerStyle_center),'',f'Nº {obj_acta.num_acta}'],
        ['','','','','','','',],
        ['','','','','Fecha Acta',obj_acta.fecha_acta,''],
        ['','','','','','','',],
        [Paragraph('<b>Empresa</b>',headerStyle),Paragraph(object_contrato.empresa_contrata.nombre,headerStyle),'','',Paragraph('<b>Proyecto</b>',headerStyle),object_contrato.proyecto.proyecto,''],
        [Paragraph('<b>Nit.</b>',headerStyle),object_contrato.empresa_contrata.pk,'','',"","",''],
        [Paragraph('<b>PROVEEDOR</b>',headerStyle_center),'','','',Paragraph('<b>DESCRIPCION</b>',headerStyle_center),'',''],
        [Paragraph('<b>Nombre</b>',headerStyle),Paragraph(object_contrato.proveedor.nombre,HdataStyle),'','',Paragraph(object_contrato.descripcion,HdataStyle),'',''],
        [Paragraph('<b>Nit</b>',headerStyle),Paragraph(object_contrato.proveedor.pk,HdataStyle),'','','','',''],
        [Paragraph('<b>Direccion</b>',headerStyle),Paragraph(object_contrato.proveedor.direccion,HdataStyle),'','',
          Paragraph('<b>Nº Orden</b>',headerStyle_center), Paragraph('<b>Fecha Orden</b>',headerStyle_center),''],
        [Paragraph('<b>Telefono</b>',headerStyle),Paragraph(object_contrato.proveedor.telefono,HdataStyle),'','',
         Paragraph(str(object_contrato.pk),HdataStyle_c),Paragraph(str(object_contrato.fecha_creacion),HdataStyle_c),''],
      ]
      styles=[
        ('GRID',(0,0),(-1,-1),0.5,colors.grey),
        ('VALIGN',(0,0),(-1,-1),'MIDDLE'),
        ('SPAN',(0,0),(3,3)),
        ('ALIGN',(0,0),(3,3),'CENTER'),
        ('BACKGROUND',(4,0),(5,1),colors.palegreen),
        ('SPAN',(4,0),(5,1)),
        ('ALIGN',(4,0),(5,1),'CENTER'),
        ('ALIGN',(6,0),(6,0),'CENTER'),
        ('ALIGN',(5,2),(6,2),'CENTER'),
        ('SPAN',(6,0),(6,1)),
        ('BACKGROUND',(4,2),(4,2),colors.palegreen),
        ('SPAN',(5,2),(6,2)),
        ('BACKGROUND',(4,3),(6,3),colors.palegreen),
        ('SPAN',(4,3),(6,3)),#Termina la parte de logo
        ('BACKGROUND',(0,4),(0,4),colors.palegreen),
        ('SPAN',(1,4),(3,4)),
        ('BACKGROUND',(4,4),(4,4),colors.palegreen),
        ('SPAN',(5,4),(6,4)),
        ('BACKGROUND',(0,5),(0,5),colors.palegreen),
        ('SPAN',(1,5),(3,5)),
        ('BACKGROUND',(4,5),(4,5),colors.palegreen),
        ('SPAN',(5,5),(6,5)),
        ('BACKGROUND',(0,6),(6,6),colors.palegreen),
        ('ALIGN',(0,6),(6,6),'CENTER'),
        ('SPAN',(0,6),(3,6)),
        ('SPAN',(4,6),(6,6)),
        ('BACKGROUND',(0,7),(0,11),colors.palegreen),
        ('SPAN',(1,7),(3,7)),
        ('SPAN',(1,8),(3,8)),
        ('SPAN',(1,9),(3,9)),
        ('SPAN',(1,10),(3,10)),
        ('SPAN',(4,7),(6,8)),
        ('SPAN',(5,9),(6,9)),
        ('SPAN',(5,10),(6,10)),
        ('BACKGROUND',(4,9),(6,9),colors.palegreen),
        ('VALIGN',(4,7),(6,8),'TOP'),
      ]
      tabla=Table(data_table,
                  colWidths=["12.5%","12.5%","12.5%","12.5%","16.6%","16.7%","16.7%"],
                  style=styles
      )
      tabla._argH[2]=7*mm
      tabla._argH[3]=4*mm
      story.append(tabla)
      
      story.append(Spacer(0,10))
      detailStyle = ParagraphStyle('encabezado tabla',alignment=0,fontSize=7,fontName='centuryg')
      detailStyle_c = ParagraphStyle('encabezado tabla',alignment=1,fontSize=7,fontName='centuryg')
      data_table=[
        [Paragraph('<b>Item</b>',headerStyle_center),Paragraph('<b>Descripcion</b>',headerStyle_center),
         Paragraph('<b>Unidad</b>',headerStyle_center),Paragraph('<b>Cantidad</b>',headerStyle_center),
         Paragraph('<b>Vr Unitario</b>',headerStyle_center),Paragraph('<b>Total<br></br><small>(IVA incluido)</small></b>',headerStyle_center)
         ]
      ]
      for item in items_recibidos:
        total_recibido=item.item.valor*item.cantidad
        data_table.append(
          [Paragraph(str(item.item.item.pk),detailStyle_c),Paragraph(item.item.item.nombre,detailStyle),
           Paragraph(item.item.item.unidad.nombre,detailStyle_c),Paragraph(str(item.cantidad),detailStyle_c),
           Paragraph(f'{item.item.valor:,.02f}',detailStyle_c),Paragraph(f'{total_recibido:,.02f}',detailStyle_c),]
        )
      styles=[
        ('BACKGROUND',(0,0),(5,0),colors.palegreen),
        ('GRID',(0,0),(-1,-1),0.5,colors.grey),
        ('VALIGN',(0,0),(-1,-1),'MIDDLE'),
      ]
      tabla=Table(data_table,
                  colWidths=["8%","42%","10%","15%","17%","17%"],
                  style=styles
      )
      story.append(tabla)
      
      story.append(Spacer(0,10))
      detailStyle = ParagraphStyle('encabezado tabla',alignment=0,fontSize=8,fontName='centuryg')
      detailStyle_c = ParagraphStyle('encabezado tabla',alignment=1,fontSize=8,fontName='centuryg')
      detailStyle_r = ParagraphStyle('encabezado tabla',alignment=2,fontSize=10,fontName='centuryg')
      porc_aiu = obj_acta.aiu*100/obj_acta.total
      if obj_acta.aiu == 0: porc_iva = obj_acta.iva*100/obj_acta.total
      else: porc_iva = obj_acta.iva*100/obj_acta.aiu
      total_acta = obj_acta.total + obj_acta.aiu + obj_acta.iva
      porc_anticipo = obj_acta.anticipo_amortizado*100/total_acta
      porc_canje = obj_acta.canje_efectuado*100/total_acta
      porc_rte = obj_acta.retencion_efectuada*100/(obj_acta.total+obj_acta.aiu)
      vr_efect = total_acta - obj_acta.anticipo_amortizado - obj_acta.canje_efectuado
      data_table=[
        [Paragraph('<b>OBSERVACIONES</b>',headerStyle_center),
         Paragraph('<b>SUBTOTAL</b>',headerStyle),Paragraph(f'${obj_acta.total:,.02f}',detailStyle_r)],
        ['',
         Paragraph(f'AIU ({porc_aiu:.02f}%)',headerStyle),Paragraph(f'${ obj_acta.aiu:,.02f}',detailStyle_r)],
        ['',
         Paragraph(f'IVA ({porc_iva:.02f}%)',headerStyle),Paragraph(f'${ obj_acta.iva:,.02f}',detailStyle_r)],
        ['',
         Paragraph(f'<b>TOTAL ACTA</b>',headerStyle),Paragraph(f'${total_acta:,.02f}',detailStyle_r)],
        ['',
         Paragraph(f'AMORTIZACION ANTICIPO ({porc_anticipo:.02f}%)',headerStyle),Paragraph(f'${ obj_acta.anticipo_amortizado:,.02f}',detailStyle_r)],
        ['',
         Paragraph(f'CANJE ({porc_canje:.02f}%)',headerStyle),Paragraph(f'${obj_acta.canje_efectuado:,.02f}',detailStyle_r)],
        ['',
         Paragraph(f'RTEFUENTE ({porc_rte:.02f}%)',headerStyle),Paragraph(f'${obj_acta.retencion_efectuada:,.02f}',detailStyle_r)],
        ['', Paragraph('<b>PAGO EFECTIVO</b>',headerStyle),Paragraph(f'<b>${vr_efect:,.02f}</b>',detailStyle_r)],
      ]
      styles=[
        ('BACKGROUND',(0,0),(1,0),colors.palegreen),
        ('BACKGROUND',(1,1),(1,7),colors.palegreen),
        ('GRID',(0,0),(-1,-1),0.5,colors.grey),
        ('VALIGN',(0,0),(-1,-1),'MIDDLE'),
        ('SPAN',(0,1),(0,7)),
      ]
      tabla=Table(data_table,
                  colWidths=["50%","25%","25%"],
                  style=styles
      )
      story.append(tabla)
      story.append(Spacer(0,10))
      data_table=[
        [Paragraph('<b>PAZ Y SALVO</b>',headerStyle_center),'','','','','',''],
        [Paragraph('Materiales',detailStyle_c),Paragraph('Herramientas',detailStyle_c),
         Paragraph('Equipos',detailStyle_c),Paragraph('Limpieza',detailStyle_c),
         Paragraph('Daños a terceros',detailStyle_c),Paragraph('Financieros',detailStyle_c),
         Paragraph('Documentos',detailStyle_c)],
        ['','','','','','','',]
      ]
      styles=[
        ('SPAN',(0,0),(-1,0)),
        ('BACKGROUND',(0,0),(-1,0),colors.palegreen),
        ('GRID',(0,0),(-1,-1),0.5,colors.grey),
        ('VALIGN',(0,0),(-1,-1),'MIDDLE'),
      ]
      tabla=Table(data_table,
                  colWidths=["14.25%","14.25%","14.25%","14.25%","14.5%","14.25%","14.25%"],
                  style=styles
      )
      
      story.append(tabla)
      
      footStyle = ParagraphStyle('encabezado tabla',alignment=4,fontSize=7,fontName='centuryg')
      firmStyle = ParagraphStyle('encabezado tabla',alignment=1,fontSize=11,fontName='centuryg')
      data_table=[
        [Paragraph(f'<b>{object_contrato.proveedor.nombre.upper()}</b>',firmStyle),
         Paragraph(f'<b>{object_contrato.empresa_contrata.nombre.upper()}</b>',firmStyle)]
      ]
      styles=[
        ('GRID',(0,0),(-1,-1),0.5,colors.grey),
      ]
      tabla=Table(data_table,
                  colWidths=["50%","50%"],
                  style=styles
      )
      tabla._argH[0]=25*mm
      story.append(tabla)
      
      page=PageTemplate(id='pagina1',frames=frames,pagesize=A4)
      doc=BaseDocTemplate(ruta,pageTemplates=(page))
      doc.build(story)
    
    def adicionalOrden(self,object_contrato,obj_adicional,items_adicional,ruta):
      story = []
      frames = []
      
      frame_detalle=Frame(13.6*mm,15*mm,185*mm,268*mm,id='detalle',showBoundary=0,topPadding=0,leftPadding=0,bottomPadding=0,rightPadding=0)
      frames.append(frame_detalle)
      estructura_tabla=[]
      headerStyle=ParagraphStyle('encabezado tabla',alignment=0,fontSize=10,fontName='centuryg')
      headerStyle_center=ParagraphStyle('encabezado tabla',alignment=1,fontSize=10,fontName='centuryg')
      HdataStyle = ParagraphStyle('encabezado tabla',alignment=0,fontSize=8,fontName='centuryg')
      HdataStyle_c = ParagraphStyle('encabezado tabla',alignment=1,fontSize=8,fontName='centuryg')
      logo_path = self.logos['Quadrata Constructores']
      logo = Image(f'{settings.MEDIA_ROOT}/{object_contrato.empresa_contrata.logo}',width=50*mm,height=13*mm)
      
      data_table =[
        [logo,'','','',Paragraph('<b>ADICIONAL</b>',headerStyle_center),'',f'Nº {obj_adicional.num_otrosi}'],
        ['','','','','','','',],
        ['','','','','Fecha Acta',obj_adicional.fecha_crea,''],
        ['','','','','','','',],
        [Paragraph('<b>Empresa</b>',headerStyle),Paragraph(object_contrato.empresa_contrata.nombre,headerStyle),'','',Paragraph('<b>Proyecto</b>',headerStyle),object_contrato.proyecto.proyecto,''],
        [Paragraph('<b>Nit.</b>',headerStyle),object_contrato.empresa_contrata.pk,'','','','',''],
        [Paragraph('<b>PROVEEDOR</b>',headerStyle_center),'','','',Paragraph('<b>DESCRIPCION</b>',headerStyle_center),'',''],
        [Paragraph('<b>Nombre</b>',headerStyle),Paragraph(object_contrato.proveedor.nombre,HdataStyle),'','',Paragraph(obj_adicional.descripcion,HdataStyle),'',''],
        [Paragraph('<b>Nit</b>',headerStyle),Paragraph(object_contrato.proveedor.pk,HdataStyle),'','','','',''],
        [Paragraph('<b>Direccion</b>',headerStyle),Paragraph(object_contrato.proveedor.direccion,HdataStyle),'','',
          Paragraph('<b>Nº Orden</b>',headerStyle_center), Paragraph('<b>Fecha Orden</b>',headerStyle_center),''],
        [Paragraph('<b>Telefono</b>',headerStyle),Paragraph(object_contrato.proveedor.telefono,HdataStyle),'','',
         Paragraph(str(object_contrato.pk),HdataStyle_c),Paragraph(str(object_contrato.fecha_creacion),HdataStyle_c),''],
      ]
      styles=[
        ('GRID',(0,0),(-1,-1),0.5,colors.grey),
        ('VALIGN',(0,0),(-1,-1),'MIDDLE'),
        ('SPAN',(0,0),(3,3)),
        ('ALIGN',(0,0),(3,3),'CENTER'),
        ('BACKGROUND',(4,0),(5,1),colors.palegreen),
        ('SPAN',(4,0),(5,1)),
        ('ALIGN',(4,0),(5,1),'CENTER'),
        ('ALIGN',(6,0),(6,0),'CENTER'),
        ('ALIGN',(5,2),(6,2),'CENTER'),
        ('SPAN',(6,0),(6,1)),
        ('BACKGROUND',(4,2),(4,2),colors.palegreen),
        ('SPAN',(5,2),(6,2)),
        ('BACKGROUND',(4,3),(6,3),colors.palegreen),
        ('SPAN',(4,3),(6,3)),#Termina la parte de logo
        ('BACKGROUND',(0,4),(0,4),colors.palegreen),
        ('SPAN',(1,4),(3,4)),
        ('BACKGROUND',(4,4),(4,4),colors.palegreen),
        ('SPAN',(5,4),(6,4)),
        ('BACKGROUND',(0,5),(0,5),colors.palegreen),
        ('SPAN',(1,5),(3,5)),
        ('BACKGROUND',(4,5),(4,5),colors.palegreen),
        ('SPAN',(5,5),(6,5)),
        ('BACKGROUND',(0,6),(6,6),colors.palegreen),
        ('ALIGN',(0,6),(6,6),'CENTER'),
        ('SPAN',(0,6),(3,6)),
        ('SPAN',(4,6),(6,6)),
        ('BACKGROUND',(0,7),(0,11),colors.palegreen),
        ('SPAN',(1,7),(3,7)),
        ('SPAN',(1,8),(3,8)),
        ('SPAN',(1,9),(3,9)),
        ('SPAN',(1,10),(3,10)),
        ('SPAN',(4,7),(6,8)),
        ('SPAN',(5,9),(6,9)),
        ('SPAN',(5,10),(6,10)),
        ('BACKGROUND',(4,9),(6,9),colors.palegreen),
        ('VALIGN',(4,7),(6,8),'TOP'),
      ]
      tabla=Table(data_table,
                  colWidths=["12.5%","12.5%","12.5%","12.5%","16.6%","16.7%","16.7%"],
                  style=styles
      )
      tabla._argH[2]=7*mm
      tabla._argH[3]=4*mm
      story.append(tabla)
      
      story.append(Spacer(0,10))
      detailStyle = ParagraphStyle('encabezado tabla',alignment=0,fontSize=7,fontName='centuryg')
      detailStyle_c = ParagraphStyle('encabezado tabla',alignment=1,fontSize=7,fontName='centuryg')
      data_table=[
        [Paragraph('<b>Item</b>',headerStyle_center),Paragraph('<b>Descripcion</b>',headerStyle_center),
         Paragraph('<b>Unidad</b>',headerStyle_center),Paragraph('<b>Cantidad</b>',headerStyle_center),
         Paragraph('<b>Vr Unitario</b>',headerStyle_center),Paragraph('<b>Total<br></br><small>(IVA incluido)</small></b>',headerStyle_center)
         ]
      ]
      data_table=[
        [Paragraph('<b>Item</b>',headerStyle_center),Paragraph('<b>Descripcion</b>',headerStyle_center),
         Paragraph('<b>Unidad</b>',headerStyle_center),Paragraph('<b>Cantidad</b>',headerStyle_center),
         Paragraph('<b>Vr Unitario</b>',headerStyle_center),Paragraph('<b>Total<br></br><small>(IVA incluido)</small></b>',headerStyle_center)
         ]
      ]
      styles=[
        ('BACKGROUND',(0,0),(5,0),colors.palegreen),
        ('GRID',(0,0),(-1,-1),0.5,colors.grey),
        ('VALIGN',(0,0),(-1,-1),'MIDDLE'),
      ]
      tabla=Table(data_table,
                  colWidths=["8%","42%","10%","15%","17%","17%"],
                  style=styles
      )
      story.append(tabla)
      obras=[]
      styles=[
        ('BACKGROUND',(0,0),(5,0),colors.lightgrey),
        ('GRID',(0,0),(-1,-1),0.5,colors.grey),
        ('VALIGN',(0,0),(-1,-1),'MIDDLE'),
        ('SPAN',(0,0),(5,0))
      ]
      colWidths=["8%","42%","10%","15%","17%","17%"]
      for i in items_adicional:
        data_table=[]
        if i.tipo_obra.nombre_tipo not in obras:
          obras.append(i.tipo_obra.nombre_tipo)
          data_table.append(
            [Paragraph(f'<strong>Obra: </strong>{i.tipo_obra.nombre_tipo}',detailStyle),'','','','','']
          )
          for item in items_adicional.filter(tipo_obra=i.tipo_obra.pk):
            data_table.append(
              [Paragraph(str(item.item.pk),detailStyle_c),Paragraph(item.item.nombre,detailStyle),
              Paragraph(item.item.unidad.nombre,detailStyle_c),Paragraph(str(item.cantidad),detailStyle_c),
              Paragraph(f'{item.valor:,.02f}',detailStyle_c),Paragraph(f'{item.total:,.02f}',detailStyle_c),]
            )
          tabla=Table(data_table,
                  colWidths=colWidths,
                  style=styles
            )
          story.append(tabla)
      
      story.append(Spacer(0,10))
      detailStyle = ParagraphStyle('encabezado tabla',alignment=0,fontSize=8,fontName='centuryg')
      detailStyle_c = ParagraphStyle('encabezado tabla',alignment=1,fontSize=8,fontName='centuryg')
      detailStyle_r = ParagraphStyle('encabezado tabla',alignment=2,fontSize=10,fontName='centuryg')
      vr_canje = obj_adicional.total_otrosi*obj_adicional.canje/100
      vr_aiu = obj_adicional.aiu*obj_adicional.valor/100
      vr_retefte = (obj_adicional.valor+vr_aiu)*obj_adicional.rte/100
      if vr_aiu == 0: vr_iva = obj_adicional.valor*obj_adicional.iva/100
      else: vr_iva = vr_aiu*obj_adicional.iva/100
      
      vr_efect = obj_adicional.total_otrosi - vr_canje - vr_retefte
      data_table=[
        ['','','','','',
         Paragraph('<b>SUBTOTAL</b>',headerStyle),Paragraph(f'${obj_adicional.valor:,.02f}',detailStyle_r)],
        ['','','','','',
         Paragraph(f'AIU ({obj_adicional.aiu}%)',headerStyle),Paragraph(f'${vr_aiu:,.02f}',detailStyle_r)],
        ['','','','','',
         Paragraph(f'IVA ({obj_adicional.iva}%)',headerStyle),Paragraph(f'${vr_iva:,.02f}',detailStyle_r)],
        ['','','','','',
         Paragraph('<b>TOTAL ORDEN</b>',headerStyle),Paragraph(f'${obj_adicional.total_otrosi:,.02f}',detailStyle_r)],
        ['','','','','',
         Paragraph(f'CANJE ({obj_adicional.canje}%)',headerStyle),Paragraph(f'${vr_canje:,.02f}',detailStyle_r)],
        ['','','','','',
         Paragraph(f'RTEFTE ({obj_adicional.rte}%)',headerStyle),Paragraph(f'${vr_retefte:,.02f}',detailStyle_r)],
        ['','','','','',
         Paragraph('<b>EFECTIVO</b>',headerStyle),Paragraph(f'${vr_efect:,.02f}',detailStyle_r)],
        [Paragraph('<b>FORMA DE PAGO</b>',headerStyle_center),'','','','','',''],
        [Paragraph('<b>Anticipado</b>',headerStyle_center),'',Paragraph('<b>Avance</b>',headerStyle_center),'','',Paragraph('<b>Contraentrega</b>',headerStyle_center),'']
      ]
      styles=[
        ('BACKGROUND',(0,7),(6,7),colors.palegreen),
        ('BACKGROUND',(5,0),(5,7),colors.palegreen),
        ('BACKGROUND',(0,8),(0,8),colors.palegreen),
        ('BACKGROUND',(2,8),(2,8),colors.palegreen),
        ('BACKGROUND',(5,8),(5,8),colors.palegreen),
        ('GRID',(0,0),(-1,-1),0.5,colors.grey),
        ('VALIGN',(0,0),(-1,-1),'MIDDLE'),
        ('SPAN',(0,7),(6,7)),
        ('SPAN',(0,0),(4,6)),
        ('SPAN',(3,8),(4,8)),
      ]
      tabla=Table(data_table,
                  colWidths=["20%","10%","15%","10%","1%","24%","20%"],
                  style=styles
      )
      story.append(tabla)
      footStyle = ParagraphStyle('encabezado tabla',alignment=4,fontSize=7,fontName='centuryg')
      firmStyle = ParagraphStyle('encabezado tabla',alignment=1,fontSize=11,fontName='centuryg')
      data_table=[
        [Paragraph(f'''Los adicionales pactados en este documento hacen parte integral de la <b>orden Nº {object_contrato.pk}</b> de fecha {object_contrato.fecha_creacion}.  
                    <b>{object_contrato.empresa_contrata.nombre}</b> se reserva el derecho de recibir o rechazar total o parcialmente 
                   los productos y/o servicios suministrados si considera que no cumplen con las caracteristicas especificadas en esta orden
                   de compra o de servicio.  Enviar factura electronica notificaciones@somosandina.co''',footStyle),''],
        [Paragraph(f'<b>{object_contrato.proveedor.nombre.upper()}</b>',firmStyle),Paragraph(f'<b>{object_contrato.empresa_contrata.nombre.upper()}</b>',firmStyle)]
      ]
      styles=[
        ('SPAN',(0,0),(1,0)),
        ('GRID',(0,0),(-1,-1),0.5,colors.grey),
      ]
      tabla=Table(data_table,
                  colWidths=["50%","50%"],
                  style=styles
      )
      tabla._argH[1]=25*mm
      story.append(tabla)
      
      page=PageTemplate(id='pagina1',frames=frames,pagesize=A4)
      doc=BaseDocTemplate(ruta,pageTemplates=(page))
      doc.build(story)
    
    def reciboEgreso(self,obj_pagos,consecutivo,ruta):
      story = []
      frames = []
      
      frame_detalle=Frame(13.6*mm,15*mm,185*mm,268*mm,id='detalle',showBoundary=0,topPadding=0,leftPadding=0,bottomPadding=0,rightPadding=0)
      frames.append(frame_detalle)
      estructura_tabla=[]
      headerStyle=ParagraphStyle('encabezado tabla',alignment=0,fontSize=10,fontName='centuryg')
      headerStyle_center=ParagraphStyle('encabezado tabla',alignment=1,fontSize=10,fontName='centuryg')
      HdataStyle = ParagraphStyle('encabezado tabla',alignment=0,fontSize=8,fontName='centuryg')
      logo = Image(f'{settings.MEDIA_ROOT}/{obj_pagos.empresa.logo}',width=30*mm,height=13*mm)
      
      oficinas ={
        'MEDELLIN':'MDE',
        'MONTERIA':'MTR'
      }
      ofic_pago = oficinas[obj_pagos.nroradicado.oficina]
      data_table =[
        [logo,Paragraph('<b>COMPROBANTE DE EGRESO DE EFECTIVO</b>',headerStyle_center),'','','',
         Paragraph(f'<b>Nº {ofic_pago}-{consecutivo}</b>',headerStyle_center)],
        ['',Paragraph(f'<b>{obj_pagos.empresa.nombre}</b>',headerStyle_center),'','','',''],
      ]
      
      styles=[
        ('GRID',(0,0),(-1,-1),1,colors.grey),
        ('VALIGN',(0,0),(-1,-1),'MIDDLE'),
        ('SPAN',(0,0),(0,1)),
        ('SPAN',(1,0),(4,0)),
        ('SPAN',(1,1),(4,1)),
        ('SPAN',(5,0),(5,1)),
      ]
      tabla=Table(data_table,
                  colWidths=["20%","15%","15%","15%","15%","20%"],
                  style=styles
      )
      tabla._argH[0]=12*mm
      tabla._argH[1]=8*mm
      story.append(tabla)
      
      story.append(Spacer(0,10))
      detailStyle = ParagraphStyle('encabezado tabla',alignment=0,fontSize=9,fontName='centuryg')
      detailStyle_c = ParagraphStyle('encabezado tabla',alignment=1,fontSize=9,fontName='centuryg')
      
      p_fecha = Paragraph(str(obj_pagos.fecha_pago),detailStyle)
      p_ciudad = Paragraph(obj_pagos.nroradicado.oficina,detailStyle)
      p_id_tercero = Paragraph(obj_pagos.nroradicado.idtercero,detailStyle)
      p_nombre_tercero = Paragraph(obj_pagos.nroradicado.nombretercero.upper(),detailStyle)
      p_concepto = Paragraph(
          f'Abono a Factura {obj_pagos.nroradicado.nrofactura} - {obj_pagos.nroradicado.descripcion}',
          detailStyle
        )
      p_valor = Paragraph(
        f'${obj_pagos.valor:,}',detailStyle_c
      )
      
      data_table =[
        ['FECHA',p_fecha,'','CIUDAD',p_ciudad,''],
        ['NIT',p_id_tercero,'NOMBRE',p_nombre_tercero,'',''],
        ['CONCEPTO','','','','VALOR',''],
        [p_concepto,'','','',p_valor,''],
        ['','','','','',''],
        [f'ELABORÓ: {obj_pagos.usuario.username}','APROBÓ','REVISÓ','RECIBE','',''],
      ]
      
      styles=[
        ('GRID',(0,0),(-1,-1),0.7,colors.black),
        ('VALIGN',(0,0),(5,2),'MIDDLE'),
        ('VALIGN',(0,3),(5,3),'TOP'),
        ('SPAN',(1,0),(2,0)),
        ('SPAN',(4,0),(5,0)),
        ('SPAN',(3,1),(5,1)),
        ('SPAN',(0,2),(3,2)),
        ('SPAN',(4,2),(5,2)),
        ('SPAN',(0,3),(3,3)),
        ('SPAN',(4,3),(5,3)),
        ('SPAN',(3,4),(3,5)),
        ('SPAN',(3,4),(5,4)),
        ('SPAN',(3,5),(5,5)),
        ('ALIGN',(0,2),(5,2),'CENTER'),
        ('ALIGN',(0,5),(5,5),'CENTER'),
        ('BACKGROUND',(0,2),(5,2),colors.slategray),
        ('BACKGROUND',(0,0),(0,0),colors.slategray),
        ('BACKGROUND',(0,1),(0,1),colors.slategray),
        ('BACKGROUND',(3,0),(3,0),colors.slategray),
        ('BACKGROUND',(2,1),(2,1),colors.slategray),
      ]
      
      tabla=Table(data_table,
                  colWidths=["20%","20%","20%","15%","10%","15%"],
                  style=styles
      )
      tabla._argH[3]=12*mm
      tabla._argH[4]=15*mm
      story.append(tabla)
      
      page=PageTemplate(id='pagina1',frames=frames,pagesize=A4)
      doc=BaseDocTemplate(ruta,pageTemplates=(page))
      doc.build(story)
    
    def reciboAnticipos(self,obj_pagos,consecutivo,ruta):
      story = []
      frames = []
      
      frame_detalle=Frame(13.6*mm,15*mm,185*mm,268*mm,id='detalle',showBoundary=0,topPadding=0,leftPadding=0,bottomPadding=0,rightPadding=0)
      frames.append(frame_detalle)
      estructura_tabla=[]
      headerStyle=ParagraphStyle('encabezado tabla',alignment=0,fontSize=10,fontName='centuryg')
      headerStyle_center=ParagraphStyle('encabezado tabla',alignment=1,fontSize=10,fontName='centuryg')
      HdataStyle = ParagraphStyle('encabezado tabla',alignment=0,fontSize=8,fontName='centuryg')
      logo = Image(f'{settings.MEDIA_ROOT}/{obj_pagos.empresa.logo}',width=30*mm,height=13*mm)
      
      oficinas ={
        'MEDELLIN':'MDE',
        'MONTERIA':'MTR'
      }
      ofic_pago = oficinas[obj_pagos.oficina]
      data_table =[
        [logo,Paragraph('<b>COMPROBANTE DE ANTICIPO</b>',headerStyle_center),'','','',
         Paragraph(f'<b>Nº {ofic_pago}-{consecutivo}</b>',headerStyle_center)],
        ['',Paragraph(f'<b>{obj_pagos.empresa.nombre}</b>',headerStyle_center),'','','',''],
      ]
      
      styles=[
        ('GRID',(0,0),(-1,-1),1,colors.grey),
        ('VALIGN',(0,0),(-1,-1),'MIDDLE'),
        ('SPAN',(0,0),(0,1)),
        ('SPAN',(1,0),(4,0)),
        ('SPAN',(1,1),(4,1)),
        ('SPAN',(5,0),(5,1)),
      ]
      tabla=Table(data_table,
                  colWidths=["20%","15%","15%","15%","15%","20%"],
                  style=styles
      )
      tabla._argH[0]=12*mm
      tabla._argH[1]=8*mm
      story.append(tabla)
      
      story.append(Spacer(0,10))
      detailStyle = ParagraphStyle('encabezado tabla',alignment=0,fontSize=9,fontName='centuryg')
      detailStyle_c = ParagraphStyle('encabezado tabla',alignment=1,fontSize=9,fontName='centuryg')
      
      p_fecha = Paragraph(str(obj_pagos.fecha_pago),detailStyle)
      p_ciudad = Paragraph(obj_pagos.oficina,detailStyle)
      p_id_tercero = Paragraph(obj_pagos.id_tercero,detailStyle)
      p_nombre_tercero = Paragraph(obj_pagos.nombre_tercero.upper(),detailStyle)
      p_cuenta = Paragraph(
          f'{obj_pagos.cuenta.cuentabanco}',
          detailStyle_c
        )
      p_concepto = Paragraph(
          f'{obj_pagos.descripcion}',
          detailStyle
        )
      p_valor = Paragraph(
        f'${obj_pagos.valor:,}',detailStyle_c
      )
      
      data_table =[
        ['FECHA',p_fecha,'','CIUDAD',p_ciudad,''],
        ['NIT',p_id_tercero,'NOMBRE',p_nombre_tercero,'',''],
        ['CUENTA','CONCEPTO','','','VALOR',''],
        [p_cuenta,p_concepto,'','',p_valor,''],
        ['','','','','',''],
        [f'ELABORÓ: {obj_pagos.usuario.username}','APROBÓ','REVISÓ','RECIBE','',''],
      ]
      
      styles=[
        ('GRID',(0,0),(-1,-1),0.7,colors.black),
        ('VALIGN',(0,0),(5,2),'MIDDLE'),
        ('VALIGN',(0,3),(5,3),'TOP'),
        ('SPAN',(1,0),(2,0)),
        ('SPAN',(4,0),(5,0)),
        ('SPAN',(3,1),(5,1)),
        ('SPAN',(1,2),(3,2)),
        ('SPAN',(4,2),(5,2)),
        ('SPAN',(1,3),(3,3)),
        ('SPAN',(4,3),(5,3)),
        ('SPAN',(3,4),(3,5)),
        ('SPAN',(3,4),(5,4)),
        ('SPAN',(3,5),(5,5)),
        ('ALIGN',(0,2),(5,2),'CENTER'),
        ('ALIGN',(0,5),(5,5),'CENTER'),
        ('BACKGROUND',(0,2),(5,2),colors.slategray),
        ('BACKGROUND',(0,0),(0,0),colors.slategray),
        ('BACKGROUND',(0,1),(0,1),colors.slategray),
        ('BACKGROUND',(3,0),(3,0),colors.slategray),
        ('BACKGROUND',(2,1),(2,1),colors.slategray),
      ]
      
      tabla=Table(data_table,
                  colWidths=["20%","20%","20%","15%","10%","15%"],
                  style=styles
      )
      tabla._argH[3]=12*mm
      tabla._argH[4]=15*mm
      story.append(tabla)
      
      page=PageTemplate(id='pagina1',frames=frames,pagesize=A4)
      doc=BaseDocTemplate(ruta,pageTemplates=(page))
      doc.build(story)
    
    def reciboIngreso(self,obj_otros_ingresos,consecutivo,ruta):
      story = []
      frames = []
      
      frame_detalle=Frame(13.6*mm,15*mm,185*mm,268*mm,id='detalle',showBoundary=0,topPadding=0,leftPadding=0,bottomPadding=0,rightPadding=0)
      frames.append(frame_detalle)
      estructura_tabla=[]
      headerStyle=ParagraphStyle('encabezado tabla',alignment=0,fontSize=10,fontName='centuryg')
      headerStyle_center=ParagraphStyle('encabezado tabla',alignment=1,fontSize=10,fontName='centuryg')
      HdataStyle = ParagraphStyle('encabezado tabla',alignment=0,fontSize=8,fontName='centuryg')
      logo = Image(f'{settings.MEDIA_ROOT}/{obj_otros_ingresos.empresa.logo}',width=30*mm,height=13*mm)
      
      oficinas ={
        'MEDELLIN':'MDE',
        'MONTERIA':'MTR'
      }
      ofic_pago = oficinas[obj_otros_ingresos.oficina]
      data_table =[
        [logo,Paragraph('<b>COMPROBANTE DE OTROS INGRESOS</b>',headerStyle_center),'','','',
         Paragraph(f'<b>Nº {ofic_pago}-{consecutivo}</b>',headerStyle_center)],
        ['',Paragraph(f'<b>{obj_otros_ingresos.empresa.nombre}</b>',headerStyle_center),'','','',''],
      ]
      
      styles=[
        ('GRID',(0,0),(-1,-1),1,colors.grey),
        ('VALIGN',(0,0),(-1,-1),'MIDDLE'),
        ('SPAN',(0,0),(0,1)),
        ('SPAN',(1,0),(4,0)),
        ('SPAN',(1,1),(4,1)),
        ('SPAN',(5,0),(5,1)),
      ]
      tabla=Table(data_table,
                  colWidths=["20%","15%","15%","15%","15%","20%"],
                  style=styles
      )
      tabla._argH[0]=12*mm
      tabla._argH[1]=8*mm
      story.append(tabla)
      
      story.append(Spacer(0,10))
      detailStyle = ParagraphStyle('encabezado tabla',alignment=0,fontSize=9,fontName='centuryg')
      detailStyle_c = ParagraphStyle('encabezado tabla',alignment=1,fontSize=9,fontName='centuryg')
      
      p_fecha = Paragraph(str(obj_otros_ingresos.fecha_ing),detailStyle)
      p_ciudad = Paragraph(obj_otros_ingresos.oficina,detailStyle)
      p_id_tercero = Paragraph(obj_otros_ingresos.id_tercero,detailStyle)
      p_nombre_tercero = Paragraph(obj_otros_ingresos.nombre_tercero.upper(),detailStyle)
      p_concepto = Paragraph(obj_otros_ingresos.descripcion.upper(),detailStyle)
      p_valor = Paragraph(f'${int(obj_otros_ingresos.valor):,}',detailStyle_c)
      
      data_table =[
        ['FECHA',p_fecha,'','CIUDAD',p_ciudad,''],
        ['NIT',p_id_tercero,'NOMBRE',p_nombre_tercero,'',''],
        ['CONCEPTO','','','','VALOR',''],
        [p_concepto,'','','',p_valor,''],
        ['','','','','',''],
        [f'ELABORÓ: {obj_otros_ingresos.usuario.username}','RECIBE','REVISÓ','ENTREGA','',''],
      ]
      
      styles=[
        ('GRID',(0,0),(-1,-1),0.7,colors.black),
        ('VALIGN',(0,0),(5,2),'MIDDLE'),
        ('VALIGN',(0,3),(5,3),'TOP'),
        ('SPAN',(1,0),(2,0)),
        ('SPAN',(4,0),(5,0)),
        ('SPAN',(3,1),(5,1)),
        ('SPAN',(0,2),(3,2)),
        ('SPAN',(4,2),(5,2)),
        ('SPAN',(0,3),(3,3)),
        ('SPAN',(4,3),(5,3)),
        ('SPAN',(3,4),(3,5)),
        ('SPAN',(3,4),(5,4)),
        ('SPAN',(3,5),(5,5)),
        ('ALIGN',(0,2),(5,2),'CENTER'),
        ('ALIGN',(0,5),(5,5),'CENTER'),
        ('BACKGROUND',(0,2),(5,2),colors.slategray),
        ('BACKGROUND',(0,0),(0,0),colors.slategray),
        ('BACKGROUND',(0,1),(0,1),colors.slategray),
        ('BACKGROUND',(3,0),(3,0),colors.slategray),
        ('BACKGROUND',(2,1),(2,1),colors.slategray),
      ]
      
      tabla=Table(data_table,
                  colWidths=["20%","20%","20%","15%","10%","15%"],
                  style=styles
      )
      tabla._argH[3]=12*mm
      tabla._argH[4]=15*mm
      story.append(tabla)
      
      page=PageTemplate(id='pagina1',frames=frames,pagesize=A4)
      doc=BaseDocTemplate(ruta,pageTemplates=(page))
      doc.build(story)

    def planillaMovimientos(self,empresa,fecha,cuentas,
                            obj_ingresos,obj_transf,obj_intercomp,
                            obj_anticipos,obj_pagos,obj_otrosing,
                            cuenta_efectivo,obj_saldo_ini,usuario,
                            pagos_efectivo,has_efectivo,ruta):
      story = []
      frames = []
     #encabelzados
      frame_detalle=Frame(13.6*mm,15*mm,185*mm,268*mm,id='detalle',showBoundary=0,topPadding=0,leftPadding=0,bottomPadding=0,rightPadding=0)
      frames.append(frame_detalle)
      estructura_tabla=[]
      headerStyle=ParagraphStyle('encabezado tabla',alignment=0,fontSize=10,fontName='centuryg')
      headerStyle_center=ParagraphStyle('encabezado tabla',alignment=1,fontSize=10,fontName='centuryg')
      HdataStyle = ParagraphStyle('encabezado tabla',alignment=0,fontSize=8,fontName='centuryg')
      logo = Image(f'{settings.MEDIA_ROOT}/{empresa.logo}',width=30*mm,height=20*mm)
      
      fecha_date = datetime.strptime(fecha,'%Y-%m-%d')
      fecha_format = datetime.strftime(fecha_date,'%A, %d de %B de %Y')
      titulo = Paragraph(f'<b>PLANILLA DE MOVIMIENTO DIARIO<br/>{empresa.nombre.upper()}</b>',headerStyle_center)
      fecha_format = Paragraph(f'<b>{fecha_format}</b>',headerStyle_center)
      data_table =[
        [logo,titulo],
        ['',fecha_format],
      ]
      
      styles=[
        ('GRID',(0,0),(-1,-1),1,colors.grey),
        ('VALIGN',(0,0),(-1,-1),'MIDDLE'),
        ('ALIGN',(0,0),(-1,-1),'CENTER'),
        ('SPAN',(0,0),(0,1)),
      ]
      tabla=Table(data_table,
                  colWidths=["20%","80%"],
                  style=styles
      )
      tabla._argH[0]=12*mm
      story.append(tabla)
      
      story.append(Spacer(0,20))
      detailStyle_gc = ParagraphStyle('encabezado tabla',alignment=1,fontSize=9,fontName='centuryg')
      detailStyle = ParagraphStyle('encabezado tabla',alignment=0,fontSize=7,fontName='centuryg')
      detailStyle_p = ParagraphStyle('encabezado tabla',alignment=0,fontSize=6,fontName='centuryg')
      detailStyle_c = ParagraphStyle('encabezado tabla',alignment=1,fontSize=7,fontName='centuryg')
      detailStyle_r = ParagraphStyle('encabezado tabla',alignment=2,fontSize=7,fontName='centuryg')
      
      story.append(
        Paragraph(f'<b>Cuentas seleccionadas: </b>{cuentas}',detailStyle)
      )
      story.append(Spacer(0,10))
      
     #ingresos
      titulo =Paragraph('<b>RECIBOS DE INGRESO</b>',detailStyle_gc)
      data_table = [
        [titulo,'','',''],
        [Paragraph('CONSECUTIVO',detailStyle_c),
         Paragraph('DESCRIPCION',detailStyle_c),
         Paragraph('CUENTA',detailStyle_c),
         Paragraph('VALOR',detailStyle_c)
         ]
      ]
      styles=[
        ('GRID',(0,0),(-1,-1),0.7,colors.black),
        ('VALIGN',(0,0),(-1,-1),'MIDDLE'),
        ('ALIGN',(0,1),(-1,1),'CENTER'),
        ('SPAN',(0,0),(3,0)),
        ('BACKGROUND',(0,0),(3,0),colors.slategray),
      ]
      detail_row = 2
      total_recibos = 0
      for proyectos in obj_ingresos:
        total_proy = 0
        for mvto in obj_ingresos[proyectos]:
          p_consecutivo = Paragraph(mvto.get('comprobante'),detailStyle_c)
          p_descripcion = Paragraph(mvto.get('descripcion').upper(),detailStyle)
          p_cuenta = Paragraph(mvto.get('cuenta'),detailStyle_c)
          p_valor = Paragraph(mvto.get('valor'),detailStyle_r)
          
          total_proy += int(mvto.get('valor').replace(',',''))
          data_table.append(
            [p_consecutivo,p_descripcion,p_cuenta,p_valor]
          )
          detail_row += 1
        total_recibos += total_proy
        data_table.append(
            [Paragraph(f'<b>Total {proyectos}:</b>',detailStyle_r),'','',
             Paragraph(f'<b>{total_proy:,}</b>',detailStyle_r)]
          )
        styles.append(
          ('SPAN',(0,detail_row),(2,detail_row))
        )
        detail_row += 1
      data_table.append(
            [Paragraph('<b>TOTAL RECIBOS DE CAJA:</b>',detailStyle_r),'','',
             Paragraph(f'<b>{total_recibos:,}</b>',detailStyle_r)]
          )
      styles.append(
          ('SPAN',(0,detail_row),(2,detail_row))
        )
      tabla=Table(data_table,
                  colWidths=["20%","40%","25%","15%"],
                  style=styles
      )
      story.append(tabla)
    
     #Otros Ingresos
      story.append(Spacer(0,10))
      titulo =Paragraph('<b>OTROS INGRESOS</b>',detailStyle_gc)
      data_table = [
        [titulo,'','',''],
        [Paragraph('CONSECUTIVO',detailStyle_c),
         Paragraph('CUENTA',detailStyle_c),
         Paragraph('TERCERO',detailStyle_c),
         Paragraph('VALOR',detailStyle_c)]
      ]
      styles=[
        ('GRID',(0,0),(-1,-1),0.7,colors.black),
        ('VALIGN',(0,0),(-1,-1),'MIDDLE'),
        ('ALIGN',(0,1),(-1,1),'CENTER'),
        ('SPAN',(0,0),(-1,0)),
        ('BACKGROUND',(0,0),(-1,0),colors.slategray),
      ]
      detail_row = 2
      total_seccion = 0
      for mvto in obj_otrosing:
        p_consec = Paragraph(mvto.get('consecutivo',''),detailStyle_c)
        p_tercero = Paragraph(mvto.get('tercero').upper(),detailStyle)
        p_cuenta = Paragraph(mvto.get('cuenta'),detailStyle_c)
        p_valor = Paragraph(mvto.get('valor'),detailStyle_r)
          
        total_seccion += int(mvto.get('valor').replace(',',''))
        data_table.append(
          [p_consec,p_cuenta,p_tercero,p_valor]
        )
        detail_row += 1
      data_table.append(
            [Paragraph('<b>TOTAL TRANSFERENCIAS:</b>',detailStyle_r),'','',
             Paragraph(f'<b>{total_seccion:,}</b>',detailStyle_r)]
          )
      styles.extend([
          ('SPAN',(0,detail_row),(-2,detail_row)),
          ('ALIGN',(-1,-1),(-1,-1),'CENTER'),
      ])
      tabla=Table(data_table,
                  colWidths=["20%","25%",'40%',"15%"],
                  style=styles
      )
      story.append(tabla)
    
     #transferencias
      story.append(Spacer(0,10))
      titulo =Paragraph('<b>TRANSFERENCIAS ENTRE CUENTAS</b>',detailStyle_gc)
      data_table = [
        [titulo,'',''],
        [Paragraph('CUENTA SALE',detailStyle_c),
         Paragraph('CUENTA INGRESA',detailStyle_c),
         Paragraph('VALOR',detailStyle_c)]
      ]
      styles=[
        ('GRID',(0,0),(-1,-1),0.7,colors.black),
        ('VALIGN',(0,0),(-1,-1),'MIDDLE'),
        ('ALIGN',(0,1),(-1,1),'CENTER'),
        ('SPAN',(0,0),(2,0)),
        ('BACKGROUND',(0,0),(2,0),colors.slategray),
      ]
      detail_row = 2
      total_seccion = 0
      for mvto in obj_transf:
        p_cuenta_sale = Paragraph(mvto.get('cuenta_sale'),detailStyle_c)
        p_cuenta_entra = Paragraph(mvto.get('cuenta_entra').upper(),detailStyle_c)
        p_valor = Paragraph(mvto.get('valor'),detailStyle_r)
          
        total_seccion += int(mvto.get('valor').replace(',',''))
        data_table.append(
          [p_cuenta_sale,p_cuenta_entra,p_valor]
        )
        detail_row += 1
      data_table.append(
            [Paragraph('<b>TOTAL TRANSFERENCIAS:</b>',detailStyle_r),'',
             Paragraph(f'<b>{total_seccion:,}</b>',detailStyle_r)]
          )
      styles.extend([
          ('SPAN',(0,detail_row),(1,detail_row)),
          ('ALIGN',(-1,-1),(-1,-1),'CENTER'),
      ])
      tabla=Table(data_table,
                  colWidths=["35%","35%","30%"],
                  style=styles
      )
      story.append(tabla)
    
     #intercompañia
      story.append(Spacer(0,10))
      titulo =Paragraph('<b>TRANSFERENCIAS ENTRE COMPAÑIAS</b>',detailStyle_gc)
      data_table = [
        [titulo,'','','',''],
        [Paragraph('ORIGEN',detailStyle_c),
         Paragraph('CUENTA ORIGEN',detailStyle_c),
         Paragraph('EMPRESA DESTINO',detailStyle_c),
         Paragraph('CUENTA DESTINO',detailStyle_c),
         Paragraph('VALOR',detailStyle_c)]
      ]
      styles=[
        ('GRID',(0,0),(-1,-1),0.7,colors.black),
        ('VALIGN',(0,0),(-1,-1),'MIDDLE'),
        ('ALIGN',(0,1),(-1,1),'CENTER'),
        ('SPAN',(0,0),(-1,0)),
        ('BACKGROUND',(0,0),(-1,0),colors.slategray),
      ]
      detail_row = 2
      sale_row = 0
      total_seccion = 0
      total_entra = 0
      total_sale = 0
      mvtos_entra = []
      mvtos_sale = []
      for mvto in obj_intercomp:
        if mvto.get('tipo') == 'entra':
          p_emp_sale = Paragraph(mvto.get('empresa_sale'),detailStyle)
          p_emp_entra = Paragraph(mvto.get('empresa_entra').upper(),detailStyle)
          p_cuenta_sale = Paragraph(mvto.get('cuenta_sale'),detailStyle_c)
          p_cuenta_entra = Paragraph(mvto.get('cuenta_entra').upper(),detailStyle_c)
          p_valor = Paragraph(mvto.get('valor'),detailStyle_r)
          total_entra += int(mvto.get('valor').replace(',',''))
          data_table.append(
            [p_emp_sale,p_cuenta_sale,p_emp_entra,p_cuenta_entra,p_valor]
          )
          detail_row += 1
      data_table.append(
            [Paragraph('<b>Total Entra:</b>',detailStyle_r),'','','',
             Paragraph(f'<b>{total_entra:,}</b>',detailStyle_r)]
          )
      styles.append(
        ('SPAN',(0,detail_row),(3,detail_row))
      )
      detail_row += 1
      for mvto in obj_intercomp:
        if mvto.get('tipo') == 'sale':
          p_emp_sale = Paragraph(mvto.get('empresa_sale'),detailStyle)
          p_emp_entra = Paragraph(mvto.get('empresa_entra').upper(),detailStyle)
          p_cuenta_sale = Paragraph(mvto.get('cuenta_sale'),detailStyle_c)
          p_cuenta_entra = Paragraph(mvto.get('cuenta_entra').upper(),detailStyle_c)
          p_valor = Paragraph(mvto.get('valor'),detailStyle_r)
          total_sale += int(mvto.get('valor').replace(',',''))
          data_table.append(
            [p_emp_sale,p_cuenta_sale,p_emp_entra,p_cuenta_entra,p_valor]
          )
          detail_row += 1
      data_table.append(
          [Paragraph('<b>Total Sale:</b>',detailStyle_r),'','','',
            Paragraph(f'<b>{total_sale:,}</b>',detailStyle_r)]
        )
      styles.append(
        ('SPAN',(0,detail_row),(3,detail_row))
      )
      detail_row += 1
      data_table.append(
            [Paragraph('<b>TOTAL NETO INTERCOMPAÑIA:</b>',detailStyle_r),'','','',
             Paragraph(f'<b>{total_entra-total_sale:,}</b>',detailStyle_r)]
          )
      styles.extend([
          ('SPAN',(0,-1),(3,-1)),
          ('ALIGN',(-1,-1),(-1,-1),'CENTER'),
      ])
      tabla=Table(data_table,
                  colWidths=["25%","17.5%","25%","17.5%","15%"],
                  style=styles
      )
      story.append(tabla)
          
     #anticipos
      story.append(Spacer(0,10))
      titulo =Paragraph('<b>ANTICIPOS PAGADOS</b>',detailStyle_gc)
      data_table = [
        [titulo,'',''],
        [Paragraph('CUENTA',detailStyle_c),
         Paragraph('TERCERO',detailStyle_c),
         Paragraph('DESCRIPCION',detailStyle_c),
         Paragraph('VALOR',detailStyle_c)]
      ]
      styles=[
        ('GRID',(0,0),(-1,-1),0.7,colors.black),
        ('VALIGN',(0,0),(-1,-1),'MIDDLE'),
        ('ALIGN',(0,1),(-1,1),'CENTER'),
        ('SPAN',(0,0),(-1,0)),
        ('BACKGROUND',(0,0),(-1,0),colors.slategray),
      ]
      detail_row = 2
      total_seccion = 0
      for mvto in obj_anticipos:
        p_cuenta = Paragraph(mvto.get('cuenta'),detailStyle_c)
        p_tercero = Paragraph(mvto.get('tercero'),detailStyle)
        p_descripcion = Paragraph(mvto.get('descripcion').upper(),detailStyle)
        p_valor = Paragraph(mvto.get('valor'),detailStyle_r)
          
        total_seccion += int(mvto.get('valor').replace(',',''))
        data_table.append(
          [p_cuenta,p_tercero,p_descripcion,p_valor]
        )
        detail_row += 1
      data_table.append(
            [Paragraph('<b>TOTAL ANTICIPOS:</b>',detailStyle_r),'','',
             Paragraph(f'<b>{total_seccion:,}</b>',detailStyle_r)]
          )
      styles.extend([
          ('SPAN',(0,detail_row),(-2,detail_row)),
          ('ALIGN',(-1,-1),(-1,-1),'CENTER'),
      ])
      tabla=Table(data_table,
                  colWidths=["20%","20%","40%","20%"],
                  style=styles
      )
      story.append(tabla)
      
     #pagos
      story.append(Spacer(0,10))
      titulo =Paragraph('<b>PAGOS EFECTUADOS</b>',detailStyle_gc)
      data_table = [
        [titulo,'','','',''],
        [Paragraph('CUENTA',detailStyle_c),
         Paragraph('CAUSACION',detailStyle_c),
         Paragraph('TERCERO',detailStyle_c),
         Paragraph('DESCRIPCION',detailStyle_c),
         Paragraph('VALOR',detailStyle_c)]
      ]
      styles=[
        ('GRID',(0,0),(-1,-1),0.7,colors.black),
        ('VALIGN',(0,0),(-1,-1),'MIDDLE'),
        ('ALIGN',(0,1),(-1,1),'CENTER'),
        ('SPAN',(0,0),(-1,0)),
        ('BACKGROUND',(0,0),(-1,0),colors.slategray),
      ]
      detail_row = 2
      total_seccion = 0
      for mvto in obj_pagos:
        p_cuenta = Paragraph(mvto.get('cuenta'),detailStyle_c)
        p_causa = Paragraph(mvto.get('causacion'),detailStyle_c)
        p_tercero = Paragraph(mvto.get('tercero'),detailStyle)
        p_descripcion = Paragraph(mvto.get('descripcion').upper(),detailStyle)
        p_valor = Paragraph(mvto.get('valor'),detailStyle_r)
          
        total_seccion += int(mvto.get('valor').replace(',',''))
        data_table.append(
          [p_cuenta,p_causa,p_tercero,p_descripcion,p_valor]
        )
        detail_row += 1
      data_table.append(
            [Paragraph('<b>TOTAL PAGOS:</b>',detailStyle_r),'','','',
             Paragraph(f'<b>{total_seccion:,}</b>',detailStyle_r)]
          )
      styles.extend([
          ('SPAN',(0,detail_row),(-2,detail_row)),
          ('ALIGN',(0,0),(-1,-1),'CENTER'),
      ])
      tabla=Table(data_table,
                  colWidths=["15%","15%","20%","35%","15%"],
                  style=styles
      )
      story.append(tabla)
      
      story.append(Spacer(0,40))
      data_table = [
        ('____________________','','____________________'),
        ('ELABORÓ','','RECIBIÓ')
      ]
      styles=[
        ('ALIGN',(0,0),(-1,1),'CENTER'),
      ]
      tabla=Table(data_table,
                  colWidths=["33%","33%","33%"],
                  style=styles
      )
      story.append(tabla)
      
     #arqueo
      if has_efectivo:
        story.append(PageBreak())
        titulo = Paragraph(f'<b>ARQUEO DE CAJA<br/>{empresa.nombre.upper()}<br/>{cuenta_efectivo.cuentabanco}</b>',headerStyle_center)
        data_table =[
          [logo,titulo],
          ['',fecha_format],
        ]
        styles=[
          ('GRID',(0,0),(-1,-1),1,colors.grey),
          ('VALIGN',(0,0),(-1,-1),'MIDDLE'),
          ('ALIGN',(0,0),(-1,-1),'CENTER'),
          ('SPAN',(0,0),(0,1)),
        ]
        tabla=Table(data_table,
                    colWidths=["20%","80%"],
                    style=styles
        )
        tabla._argH[0]=16*mm
        tabla._argH[1]=8*mm
        story.append(tabla)
        
        story.append(Spacer(0,20))
        ultimo_reg = obj_saldo_ini.filter(fecha__lt=fecha).order_by('-fecha')
        if ultimo_reg.exists():
          fecha_ultimo_reg = ultimo_reg.first().fecha
          saldo_ultimo_reg = ultimo_reg.first().saldo_inicial
        else:
          fecha_ultimo_reg = 'NO HAY REGISTROS PREVIOS'
          saldo_ultimo_reg = 0
          
        story.append(
          Paragraph(f'<b>SALDO INICIAL</b> (Saldo a {fecha_ultimo_reg}): ${saldo_ultimo_reg:,}',
                    detailStyle)
        )
        story.append(Spacer(0,10))
        
        titulo =Paragraph('<b>MOVIMIENTOS</b>',detailStyle_gc)
        ingresos = pagos_efectivo.get('ingresos')
        otros_ingresos = pagos_efectivo.get('otros_ingresos')
        transf_entra = pagos_efectivo.get('transferencias_entra')
        transf_sale = pagos_efectivo.get('transferencias_sale')
        inter_entra = pagos_efectivo.get('intercompañia_entra')
        inter_sale = pagos_efectivo.get('intercompañia_sale')
        anticipos = pagos_efectivo.get('anticipos')
        pagos = pagos_efectivo.get('pagos')
        from decimal import Decimal
        saldo_final = Decimal(saldo_ultimo_reg) + ingresos + otros_ingresos + (transf_entra-transf_sale) + (inter_entra-inter_sale) - anticipos - pagos
        
        data_table = [
          [titulo,''],
          [Paragraph('(+) Ingresos',detailStyle),
          Paragraph(f'$ {ingresos:,}',detailStyle_r)],
          [Paragraph('(+) Otros ingresos',detailStyle),
          Paragraph(f'$ {otros_ingresos:,}',detailStyle_r)],
          [Paragraph('(+) Transferencias entra',detailStyle),
          Paragraph(f'$ {transf_entra:,}',detailStyle_r)],
          [Paragraph('(-) Transferencias sale',detailStyle),
          Paragraph(f'$ {transf_sale:,}',detailStyle_r)],
          [Paragraph('(+) Intercompañia entra',detailStyle),
          Paragraph(f'$ {inter_entra:,}',detailStyle_r)],
          [Paragraph('(-) Intercompañia sale',detailStyle),
          Paragraph(f'$ {inter_sale:,}',detailStyle_r)],
          [Paragraph('(-) Anticipos',detailStyle),
          Paragraph(f'$ {anticipos:,}',detailStyle_r)],
          [Paragraph('(-) Pagos',detailStyle),
          Paragraph(f'$ {pagos:,}',detailStyle_r)],
          [Paragraph(f'<b>(=) SALDO FINAL TEORICO</b>:',detailStyle),
            Paragraph(f'<b>{saldo_final:,}</b>',detailStyle_r)]
        ]
        styles=[
          ('BOX',(0,0),(-1,-1),0.5,colors.black),
          ('VALIGN',(0,0),(-1,-1),'MIDDLE'),
          ('SPAN',(0,0),(-1,0)),
          ('BACKGROUND',(0,0),(-1,0),colors.slategray),
        ]
        
        tabla=Table(data_table,
                    colWidths=["20%","30%"],
                    style=styles
        )
        story.append(tabla)
        story.append(Spacer(0,20))
        
        import json, pytz
        titulo =Paragraph('<b>ARQUEO FISICO DE CAJA</b>',detailStyle_gc)
        saldo_dia = obj_saldo_ini.filter(fecha=fecha)
        if saldo_dia.exists():
          usuario_forma = saldo_dia[0].usuario.username
          fecha_forma = pytz.timezone('America/Bogota').normalize(saldo_dia[0].fecha_registro)
          valor_dia = saldo_dia[0].saldo_inicial
          forma = json.loads(saldo_dia[0].forma)
          m50 = forma.get('50',0)
          m100 = forma.get('100',0)
          m200 = forma.get('200',0)
          m500 = forma.get('500',0)
          m1000 = forma.get('1.000',0)
          b1k = forma.get('1000',0)
          b2k = forma.get('2000',0)
          b5k = forma.get('5000',0)
          b10k = forma.get('10000',0)
          b20k = forma.get('20000',0)
          b50k = forma.get('50000',0)
          b100k = forma.get('100000',0)
        else:
          usuario_forma = 'NO REGISTRADO'
          fecha_forma = 'NO REGISTRADO '
          valor_dia = 0
          m50 = 0
          m100 = 0
          m200 = 0
          m500 = 0
          m1000 = 0
          b1k = 0
          b2k = 0
          b5k = 0
          b10k = 0
          b20k = 0
          b50k = 0
          b100k = 0 
          
        data_table = [
          [titulo,'','',''],
          [Paragraph('<b>Monedas</b>',detailStyle_c),'',Paragraph('<b>Billetes</b>',detailStyle_c),''],
          [Paragraph('50',detailStyle),Paragraph(str(m50),detailStyle_r),
          Paragraph('1.000',detailStyle),Paragraph(str(b1k),detailStyle_r)],
          [Paragraph('100',detailStyle),Paragraph(str(m100),detailStyle_r),
          Paragraph('2.000',detailStyle),Paragraph(str(b2k),detailStyle_r)],
          [Paragraph('200',detailStyle),Paragraph(str(m200),detailStyle_r),
            Paragraph('5.000',detailStyle),Paragraph(str(b5k),detailStyle_r)],
          [Paragraph('500',detailStyle),Paragraph(str(m500),detailStyle_r),
            Paragraph('10.000',detailStyle),Paragraph(str(b10k),detailStyle_r)],
          [Paragraph('1.000',detailStyle),Paragraph(str(m1000),detailStyle_r)
          ,Paragraph('20.000',detailStyle),Paragraph(str(b20k),detailStyle_r)],
          ['','',Paragraph('50.000',detailStyle),Paragraph(str(b50k),detailStyle_r)],
          ['','',Paragraph('100.000',detailStyle),Paragraph(str(b100k),detailStyle_r)],
          [Paragraph(f'<b>TOTAL EN CAJA: ${valor_dia:,}</b><br/><small>*Arqueo fisico registrado por {usuario_forma} el {fecha_forma}<small>',detailStyle_c),'','',''],
          
        ]
        styles=[
          ('BOX',(0,0),(-1,-1),0.5,colors.black),
          ('VALIGN',(0,0),(-1,-1),'MIDDLE'),
          ('SPAN',(0,0),(-1,0)),
          ('SPAN',(0,-1),(-1,-1)),
          ('SPAN',(0,1),(1,1)),
          ('SPAN',(0,1),(1,1)),
          ('SPAN',(2,1),(3,1)),
          ('BACKGROUND',(0,0),(-1,0),colors.slategray),
        ]
        
        tabla=Table(data_table,
                    colWidths=["12.5%","12.5%","12.5%","12.5%"],
                    style=styles
        )
        story.append(tabla)
        
        story.append(Spacer(0,20))
        diferencia = Decimal(valor_dia) - saldo_final
        story.append(
          Paragraph(f'<b>DIFERENCIA EN SALDOS: </b> {diferencia:,}',
                    detailStyle)
        )
        story.append(Spacer(0,20))
        data_table=(
          [Paragraph('<b>OBSERVACIONES:</b>',detailStyle)],
        )
        styles=[
          ('BOX',(0,0),(-1,-1),0.5,colors.black),
          ('VALIGN',(0,0),(-1,-1),'TOP'),
        ]
        tabla=Table(data_table,
                    style=styles
        )
        tabla._argH[0]=25*mm
        story.append(tabla)
        story.append(Spacer(0,20))
        
        
        
        story.append(Spacer(0,60))
        data_table = [
          ('____________________','','____________________'),
          ('ELABORÓ','','RECIBIÓ')
        ]
        styles=[
          ('ALIGN',(0,0),(-1,1),'CENTER'),
        ]
        tabla=Table(data_table,
                    colWidths=["33%","33%","33%"],
                    style=styles
        )
        story.append(tabla)
      
     #generar doc
    
      texto = f'Movimiento diario generado por {usuario.username} el {datetime.now()}'
      page=PageTemplate(id='pagina1',frames=frames,pagesize=A4,onPage=partial(footer, text=texto))
      doc=BaseDocTemplate(ruta,pageTemplates=(page))
      doc.build(story)
    
    def terminosAlttum(self,proyecto,beneficiarios,cliente,cc_cliente,email,ocupacion,
                       telefono,direccion,cel,fecha_contrato,ruta):
      story=[]
      grupos=[]
      frames_pag1=[]
      # Imagen base del doc
      frame_base=Frame(0,0,210*mm,297*mm)
      frames_pag1.append(frame_base)
      pagina1=Image('./resources/Formato terminos y condiciones alianzas.png',width=202*mm,height=280*mm)
      story.append(pagina1)
      story.append(FrameBreak())
      
      frame_cliente=Frame(32*mm,261.3*mm,86*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,id='cliente')
      grupos.append((frame_cliente,cliente))
      
      frame_cc_cliente=Frame(124.3*mm,261.3*mm,67*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,id='cc_cliente')
      grupos.append((frame_cc_cliente,cc_cliente))
  
      frame_proyecto=Frame(40.8*mm,252.2*mm,77*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,id='proyecto')
      grupos.append((frame_proyecto,proyecto))
      
      frame_email=Frame(128.3*mm,252.2*mm,67*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,id='email')
      grupos.append((frame_email,email))
      
      frame_ocupacion=Frame(37.5*mm,243.2*mm,82*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,id='ocupacion')
      grupos.append((frame_ocupacion,ocupacion))
      
      frame_tel=Frame(132.3*mm,243.2*mm,60*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,id='tel')
      grupos.append((frame_tel,telefono))

      frame_direccion=Frame(33*mm,234.1*mm,66*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,id='direccion')
      grupos.append((frame_direccion,direccion))
      
      frame_celular=Frame(112.7*mm,234.1*mm,45*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,id='celular')
      grupos.append((frame_celular,cel))
      
      frame_benef=Frame(185.7*mm,234.1*mm,10.8*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,id='celular')
      grupos.append((frame_benef,beneficiarios))
      
      nro_benef=Utilidades().numeros_letras(int(beneficiarios),'Numero')
      frame_nro_benef=Frame(78.7*mm,99.6*mm,12.8*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,id='nro_benef')
      grupos.append((frame_nro_benef,nro_benef))
      
      frame_benef_cant=Frame(89.9*mm,99.6*mm,4*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0,id='benef_cant')
      grupos.append((frame_benef_cant,beneficiarios))
      
      frame_dia=Frame(89.5*mm,55*mm,11.9*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      grupos.append((frame_dia,str(fecha_contrato.day)))
      
      frame_mes=Frame(112.3*mm,55*mm,11.8*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      grupos.append((frame_mes,f'{fecha_contrato.month:02d}'))
      
      frame_año=Frame(133.4*mm,55*mm,13.3*mm,4.5*mm,showBoundary=0,leftPadding=0,topPadding=0,bottomPadding=0)
      grupos.append((frame_año,str(fecha_contrato.year)))
      
      for grupo in grupos:
        contenido=grupo[1]
        if contenido!=None and contenido!='None':
          frame=grupo[0]
          fontName='centuryg'
          fontSize=9
          estilo=ParagraphStyle('estilo',fontName=fontName,fontSize=fontSize)
          flowable=Paragraph(contenido,estilo)
          textwidth=stringWidth(contenido,'centuryG',fontSize)
          i=1
          j=1
          while textwidth>frame._aW:
            if fontSize>6:
              fontSize-=i
            else:
              contenido=contenido[:len(contenido)-j]
            estilo=ParagraphStyle('estilo',fontName=fontName,fontSize=fontSize)
            flowable=Paragraph(contenido,estilo)
            textwidth=stringWidth(contenido,'centuryG',fontSize)
            i+=1
            j+=1
          frames_pag1.append(frame)
          story.append(flowable)
          story.append(FrameBreak())
      grupos=[]
      
      page1=PageTemplate(id='pagina1',frames=frames_pag1)
      doc=BaseDocTemplate(ruta,pageTemplates=page1,pagesize=A4)
      doc.build(story)
    
def header(canvas, doc,content):
    canvas.saveState()
    w, h = content.wrap(0,0)
    content.drawOn(canvas, 0, 0)
    canvas.restoreState()
    
def footer(canvas, doc,text): 
  style = ParagraphStyle('footer',alignment=0,fontSize=6,fontName='centuryg')
  canvas.saveState() 
  P = Paragraph(text, 
      style) 
  w, h = P.wrap(doc.width, doc.bottomMargin) 
  P.drawOn(canvas, doc.leftMargin, h) 
  canvas.restoreState() 


        