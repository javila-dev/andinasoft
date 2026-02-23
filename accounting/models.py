from django.db import models
from django.contrib.auth.models import User
from andinasoft.models import empresas,cuentas_pagos, proyectos, Gtt, Countries, States, Cities
from andinasoft.shared_models import Pagocomision, ventas_nuevas
from django.db.models.aggregates import Sum, Max, Min

class info_interfaces(models.Model):
    id_doc = models.AutoField(primary_key=True)
    empresa = models.ForeignKey(empresas,on_delete=models.CASCADE)
    descripcion = models.CharField(max_length=255)
    tipo_doc = models.CharField(max_length=255,null=True,blank=True)
    cuenta_debito_1 = models.CharField(max_length=255,null=True,blank=True)
    cuenta_debito_2 = models.CharField(max_length=255,null=True,blank=True)
    cuenta_debito_3 = models.CharField(max_length=255,null=True,blank=True)
    cuenta_credito_1 = models.CharField(max_length=255,null=True,blank=True)
    cuenta_credito_2 = models.CharField(max_length=255,null=True,blank=True)
    cuenta_credito_3 = models.CharField(max_length=255,null=True,blank=True)
    
    class Meta:
        verbose_name = 'Interfaz'
        verbose_name_plural = 'Interfaces'
    
    def __str__(self):
        return f'{self.empresa}|{self.descripcion}|{self.cuenta_credito_1}'    
    
class Facturas(models.Model):
    nroradicado = models.AutoField(db_column='NroRadicado', primary_key=True)
    fecharadicado = models.DateField(db_column='FechaRadica',auto_now_add=True,blank=True) 
    nrofactura = models.CharField(db_column='NroFactura', max_length=255, blank=True, null=True)
    fechafactura = models.DateField(db_column='FechaFactura', blank=True, null=True)
    idtercero = models.CharField(db_column='idTercero', max_length=255, blank=True, null=True)
    nombretercero = models.CharField(db_column='NombreTercero', max_length=255, blank=True, null=True)
    descripcion = models.CharField(null=True,blank=True,max_length=255)
    empresa = models.ForeignKey(empresas,on_delete=models.CASCADE,related_name='empresa_causa')
    valor = models.IntegerField(db_column='Valor', blank=True, null=True)
    pago_neto = models.IntegerField(db_column='PagoNeto', blank=True, null=True)
    fechavenc = models.DateField(db_column='FechaVenc', blank=True, null=True) 
    nrocausa = models.CharField(db_column='NroCausa', max_length=255, blank=True, null=True)
    cuenta_por_pagar = models.ForeignKey(info_interfaces,on_delete=models.PROTECT,null=True,blank=True)
    secuencia_cxp = models.IntegerField(null=True,blank=True)
    fechacausa = models.DateField(db_column='FechaCausa', blank=True, null=True)
    origen_choices = (
        ('Radicado','Radicado'),
        ('Proyectos','Proyectos'),
        ('Comisiones','Comisiones'),
        ('GTT','GTT'),
        ('Otros','Otros'),
    )
    origen = models.CharField(db_column='Origen', max_length=255, choices=origen_choices, default='Radicado')
    oficinas_choices = (
        ('MONTERIA','MONTERIA'),
        ('MEDELLIN','MEDELLIN')
        
    )
    oficina = models.CharField(db_column='Oficina', max_length=255,blank=True,null=True,choices=oficinas_choices)
    soporte_radicado = models.FileField(upload_to='Facturas/Facturas',null=True,blank=True)
    soporte_causacion = models.FileField(upload_to='Facturas/Causacion',null=True,blank=True)
    proyecto_rel = models.CharField(max_length=255, choices=(
        ('Perla del Mar','Perla del Mar'),
        ('Caracola del Mar','Caracola del Mar'),
        ('Bugambilias','Bugambilias'),
        ('Vegas de Venecia','Vegas de Venecia'),
        ('Carmelo Reservado','Carmelo Reservado'),
        ('Fractal','Fractal'),
        ('Alttum Venecia','Alttum Venecia'),
        ('Alttum Caribe','Alttum Caribe'),
        ('Integral','Integral'),
    ), null=True,blank=True)
    centro_costo = models.CharField(max_length=255, choices=(
        ('Administracion','Administracion'),
        ('Comercial','Comercial'),
        ('Proyectos','Proyectos'),
        ('Operacion club','Operacion club'),
        ('Integral','Integral'),
        ('Impuestos','Impuestos'),
        ('Tierras','Tierras'),
    ), null=True,blank=True)
    
    class Meta:
        verbose_name = 'Factura'
        verbose_name_plural = 'Facturas'
        constraints = [
            models.UniqueConstraint(fields=['idtercero', 'nrofactura'], name='unique_factura')
        ]
    
    def __str__(self):
        return str(self.pk)

class history_facturas(models.Model):
    idmvto = models.AutoField(primary_key=True)
    factura = models.ForeignKey(Facturas,on_delete=models.CASCADE)
    usuario = models.ForeignKey(User,on_delete=models.PROTECT)
    fecha = models.DateTimeField(auto_now=True)
    accion = models.CharField(max_length=255)
    ubicacion = models.CharField(choices=(
        ('Recepcion','Recepcion'),
        ('Contabilidad','Contabilidad'),
        ('Tesoreria','Tesoreria'),
        ('Solicitante','Solicitante')
    ),max_length=255)
    
    class Meta:
        verbose_name = 'Historial factura'
        verbose_name_plural = 'Historial Facturas'

class conciliaciones(models.Model):
    id_concilacion = models.AutoField(primary_key=True)
    empresa = models.ForeignKey(empresas,on_delete=models.CASCADE)
    cuenta_asociada = models.ForeignKey(cuentas_pagos,on_delete=models.CASCADE)
    usuario_crea = models.ForeignKey(User,on_delete=models.PROTECT)
    fecha_crea = models.DateField()
    
    class Meta:
        verbose_name = 'Conciliacion'
        verbose_name_plural = 'Conciliaciones'

class egresos_contable(models.Model):
    id_mvto = models.AutoField(primary_key=True)
    empresa = models.ForeignKey(empresas,on_delete=models.CASCADE)
    cuenta = models.ForeignKey(cuentas_pagos,on_delete=models.PROTECT)
    comprobante = models.CharField(max_length=255)
    fecha = models.DateField()
    descripcion = models.CharField(max_length=255)
    valor = models.DecimalField(max_digits=15,decimal_places=2)
    estado = models.CharField(max_length=255,choices=(
        ('CONCILIADO','CONCILIADO'),
        ('SIN CONCILIAR','SIN CONCILIAR')
    ),default='SIN CONCILIAR')
    conciliacion = models.ForeignKey(conciliaciones,on_delete=models.PROTECT,null=True,blank=True)
    tipo = models.CharField(max_length=255,choices=(
        ('PAGO','PAGO'),
        ('TRANSFERENCIA','TRANSFERENCIA'),
        ('ANTICIPO','ANTICIPO'),
        ('CONSIGNACION','CONSIGNACION'),
        ('INTEREMPRESAS','INTEREMPRESAS'),
    ),null=True,blank=True)
    proyecto = models.ForeignKey(proyectos,on_delete=models.CASCADE,null=True,blank=True)
    soporte_egreso = models.FileField(upload_to='Facturas/Egresos contables', null=True,blank=True)
    
    
    
    class Meta:
        verbose_name = 'Egreso contable'
        verbose_name_plural = 'Egresos contables'
        constraints = [
            models.UniqueConstraint(fields=['comprobante', 'cuenta'], name='unique_egreso')
        ]
    



class Pagos(models.Model):
    idpago = models.AutoField(db_column='IdPago', primary_key=True)
    nroradicado = models.ForeignKey(Facturas,on_delete=models.PROTECT)
    valor = models.IntegerField()
    usuario = models.ForeignKey(User,on_delete=models.CASCADE)
    fecha_pago = models.DateField()
    fecha_registro = models.DateTimeField(auto_now=True)
    cuenta = models.ForeignKey(cuentas_pagos,on_delete=models.PROTECT,related_name='cuenta_pago')
    empresa = models.ForeignKey(empresas,on_delete=models.PROTECT,related_name='empresa_pago')
    soporte_pago = models.FileField(upload_to='Facturas/Soportes de pago', null=True,blank=True)
    
    class Meta:
        verbose_name = 'Pago'
        verbose_name_plural = 'Pagos'
        
class Anticipos(models.Model):
    id_ant = models.AutoField(primary_key=True)
    valor = models.IntegerField()
    usuario = models.ForeignKey(User,on_delete=models.CASCADE)
    id_tercero = models.CharField(max_length=255)
    nombre_tercero = models.CharField(max_length=255,null=True,blank=True)
    descripcion = models.CharField(max_length=255)
    fecha_pago = models.DateField()
    fecha_registro = models.DateTimeField(auto_now=True)
    tipo_anticipo = models.ForeignKey(info_interfaces,on_delete=models.PROTECT,related_name='tipo_anticipo')
    cuenta = models.ForeignKey(cuentas_pagos,on_delete=models.PROTECT,related_name='cuenta_anticipo')
    empresa = models.ForeignKey(empresas,on_delete=models.PROTECT,related_name='empresa_anticipo')
    soporte_pago = models.FileField(upload_to='Anticipos/Soportes de pago', null=True,blank=True)
    oficina = models.CharField(choices=(
            ('MEDELLIN','MEDELLIN'),
            ('MONTERIA','MONTERIA'),),
        max_length=255)
    
    
    class Meta:
        verbose_name = 'Pago de anticipo'
        verbose_name_plural = 'Pago de anticipos'
        
    def is_linked(self):
        banco = egresos_banco.objects.filter(anticipo_asociado=self.pk)
        if banco.exists(): return True
        return False

class transferencias_companias(models.Model):
    id_transf = models.AutoField(primary_key=True)
    fecha = models.DateField()
    empresa_entra = models.ForeignKey(empresas,on_delete=models.PROTECT,related_name='empresa_entra')
    cuenta_entra = models.ForeignKey(cuentas_pagos,on_delete=models.PROTECT,related_name='cuenta_entra')
    empresa_sale = models.ForeignKey(empresas,on_delete=models.PROTECT,related_name='empresa_sale')
    cuenta_sale = models.ForeignKey(cuentas_pagos,on_delete=models.PROTECT,related_name='cuenta_sale')
    valor = models.IntegerField()
    oficina = models.CharField(choices=(
            ('MEDELLIN','MEDELLIN'),
            ('MONTERIA','MONTERIA'),),
        max_length=255)
    usuario = models.ForeignKey(User,on_delete=models.PROTECT)
    soporte_pago = models.FileField(upload_to='Transferencias/Soportes de pago', null=True,blank=True)
    
    class Meta:
        verbose_name = 'Transferencia'
        verbose_name_plural = 'Transferencias'
        
class egresos_banco(models.Model):
    id_mvto = models.AutoField(primary_key=True)
    empresa = models.ForeignKey(empresas,on_delete=models.CASCADE)
    cuenta = models.ForeignKey(cuentas_pagos,on_delete=models.PROTECT)
    fecha = models.DateField()
    descripcion = models.CharField(max_length=255)
    referencia = models.CharField(max_length=255,blank=True,null=True)
    valor = models.DecimalField(max_digits=15,decimal_places=2)
    estado = models.CharField(max_length=255,choices=(
        ('CONCILIADO','CONCILIADO'),
        ('SIN CONCILIAR','SIN CONCILIAR')
    ),default='SIN CONCILIAR')
    conciliacion = models.ForeignKey(conciliaciones,on_delete=models.PROTECT,null=True,blank=True)
    pago_asociado = models.ForeignKey(Pagos, on_delete=models.PROTECT,null=True,blank=True)
    anticipo_asociado = models.ForeignKey(Anticipos, on_delete=models.PROTECT,null=True,blank=True)
    transferencia_asociada = models.ForeignKey(transferencias_companias, on_delete=models.PROTECT,null=True,blank=True)
    usado_agente = models.BooleanField(default=False, help_text='Indica si este movimiento ya fue usado por el agente de conciliación automática')
    fecha_uso_agente = models.DateTimeField(null=True, blank=True, help_text='Fecha en que el agente usó este movimiento')
    recibo_asociado_agente = models.CharField(max_length=255, null=True, blank=True, help_text='Número de recibo con el que el agente usó este movimiento')
    proyecto_asociado_agente = models.CharField(max_length=255, null=True, blank=True, help_text='Proyecto del recibo con el que el agente usó este movimiento')


    class Meta:
        verbose_name = 'Egreso banco'
        verbose_name_plural = 'Egresos banco'
        
    def tipo_pago(self):
        tipo = None
        objeto = None
        if self.pago_asociado != "" and self.pago_asociado != None:
            tipo = 'Pago'
            objeto = self.pago_asociado
        elif self.anticipo_asociado != "" and self.anticipo_asociado != None:
            tipo = 'Anticipo'
            objeto = self.anticipo_asociado
        elif self.transferencia_asociada != "" and self.transferencia_asociada != None:
            tipo = 'Transferencia'
            objeto = self.transferencia_asociada
        
        return tipo, objeto
    
    
class saldos_banco(models.Model):
    fecha = models.DateField()
    cuenta = models.ForeignKey(cuentas_pagos,on_delete=models.PROTECT)
    valor = models.FloatField()
    usuario = models.ForeignKey(User, on_delete = models.PROTECT)
    
    

class planilla_movimiento(models.Model):
    id_mvto = models.AutoField(primary_key=True)
    mes = models.IntegerChoices('mes',
            ('Enero','Febrero','Marzo','Abril',
            'Mayo','Junio','Julio','Agosto',
            'Septiembre','Octubre','Noviembre','Diciembre'))
    año = models.IntegerField()
    saldo_inicial = models.DecimalField(decimal_places=2,max_digits=20)
    cuenta = models.ForeignKey(cuentas_pagos,on_delete=models.PROTECT)
    fecha_cierre = models.DateField(null=True,blank=True)
    usuario_cierra = models.ForeignKey(User,on_delete=models.PROTECT,null=True,blank=True)
    



class otros_ingresos(models.Model):
    id_ingreso = models.AutoField(primary_key=True)
    fecha_ing = models.DateField()
    id_tercero = models.CharField(max_length=255)
    nombre_tercero = models.CharField(max_length=255)
    descripcion = models.CharField(max_length=255)
    valor = models.IntegerField()
    usuario = models.ForeignKey(User,on_delete=models.PROTECT)
    empresa = models.ForeignKey(empresas,on_delete=models.PROTECT)
    cuenta = models.ForeignKey(cuentas_pagos,on_delete=models.PROTECT)
    oficina = models.CharField(choices=(
            ('MEDELLIN','MEDELLIN'),
            ('MONTERIA','MONTERIA'),),
        max_length=255)
    fecha_registro = models.DateTimeField(auto_now=True)
    soporte = models.FileField(upload_to='Otros Ingresos', null=True,blank=True)
    
    
    class Meta:
        verbose_name = 'Ingreso'
        verbose_name_plural = 'Otros ingresos'
        

    

class docs_cuentas_oficinas(models.Model):
    id_rel = models.AutoField(primary_key=True)
    cuenta = models.ManyToManyField(cuentas_pagos)
    empresa = models.ForeignKey(empresas,on_delete=models.PROTECT)
    documento = models.CharField(max_length=255)
    
    class Meta:
        verbose_name = 'Documento rel'
        verbose_name_plural = 'Tipos docs cuentas'

class docs_tipos_oficinas(models.Model):
    id_rel = models.AutoField(primary_key=True)
    tipo = models.CharField(max_length=255)
    oficina = models.CharField(choices=(
        ('MEDELLIN','MEDELLIN'),
        ('MONTERIA','MONTERIA'),
    ),max_length=255)
    documento = models.CharField(max_length=255)
    empresa = models.ForeignKey(empresas,on_delete=models.PROTECT)
    
    class Meta:
        verbose_name = 'Documento rel'
        verbose_name_plural = 'Tipos docs conceptos'

class cuentas_intercompanias(models.Model):
    empresa_desde = models.ForeignKey(empresas,on_delete=models.PROTECT,related_name='empresa_desde')
    empresa_hacia = models.ForeignKey(empresas,on_delete=models.PROTECT,related_name='empresa_hacia')
    cuenta_por_cobrar = models.BigIntegerField()
    cuenta_por_pagar = models.BigIntegerField()
    documento = models.CharField(max_length=5)
    
    class Meta:
        verbose_name = 'Cuenta intercompañia'
        verbose_name_plural = 'Cuentas intercompañia'
        unique_together =['empresa_desde','empresa_hacia']
        
class pago_detallado_relacionado(models.Model):
    pago = models.ForeignKey(Pagos, on_delete=models.CASCADE)
    id_tercero = models.CharField(max_length=255)
    nombre_tercero = models.CharField(max_length=255)
    vencimiento = models.IntegerField()
    valor = models.IntegerField()
    tipo = models.CharField(max_length=255,null=True,blank=True)

    class Meta:
        verbose_name = 'Pago relacionado'
        verbose_name_plural = 'Pagos relacionados'
        unique_together =['pago','id_tercero']

    def __str__(self):
        return f'{self.nombre_tercero}-{self.valor}'

class saldos_cuentas_tesoreria(models.Model):
    cuenta = models.ForeignKey(cuentas_pagos,on_delete=models.PROTECT)
    fecha = models.DateField()
    fecha_registro = models.DateTimeField(auto_now_add=True)
    saldo_inicial = models.FloatField()
    saldo_teorico = models.FloatField(null=True,blank=True)
    usuario = models.ForeignKey(User,on_delete=models.PROTECT)
    forma = models.CharField(null=True,blank=True,max_length=500)
    
    class Meta:
        verbose_name = 'Saldo inicio dia'
        verbose_name_plural = 'Saldos inicio dia'
        unique_together =['cuenta','fecha']
    
class distribucion_centros_costos(models.Model):
    cedula = models.CharField(max_length=255)
    centro = models.CharField(max_length=255)
    subcentro = models.CharField(max_length=255,null=True,blank=True)
    porcentaje = models.FloatField()
    
    class Meta:
        verbose_name = 'Distribucion centro de costo'
        verbose_name_plural = 'Distribucion centros de costos'
        
class solicitud_anticipos(models.Model):
    id_solicitud = models.AutoField(primary_key = True)
    empresa = models.ForeignKey(empresas, on_delete = models.PROTECT)
    usuario_solicita = models.ForeignKey(User, on_delete = models.PROTECT,
                                         related_name = 'user_ant_solicita')
    fecha = models.DateField(auto_now_add=True)
    descripcion = models.CharField(max_length = 255)
    valor = models.IntegerField()
    estado = models.CharField(max_length =255, choices =(
        ('pendiente','Pendiente'),
        ('aprobado','aprobado'),
        ('pagado','Pagado'),
        ('legalizado','Legalizado'),
        ('rechazado','Rechazado')
    ), default='pendiente')
    oficina = models.CharField(max_length =255, choices =(
        ('MEDELLIN','MEDELLIN'),
        ('MONTERIA','MONTERIA'),
    ))
    quien_aprueba = models.ForeignKey(User,on_delete=models.PROTECT,
                                        related_name = 'user_who_approve',
                                        null=True,blank=True)
    usuario_aprueba = models.ForeignKey(User,on_delete=models.PROTECT,
                                        related_name = 'user_ant_aprueba',
                                        null=True,blank=True)
    pago_anticipo = models.ForeignKey(Anticipos, on_delete = models.PROTECT,
                                      null=True, blank=True)
    
    class Meta:
        verbose_name = 'Solicitud de anticipo'
        verbose_name_plural = 'Solicitudes de anticipos'
        
    def has_reembolsos(self):
        obj_reembolsos = reintegros_anticipos.objects.filter(id_anticipo = self.pk)
        if obj_reembolsos.exists():
            return True
        return False
    
    def recibo_reembolso(self):
        if self.has_reembolsos():
            reembolso = reintegros_anticipos.objects.filter(id_anticipo = self.pk)[0]
            ingreso = reembolso.id_otros_ingresos.pk
            return ingreso
        return None
            
    def data_user_solicita(self):
        data = {
            'id':self.usuario_solicita.profiles.identificacion,
            'name':self.usuario_solicita.get_full_name().upper()
        }
        
        return data

    def has_legalizacion(self):
        obj_leg = legalizacion_anticipos.objects.filter(anticipo = self.pk)
        if obj_leg.exists():
            return True
        return False
    
    def fecha_legalizacion(self):
        obj_leg = legalizacion_anticipos.objects.filter(anticipo=self.pk)
        
        fecha_max = obj_leg.aggregate(fecha_max=Max('fecha_legalizacion')).get('fecha_max')
        
        return fecha_max
            
            
    def total_legalizado(self):
        obj_leg = legalizacion_anticipos.objects.filter(anticipo=self.pk)
        total = obj_leg.aggregate(total=Sum('valor')).get('total')
        total = total if total != None else 0
        
        return total
    
    def reembolsos(self):
        total_leg = self.total_legalizado()
        if self.valor > total_leg:
            a = 'empresa'
        else:
            a = 'empleado'
            
        valor = abs(self.valor - total_leg)
        
        
        data = {
            'reembolso_a':a,
            'valor':valor,
            'detalle':reintegros_anticipos.objects.filter(id_anticipo=self.pk)
        }
        
        return data
        
    
class Partners(models.Model):
    idTercero=models.CharField(primary_key=True,max_length=255)
    dc_types = (
        ('13',    'Cédula de ciudadanía'),
        ('31',	'NIT'),
        ('22',	'Cédula de extranjería'),
        ('42',	'Documento de identificación extranjero'),
        ('50',	'NIT de otro país'),
        ('R-00-PN',	'No obligado a registrarse en el RUT PN'),
        ('91',	'NUIP'),
        ('41',	'Pasaporte'),
        ('47',	'Permiso especial de permanencia PEP'),
        ('11',	'Registro civil'),
        ('43',	'Sin identificación del exterior o para uso definido por la DIAN'),
        ('21',	'Tarjeta de extranjería'),
        ('12',	'Tarjeta de identidad'),
    )
    document_type = models.CharField(choices=dc_types,max_length=255, null=True,blank=True)
    nombres=models.CharField(max_length=255)
    apellidos=models.CharField(max_length=255, null=True, blank=True)
    telefono=models.CharField(max_length=255,null=True,blank=True)    
    pais=models.ForeignKey(Countries, on_delete =models.PROTECT)
    estado =models.ForeignKey(States, on_delete =models.PROTECT)
    ciudad=models.ForeignKey(Cities, on_delete =models.PROTECT)
    direccion=models.CharField(max_length=255,null=True,blank=True)
    email=models.EmailField()
    responsabilidad_fiscal=models.CharField(max_length=255,choices=(
        ('R-99-PN','No Aplica - Otros*'),
        ('O-13','Gran contribuyente'),
        ('O-15','Autorretenedor'),
        ('O-23','Agente de retención IVA'),
        ('O-47','Régimen simple de tributación')
    ), null=True,blank=True)    
    fecha_actualizacion=models.DateField(auto_now=True)
    fecha_creacion=models.DateField(auto_now_add=True)
    siigo_id = models.CharField(max_length=255, null=True,blank=True)
    soporte_identificacion = models.FileField(upload_to='Proveedores', null=True, blank=True)
    
    class Meta:
        verbose_name = 'Proveedor'
        verbose_name_plural = 'Proveedores'
    
    def __str__(self):
        nc = self.nombres.upper()
        if self.apellidos is not None:
            nc+= ' ' + self.apellidos.upper()
        return nc
    
    def nombre_completo(self):
        nc = self.nombres.upper()
        if self.apellidos is not None:
            nc+= ' ' + self.apellidos.upper()
        return nc
    
class conceptos_legalizacion(models.Model):
    descripcion = models.CharField(max_length=255)
    naturaleza_cuenta = models.CharField(max_length=255,choices=[('D','Debito'),('C','Credito')])
    activo = models.BooleanField(default=True)
    cuenta_andina = models.CharField(max_length=255,
                                     null=True, blank=True, help_text='Incluir los 10 digitos de la cuenta en SIIGO')
    cuenta_status = models.CharField(max_length=255,
                                     null=True, blank=True, help_text='Incluir los 10 digitos de la cuenta en SIIGO')
    cuenta_quadrata = models.CharField(max_length=255,
                                     null=True, blank=True, help_text='Incluir los 10 digitos de la cuenta en SIIGO')
    
    
    class Meta:
        verbose_name = 'Concepto legalizacion'
        verbose_name_plural = 'Conceptos legalizacion'
        
    def __str__(self):
        return self.descripcion.upper()


class impuestos_legalizacion(models.Model):
    descripcion = models.CharField(max_length=255)
    naturaleza_cuenta = models.CharField(max_length=255,choices=[('D','Debito'),('C','Credito')])
    activo = models.BooleanField(default=True)
    cuenta_andina = models.CharField(max_length=255,
                                     null=True, blank=True, help_text='Incluir los 10 digitos de la cuenta en SIIGO')
    cuenta_status = models.CharField(max_length=255,
                                     null=True, blank=True, help_text='Incluir los 10 digitos de la cuenta en SIIGO')
    cuenta_quadrata = models.CharField(max_length=255,
                                     null=True, blank=True, help_text='Incluir los 10 digitos de la cuenta en SIIGO')
    
    class Meta:
        verbose_name = 'Impuesto legalizacion'
        verbose_name_plural = 'Impuestos legalizacion'
        
    def __str__(self):
        return self.descripcion.upper()
    
class legalizacion_anticipos(models.Model):
    id_legalizacion = models.AutoField(primary_key = True)
    anticipo = models.ForeignKey(solicitud_anticipos, on_delete=models.PROTECT)
    concepto = models.ForeignKey(conceptos_legalizacion, on_delete = models.PROTECT)
    fecha_gasto = models.DateField()
    descripcion = models.CharField(max_length=255)
    tercero = models.ForeignKey(Partners, on_delete=models.PROTECT)
    valor = models.IntegerField()
    soporte = models.FileField(upload_to='legalizaciones_anticipos')
    aprobado = models.BooleanField(default=False)
    usuario_carga = models.ForeignKey(User, on_delete = models.PROTECT,
                                      related_name='user_leg_carga')
    usuario_aprueba = models.ForeignKey(User, on_delete = models.PROTECT,
                                      related_name='user_leg_aprueba',
                                      null=True,blank=True)
    fecha_legalizacion = models.DateField(auto_now_add=True)
    fecha_aprobacion = models.DateField(null=True,blank=True)
    cuenta_iva = models.ForeignKey(impuestos_legalizacion, on_delete=models.PROTECT,
                                   null=True,blank=True, related_name='cuenta_iva')
    valor_iva = models.FloatField(null=True, blank=True)
    cuenta_rte = models.ForeignKey(impuestos_legalizacion, on_delete=models.PROTECT,
                                   null=True,blank=True, related_name='cuenta_rte')
    valor_rte = models.FloatField(null=True, blank=True)
    rte_asumida = models.BooleanField(null=True, blank=True)
    
    
    class Meta:
        verbose_name = 'Legalizacion de anticipo'
        verbose_name_plural = 'Legalizaciones de anticipos'
        
    def nombre_tercero(self):
        return self.tercero.nombre_completo()
        
class reintegros_anticipos(models.Model):
    id_reintegro = models.AutoField(primary_key = True)
    id_anticipo = models.ForeignKey(solicitud_anticipos, on_delete = models.PROTECT,
                                    related_name="anticipo")
    valor = models.IntegerField()
    tipo = models.CharField(max_length=255, choices = (
        ('D','A la empresa'),
        ('C','Al empleado')
    ))
    id_otros_ingresos = models.ForeignKey(otros_ingresos, on_delete = models.PROTECT,
                                          null=True, blank = True)
    id_radicado = models.ForeignKey(Facturas, on_delete = models.PROTECT,
                                          null=True, blank = True)
    
    class Meta:
        verbose_name = 'Reintegro de anticipo'
        verbose_name_plural = 'Reintegros de anticipos'

class reembolsos_caja(models.Model):
    fecha_solicita = models.DateField(auto_now_add=True)
    caja = models.ForeignKey(cuentas_pagos, on_delete = models.PROTECT)
    usuario_solicita = models.ForeignKey(User, on_delete = models.PROTECT, related_name = 'usuario_solicita_reemb')
    valor = models.IntegerField()
    usuario_aprueba = models.ForeignKey(User, on_delete = models.PROTECT, related_name = 'usuario_aprueba_reemb',
                                        null = True, blank =  True)
    fecha_aprueba =  models.DateField(null=True, blank=True)
    doc_legalizacion = models.CharField(max_length=255, null=True, blank=True)
    soporte_legalizacion = models.FileField(upload_to='Cajas/Legalizacion')
    transferencia_asociada = models.ForeignKey(transferencias_companias, on_delete=models.PROTECT, null=True, blank=True)
    valor_a_reembolsar = models.IntegerField(null=True, blank=True)
    
class parametros(models.Model):
    descripcion = models.CharField(max_length=255, unique=True)
    activo = models.BooleanField(default=False)
    valor = models.CharField(max_length=255)
    
    
class gastos_caja(models.Model):
    id_gasto = models.AutoField(primary_key = True)
    concepto = models.ForeignKey(conceptos_legalizacion,  related_name='concepto_gasto', on_delete = models.PROTECT)
    fecha_gasto = models.DateField()
    descripcion = models.CharField(max_length=255)
    tercero = models.ForeignKey(Partners, related_name='tercero_gasto',on_delete=models.PROTECT)
    valor = models.IntegerField()
    soporte = models.FileField(upload_to='Cajas/Gastos')
    aprobado = models.BooleanField(default=False)
    usuario_carga = models.ForeignKey(User, on_delete = models.PROTECT,
                                      related_name='user_carga_gasto')
    usuario_aprueba = models.ForeignKey(User, on_delete = models.PROTECT,
                                      related_name='user_aprueba_gasto',
                                      null=True,blank=True)
    fecha_registro = models.DateField(auto_now_add=True)
    fecha_aprobacion = models.DateField(null=True,blank=True)
    cuenta_iva = models.ForeignKey(impuestos_legalizacion, on_delete=models.PROTECT,
                                   null=True,blank=True, related_name='cuenta_iva_gasto')
    valor_iva = models.FloatField(null=True, blank=True)
    cuenta_rte = models.ForeignKey(impuestos_legalizacion, on_delete=models.PROTECT,
                                   null=True,blank=True, related_name='cuenta_rte_gasto')
    valor_rte = models.FloatField(null=True, blank=True)
    rte_asumida = models.BooleanField(null=True, blank=True)
    estado = models.CharField(max_length=255, default='Pendiente')
    forma_pago = models.ForeignKey(cuentas_pagos, on_delete = models.PROTECT)
    reembolso = models.ForeignKey(reembolsos_caja, on_delete = models.PROTECT, null=True, blank=True)
        
    class Meta:
        verbose_name = 'Gasto de caja'
        verbose_name_plural = 'Gastos de caja'
        
    def nombre_tercero(self):
        return self.tercero.nombre_completo()

    def has_reemb(self):
        if self.reembolso is not None:
            return True
    
        return False
    
    def subtotal(self):
        vr_iva = 0 if self.valor_iva is None else self.valor_iva
        vr_rte = 0 if self.valor_rte is None else self.valor_rte
        sbt = self.valor - vr_iva + vr_rte
        if self.rte_asumida: sbt -= vr_rte
        return sbt

def upload_to(instance, filename):
    extension = filename.split('.')[-1]
    return f'archivo_contabilidad/{instance.empresa}/{instance.tipo_doc}/{instance.fecha_doc.year}/{instance.fecha_doc.month}/{instance.fecha_doc.day}/{instance.tipo_doc}-{instance.consecutivo}.{extension}'

class archivo_contable(models.Model):
    empresa = models.ForeignKey(empresas, on_delete = models.PROTECT)
    tipo_doc = models.CharField(max_length=255)
    consecutivo = models.IntegerField()
    fecha_doc = models.DateField()
    document = models.FileField(upload_to=upload_to)
    user_carga = models.ForeignKey(User, on_delete=models.PROTECT)
    fecha_carga = models.DateTimeField(auto_now_add=True)
    ocr_text = models.TextField(null=True, blank=True)
    
    class Meta:
        verbose_name = 'Archivo contable'
        verbose_name_plural = 'Archivo contable'
        unique_together = ['empresa','tipo_doc','consecutivo']
        
      
#Vistas
class info_facturas(models.Model):
    
    radicado = models.IntegerField(primary_key=True)
    nombretercero = models.CharField(max_length = 255)
    fecharadicado = models.DateField()
    fechafactura = models.DateField()
    valor = models.IntegerField()
    pagoneto = models.IntegerField()
    empresa = models.CharField(max_length=255)
    causacion = models.CharField(max_length=255)
    origen = models.CharField(max_length=255)
    descripcion = models.CharField(max_length=255)
    pagos = models.DecimalField(max_digits = 32, decimal_places = 2)
    saldo = models.DecimalField(max_digits = 32, decimal_places = 2)
    oficina = models.CharField(max_length=255)
    ubicacion = models.CharField(max_length=255)
    
    class Meta:
        db_table = 'info_facturas'
        managed = False

class PlinkMovement(models.Model):
    empresa = models.ForeignKey(empresas, on_delete=models.PROTECT, related_name='plink_movements')
    nit = models.CharField(max_length=30)
    codigo_establecimiento = models.CharField(max_length=50)
    origen_compra = models.CharField(max_length=50, null=True, blank=True)
    tipo_transaccion = models.CharField(max_length=30, null=True, blank=True)
    franquicia = models.CharField(max_length=30, null=True, blank=True)
    identificador_red = models.CharField(max_length=50, null=True, blank=True)
    fecha_transaccion = models.DateField()
    fecha_canje = models.DateField(null=True, blank=True)
    cuenta_consignacion = models.CharField(max_length=50, null=True, blank=True)
    valor_compra = models.DecimalField(max_digits=18, decimal_places=2)
    valor_propina = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    valor_iva = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    valor_impoconsumo = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    valor_total = models.DecimalField(max_digits=18, decimal_places=2)
    valor_comision = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    valor_retefuente = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    valor_rete_iva = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    valor_rte_ica = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    valor_provision = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    valor_neto = models.DecimalField(max_digits=18, decimal_places=2)
    codigo_autorizacion = models.CharField(max_length=50, null=True, blank=True)
    tipo_tarjeta = models.CharField(max_length=50, null=True, blank=True)
    numero_terminal = models.CharField(max_length=50, null=True, blank=True)
    tarjeta = models.CharField(max_length=50, null=True, blank=True)
    comision_porcentual = models.CharField(max_length=20, null=True, blank=True)
    comision_base = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    fecha_compensacion = models.DateField(null=True, blank=True)
    cuenta_normalizada = models.CharField(max_length=60, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    usado_agente = models.BooleanField(default=False, help_text='Indica si este movimiento ya fue usado por el agente de conciliación automática')
    fecha_uso_agente = models.DateTimeField(null=True, blank=True, help_text='Fecha en que el agente usó este movimiento')
    recibo_asociado_agente = models.CharField(max_length=255, null=True, blank=True, help_text='Número de recibo con el que el agente usó este movimiento')

    class Meta:
        verbose_name = 'Movimiento Plink'
        verbose_name_plural = 'Movimientos Plink'
        unique_together = ['empresa', 'codigo_autorizacion', 'fecha_transaccion']


class WompiMovement(models.Model):
    empresa = models.ForeignKey(empresas, on_delete=models.PROTECT, related_name='wompi_movements')
    transaction_id = models.CharField(max_length=100, unique=True)
    fecha = models.DateTimeField()
    referencia = models.CharField(max_length=255)
    monto = models.DecimalField(max_digits=18, decimal_places=2)
    iva = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    impuesto_consumo = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    moneda = models.CharField(max_length=10)
    medio_pago = models.CharField(max_length=30)
    email_pagador = models.EmailField(null=True, blank=True)
    nombre_pagador = models.CharField(max_length=255, null=True, blank=True)
    telefono_pagador = models.CharField(max_length=50, null=True, blank=True)
    id_conciliacion = models.CharField(max_length=100, null=True, blank=True)
    id_link_pago = models.CharField(max_length=100, null=True, blank=True)
    documento_pagador = models.CharField(max_length=50, null=True, blank=True)
    tipo_documento_pagador = models.CharField(max_length=10, null=True, blank=True)
    referencia_1_nombre = models.CharField(max_length=100, null=True, blank=True)
    referencia_1 = models.CharField(max_length=255, null=True, blank=True)
    cuenta_normalizada = models.CharField(max_length=60, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    usado_agente = models.BooleanField(default=False, help_text='Indica si este movimiento ya fue usado por el agente de conciliación automática')
    fecha_uso_agente = models.DateTimeField(null=True, blank=True, help_text='Fecha en que el agente usó este movimiento')
    recibo_asociado_agente = models.CharField(max_length=255, null=True, blank=True, help_text='Número de recibo con el que el agente usó este movimiento')

    class Meta:
        verbose_name = 'Movimiento Wompi'
        verbose_name_plural = 'Movimientos Wompi'


class upload_movements_job(models.Model):
    """
    Modelo para rastrear trabajos de carga de movimientos bancarios
    """
    STATUS_CHOICES = (
        ('pending', 'Pendiente'),
        ('processing', 'Procesando'),
        ('completed', 'Completado'),
        ('failed', 'Fallido'),
        ('partial', 'Parcialmente completado'),
    )

    id = models.AutoField(primary_key=True)
    empresa = models.ForeignKey(empresas, on_delete=models.CASCADE)
    usuario = models.ForeignKey(User, on_delete=models.CASCADE)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')

    # Archivos enviados
    tiene_banco = models.BooleanField(default=False)
    tiene_wompi = models.BooleanField(default=False)
    tiene_plink = models.BooleanField(default=False)

    # Resultados
    movimientos_banco = models.IntegerField(null=True, blank=True, help_text='Movimientos de banco procesados')
    movimientos_wompi = models.IntegerField(null=True, blank=True, help_text='Movimientos de Wompi procesados')
    movimientos_plink = models.IntegerField(null=True, blank=True, help_text='Movimientos de Plink procesados')

    movimientos_rechazados = models.IntegerField(null=True, blank=True, help_text='Movimientos rechazados')
    archivo_rechazados = models.TextField(null=True, blank=True, help_text='Base64 del archivo de rechazados')
    nombre_archivo_rechazados = models.CharField(max_length=255, null=True, blank=True)

    mensaje = models.TextField(null=True, blank=True, help_text='Mensaje de resultado')
    error_detail = models.TextField(null=True, blank=True, help_text='Detalle del error si falla')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Trabajo de Carga de Movimientos'
        verbose_name_plural = 'Trabajos de Carga de Movimientos'
        ordering = ['-created_at']

    def __str__(self):
        return f'Job #{self.id} - {self.empresa.nombre} - {self.status}'
