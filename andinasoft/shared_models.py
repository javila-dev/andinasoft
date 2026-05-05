import calendar
import math
from datetime import date, datetime, timedelta
from decimal import Decimal
from dateutil import relativedelta
from django.db import models
from django.db.models.aggregates import Sum, Max, Min
from django.db.models.query_utils import Q
from django.conf import settings
from django.core.files.storage import default_storage
from andinasoft.models import clientes, cuentas_pagos

from andinasoft.utilities import JsonRender, Utilidades



class titulares_por_adj(models.Model):
    adj = models.CharField(db_column='IdAdjudicacion', primary_key=True,max_length=12)
    IdTercero1=models.CharField(max_length=255,db_column='IdTercero1')
    IdTercero2=models.CharField(max_length=255,db_column='IdTercero2')
    IdTercero3=models.CharField(max_length=255,db_column='IdTercero3')
    IdTercero4=models.CharField(max_length=255,db_column='IdTercero4')
    titular1= models.CharField(max_length=255,db_column='titular1')
    titular2=models.CharField(max_length=255,db_column='titular2')
    titular3= models.CharField(max_length=255,db_column='titular3')
    titular4= models.CharField(max_length=255,db_column='titular4')
    class Meta:
        managed = False
        db_table='titulares_por_adj'

class Adjudicacion(models.Model):
    fecha = models.DateTimeField(db_column='Fecha', blank=True, null=True)  # Field name made lowercase.
    idadjudicacion = models.CharField(db_column='IdAdjudicacion', primary_key=True, max_length=12)  # Field name made lowercase.
    tipocontrato = models.CharField(db_column='TipoContrato', max_length=255, blank=True, null=True)  # Field name made lowercase.
    contrato = models.CharField(db_column='Contrato', max_length=15, blank=True, null=True)  # Field name made lowercase.
    idinmueble = models.CharField(db_column='IdInmueble', unique=True, max_length=50, blank=True, null=True)  # Field name made lowercase.
    idtercero1 = models.CharField(db_column='IdTercero1', max_length=12, blank=True, null=True)  # Field name made lowercase.
    idtercero2 = models.CharField(db_column='IdTercero2', max_length=12, blank=True, null=True)  # Field name made lowercase.
    idtercero3 = models.CharField(db_column='Idtercero3', max_length=30, blank=True, null=True)  # Field name made lowercase.
    idtercero4 = models.CharField(db_column='Idtercero4', max_length=30, blank=True, null=True)  # Field name made lowercase.
    formapago = models.CharField(db_column='FormaPago', max_length=25, blank=True, null=True)  # Field name made lowercase.
    valor = models.DecimalField(db_column='Valor', max_digits=14, decimal_places=2, blank=True, null=True)  # Field name made lowercase.
    contado = models.DecimalField(max_digits=14, decimal_places=2, blank=True, null=True)
    cuotainicial = models.DecimalField(db_column='CuotaInicial', max_digits=14, decimal_places=2, blank=True, null=True)  # Field name made lowercase.
    financiacion = models.DecimalField(db_column='Financiacion', max_digits=14, decimal_places=2, blank=True, null=True)  # Field name made lowercase.
    plazofnc = models.IntegerField(db_column='PlazoFnc', blank=True, null=True)  # Field name made lowercase.
    tasafnc = models.DecimalField(db_column='TasaFnc', max_digits=4, decimal_places=4, blank=True, null=True)  # Field name made lowercase.
    cuotafnc = models.IntegerField(db_column='CuotaFnc', blank=True, null=True)  # Field name made lowercase.
    iniciofnc = models.DateTimeField(db_column='InicioFnc', blank=True, null=True)  # Field name made lowercase.
    extraordinaria = models.DecimalField(db_column='Extraordinaria', max_digits=14, decimal_places=2, blank=True, null=True)  # Field name made lowercase.
    plazoextra = models.IntegerField(db_column='PlazoExtra', blank=True, null=True)  # Field name made lowercase.
    tasaextra = models.DecimalField(db_column='TasaExtra', max_digits=7, decimal_places=2, blank=True, null=True)  # Field name made lowercase.
    cuotaextra = models.DecimalField(db_column='CuotaExtra', max_digits=10, decimal_places=2, blank=True, null=True)  # Field name made lowercase.
    inicioextra = models.DateField(db_column='InicioExtra', blank=True, null=True)  # Field name made lowercase.
    usuario = models.CharField(db_column='Usuario', max_length=12, blank=True, null=True)  # Field name made lowercase.
    estado = models.CharField(db_column='Estado', max_length=20, blank=True, null=True)  # Field name made lowercase.
    fechadesistimiento = models.DateField(db_column='FechaDesistimiento', blank=True, null=True)  # Field name made lowercase.
    origenventa = models.CharField(db_column='OrigenVenta', max_length=20, blank=True, null=True)  # Field name made lowercase.
    tipoorigen = models.CharField(db_column='TipoOrigen', max_length=255, blank=True, null=True)  # Field name made lowercase.
    basecomision = models.DecimalField(db_column='BaseComision', max_digits=14, decimal_places=2)  # Field name made lowercase.
    fecharadicacion = models.DateField(db_column='FechaRadicacion', blank=True, null=True)  # Field name made lowercase.
    fechacontrato = models.DateField(db_column='FechaContrato', blank=True, null=True)  # Field name made lowercase.
    usuarioradica = models.CharField(db_column='UsuarioRadica', max_length=20, blank=True, null=True)  # Field name made lowercase.
    oficina = models.CharField(db_column='Oficina', max_length=255, blank=True, null=True)  # Field name made lowercase.
    p_enmendadura= models.IntegerField(blank=True, null=True)
    p_doccompleta= models.IntegerField(blank=True, null=True)
    p_valincorrectos= models.IntegerField(blank=True, null=True)
    p_obs = models.CharField(max_length=255, blank=True, null=True)  # Field name made lowercase.
    es_juridico= models.IntegerField(blank=True, null=True)
    
        
    class Meta:
        managed = False
        db_table = 'adjudicacion'
    
    def __str__(self):
        titular1 = self.titulares().get('titular_1').nombrecompleto
        return f'{self.pk} - {titular1}'
    
    def titulares(self):
        try: titular1 = clientes.objects.get(pk=self.idtercero1)
        except: titular1 = clientes.objects.get(pk='')
        try: titular2 = clientes.objects.get(pk=self.idtercero2)
        except: titular2 = clientes.objects.get(pk='')
        try: titular3 = clientes.objects.get(pk=self.idtercero3)
        except: titular3 = clientes.objects.get(pk='')
        try: titular4 = clientes.objects.get(pk=self.idtercero4)
        except: titular4 = clientes.objects.get(pk='')
        data = {
            'titular_1' : titular1,
            'titular_2' : titular2,
            'titular_3' : titular3,
            'titular_4' : titular4,
        }
        
        return data
    
    def titulares2(self):
        t = []
        
        for i in (self.idtercero1,self.idtercero2,self.idtercero3,self.idtercero4):
            if i!= '' and i!= None:
                t.append(clientes.objects.get(pk=i))
                
        return t
    
    def cantidad_titulares(self):
        cant = 1
        if self.idtercero2 != '' and self.idtercero2!= None: cant += 1
        if self.idtercero3!= '' and self.idtercero3!= None: cant += 1
        if self.idtercero4!= '' and self.idtercero4!= None: cant += 1
        
        return cant
    
    def recaudo_detallado(self,proyecto=None,date=date.today()):
        
        if proyecto == None: proyecto = self._state.db
        obj_rcdos = Recaudos.objects.using(proyecto).filter(idadjudicacion=self.idadjudicacion)
        
        capital = obj_rcdos.aggregate(Sum('capital'))
        interescte = obj_rcdos.aggregate(Sum('interescte'))
        interesmora = obj_rcdos.aggregate(Sum('interesmora'))

        cap = capital.get('capital__sum',0)
        if cap == None: cap = 0
        intcte = interescte.get('interescte__sum',0)
        if intcte == None: intcte=0
        intmora = interesmora.get('interesmora__sum',0)
        if intmora == None: intmora = 0
        
        data = {
            'capital':cap,
            'interescte':intcte,
            'interesmora':intmora,
            'total':cap+intcte+intmora,
            'saldo_cap': self.valor - cap,
            'date':date
        }
        return data
    
    def recaudo_detallado_interfaz(self,date_until,proyecto=None):
        
        if proyecto == None: proyecto = self._state.db
        recibos = Recaudos_general.objects.using(proyecto).filter(idadjudicacion=self.idadjudicacion,fecha__lte = date_until)
        
        capital = 0
        interescte = 0
        interesmora = 0
        
        for r in recibos:
            detalle = Recaudos.objects.using(proyecto).filter(recibo=r.numrecibo)
            
            c = detalle.aggregate(Sum('capital'))
            ic = detalle.aggregate(Sum('interescte'))
            im = detalle.aggregate(Sum('interesmora'))

            c = c.get('capital__sum',0)
            if c == None: c = 0
            ic = ic.get('interescte__sum',0)
            if ic == None: ic=0
            im = im.get('interesmora__sum',0)
            if im == None: im = 0
            
            capital += c
            interescte += ic
            interesmora += im

        
        data = {
            'capital':capital,
            'interescte':interescte,
            'interesmora':interesmora,
            'total':capital+interescte+interesmora,
            'saldo_cap': self.valor - capital,
            'date':date
        }
        return data
    
    def saldos_por_cartera(self):
        proyecto = self._state.db
        
        obj_saldo = saldos_adj.objects.using(proyecto).filter(
            adj=self.pk)
        
        ci = obj_saldo.filter(tipocta='CI')
        
        abonado_ci = ci.aggregate(total=Sum('rcdocapital')).get('total')
        
        if abonado_ci == None: abonado_ci = 0
        
        saldo_ci = ci.aggregate(total=Sum('saldocapital')).get('total')
        
        if saldo_ci == None: saldo_ci = 0
        
        fn = obj_saldo.exclude(tipocta='CI')
        
        abonado_fn = fn.aggregate(total=Sum('rcdocapital')).get('total')
        
        if abonado_fn == None: abonado_fn = 0
        
        saldo_fn = fn.aggregate(total=Sum('saldocapital')).get('total')
        
        if saldo_fn == None: saldo_fn = 0
        
        ctas_vencidas = obj_saldo.filter(fecha__lte=datetime.today())
        ctas_vigentes = obj_saldo.filter(fecha__gt=datetime.today())
        
        cap_vencido = ctas_vencidas.aggregate(total=Sum('saldocapital')).get('total')
        if cap_vencido == None: cap_vencido = 0
        int_vencido = ctas_vencidas.aggregate(total=Sum('saldointcte')).get('total')
        if int_vencido == None: int_vencido = 0
        
        
        
        total_valor_futuro = ctas_vigentes.aggregate(total=Sum('capital')).get('total')
        if total_valor_futuro == None: total_valor_futuro = 0
        
        total_pago_hoy = cap_vencido + int_vencido + total_valor_futuro
        
        
        data = {
            'abonado_ci':abonado_ci,
            'saldo_ci': saldo_ci,
            'abonado_fn': abonado_fn,
            'saldo_fn': saldo_fn,
            'pago_hoy':{
                'cap_vencido':cap_vencido,
                'int_vencido':int_vencido,
                'cap_futuro':total_valor_futuro,
                'total_pago_hoy':total_pago_hoy
            }
        }
        
        return data
    
    def extra_info(self):
        proyecto = self._state.db
        adj_info = Vista_Adjudicacion.objects.using(proyecto).get(IdAdjudicacion=self.pk)
        return adj_info
    
    def gestor_cartera(self):
        proyecto = self._state.db
        gestor = InfoCartera.objects.using(proyecto).filter(idadjudicacion=self.pk)
        gestor_asignado = gestor[0].gestorasignado if gestor.exists() else 'Sin Gestor'
        return gestor_asignado
    
    def presupuesto(self):
        proyecto = self._state.db
        plan = PlanPagos.objects.using(proyecto).filter(adj=self.pk)
        today = date.today()
        last_day=calendar.monthrange(today.year,int(today.month))[1]
        end_month = date(today.year,today.month,last_day)
        dias_mora = 0
        por_vencer = 0
        lt_30_value = 0
        lt_60_value = 0
        lt_90_value = 0
        lt_120_value = 0
        gt_120_value = 0
        
        for q in plan:
            if q.fecha <= end_month:
                pendiente = q.pendiente().get('total')
                if pendiente > 0:
                    mora = q.mora().get('dias_totales')
                    dias_mora = mora if mora > dias_mora else dias_mora
                    if mora <= 0:
                        por_vencer += pendiente
                    elif 0 < mora <= 30:
                        lt_30_value += pendiente
                    elif 30 < mora <= 60:
                        lt_60_value += pendiente
                    elif 60 < mora <= 90:
                        lt_90_value += pendiente
                    elif 90 < mora <= 120:
                        lt_120_value += pendiente
                    elif 120 < mora:
                        gt_120_value += pendiente
                    
        total_pendiente = por_vencer + lt_30_value + lt_60_value + lt_90_value + lt_120_value + gt_120_value
        gte60 =  lt_90_value + lt_120_value + gt_120_value
        ultimo_pago = Recaudos.objects.using(proyecto).filter(idadjudicacion=self.pk
                                                              ).aggregate(maximo=Max('fecha')
                                                                          ).get('maximo')
        
        data = {
            'por_vencer':por_vencer,
            'lt30':lt_30_value,
            'lt60':lt_60_value,
            'lt90':lt_90_value,
            'lt120':lt_120_value,
            'gt120':gt_120_value,
            'gte60': gte60,
            'total_pendiente': total_pendiente,
            'ultimo_pago':ultimo_pago,
            'dias_mora':dias_mora
        }
        
        return data
    
    def logo(self):
        
        proyecto = self._state.db
        
        logo_path = {
            'Sandville Beach': 'img/sandville_beach.png',
            'Tesoro Escondido': 'img/logo-Tesoro-Escondido.png',
            'Perla del Mar': 'img/logo-perla-mar-nuevo.png',
            'Vegas de Venecia': 'img/logo_vegas_de_venecia.png',
            'Carmelo Reservado': 'img/logo_carmelo_reservado.png'
        }
        
        encabezado_path = {
            'Sandville Beach': 'img/conceptos_inmob_beach.png',
            'Tesoro Escondido': 'img/conceptos_inmob_bugambilias.png',
            'Perla del Mar': 'img/conceptos_inmobiliarios_suenos_extraord.png',
            'Vegas de Venecia': 'img/conceptos_inmob_vegas_de_venecia.png',
            'Carmelo Reservado': 'img/conceptos_inmob_carmelo.png'

        }
        
        return logo_path.get(proyecto), encabezado_path.get(proyecto)
    
    def tiempos_pagos(self):
        proyecto = self._state.db
        obj_plan = PlanPagos.objects.using(proyecto).filter(adj=self.pk)
        
        ci = obj_plan.filter(tipocta='CI')
        numero_ctas_ci = ci.count()
        
        if numero_ctas_ci > 0:
            dates_ci = ci.aggregate(fecha_min = Min('fecha'), fecha_max = Max('fecha'))
            min_date_ci = self.fechacontrato
            max_date_ci = dates_ci.get('fecha_max')
            
            months_to_pay_ci = (max_date_ci.year - min_date_ci.year)*12 + (max_date_ci.month - min_date_ci.month)
        else: months_to_pay_ci = 0
        
        fn = obj_plan.exclude(tipocta='CI')
        numero_ctas_fn = fn.count()
        if numero_ctas_fn > 0:
            dates_fn = fn.aggregate(fecha_min = Min('fecha'), fecha_max = Max('fecha'))
            min_date_fn = dates_fn.get('fecha_min')
            max_date_fn = dates_fn.get('fecha_max')
            
            months_to_pay_fn = (max_date_fn.year - min_date_fn.year)*12 + (max_date_fn.month - min_date_fn.month +1)
        else: months_to_pay_fn = 0
        
        data = {
            'numero_ctas_ci': numero_ctas_ci,
            'months_to_pay_ci': months_to_pay_ci,
            'numero_ctas_fn': numero_ctas_fn,
            'months_to_pay_fn': months_to_pay_fn
        }
        
        return data
    
    def detalle_fraccciones(self):
        db = self._state.db
        f = fractales_ventas.objects.using(db).get(contrato__adj=self.pk)
        
        return f
    
    def data_otrosi(self):
        db = self._state.db
        today = date.today()
        
        tl = timeline.objects.using(db).filter(adj=self.pk, accion__icontains='reestructuracion')
        rd = self.recaudo_detallado()
        saldos = self.saldos_por_cartera()
        plan = PlanPagos.objects.using(db).filter(adj=self.pk, fecha__lte=today).order_by('fecha')
        
        
        if tl.exists():
            cantidad_otrosi = tl.count()
            ultimo_otrosi = tl.order_by('fecha').last().fecha
        else:
            cantidad_otrosi = 0
            ultimo_otrosi = None
        
        vr_contrato = self.valor
        capital_pagado = rd.get('capital')
        capital_pendiente = rd.get('saldo_cap')
        interes_cte_pendiente = 0
        interes_mora_pendiente = 0
        
        for q in plan:
            if q.is_pending():
                interes_cte_pendiente += q.pendiente().get('interes')
                interes_mora_pendiente += q.mora().get('valor')
                
        total_int_pdte = interes_cte_pendiente + interes_mora_pendiente
        ci_pdte = saldos.get('saldo_ci')
        fn_pdte = saldos.get('saldo_fn')
        
        
        data = {
            'fecha_ctr': self.fechacontrato,
            'cantidad_otrosi':cantidad_otrosi,
            'ultimo_otrosi': ultimo_otrosi,
            'vr_contrato': vr_contrato,
            'capital_pagado': capital_pagado,
            'capital_pendiente': capital_pendiente,
            'interes_cte_pendiente': interes_cte_pendiente,
            'interes_mora_pendiente': interes_mora_pendiente,
            'total_int_pdte':total_int_pdte,
            'ci_pdte':ci_pdte,
            'fn_pdte':fn_pdte,
        }
        
        return data

    
class PresupuestoCartera(models.Model):
    id_ppto = models.CharField(db_column='Id', primary_key=True, max_length=35)  # Field name made lowercase.
    periodo = models.CharField(db_column='Periodo', max_length=255, blank=True, null=True)  # Field name made lowercase.
    idadjudicacion = models.CharField(db_column='IdAdjudicacion', max_length=22, blank=True, null=True)  # Field name made lowercase.
    cliente = models.CharField(db_column='Cliente', max_length=120, blank=True, null=True)  # Field name made lowercase.
    tipocta = models.CharField(db_column='TipoCta', max_length=4, blank=True, null=True)  # Field name made lowercase.
    ncta = models.IntegerField(db_column='NCta')  # Field name made lowercase.
    idcta = models.CharField(db_column='IdCta', max_length=255)  # Field name made lowercase.
    tipocartera = models.CharField(db_column='TipoCartera', max_length=30, blank=True, null=True)  # Field name made lowercase.
    fecha = models.DateTimeField(db_column='Fecha', blank=True, null=True)  # Field name made lowercase.
    capital = models.DecimalField(db_column='Capital', max_digits=20, decimal_places=2, blank=True, null=True)  # Field name made lowercase.
    interes = models.DecimalField(db_column='Interes', max_digits=20, decimal_places=2, blank=True, null=True)  # Field name made lowercase.
    cuota = models.DecimalField(db_column='Cuota', max_digits=20, decimal_places=2, blank=True, null=True)  # Field name made lowercase.
    diasmora = models.IntegerField(db_column='DiasMora', blank=True, null=True)  # Field name made lowercase.
    mora = models.DecimalField(db_column='Mora', max_digits=20, decimal_places=2, blank=True, null=True)  # Field name made lowercase.
    asesor = models.CharField(db_column='Asesor', max_length=120, blank=True, null=True)  # Field name made lowercase.
    usuario = models.CharField(db_column='Usuario', max_length=20, blank=True, null=True)  # Field name made lowercase.
    fechaoperacion = models.DateField(db_column='FechaOperacion', blank=True, null=True)  # Field name made lowercase.
    edad = models.CharField(db_column='Edad', max_length=50, blank=True, null=True)  # Field name made lowercase.
    segmento = models.CharField(db_column='Segmento', max_length=200, blank=True, null=True)  # Field name made lowercase.

    class Meta:
        managed = False
        db_table = 'presupuesto_cartera'

class Promesas(models.Model):
    idadjudicacion = models.CharField(db_column='idAdjudicacion', primary_key=True, max_length=255)  # Field name made lowercase.
    nropromesa = models.CharField(db_column='NroPromesa', max_length=255, blank=True, null=True)
    fechapromesa = models.DateField(db_column='FechaPromesa', blank=True, null=True)  # Field name made lowercase.
    fechaentrega = models.DateField(db_column='FechaEntrega', blank=True, null=True)  # Field name made lowercase.
    fechaescritura = models.DateField(db_column='FechaEscritura', blank=True, null=True)  # Field name made lowercase.
    formapago = models.CharField(db_column='FormaPago', max_length=255, blank=True, null=True)  # Field name made lowercase.
    formaci = models.CharField(db_column='FormaCI', max_length=255, blank=True, null=True)  # Field name made lowercase.
    formasaldo = models.CharField(db_column='FormaSaldo', max_length=255, blank=True, null=True)  # Field name made lowercase.
    estado = models.CharField(db_column='Estado', max_length=255, blank=True, null=True)  # Field name made lowercase.
    entregado = models.BooleanField(db_column='Entregado', blank=True, null=True)  # Field name made lowercase.
    escriturado = models.BooleanField(db_column='Escriturado', blank=True, null=True)  # Field name made lowercase.
    prorroga = models.IntegerField(db_column='Prorroga',blank=True,null=True)
    usuariocrea = models.CharField(db_column='UsuarioCrea', max_length=255, blank=True, null=True)  # Field name made lowercase.
    usuarioaprueba = models.CharField(db_column='UsuarioAprueba', max_length=255, blank=True, null=True)  # Field name made lowercase.
    fechaaprueba = models.DateField(db_column='FechaAprueba', max_length=255, blank=True, null=True)  # Field name made lowercase.
    observaciones = models.CharField(db_column='Observaciones', max_length=255, blank=True, null=True)  # Field name made lowercase.
    ciudad = models.CharField(db_column='Ciudad', max_length=255, blank=True, null=True)  # Field name made lowercase.
    dias_prorroga = models.IntegerField(null=True,blank=True)
    

    class Meta:
        managed = False
        db_table = 'promesas'
        
        
        
    def titulares(self):
        db_name = self._state.db
        obj_adj = Adjudicacion.objects.using(db_name).get(pk = self.idadjudicacion)
        
        titulares_list = []
        clients = (obj_adj.idtercero1,obj_adj.idtercero2,
                   obj_adj.idtercero3,obj_adj.idtercero4)
        for client in clients:
            if client != '' and client != None:
                titulares_list.append(
                    clientes.objects.get(pk=client)
                )
        return titulares_list
    
    def fp(self):
        return self.formaci, self.formasaldo
    
    
    def general_info(self):
        db_name = self._state.db
        obj_adj = Adjudicacion.objects.using(db_name).get(pk = self.idadjudicacion)
        obj_inmueble = Inmuebles.objects.using(db_name).get(pk=obj_adj.idinmueble)
        fps = self.fp()
        obj_planpagos=PlanPagos.objects.using(db_name).filter(adj=obj_adj.pk)
        cuota_inicial=obj_planpagos.filter(tipocta='CI').aggregate(Sum('capital'))['capital__sum']
        if cuota_inicial==None: cuota_inicial=0
        info = {
            'valor':obj_adj.valor,
            'inmueble':obj_inmueble,
            'valor_en_letras':Utilidades().numeros_letras(obj_adj.valor),
            'ci':cuota_inicial,
            'saldo':obj_adj.valor - cuota_inicial,
            'fp_ci':fps[0],
            'fp_saldo':fps[1]
        }
        
        return info

class Inmuebles(models.Model):
    idinmueble = models.CharField(db_column='IdInmueble', primary_key=True, max_length=12)  # Field name made lowercase.
    etapa = models.CharField(db_column='Etapa', max_length=20, blank=True, null=True)  # Field name made lowercase.
    manzananumero = models.CharField(db_column='ManzanaNumero', max_length=5, blank=True, null=True)  # Field name made lowercase.
    lotenumero = models.CharField(db_column='LoteNumero', max_length=5, blank=True, null=True)  # Field name made lowercase.
    matricula = models.CharField(db_column='Matricula', unique=True, max_length=20, blank=True, null=True)  # Field name made lowercase.
    vrmetrocuadrado = models.DecimalField(db_column='VrMetroCuadrado', max_digits=20, decimal_places=2, blank=True, null=True)  # Field name made lowercase.
    estado = models.CharField(db_column='Estado', max_length=20, blank=True, null=True)  # Field name made lowercase.
    finobra = models.DateTimeField(db_column='FinObra', blank=True, null=True)  # Field name made lowercase.
    areaprivada = models.DecimalField(db_column='AreaPrivada', max_digits=10, decimal_places=2, blank=True, null=True)  # Field name made lowercase.
    areaconstruida = models.DecimalField(db_column='AreaConstruida', max_digits=10, decimal_places=2, blank=True, null=True)  # Field name made lowercase.
    area_lt = models.DecimalField(db_column='AREA_LT', max_digits=20, decimal_places=2, blank=True, null=True)  # Field name made lowercase.
    area_mz = models.DecimalField(db_column='AREA_MZ', max_digits=20, decimal_places=2, blank=True, null=True)  # Field name made lowercase.
    norte = models.DecimalField(db_column='NORTE', max_digits=20, decimal_places=2, blank=True, null=True)  # Field name made lowercase.
    lindero_norte = models.CharField(db_column='LINDERO_NORTE', max_length=255, blank=True, null=True)  # Field name made lowercase.
    colindante_norte = models.CharField(db_column='COLINDANTE_NORTE', max_length=255, blank=True, null=True)  # Field name made lowercase.
    sur = models.DecimalField(db_column='SUR', max_digits=20, decimal_places=2, blank=True, null=True)  # Field name made lowercase.
    lindero_sur = models.CharField(db_column='LINDERO_SUR', max_length=255, blank=True, null=True)  # Field name made lowercase.
    colindante_sur = models.CharField(db_column='COLINDANTE_SUR', max_length=255, blank=True, null=True)  # Field name made lowercase.
    este = models.DecimalField(db_column='ESTE', max_digits=20, decimal_places=2, blank=True, null=True)  # Field name made lowercase.
    lindero_este = models.CharField(db_column='LINDERO_ESTE', max_length=255, blank=True, null=True)  # Field name made lowercase.
    colidante_este = models.CharField(db_column='COLIDANTE_ESTE', max_length=255, blank=True, null=True)  # Field name made lowercase.
    oeste = models.DecimalField(db_column='OESTE', max_digits=20, decimal_places=2, blank=True, null=True)  # Field name made lowercase.
    lindero_oeste = models.CharField(db_column='LINDERO_OESTE', max_length=255, blank=True, null=True)  # Field name made lowercase.
    colindante_oeste = models.CharField(db_column='COLINDANTE_OESTE', max_length=255, blank=True, null=True)  # Field name made lowercase.
    fac_valor_via_principal = models.DecimalField(db_column='FAC_VALOR_VIA_PRINCIPAL', max_digits=10, decimal_places=2, blank=True, null=True)  # Field name made lowercase.
    fac_valor_area_social = models.DecimalField(db_column='FAC_VALOR_AREA_SOCIAL', max_digits=10, decimal_places=2, blank=True, null=True)  # Field name made lowercase.
    fac_valor_esquinero = models.DecimalField(db_column='FAC_VALOR_ESQUINERO', max_digits=10, decimal_places=2, blank=True, null=True)  # Field name made lowercase.
    obsbloqueo = models.CharField(db_column='ObsBloqueo', max_length=500, blank=True, null=True)  # Field name made lowercase.
    fechadesbloque = models.DateField(db_column='FechaDesBloque', blank=True, null=True)  # Field name made lowercase.
    usuariobloquea = models.CharField(db_column='UsuarioBloquea', max_length=30, blank=True, null=True)  # Field name made lowercase.
    meses = models.IntegerField(blank=True, null=True,db_column='MesesEntrega')
    
    class Meta:
        managed = False
        db_table = 'inmuebles'
        
    def porcentaje_derecho(self):
        p = self.areaprivada * 100 / self.area_lt
        p = round(p,2)
        return p
    
    def nro_fraccion(self):
        
        nf = self.idinmueble[-1]
        
        return nf
        
    def fracciones(self):
        
        db = self._state.db
        
        rsv = fractales_ventas.objects.using(db).filter(Q(contrato__estado__icontains='pendiente')|Q(contrato__estado__icontains='aprobado')|
                                                     Q(contrato__adj__estado='Aprobado')|Q(contrato__adj__estado='Pagado'),
                                                     contrato__inmueble= self.idinmueble)
        
        total_fracciones = rsv.aggregate(total_fracciones = Sum('nro_fracciones')).get('total_fracciones')
        
        
        total_fracciones = 0 if total_fracciones == None else total_fracciones
        return total_fracciones
        
    def porcentaje_vendido(self):
        
        perc = math.ceil(self.fracciones()* 100/25 )
        return perc
    
    def fractales_disponibles(self):
        return 25 - self.fracciones()
    
    def valor_fractal(self):
        valor_casa = 355000000
        valor_lote = self.areaprivada * self.areaconstruida * self.vrmetrocuadrado * (self.fac_valor_via_principal * self.fac_valor_area_social * self.fac_valor_esquinero)
        
        
        vr_fraccion = (valor_casa + valor_lote) / 25
        
        tr = Utilidades().redondear_numero(numero=vr_fraccion,multiplo=1000000,redondeo='>')
        
        return tr
    
    def numero_casa(self):
        
        casa = self.pk.split(' ')[1]
        
        return casa
        
    def id_lote(self):
        name = f'M{self.manzananumero}L{self.lotenumero}'
        return name
    
class formas_pago(models.Model):
    descripcion=models.CharField(max_length=255,db_column='descripcion',primary_key=True)
    cuenta_banco=models.CharField(max_length=255,db_column='cuenta_banco')
    cuenta_contable=models.CharField(max_length=255,db_column='cuenta_contable')
    cuenta_asociada = models.ForeignKey(cuentas_pagos,on_delete=models.PROTECT,null=True,blank=True)
    
    class Meta:
        managed=False
        db_table='formas_pago'
    
    def __str__(self):
        return self.descripcion
    
class Recaudos_general(models.Model):
    idrecaudo = models.IntegerField(db_column='IdRecaudo', primary_key=True)  # Field name made lowercase.
    idadjudicacion = models.CharField(db_column='IdAdjudicacion', max_length=12, blank=True, null=True)  # Field name made lowercase.
    fecha = models.DateField(db_column='Fecha')  # Field name made lowercase.
    numrecibo = models.CharField(db_column='NumRecibo', unique=True, max_length=12)  # Field name made lowercase.
    idtercero = models.CharField(db_column='IdTercero', max_length=12, blank=True, null=True)  # Field name made lowercase.
    operacion = models.CharField(db_column='Operacion', max_length=30)  # Field name made lowercase.
    valor = models.DecimalField(db_column='Valor', max_digits=20, decimal_places=2)  # Field name made lowercase.
    formapago = models.CharField(db_column='FormaPago', max_length=25, blank=True, null=True)  # Field name made lowercase.
    concepto = models.CharField(db_column='Concepto', max_length=12, blank=True, null=True)
    usuario = models.CharField(db_column='Usuario', max_length=12, blank=True, null=True)
    fecha_pago = models.DateField(db_column='Fecha_pago',null=True,blank=True)  # Field name made lowercase.
    
    class Meta:
        managed = False
        db_table = 'recaudos_general'
        
    
    def info_adj(self):
        db_name = self._state.db
        adj = Adjudicacion.objects.using(db_name).get(pk=self.idadjudicacion)
        
        return adj
    
    def pago_por_titular(self):
        adj = self.info_adj()
        
        titulares = adj.titulares()
        valor = self.valor
        if titulares.get('titular_2').nombrecompleto != "":
            valor = self.valor/2
        if titulares.get('titular_3').nombrecompleto != "":
            valor = self.valor/3
        if titulares.get('titular_4').nombrecompleto != "":
            valor = self.valor/4
            
        return valor
    
    def interfaz_contabilidad(self):
        db_name = self._state.db
        adj = self.info_adj()
        
        titulares = adj.titulares()
        porcentaje = 1
        if titulares.get('titular_2').nombrecompleto != "":
            porcentaje = 0.5
            if titulares.get('titular_3').nombrecompleto != "":
                porcentaje = 0.333333333333
                if titulares.get('titular_4').nombrecompleto != "":
                    porcentaje = 0.25
        
        
        c = consecutivos.objects.using(db_name).get(documento='RC')
        lista_titulares = []
        
        rec_det = Recaudos.objects.using(db_name
                                         ).filter(recibo=self.numrecibo
                                                         ).aggregate(
                                                             cap = Sum('capital'),
                                                             intcte = Sum('interescte'),
                                                             intmora = Sum('interesmora')
                                                         )
        capital = float(rec_det.get('cap'))
        intcte = float(rec_det.get('intcte'))
        intmora = float(rec_det.get('intmora'))
        
        fp = formas_pago.objects.using(db_name).filter(descripcion=self.formapago)
        if fp.exists():fp = fp[0].cuenta_contable
        else: fp = ''
         
        for t in titulares.values():
            if t.pk!='':
                if capital>0:
                    lista_titulares.append({
                        'tipocomprobante':"R",
                        'codigocomprobante':c.comprobante_contable,
                        'numerocomprobante':self.numrecibo,
                        'cuenta':c.cuenta_capital,
                        'naturaleza':'C',
                        'valor':round(capital * porcentaje,2),
                        'año':self.fecha.year,
                        'mes':self.fecha.month,
                        'dia':self.fecha.day,
                        'nit':t.pk,
                        'descripcion':t.nombrecompleto.upper() + ' - CAPITAL',
                    })
                if intcte > 0:
                    lista_titulares.append({
                        'tipocomprobante':"R",
                        'codigocomprobante':c.comprobante_contable,
                        'numerocomprobante':self.numrecibo,
                        'cuenta':c.cuenta_capital,
                        'naturaleza':'C',
                        'valor':round(intcte * porcentaje,2),
                        'año':self.fecha.year,
                        'mes':self.fecha.month,
                        'dia':self.fecha.day,
                        'nit':t.pk,
                        'descripcion':t.nombrecompleto.upper() + ' - INTERES CTE',
                    })
                if intmora > 0:
                    lista_titulares.append({
                        'tipocomprobante':"R",
                        'codigocomprobante':c.comprobante_contable,
                        'numerocomprobante':self.numrecibo,
                        'cuenta':c.cuenta_capital,
                        'naturaleza':'C',
                        'valor':round(intmora * porcentaje,2),
                        'año':self.fecha.year,
                        'mes':self.fecha.month,
                        'dia':self.fecha.day,
                        'nit':t.pk,
                        'descripcion':t.nombrecompleto.upper() + ' - INTERES MORA',
                    })
                    
        lista_titulares.append({
            'tipocomprobante':"R",
            'codigocomprobante':c.comprobante_contable,
            'numerocomprobante':self.numrecibo,
            'cuenta':fp,
            'naturaleza':'D',
            'valor':self.valor,
            'año':self.fecha.year,
            'mes':self.fecha.month,
            'dia':self.fecha.day,
            'nit':titulares.get('titular_1').pk,
            'descripcion':self.idadjudicacion +' - '+ titulares.get('titular_1').nombrecompleto,
        })
        
        return lista_titulares
    
    def recibo(self):
        return self.pk
    
    def contrato(self):
        return self.idadjudicacion      
     
    def infocontrato(self):
        db_name = self._state.db
        adj = self.info_adj()
        data = {
            'titulares':[
                adj.titulares().get('titular_1'),
            ],
            'inmueble':adj.idinmueble
        }
        return data
        
class Recaudos(models.Model):
    idrecaudo = models.IntegerField(primary_key=True,db_column='id')
    recibo = models.CharField(db_column='Recibo', max_length=12, blank=True, null=True)  # Field name made lowercase.
    fecha = models.DateField(db_column='Fecha', blank=True, null=True)  # Field name made lowercase.
    idcta = models.CharField(db_column='IdCta', max_length=20, blank=True, null=True)  # Field name made lowercase.
    idadjudicacion = models.CharField(db_column='IdAdjudicacion', max_length=12, blank=True, null=True)  # Field name made lowercase.
    capital = models.DecimalField(db_column='Capital', max_digits=16, decimal_places=2, blank=True, null=True)  # Field name made lowercase.
    interescte = models.DecimalField(db_column='InteresCte', max_digits=16, decimal_places=2, blank=True, null=True)  # Field name made lowercase.
    interesmora = models.DecimalField(db_column='InteresMora', max_digits=16, decimal_places=2, blank=True, null=True)  # Field name made lowercase.
    moralqd = models.DecimalField(db_column='MoraLqd', max_digits=16, decimal_places=2, blank=True, null=True)  # Field name made lowercase.
    fechaoperacion = models.DateField(db_column='FechaOperacion', blank=True, null=True)  # Field name made lowercase.
    usuario = models.CharField(db_column='Usuario', max_length=12, blank=True, null=True)  # Field name made lowercase.
    estado = models.CharField(db_column='Estado', max_length=20, blank=True, null=True)  # Field name made lowercase.

    class Meta:
        managed = False
        db_table = 'recaudos'

class Cargos_comisiones(models.Model):
    idcargo = models.IntegerField(primary_key=True,db_column='IdCarg')
    nombrecargo = models.CharField(db_column='NombreCargo', max_length=100, blank=True, null=True)  # Field name made lowercase.

    class Meta:
        managed = False
        db_table = 'cargos_comisiones'

class RecaudosNoradicados(models.Model):
    recibo = models.CharField(max_length=255,primary_key=True)
    contrato = models.CharField(max_length=255, blank=True, null=True)
    fecha = models.CharField(max_length=255, blank=True, null=True)
    concepto = models.CharField(max_length=255, blank=True, null=True)
    valor = models.IntegerField(blank=True, null=True)
    formapago= models.CharField(max_length=255, blank=True, null=True)
    usuario = models.CharField(max_length=255, blank=True, null=True)
    soportepago = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'recaudos_noradicados'
        
    def infocontrato(self):
        db_name = self._state.db
        contrato = ventas_nuevas.objects.using(db_name).get(pk=self.contrato)
        
        return contrato

class DescuentosCondicionados(models.Model):
    idadjudicacion = models.CharField(db_column='idAdjudicacion', primary_key=True, max_length=255)  # Field name made lowercase.
    fecha_condicion = models.DateField(blank=True, null=True)
    valor_condicion = models.IntegerField(blank=True, null=True)
    valor_dcto = models.IntegerField(blank=True, null=True)
    nueva_ci = models.IntegerField(blank=True, null=True)
    nuevo_saldo = models.IntegerField(blank=True, null=True)
    estado = models.CharField(db_column='estado',blank=True, null=True, max_length=255)

    class Meta:
        managed = False
        db_table = 'descuentos_condicionados'
        
class VerificacionOperaciones(models.Model):
    idadjudicacion = models.CharField(db_column='idAdjudicacion', primary_key=True, max_length=255)  # Field name made lowercase.
    enmendaduras = models.IntegerField(blank=True, null=True)
    doc_incompleta = models.IntegerField(blank=True, null=True)
    valores_incorrectos = models.IntegerField(blank=True, null=True)
    observaciones = models.CharField(max_length=300, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'verificacion_operaciones'

class documentos_contratos(models.Model):
    id_model=models.IntegerField(db_column='id',primary_key=True)
    adj= models.CharField(max_length=255,db_column='adj')
    descripcion_doc=models.CharField(max_length=255,db_column='descripcion_doc')
    fecha_carga=models.CharField(max_length=255,db_column='fecha_carga')
    usuario_carga=models.CharField(max_length=255,db_column='usuario_carga')
    class Meta:
        managed=False
        db_table='documentos_contratos'
        
class timeline(models.Model):
    id_line=models.IntegerField(db_column='id',primary_key=True)
    adj=models.CharField(max_length=255,db_column='adj')
    fecha=models.DateField(db_column='fecha')
    usuario=models.CharField(max_length=255,db_column='usuario')
    accion=models.CharField(max_length=255,db_column='accion')
    
    class Meta:
        managed=False
        db_table='timeline_adj'
        
class seguimientos(models.Model):
    id_seg= models.IntegerField(db_column='id',primary_key=True)
    adj=models.CharField(max_length=255,db_column='adj')
    fecha=models.DateField(db_column='fecha')
    tipo_seguimiento=models.CharField(max_length=255,db_column='tipo_seguimiento')
    forma_contacto=models.CharField(max_length=255,db_column='forma_contacto')
    respuesta_cliente=models.CharField(max_length=255,db_column='respuesta_cliente')
    valor_compromiso=models.IntegerField(db_column='valor_compromiso')
    fecha_compromiso=models.CharField(max_length=255,db_column='fecha_compromiso')
    usuario=models.CharField(max_length=255,db_column='usuario')
    
    class Meta:
        managed = False
        db_table='seguimientos'
        
class consecutivos(models.Model):
    id_consec=models.IntegerField(db_column='id',primary_key=True)
    documento=models.CharField(max_length=255,db_column='documento')
    consecutivo=models.IntegerField(db_column='consecutivo')
    prefijo=models.CharField(max_length=255,db_column='prefijo')
    comprobante_contable = models.CharField(max_length=255, blank=True, null=True)
    cuenta_capital = models.CharField(max_length=255, blank=True, null=True)
    cuenta_intcte = models.CharField(max_length=255, blank=True, null=True)
    cuenta_inmora = models.CharField(max_length=255, blank=True, null=True)
    cuenta_aux1 = models.CharField(max_length=255, blank=True, null=True)
    
    class Meta:
        managed = False
        db_table='consecutivos'
    
class ventas_nuevas(models.Model):
    
    id_venta = models.AutoField(db_column='Id', primary_key=True)  # Field name made lowercase.
    id_t1 = models.CharField(max_length=255)
    id_t2 = models.CharField(max_length=255, blank=True, null=True)
    id_t3 = models.CharField(max_length=255, blank=True, null=True)
    id_t4 = models.CharField(max_length=255, blank=True, null=True)
    inmueble = models.CharField(max_length=255)
    valor_venta = models.IntegerField()
    forma_pago=models.CharField(max_length=255, blank=True, null=True)
    cuota_inicial = models.IntegerField()
    cant_ci1 = models.IntegerField(blank=True, null=True)
    fecha_ci1 = models.DateField(blank=True, null=True)
    valor_ci1 = models.IntegerField(blank=True, null=True)
    cant_ci2 = models.IntegerField(blank=True, null=True)
    fecha_ci2 = models.DateField(blank=True, null=True)
    valor_ci2 = models.IntegerField(blank=True, null=True)
    cant_ci3 = models.IntegerField(blank=True, null=True)
    fecha_ci3 = models.DateField(blank=True, null=True)
    valor_ci3 = models.IntegerField(blank=True, null=True)
    cant_ci4 = models.IntegerField(blank=True, null=True)
    fecha_ci4 = models.DateField(blank=True, null=True)
    valor_ci4 = models.IntegerField(blank=True, null=True)
    cant_ci5 = models.IntegerField(blank=True, null=True)
    fecha_ci5 = models.DateField(blank=True, null=True)
    valor_ci5 = models.IntegerField(blank=True, null=True)
    cant_ci6 = models.IntegerField(blank=True, null=True)
    fecha_ci6 = models.DateField(blank=True, null=True)
    valor_ci6 = models.IntegerField(blank=True, null=True)
    cant_ci7 = models.IntegerField(blank=True, null=True)
    fecha_ci7 = models.DateField(blank=True, null=True)
    valor_ci7 = models.IntegerField(blank=True, null=True)
    saldo = models.IntegerField(blank=True, null=True)
    forma_saldo = models.CharField(max_length=255, blank=True, null=True)
    valor_ctas_fn = models.IntegerField(blank=True, null=True)
    inicio_fn = models.DateField(blank=True, null=True)
    nro_cuotas_fn = models.IntegerField(blank=True, null=True)
    valor_ctas_ce = models.IntegerField(blank=True, null=True)
    inicio_ce = models.DateField(blank=True, null=True)
    nro_cuotas_ce = models.IntegerField(blank=True, null=True)
    period_ce = models.CharField(max_length=255, blank=True, null=True)
    observaciones = models.TextField(blank=True, null=True)
    grupo = models.CharField(max_length=255, blank=True, null=True)
    fecha_contrato = models.DateField(blank=True, null=True)
    usuario = models.CharField(max_length=255, blank=True, null=True)
    estado = models.CharField(max_length=255, blank=True, null=True)
    usuarioaprueba = models.CharField(max_length=255, blank=True, null=True)
    fecha_aprueba= models.CharField(max_length=255, blank=True, null=True)
    tasa = models.DecimalField(db_column='tasa_fn',max_digits=6, decimal_places=4, blank=True, null=True) 
    tipo_venta = models.CharField(max_length=255, choices = [
        ('Lote','Lote'),
        ('Fractal','Fractal'),
    ], default="Lote", null=True, blank=True)
    adj = models.ForeignKey(Adjudicacion, on_delete=models.CASCADE,
                            null=True, blank=True)
    
    
    
    class Meta:
        managed = False
        db_table = 'nuevas_ventas'
    
    def __str__(self):
        return str(self.id_venta)
    
    def titulares(self):
        titulares_list = []
        clients = (self.id_t1,self.id_t2,self.id_t3,self.id_t4)
        for client in clients:
            if client != '' and client != None:
                titulares_list.append(
                    clientes.objects.get(pk=client)
                )
        return titulares_list
    
    def name_period(self,q):
        period = ''
        if self.period_ce == "1":
            period = 'mensual'
        elif self.period_ce == "3":
            period = 'trimestral'
        elif self.period_ce == "6":
            period = 'semestral'
        elif self.period_ce == "12":
            period = 'anual'
        
        if q>1:
            period += 'es'
        
        return period
            
        
    
    def fp(self):
        fci=''
        if self.cant_ci1!=None:
            if self.cant_ci1>1:
                fci+=f'{self.cant_ci1} cuotas mensuales de ${self.valor_ci1:,} a partir del {self.fecha_ci1}'
            else:
                fci+=f'1 cuota de ${self.valor_ci1:,} el {self.fecha_ci1}'
        if self.cant_ci2!=None:
            if self.cant_ci2>1:
                fci+=f'; {self.cant_ci2} cuotas mensuales de ${self.valor_ci2:,} a partir del {self.fecha_ci2}'
            else:
                fci+=f'; 1 cuota de ${self.valor_ci2:,} el {self.fecha_ci2}'
        if self.cant_ci3!=None:
            if self.cant_ci3>1:
                fci+=f'; {self.cant_ci3} cuotas mensuales de ${self.valor_ci3:,} a partir del {self.fecha_ci3}'
            else:
                fci+=f'; 1 cuota de ${self.valor_ci3:,} el {self.fecha_ci3}'
        if self.cant_ci4!=None:
            if self.cant_ci4>1:
                fci+=f'; {self.cant_ci4} cuotas mensuales de ${self.valor_ci4:,} a partir del {self.fecha_ci4}'
            else:
                fci+=f'; 1 cuota de ${self.valor_ci4:,} el {self.fecha_ci4}'
        if self.cant_ci5!=None:
            if self.cant_ci5>1:
                fci+=f'; {self.cant_ci5} cuotas mensuales de ${self.valor_ci5:,} a partir del {self.fecha_ci5}'
            else:
                fci+=f'; 1 cuota de ${self.valor_ci5:,} el {self.fecha_ci5}'
        if self.cant_ci6!=None:
            if self.cant_ci6>1:
                fci+=f'; {self.cant_ci6} cuotas mensuales de ${self.valor_ci6:,} a partir del {self.fecha_ci6}'
            else:
                fci+=f'; 1 cuota de ${self.valor_ci6:,} el {self.fecha_ci6}'
        if self.cant_ci7!=None:
            if self.cant_ci7>1:
                fci+=f'; {self.cant_ci7} cuotas mensuales de ${self.valor_ci7:,} a partir del {self.fecha_ci7}'
            else:
                fci+=f'; 1 cuota de ${self.valor_ci7:,} el {self.fecha_ci7}'
        formaCI=fci
        if self.nro_cuotas_fn>1:
            ffn=f'{self.nro_cuotas_fn} cuotas mensuales de ${self.valor_ctas_fn:,} a partir de {self.inicio_fn}'
        elif self.nro_cuotas_fn==0:
            ffn=''
        else:
            ffn=f'{self.nro_cuotas_fn} cuota de ${self.valor_ctas_fn:,} el {self.inicio_fn}'
        if self.nro_cuotas_ce!=None and self.nro_cuotas_ce!='':
            if self.nro_cuotas_ce>1:
                ffn+=f' y {self.nro_cuotas_ce} cuotas {self.name_period(2)} por valor de ${self.valor_ctas_ce:,} a partir de {self.inicio_ce}'
            else:
                ffn+=f' y {self.nro_cuotas_ce} cuota por valor de ${self.valor_ctas_ce:,} el {self.inicio_ce}'
        return fci, ffn
    
    
    def general_info(self):
        db_name = self._state.db
        obj_inmueble = Inmuebles.objects.using(db_name).get(pk=self.inmueble)
        fps = self.fp()
        info = {
            'valor':self.valor_venta,
            'inmueble':obj_inmueble,
            'valor_en_letras':Utilidades().numeros_letras(self.valor_venta),
            'ci':self.cuota_inicial,
            'saldo':self.valor_venta - self.cuota_inicial,
            'fp_ci':fps[0],
            'fp_saldo':fps[1]
        }
        
        return info
    
    def fractal(self):
        db_name = self._state.db
        fractales = fractales_ventas.objects.using(db_name).get(contrato=self.pk)
        obj_inmueble = Inmuebles.objects.using(db_name).get(pk=self.inmueble)
        cliente = clientes.objects.get(pk=self.id_t1)
        data = {
            'cantidad': fractales.nro_fracciones,
            'porcentaje_propiedad': fractales.nro_fracciones * 4,
            'valor_fraccion': fractales.valor_fraccion,
            'titular': cliente.nombrecompleto,
            'idtitular': self.id_t1,
            'disponibles': obj_inmueble.fractales_disponibles()
        }
        return data
    
    def documents(self):
        db_name = self._state.db
        docs = list(documentos_contratos.objects.using(db_name).filter(adj=self.pk).values())
        for doc in docs:
            doc_path = f"docs_andinasoft/doc_contratos/{db_name}/{doc['adj']}/{doc['descripcion_doc']}.pdf"
            try:
                doc['url'] = default_storage.url(doc_path)
            except Exception:
                doc['url'] = f"{settings.MEDIA_URL}{doc_path}"
        return docs
    
    def recaudos(self):
        db_name = self._state.db
        recaudos = RecaudosNoradicados.objects.using(db_name).filter(contrato=self.pk
                                                                     ).order_by('-fecha').values()
        
        return list(recaudos)
        

class AsignacionComisiones(models.Model):
    id_comision = models.CharField(db_column='Id', primary_key=True, max_length=11)  # Field name made lowercase.
    idadjudicacion = models.CharField(db_column='IdAdjudicacion', max_length=10, blank=True, null=True)  # Field name made lowercase.
    fecha = models.DateField(db_column='Fecha', blank=True, null=True)  # Field name made lowercase.
    idgestor = models.CharField(db_column='IdGestor', max_length=12, blank=True, null=True)  # Field name made lowercase.
    idcargo = models.CharField(db_column='IdCargo', max_length=12, blank=True, null=True)  # Field name made lowercase.
    comision = models.DecimalField(db_column='Comision', max_digits=6, decimal_places=4, blank=True, null=True)  # Field name made lowercase.
    usuario = models.CharField(db_column='Estado', max_length=20, blank=True, null=True)
    class Meta:
        managed = False
        db_table = 'asignacion_comisiones'

class CargosFijos(models.Model):
    idcargo = models.IntegerField(db_column='idcargo', primary_key=True)  # Field name made lowercase.
    cc_fija= models.CharField(db_column='cc_fijo', max_length=255, blank=True, null=True)
    porc_fijo= models.DecimalField(db_column='porc_fijo', max_digits=2, decimal_places=2, blank=True, null=True)
    class Meta:
        managed = False
        db_table = 'cargos_fijos'

class InfoCartera(models.Model):
    idadjudicacion = models.CharField(db_column='IdAdjudicacion', primary_key=True, max_length=255)  # Field name made lowercase.
    gestorasignado = models.CharField(db_column='GestorAsignado', max_length=255, blank=True, null=True)  # Field name made lowercase.
    segmento = models.CharField(db_column='Segmento', max_length=255, blank=True, null=True)  # Field name made lowercase.
    accionrecomendada = models.CharField(db_column='AccionRecomendada', max_length=255, blank=True, null=True)  # Field name made lowercase.

    class Meta:
        managed = False
        db_table = 'info_cartera'

class PlanPagos(models.Model):
    idcta = models.CharField(primary_key=True, max_length=255)
    tipocta = models.CharField(max_length=255, blank=True, null=True)
    nrocta = models.IntegerField(blank=True, null=True)
    adj = models.CharField(max_length=255, blank=True, null=True)
    capital = models.DecimalField(max_digits=14, decimal_places=2, blank=True, null=True)
    intcte = models.DecimalField(max_digits=14, decimal_places=2, blank=True, null=True)
    cuota = models.DecimalField(max_digits=14, decimal_places=2, blank=True, null=True)
    fecha = models.DateField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'plan_pagos'
        
    def is_pending(self):
        proyecto = self._state.db
        capital = Recaudos.objects.using(proyecto).filter(idcta = self.idcta
                    ).aggregate(
                capital=Sum('capital'),
            )

        capital_pagado = capital.get('capital') or 0
        if self.capital == capital_pagado:
            return False

        return True
    
    def is_expired(self):
        
        if self.fecha < date.today():
            return True
        
        return False
    
    def is_prx_to_expire(self):
        today = date.today()
        next_month = today+ timedelta(days=30)
        
        if  next_month >= self.fecha >= today:
            
            return True
        
        return False
            
    
                    
    def pagado(self):
        proyecto = self._state.db
        obj_recaudos_detallados= Recaudos.objects.using(proyecto).filter(idcta = self.idcta
                    ).aggregate(
                capital=Sum('capital'),
                interes=Sum('interescte'),
                mora = Sum('interesmora')
            )
        
        capital_pagado = obj_recaudos_detallados.get('capital')
        if capital_pagado is None: capital_pagado = 0
        interes_pagado = obj_recaudos_detallados.get('interes')
        if interes_pagado is None: interes_pagado = 0
        mora_pagada = obj_recaudos_detallados.get('mora')
        if mora_pagada is None: mora_pagada = 0
        total = capital_pagado + interes_pagado + mora_pagada
        
        
        data = {
            'capital':capital_pagado,
            'interes':interes_pagado,
            'mora':mora_pagada,
            'total':total,
        }
        
        return data
    
    def pendiente(self):
        pagado = self.pagado()
        pendiente_capital = self.capital - pagado.get('capital')
        pendiente_interes = self.intcte - pagado.get('interes')
        total = pendiente_capital + pendiente_interes
        
        data = {
            'capital':pendiente_capital,
            'interes':pendiente_interes,
            'total':total
        }
        
        return data
        
    def mora(self, dia_pago=None):
        if dia_pago is None:
            dia_pago = date.today()
        proyecto = self._state.db
        tasamv = 2
        dias_gracia = 15
        total_pendiente = self.pendiente().get('total',0)
        ultima_fecha_pago = Recaudos.objects.using(proyecto
            ).filter(Q(capital__gt=0)|Q(interescte__gt=0),idcta=self.idcta,
            ).aggregate(Max('fecha')
                        ).get('fecha__max',None)
        if ultima_fecha_pago is None: ultima_fecha_pago = self.fecha
        
        ultimo_rcdo_solo_mora = Recaudos.objects.using(proyecto
            ).filter(capital=0,interescte=0,interesmora__gt=0,idcta=self.idcta,
            ).aggregate(Max('fecha')
                        ).get('fecha__max',None)
        
        fecha_con_gracia = self.fecha  + relativedelta.relativedelta(days=15)
        dias_totales = 0
        if type(dia_pago) == datetime:
            dia_pago = dia_pago.date()
        if self.fecha < dia_pago:
            dias_totales = (dia_pago - self.fecha).days
        
        if  fecha_con_gracia >= dia_pago or total_pendiente <= 0:
            dias = 0
            valor = 0
        elif ultimo_rcdo_solo_mora and ultimo_rcdo_solo_mora > ultima_fecha_pago:
            dias = (dia_pago - ultima_fecha_pago).days
            total_mora = total_pendiente * dias * (Decimal(tasamv)/30)/100
            mora_pagada = Recaudos.objects.using(proyecto
            ).filter(fecha__lte=ultimo_rcdo_solo_mora,
                     fecha__gte=ultima_fecha_pago,
                     idcta=self.idcta,
            ).aggregate(total=Sum('interesmora')).get('total',0)
            if mora_pagada == None: mora_pagada = 0
            valor = int(total_mora - mora_pagada)
        else:
            if ultima_fecha_pago < self.fecha: ultima_fecha_pago = self.fecha
            dias = (dia_pago - ultima_fecha_pago).days
            if dias <0: dias = 0
            valor = total_pendiente * dias * (Decimal(tasamv)/30)/100
            valor = int(valor)
        
        data = {
            'dias_totales':dias_totales,
            'dias':dias,
            'dias_reales':(date.today() - self.fecha).days,
            'valor':valor
        }
        
        return data
    
#VISTAS
class Vista_Adjudicacion(models.Model):
    
    IdAdjudicacion = models.CharField(max_length=255,db_column='IdAdjudicacion',primary_key=True)
    FechaContrato=models.DateField(db_column='FechaContrato')
    Nombre=models.CharField(max_length=255,db_column='Nombre')
    Inmueble=models.CharField(max_length=255,db_column='Inmueble')
    Valor=models.DecimalField(max_digits=14, decimal_places=2,db_column='Valor')
    Estado=models.CharField(max_length=255,db_column='Estado')
    Origen=models.CharField(max_length=255,db_column='Origen')
    tipo_cartera=models.CharField(max_length=255,db_column='TipoCartera')
    cta_inicial=models.DecimalField(db_column='Cuota_inicial',max_digits=14,decimal_places=2)
    saldo=models.DecimalField(db_column='Saldo',max_digits=14,decimal_places=2)
    oficina=models.CharField(max_length=255,db_column='Oficina')
    
    class Meta:
        managed = False
        db_table='info_adjudicaciones'
        
    def fractal(self):
        db = self._state.db
        adj = Adjudicacion.objects.using(db).filter(pk=self.IdAdjudicacion)
        
        jsondata = JsonRender(adj, query_functions=['presupuesto']).render()[0]
        
        return jsondata
    
    def rcdo_total(self):
        rcdos = Recaudos_general.objects.using(self._state.db).filter(idadjudicacion=self.IdAdjudicacion)
        
        total = rcdos.aggregate(total=Sum('valor')).get('total')
        
        total = 0 if total is None else total
        
        return total
    
    def detalle_fraccciones(self):
        db = self._state.db
        f = fractales_ventas.objects.using(db).get(contrato__adj=self.pk)
        
        return f
        

class Pagocomision(models.Model):
    id_comision = models.CharField(db_column='Id', max_length=11)  # Field name made lowercase.
    fecha = models.DateField(blank=True, null=True)
    idadjudicacion = models.CharField(max_length=12, blank=True, null=True)
    idgestor = models.CharField(max_length=12, blank=True, null=True)
    idcargo = models.CharField(max_length=12, blank=True, null=True)
    tasacomision = models.DecimalField(max_digits=6, decimal_places=3, blank=True, null=True)
    comision = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    retefuente = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    dctoanticipo = models.DecimalField(db_column='DctoAnticipo', max_digits=10, decimal_places=2, blank=True, null=True)  # Field name made lowercase.
    pagoneto = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    transaccion = models.IntegerField(blank=True, null=True)
    veces = models.IntegerField(blank=True, null=True)
    veriact = models.IntegerField(blank=True, null=True)
    id_pago=models.AutoField(db_column='id_pago', primary_key=True)

    class Meta:
        managed = False
        db_table = 'pagocomision'

class saldos_adj(models.Model):
    adj=models.CharField(db_column='adj',max_length=255)
    tipocta=models.CharField(max_length=255,db_column='tipocta')
    idcta=models.CharField(max_length=255,db_column='idcta',primary_key=True)
    nrocta=models.IntegerField(db_column='nrocta')
    fecha=models.DateField(db_column='fecha')
    capital=models.DecimalField(max_digits=14, decimal_places=2,db_column='capital')
    intcte=models.DecimalField(max_digits=14, decimal_places=2,db_column='intcte')
    cuota=models.DecimalField(max_digits=14, decimal_places=2,db_column='cuota')
    rcdocapital=models.DecimalField(max_digits=14, decimal_places=2,db_column='rcdocapital')
    rcdointcte=models.DecimalField(max_digits=14, decimal_places=2,db_column='rcdointcte')
    rcdointmora=models.DecimalField(max_digits=14, decimal_places=2,db_column='rcdointmora')
    saldocapital=models.DecimalField(max_digits=14, decimal_places=2,db_column='saldocapital')
    saldointcte=models.DecimalField(max_digits=14, decimal_places=2,db_column='saldoint')
    saldocuota=models.DecimalField(max_digits=14, decimal_places=2,db_column='saldocuota')
    diasmora=models.IntegerField(db_column='diasmora')
    saldomora=models.DecimalField(max_digits=14, decimal_places=2,db_column='saldomora')
    
    class Meta:
        managed = False
        db_table='saldos_cuotas'
        
class Pqrs(models.Model):
    id_pqrs = models.AutoField(primary_key=True)
    idadjudicacion = models.CharField(db_column='idAdjudicacion', max_length=255, blank=True, null=True)  # Field name made lowercase.
    tipo = models.CharField(max_length=255, blank=True, null=True)
    fecha_radicado = models.DateField(blank=True, null=True)
    fecha_vencimiento = models.DateField(blank=True, null=True)
    fecha_respuesta = models.DateField(blank=True, null=True)
    estado = models.CharField(max_length=255, blank=True, null=True)
    req_respuesta = models.CharField(max_length=255, blank=True, null=True)
    tipo_respuesta = models.CharField(max_length=255, blank=True, null=True)
    doc_peticion = models.CharField(max_length=255, blank=True, null=True)
    doc_respuesta = models.CharField(max_length=255, blank=True, null=True)
    doc_envio = models.CharField(max_length=255, blank=True, null=True)
    usuario_radica = models.CharField(max_length=255, blank=True, null=True)
    usuario_cierra = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'pqrs'

class Parametros_Operaciones(models.Model):
    descripcion = models.CharField(db_column='Descripcion', max_length=255, primary_key=True)
    estado = models.BooleanField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'parametros'
    
class EntregaManzanas(models.Model):
    manzana = models.CharField(max_length=255, primary_key=True)
    meses = models.IntegerField(blank=True, null=True,db_column='MesesEntrega')

    class Meta:
        managed = False
        db_table = 'entrega_manzanas'

class fractales_ventas(models.Model):
    contrato = models.OneToOneField(ventas_nuevas, on_delete = models.CASCADE)
    nro_fracciones = models.IntegerField()
    valor_fraccion = models.FloatField()
    valor_lista_fraccion = models.FloatField()
    valor_venta = models.FloatField()
    
    class Meta:
        managed = False
        db_table = 'fractales_ventas'
