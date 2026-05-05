from django.db import models
from django.contrib.auth.models import User
from django.db.models import Q
from andina.storage.media_policy import PRIVATE_MEDIA_STORAGE, PUBLIC_MEDIA_STORAGE
import json




# Create your models here.

class Countries(models.Model):
    id_country = models.CharField(max_length=255, primary_key=True)
    country_name = models.CharField(max_length=255)
    
    class Meta:
        verbose_name = 'Pais'
        verbose_name_plural = 'Paises'
        
    def __str__(self):
        return self.country_name
    
class States(models.Model):
    id_state = models.CharField(max_length=255)
    country = models.ForeignKey(Countries, on_delete = models.CASCADE)
    state_name = models.CharField(max_length=255)
    
    class Meta:
        verbose_name = 'Estado'
        verbose_name_plural = 'Estados'
        
    def __str__(self):
        return self.state_name

class Cities(models.Model):
    id_city = models.CharField(max_length=255)
    state = models.ForeignKey(States, on_delete= models.CASCADE)
    city_name = models.CharField(max_length=255)
    
    
    class Meta:
        verbose_name = 'Ciudad'
        verbose_name_plural = 'Ciudades'
        
    def __str__(self):
        return self.city_name

class empresas(models.Model):
    Nit=models.CharField(max_length=255,primary_key=True)
    nombre=models.CharField(max_length=255)
    representante_legal=models.CharField(max_length=255)
    cc_replegal=models.CharField(max_length=255)
    logo=models.ImageField(upload_to='logos_empresas', storage=PUBLIC_MEDIA_STORAGE)
    alegra_enabled=models.BooleanField(default=False)
    alegra_token=models.CharField(max_length=1024,null=True,blank=True)
    
    def __str__(self):
        return self.nombre.upper()

class notificaciones_correo(models.Model):
    id_notificacion = models.AutoField(primary_key=True)
    identificador = models.CharField(max_length=255,unique=True)
    users_to_send = models.ManyToManyField(User)
    
    class Meta:
        verbose_name = 'Notificacion email'
        verbose_name_plural = 'Notificaciones email'

class Avatars(models.Model):
    id_avatar = models.AutoField(primary_key=True)
    name = models.CharField(max_length=255,unique=True)
    image = models.ImageField(upload_to="avatars", storage=PUBLIC_MEDIA_STORAGE)
    
    def __str__(self):
        return self.name

class Profiles(models.Model):
    user=models.OneToOneField(User,on_delete=models.CASCADE)
    fecha_nacimiento=models.DateField(null=True,blank=True)
    identificacion=models.CharField(max_length=255,null=True,blank=True)
    sexo_choices=(
        ('F','Femenino'),
        ('M','Masculino'),
    )
    sexo=models.CharField(max_length=255,choices=sexo_choices)
    avatar=models.ForeignKey(Avatars,on_delete=models.PROTECT,default=9999999)
    
    def __str__(self):
        return self.user.first_name+" "+self.user.last_name

class asesores(models.Model):
    cedula=models.CharField(primary_key=True,max_length=255)
    nombre=models.CharField(max_length=255)
    email=models.EmailField()
    banco=models.CharField(max_length=255,null=True,blank=True)
    cuenta=models.CharField(max_length=255,null=True,blank=True)
    tipo_cuenta=models.CharField(max_length=255,null=True,blank=True)
    telefono=models.CharField(max_length=255,null=True,blank=True)
    rut=models.BooleanField(default=0)
    cc=models.BooleanField(default=0)
    cert_banc=models.BooleanField(default=0)
    hv=models.BooleanField(default=0)
    afiliaciones=models.BooleanField(default=0)
    direccion=models.CharField(max_length=255)
    fecha_nacimiento=models.DateField()
    estado_civil=models.CharField(max_length=255)
    nivel_educativo=models.CharField(max_length=255)
    equipo=models.CharField(max_length=255,null=True)
    estado=models.CharField(max_length=255,null=True,default='Activo')
    fecha_registro=models.DateField(auto_now_add=True)
    fecha_baja=models.DateField(null=True, blank=True)
    acceso_online=models.BooleanField(default=1)
    tipo_asesor=models.CharField(max_length=255,choices=(
        ('Interno','Interno'),
        ('Externo','Externo'),
    ),help_text='Para que un asesor sea visible en GTT debe estar marcado como Externo')
    
    def __str__(self):
        return self.nombre.upper()
    
class departamentos_municipios(models.Model):
    departamento=models.CharField(max_length=255)
    municipio=models.CharField(max_length=255)

class entidades_bancarias(models.Model):
    banco=models.CharField(max_length=255)  
    codigo=models.IntegerField()
    
    def __str__(self):
        return self.banco

class clientes(models.Model):
    idTercero=models.CharField(primary_key=True,max_length=255)
    dc_types = (
        ('13',  'Cédula de ciudadanía'),
        ('31',	'NIT'),
        ('22',	'Cédula de extranjería'),
        ('42',	'Documento de identificación extranjero'),
        ('50',	'NIT de otro país'),
        ('91',	'NUIP'),
        ('41',	'Pasaporte'),
        ('47',	'Permiso especial de permanencia PEP'),
        ('21',	'Tarjeta de extranjería'),
        ('R-00-PN',	'No obligado a registrarse en el RUT PN'),
    )
    tipo_doc = models.CharField(choices=dc_types,max_length=255, null=True,blank=True)
    lugar_exp_id = models.CharField(choices=dc_types,max_length=255, null=True,blank=True)
    fecha_exp_id = models.DateField(null=True,blank=True)
    nombrecompleto=models.CharField(max_length=255)
    nombres=models.CharField(max_length=255)
    apellidos=models.CharField(max_length=255)
    celular1=models.CharField(max_length=255)
    celular2=models.CharField(max_length=255,null=True,blank=True)
    telefono1=models.CharField(max_length=255,null=True,blank=True)
    telefono2=models.CharField(max_length=255,null=True,blank=True)
    domicilio=models.CharField(max_length=255)
    pais = models.ForeignKey(Countries, on_delete = models.PROTECT, blank=True, null=True)
    estado = models.ForeignKey(States, on_delete = models.PROTECT, blank=True, null=True)
    city = models.ForeignKey(Cities, on_delete = models.PROTECT, blank=True, null=True)
    ciudad=models.CharField(max_length=255,null=True,blank=True)
    oficina=models.CharField(max_length=255,null=True,blank=True)
    email=models.EmailField()
    fecha_nac=models.DateField()
    lugar_nac = models.CharField(max_length=255,null=True,blank=True)
    nacionalidad = models.CharField(max_length=255,null=True,blank=True)
    
    ocupacion=models.CharField(max_length=255,null=True,blank=True, choices = [
        ('DEPENDIENTE','Dependiente'),
        ('INDEPENDIENTE','Independiente'),
        ('EMPLEADO PUBLICO','Empleado Público'),
        ('PENSIONADO','Pensionado'),
        ('FUERZA PUBLICA','Miembro Fuerza Publica'),
        ('OTRO','Otro'),
    ])
    cual_otro_ocupacion = models.CharField(max_length=255,null=True,blank=True)
    hijos=models.CharField(max_length=255,null=True,blank=True)
    nivel_educativo=models.CharField(max_length=255)
    estado_civil=models.CharField(max_length=255,null=True,blank=True)
    nivel_ingresos=models.CharField(max_length=255,null=True,blank=True)
    vehiculo=models.CharField(max_length=255,null=True,blank=True)
    vivienda=models.CharField(max_length=255,null=True,blank=True, choices = [
        ('PROPIA','Propia'),
        ('FAMILIAR','Familiar'),
        ('ARRENDADA','Arrendada')
    ])
    pasatiempos=models.CharField(max_length=255,null=True,blank=True)
    id_conyuge=models.CharField(max_length=255,null=True,blank=True)
    nombre_cony=models.CharField(max_length=255,null=True,blank=True)
    apellido_cony=models.CharField(max_length=255,null=True,blank=True)
    celular_cony=models.CharField(max_length=255,null=True,blank=True)
    email_cony=models.CharField(max_length=255,null=True,blank=True)
    fechanac_cony=models.DateField(null=True,blank=True)
    ocupacion_cony=models.CharField(max_length=255,null=True,blank=True, choices = [
        ('DEPENDIENTE','Dependiente'),
        ('INDEPENDIENTE','Independiente'),
        ('EMPLEADO PUBLICO','Empleado Público'),
        ('PENSIONADO','Pensionado'),
        ('FUERZA PUBLICA','Miembro Fuerza Publica'),
        ('OTRO','Otro'),
    ])
    fecha_actualizacion=models.DateField()
    
    
    
    class Meta:
        verbose_name = 'Cliente'
        verbose_name_plural = 'Clientes'
        
    def __str__(self):
        if self.nombrecompleto:
            return f'{self.nombrecompleto} ({self.idTercero})'
        return str(self.idTercero)

    def tipo_documento_str(self):
        tipos = {
            '13':  'Cédula de ciudadanía',
            '31':	'NIT',
            'ventas22':	'Cédula de extranjería',
            '42':	'Documento de identificación extranjero',
            '50':	'NIT de otro país',
            '91':	'NUIP',
            '41':	'Pasaporte',
            '47':	'Permiso especial de permanencia PEP',
            '21':	'Tarjeta de extranjería',
            'R-00-PN':	'No obligado a registrarse en el RUT PN',
        }
        tipo_cliente = tipos.get(self.tipo_doc)
        return tipo_cliente
    
    def tipo_ocupacion(self):
        ocupaciones = {
            'D':'Dependiente',
            'I':'Independiente',
            'EP':'Empleado Público',
            'P':'Pensionado',
            'FP':'Miembro Fuerza Publica',
            'O':'Otro',
        }
        ocupacion = ocupaciones.get(self.ocupacion)
        return ocupacion

class proyectos(models.Model):
    proyecto=models.CharField(max_length=255,primary_key=True)
    activo=models.BooleanField(default=True)
    
    def __str__(self):
        return self.proyecto

class parametros(models.Model):
    parametro=models.CharField(max_length=255)
    valor=models.DecimalField(max_digits=10,decimal_places=2)

class cuentas_pagos(models.Model):
    idcuenta=models.AutoField(db_column='Idcuenta', primary_key=True)  # Field name made lowercase.
    empresa = models.CharField(db_column='Empresa', max_length=255, blank=True, null=True)
    cuentabanco = models.CharField(db_column='Cuentabanco', max_length=255, blank=True, null=True)
    cuentacontable = models.CharField(db_column='Cuentacontable', max_length=255, blank=True, null=True)
    nit_empresa = models.ForeignKey(empresas,on_delete=models.CASCADE,null=True,blank=True)
    nro_cuentacontable = models.IntegerField(null=True,blank=True)
    doc_contable = models.CharField(null=True,blank=True,max_length=255)
    es_conciliable = models.BooleanField(default=False)
    es_caja = models.BooleanField(default=False)
    usuario_responsable = models.ForeignKey(User, on_delete=models.PROTECT, null=True, blank=True,
                                            related_name='usuario_responsable')
    usuario_aprobador = models.ForeignKey(User, on_delete=models.PROTECT, null=True, blank=True,
                                          related_name='usuario_aprobador')
    activo = models.BooleanField(default=True)
    oficina = models.CharField(max_length=255, null=True, blank=True)
    
    def __str__(self):
        return self.cuentabanco

class Facturas(models.Model):
    nroradicado = models.AutoField(db_column='NroRadicado', primary_key=True)  # Field name made lowercase.
    fecharadicado = models.DateField(db_column='FechaRadica', blank=True, null=True)  # Field name made lowercase.
    nrofactura = models.CharField(db_column='NroFactura', max_length=255, blank=True, null=True)
    fechafactura = models.DateField(db_column='FechaFactura', blank=True, null=True)  # Field name made lowercase.
    idtercero = models.CharField(db_column='idTercero', max_length=255, blank=True, null=True)  # Field name made lowercase.
    nombretercero = models.CharField(db_column='NombreTercero', max_length=255, blank=True, null=True)  # Field name made lowercase.
    empresa = models.CharField(db_column='Empresa', max_length=255, blank=True, null=True)  # Field name made lowercase.
    valor = models.IntegerField(db_column='Valor', blank=True, null=True)  # Field name made lowercase.
    pago_neto = models.IntegerField(db_column='PagoNeto', blank=True, null=True)
    fechavenc = models.DateField(db_column='FechaVenc', blank=True, null=True)  # Field name made lowercase.
    nrocausa = models.CharField(db_column='NroCausa', max_length=255, blank=True, null=True)  # Field name made lowercase.
    fechacausa = models.DateField(db_column='FechaCausa', blank=True, null=True)  # Field name made lowercase.
    estado = models.CharField(db_column='Estado', max_length=255, blank=True, null=True)
    origen = models.CharField(db_column='Origen', max_length=255, blank=True, null=True, default='Radicado')
    oficinas_choices = (
        ('MONTERIA','MONTERIA'),
        ('MEDELLIN','MEDELLIN')
        
    )
    oficina = models.CharField(db_column='Oficina', max_length=255,blank=True,null=True,choices=oficinas_choices)
    usuario = models.CharField(db_column='Usuario', max_length=255, blank=True, null=True)

class Pagos(models.Model):
    idpago = models.AutoField(db_column='IdPago', primary_key=True)
    nroradicado = models.CharField(db_column='NroRadicado',blank=True, null=True,max_length=255)
    valor = models.IntegerField(db_column='Valorpago', blank=True, null=True)
    empresapago=models.CharField(db_column='EmpresaPago', max_length=255, blank=True, null=True)
    fechapago = models.DateField(db_column='Fechapago', blank=True, null=True)
    formapago = models.CharField(db_column='FormaPago', max_length=255, blank=True, null=True)
    usuario = models.CharField(db_column='Usuario', max_length=255, blank=True, null=True)
    
class Peticiones(models.Model):
    nroradicado = models.AutoField(db_column='NroRadicado', primary_key=True)  # Field name made lowercase.
    fecharadicado = models.DateField(db_column='FechaRadica', blank=True, null=True)  # Field name made lowercase.
    idcliente = models.CharField(db_column='idCliente', max_length=255, blank=True, null=True)  # Field name made lowercase.
    nombrecliente = models.CharField(db_column='NombreCliente', max_length=255, blank=True, null=True)  # Field name made lowercase.
    proyecto = models.CharField(db_column='Proyecto', max_length=255, blank=True, null=True)  # Field name made lowercase.
    tiporeq = models.CharField(db_column='TipoReq', max_length=255, blank=True, null=True)  # Field name made lowercase.
    adj = models.CharField(db_column='Adj', max_length=255, blank=True, null=True)  # Field name made lowercase.
    carteraadj = models.CharField(db_column='CarteraAdj', max_length=255, blank=True, null=True)  # Field name made lowercase.
    estadoadj = models.CharField(db_column='EstadoAdj', max_length=255, blank=True, null=True)  # Field name made lowercase.
    vencimiento = models.DateField(db_column='Vencimiento', blank=True, null=True)  # Field name made lowercase.
    estadoenvio = models.CharField(db_column='EstadoEnvio', max_length=255, blank=True, null=True)  # Field name made lowercase.
    fecharespuesta = models.DateField(db_column='FechaRespuesta', blank=True, null=True)  # Field name made lowercase.
    formaenviorta = models.CharField(db_column='FormaEnvioRta', max_length=255, blank=True, null=True)  # Field name made lowercase.
    fechaenviorta = models.DateField(db_column='FechaEnvioRta', blank=True, null=True)  # Field name made lowercase.
    fechaconfirrta = models.DateField(db_column='FechaConfirRta', blank=True, null=True)  # Field name made lowercase.
    nroguia = models.CharField(db_column='NroGuia', max_length=255, blank=True, null=True)  # Field name made lowercase.
    estado = models.CharField(db_column='Estado', max_length=255, blank=True, null=True)

class timeline_radicados(models.Model):
    id_flow =  models.AutoField(db_column='id_flow', primary_key=True)  # Field name made lowercase.
    tiporadicado =  models.CharField(db_column='TipoRadicado', max_length=255, blank=True, null=True)  # Field name made lowercase.
    nroradicado =  models.CharField(db_column='NroRadicado', max_length=255, blank=True, null=True)  # Field name made lowercase.
    usuario = models.CharField(db_column='Usuario', max_length=255, blank=True, null=True)
    accion = models.CharField(db_column='Accion', max_length=255, blank=True, null=True)
    fecha=models.DateField(db_column='Fecha', blank=True, null=True)
        
class CuentasAsociadas(models.Model):
    Id = models.AutoField(db_column='Id', primary_key=True)
    empresa = models.CharField(max_length=255, blank=True, null=True,db_column='Empresa')
    cuenta = models.CharField(max_length=255, blank=True, null=True,db_column='Cuenta')
    descrip_cuenta = models.CharField(max_length=255, blank=True, null=True,db_column='Descripcion_Cuenta')
    item_asociado = models.CharField(max_length=255, blank=True, null=True,db_column='Item_Asociado')

    class Meta:
        managed = True
        unique_together = (('empresa', 'cuenta'),)

class GastosInforme(models.Model):
    Id = models.AutoField(db_column='Id', primary_key=True)
    empresa = models.CharField(db_column='Empresa',max_length=255)
    cuenta = models.CharField(db_column='Cuenta',max_length=255, blank=True, null=True)
    descrip_cuenta = models.CharField(db_column='DescripcionCuenta',max_length=255, blank=True, null=True)
    fecha = models.DateField(db_column='Fecha',blank=True, null=True)
    comprobante = models.CharField(db_column='Comprobante',max_length=255)
    tercero = models.CharField(db_column='Tercero',max_length=255, blank=True, null=True)
    descrip_gasto = models.CharField(db_column='DescripcionGasto',max_length=255, blank=True, null=True)
    valor = models.DecimalField(db_column='Valor',max_digits=20, decimal_places=2, blank=True, null=True)
    proyecto = models.CharField(db_column='Proyecto',max_length=255, blank=True, null=True)
    centro_costo = models.CharField(db_column='CentroCosto',max_length=255, blank=True, null=True)
    item_asociado = models.CharField(db_column='ItemAsociado',max_length=255, blank=True, null=True)

    class Meta:
        managed = True
        unique_together = (('comprobante', 'empresa'),)
        
class ItemsInforme(models.Model):
    Id = models.AutoField(db_column='Id', primary_key=True)  # Field name made lowercase.
    grupo = models.CharField(db_column='Grupo', max_length=30, blank=True, null=True)  # Field name made lowercase.
    temas = models.CharField(db_column='Item', max_length=1000, blank=True, null=True)  # Field name made lowercase.

    class Meta:
        managed = True
        
class Gtt(models.Model):
    id_pago = models.AutoField(primary_key=True)
    fecha_desde = models.DateField()
    fecha_hasta = models.DateField()
    proyecto = models.CharField(max_length=255,null=True,blank=True)
    estado = models.CharField(max_length=255,null=True,blank=True)
    usuario_crea = models.CharField(max_length=255,null=True,blank=True)
    usuario_aprueba = models.CharField(max_length=255,null=True,blank=True)
    
    class Meta:
        managed = True

class Detalle_gtt(models.Model):
    id_pago = models.AutoField(primary_key=True)
    gtt = models.ForeignKey(Gtt,on_delete=models.CASCADE)
    asesor = models.ForeignKey(asesores,on_delete=models.CASCADE)
    valor = models.IntegerField()
    
    class Meta:
        managed = True
    
class CentrosCostos(models.Model):
    Id = models.AutoField(db_column='Id', primary_key=True)
    empresa = models.CharField(db_column='Empresa', max_length=255)  # Field name made lowercase.
    idcentrocosto = models.CharField(db_column='IdCentroCosto', max_length=255)  # Field name made lowercase.
    centro = models.CharField(max_length=255,db_column='CentroCosto')
    subcentro = models.CharField(db_column='SubcentroCosto',max_length=255, blank=True, null=True)
    proyecto = models.CharField(db_column='Proyecto',max_length=255, blank=True, null=True)
    detalle = models.CharField(db_column='Detalle',max_length=255, blank=True, null=True)

    class Meta:
        managed = True
        unique_together = (('idcentrocosto', 'empresa'),)

class Usuarios_Proyectos(models.Model):
    id_rel=models.AutoField(primary_key=True)
    usuario=models.ForeignKey(User,on_delete=models.CASCADE)
    proyecto=models.ManyToManyField(proyectos)

class sidebar_pinned(models.Model):
    usuario = models.OneToOneField(User, on_delete=models.CASCADE,unique=True)
    pinned = models.BooleanField()

class bk_bfchangeplan(models.Model):
    proyecto = models.ForeignKey(proyectos,on_delete = models.PROTECT)
    fecha_bk = models.DateTimeField(auto_now=True)
    usuario_bk = models.ForeignKey(User, on_delete= models.PROTECT)
    adj = models.CharField(max_length=255, blank=True, null=True)

class bk_planpagos(models.Model):
    id_bk = models.ForeignKey(bk_bfchangeplan, on_delete = models.CASCADE)
    proyecto = models.ForeignKey(proyectos,on_delete = models.PROTECT)
    idcta = models.CharField(max_length=255, blank=True, null=True)
    tipocta = models.CharField(max_length=255, blank=True, null=True)
    nrocta = models.IntegerField(blank=True, null=True)
    adj = models.CharField(max_length=255, blank=True, null=True)
    capital = models.DecimalField(max_digits=14, decimal_places=2, blank=True, null=True)
    intcte = models.DecimalField(max_digits=14, decimal_places=2, blank=True, null=True)
    cuota = models.DecimalField(max_digits=14, decimal_places=2, blank=True, null=True)
    fecha = models.DateField(blank=True, null=True)    
    
class bk_recaudodetallado(models.Model):
    id_bk = models.ForeignKey(bk_bfchangeplan, on_delete = models.CASCADE)
    proyecto = models.ForeignKey(proyectos,on_delete = models.PROTECT)
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

class CIUU(models.Model):
    codigo = models.CharField(max_length=11, primary_key=True)
    descripcion = models.CharField(max_length=255)
    
    class Meta:
        verbose_name = 'Codigo CIUU'
        verbose_name_plural = 'Codigos CIUU'
        
    def __str__(self):
        return f'({self.pk}) {self.descripcion}'

class sagrilaft_info(models.Model):
    cliente = models.OneToOneField(clientes, on_delete = models.CASCADE, primary_key=True)
    empresa_labora = models.CharField(max_length=255, null= True, blank=True)
    cargo_actual = models.CharField(max_length=255, blank=True, null=True)
    origen_ingresos = models.CharField(max_length=255)
    declara_renta = models.BooleanField(null=True, blank=True)
    tiene_rut = models.BooleanField(null=True, blank=True)
    codigo_ciuu = models.ForeignKey(CIUU, on_delete=models.PROTECT, null=True, blank=True)
    preguntas_complementarias = models.CharField(max_length=9999, blank=True, null=True)
    es_peps = models.BooleanField(null=True, blank=True)
    peps_desde = models.DateField(null=True, blank=True)
    peps_hasta = models.DateField(null=True, blank=True)
    peps_entidad = models.CharField(max_length=255, blank=True, null=True)
    peps_cargo = models.CharField(max_length=255, blank=True, null=True)
    peps_familiar = models.BooleanField(null=True, blank=True)
    peps_familiar_parentesco = models.CharField(max_length=255, blank=True, null=True)
    peps_familiar_entidad = models.CharField(max_length=255, blank=True, null=True)
    peps_familiar_cargo = models.CharField(max_length=255, blank=True, null=True)
    
    referencia_familiar = models.CharField(max_length=999, blank=True, null=True)
    referencia_familiar_telefono = models.CharField(max_length=999, blank=True, null=True)
    referencia_personal = models.CharField(max_length=999, blank=True, null=True)
    referencia_personal_telefono = models.CharField(max_length=999, blank=True, null=True)
    
    def humanize_declara_renta(self):        
        return 'Si' if self.declara_renta else 'No'
    
    def humanize_tiene_rut(self):
        return 'Si' if self.tiene_rut else 'No'
    
    def json_preguntas(self):
        json_pc = json.loads(self.preguntas_complementarias)
        return json_pc
    
    class Meta:
        verbose_name = 'Información sagrilaft cliente'
        verbose_name_plural = 'Información sagrilaft clientes'
    
    def __str__(self):
        return f'{self.cliente.pk}-{self.cliente.nombrecompleto}' 

class reestructuraciones_otrosi(models.Model):
    fecha = models.DateField()
    adj = models.ForeignKey('andinasoft.Adjudicacion', on_delete = models.PROTECT)
    cuotas_vencidas = models.IntegerField()
    dias_mora = models.IntegerField()
    int_cte_causado = models.IntegerField()
    int_mora_causado = models.IntegerField()
    capital_pendiente = models.IntegerField()
    interes_a_reestructurar = models.IntegerField()
    cuotas_dividir_interes = models.IntegerField(null=True, blank=True)
    tipo_reestructuracion = models.CharField(choices = (
        ('Normal','Normal'),
        ('Especial','Especial'),
        ('Descuento','Descuento'),
    ),max_length=100)
    estado = models.CharField(choices=(
        ('Pendiente','Pendiente'),
        ('Aprobado','Aprobado'),
        ('Firmado','Firmado'),
        ('Aplicado','Aplicado')
    ),max_length=255)
    usuario_solicita = models.ForeignKey(User, related_name='usuario_solicita_reestr',on_delete=models.PROTECT)
    usuario_aprueba = models.ForeignKey(User, related_name='usuario_aprueba_reestr',on_delete=models.PROTECT)
    fecha_aprobacion = models.DateField(null=True, blank=True)
    usuario_aplica = models.ForeignKey(User, related_name='usuario_aplica',on_delete=models.PROTECT)
    fecha_aplica = models.DateField(null=True, blank=True)
    observaciones = models.CharField(max_length=255,null=True,blank=True)
    proyecto = models.ForeignKey(proyectos, on_delete = models.PROTECT)
    solicitud = models.FileField(upload_to='otrosi/solicitudes', storage=PRIVATE_MEDIA_STORAGE)
    otrosi = models.FileField(upload_to='otrosi/firmados', null=True, blank=True, storage=PRIVATE_MEDIA_STORAGE)
    
    def extra_info(self):
        
        return self.adj.extra_info()
    

class plan_pagos_reestructuracion(models.Model):
    reestructuracion = models.ForeignKey(reestructuraciones_otrosi, on_delete = models.CASCADE)
    idcta = models.CharField(primary_key=True, max_length=255)
    tipocta = models.CharField(max_length=255, blank=True, null=True)
    nrocta = models.IntegerField(blank=True, null=True)
    adj = models.CharField(max_length=255, blank=True, null=True)
    capital = models.DecimalField(max_digits=14, decimal_places=2, blank=True, null=True)
    intcte = models.DecimalField(max_digits=14, decimal_places=2, blank=True, null=True)
    cuota = models.DecimalField(max_digits=14, decimal_places=2, blank=True, null=True)
    fecha = models.DateField(blank=True, null=True)
    
    
