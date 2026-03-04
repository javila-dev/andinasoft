from django.db import models
from django.contrib.auth.models import User
#------Otros modelos---------
from andinasoft.models import proyectos,empresas,Pagos, ItemsInforme
from andina.storage.media_policy import PRIVATE_MEDIA_STORAGE
#Universal packages
import datetime

class unidades_medida(models.Model):
    id_unid=models.AutoField(primary_key=True)
    nombre=models.CharField(max_length=255,unique=True)

    class Meta:
        verbose_name = 'Unidad de medida'
        verbose_name_plural = 'Unidades de medidas'
        
    def __str__(self):
        return self.nombre

class tiposobra(models.Model):
    id_tipo=models.AutoField(primary_key=True)
    nombre_tipo=models.CharField(max_length=255)
    
    class Meta:
        verbose_name = 'Tipo de Obra'
        verbose_name_plural = 'Tipos de Obras'
    
    def __str__(self):
        return self.nombre_tipo

class retenciones(models.Model):
    id_rte=models.AutoField(primary_key=True)
    descripcion=models.CharField(max_length=255,unique=True)
    valor = models.DecimalField(decimal_places=2,max_digits=10)
    
    class Meta:
        verbose_name = 'Retencion'
        verbose_name_plural = 'Retenciones'
    
    def __str__(self):
        return f'{self.valor}%-{self.descripcion}'

class proveedores(models.Model):
    id_proveedor=models.CharField(primary_key=True,max_length=255)
    nombre=models.CharField(max_length=255)
    telefono=models.CharField(max_length=255,null=True,blank=True)
    direccion=models.CharField(max_length=255,null=True,blank=True)
    fecha_creacion = models.DateField(auto_now=True)
    doc_rut = models.FileField(upload_to='building_control/proveedores', null=True, blank=True, storage=PRIVATE_MEDIA_STORAGE)
    doc_cert_bancaria = models.FileField(upload_to='building_control/proveedores', null=True, blank=True, storage=PRIVATE_MEDIA_STORAGE)
    
    class Meta:
        verbose_name = 'Proveedor'
        verbose_name_plural = 'Proveedores'
    
    def __str__(self):
        return self.nombre

class productos_servicios(models.Model):
    id_producto=models.AutoField(primary_key=True)
    nombre=models.CharField(unique=True,max_length=255)
    tipos=(
        ('Producto','Producto'),
        ('Servicio','Servicio'),
    )
    tipo=models.CharField(max_length=255,choices=tipos)
    unidad=models.ForeignKey(unidades_medida,on_delete=models.CASCADE)
    
    class Meta:
        verbose_name = 'Producto/Servicio'
        verbose_name_plural = 'Productos/Servicios'
    
    def __str__(self):
        return self.nombre


class contratos(models.Model):
    id_contrato=models.AutoField(primary_key=True)
    proveedor=models.ForeignKey(proveedores,on_delete=models.CASCADE)
    proyecto=models.ForeignKey(proyectos,on_delete=models.CASCADE)
    descripcion=models.CharField(max_length=255)
    valor=models.IntegerField()
    anticipo=models.DecimalField(decimal_places=2,max_digits=6)
    retencion = models.ForeignKey(retenciones,on_delete=models.PROTECT,null=True,blank=True)
    fecha_creacion=models.DateField()
    fecha_inicio=models.DateField()
    fecha_fin=models.DateField()
    usuario_crea=models.ForeignKey(User,on_delete=models.PROTECT,related_name='usuario_crea_contrato')
    usuario_aprueba=models.ForeignKey(User,on_delete=models.PROTECT,related_name='usuario_aprueba_contrato',null=True,blank=True)
    estados=(
        ('Pendiente','Pendiente'),
        ('Aprobado','Aprobado'),
        ('Anulado','Anulado')
    )
    estado=models.CharField(max_length=255,choices=estados)
    porcentaje_canje=models.IntegerField()
    contrato_docs = models.FileField(upload_to='contratos_obra', null=True, blank=True, storage=PRIVATE_MEDIA_STORAGE)
    empresa_contrata = models.ForeignKey(empresas,null=True,blank=True,on_delete=models.PROTECT)
    a = models.DecimalField(decimal_places=2,max_digits=6)
    i = models.DecimalField(decimal_places=2,max_digits=6)
    u = models.DecimalField(decimal_places=2,max_digits=6)
    aiu = models.DecimalField(decimal_places=2,max_digits=6)
    iva = models.DecimalField(decimal_places=2,max_digits=6)
    total_costo = models.DecimalField(decimal_places=2,max_digits=20)
    
    class Meta:
        verbose_name = 'Contrato'
        verbose_name_plural = 'Contratos'
    
    def __str__(self):
        return f'Contrato #{self.id_contrato} - {self.proveedor.nombre}'

class requisiciones(models.Model):
    id_req = models.AutoField(primary_key=True)
    proyecto=models.ForeignKey(proyectos,on_delete=models.PROTECT)
    fecha=models.DateField()
    descripcion=models.CharField(max_length=255,null=True,blank=True)
    usuario_crea=models.ForeignKey(User,on_delete=models.PROTECT,related_name='usuario_crea_req')
    usuario_aprueba=models.ForeignKey(User,on_delete=models.PROTECT,related_name='usuario_aprueba_req',null=True,blank=True)
    fecha_aprueba=models.DateTimeField(null=True,blank=True)
    estados=(
        ('Pendiente','Pendiente'),
        ('Aprobado','Aprobado'),
        ('Cruzado','Cruzado'),
    )
    estado=models.CharField(max_length=255,choices=estados)
    orden_cruce = models.ForeignKey(contratos,on_delete=models.PROTECT,null=True,blank=True)

    class Meta:
        verbose_name = 'Requisicion'
        verbose_name_plural = 'Requisiciones'
    
    
class items_requisiciones(models.Model):
    id_item=models.AutoField(primary_key=True)
    item=models.ForeignKey(productos_servicios,on_delete=models.CASCADE)
    cantidad=models.DecimalField(decimal_places=2,max_digits=15)
    tipo_obra=models.ForeignKey(tiposobra,on_delete=models.PROTECT)
    requisicion =models.ForeignKey(requisiciones,on_delete=models.CASCADE)

    class Meta:
        verbose_name = 'Item requisicion'
        verbose_name_plural = 'Items requisiciones'
    
class otrosi(models.Model):
    id_otrosi = models.AutoField(primary_key=True)
    num_otrosi = models.IntegerField()
    contrato = models.ForeignKey(contratos,on_delete=models.CASCADE)
    estado = models.CharField(max_length=255,default='Pendiente')
    descripcion = models.CharField(max_length=255)
    valor = models.DecimalField(decimal_places=2,max_digits=15)
    canje = models.IntegerField()
    aiu = models.DecimalField(decimal_places=2,max_digits=6)
    iva = models.DecimalField(decimal_places=2,max_digits=6)
    rte = models.DecimalField(decimal_places=2,max_digits=6)
    total_otrosi = models.DecimalField(decimal_places=2,max_digits=20)
    fecha_crea=models.DateField()
    usuario_crea=models.ForeignKey(User,on_delete=models.PROTECT,related_name='usuario_crea_otrosi')
    fecha_aprueba=models.DateField(null=True,blank=True)
    usuario_aprueba=models.ForeignKey(User,null=True,blank=True,on_delete=models.PROTECT,related_name='usuario_aprueba_otrosi')
    
    class Meta:
        verbose_name = 'Otrosi'
        verbose_name_plural = 'Otrosi'
    
    def __str__(self):
        return f'Otrosi #{self.num_otrosi} contrato {self.contrato.pk} - {self.contrato.proveedor.nombre}'

class items_contrato(models.Model):
    id_item=models.AutoField(primary_key=True)
    item=models.ForeignKey(productos_servicios,on_delete=models.CASCADE)
    cantidad=models.DecimalField(decimal_places=2,max_digits=15)
    valor=models.DecimalField(decimal_places=2,max_digits=15)
    total=models.DecimalField(decimal_places=2,max_digits=15)
    contrato=models.ForeignKey(contratos,on_delete=models.CASCADE)
    tipo_obra=models.ForeignKey(tiposobra,on_delete=models.CASCADE)
    otrosi=models.ForeignKey(otrosi,null=True,blank=True,on_delete=models.CASCADE)

    class Meta:
        verbose_name = 'Item de contrato'
        verbose_name_plural = 'Items de contrato'
    
    def __str__(self):
        return self.item.nombre
    
class actas_contratos(models.Model):
    id_acta=models.AutoField(primary_key=True)
    num_acta = models.IntegerField()
    contrato=models.ForeignKey(contratos,on_delete=models.PROTECT)
    estado = models.CharField(max_length=255,default='Pendiente')
    canje_efectuado = models.DecimalField(max_digits=15,decimal_places=2,default=0)
    anticipo_amortizado = models.DecimalField(max_digits=15,decimal_places=2,default=0)
    retencion_efectuada = models.DecimalField(max_digits=15,decimal_places=2,default=0)
    aiu = models.DecimalField(max_digits=15,decimal_places=2,default=0)
    iva = models.DecimalField(max_digits=15,decimal_places=2,default=0)
    fecha_acta=models.DateField()
    usuario_crea=models.ForeignKey(User,on_delete=models.PROTECT,related_name='usuario_crea_acta')
    fecha_aprueba=models.DateField(null=True,blank=True)
    usuario_aprueba=models.ForeignKey(User,on_delete=models.PROTECT,related_name='usuario_aprueba_acta',
                                      null=True,blank=True)
    observaciones = models.CharField(max_length=255,null=True,blank=True)
    
    class Meta:
        verbose_name = 'Acta de recibido'
        verbose_name_plural = 'Actas de recibido'
        unique_together = ('contrato','num_acta')

    def __str__(self):
        return f'Acta {self.num_acta} - Contrato {self.contrato.pk}/{self.contrato.proveedor.nombre}'
    
class items_recibidos(models.Model):
    id_recibido=models.AutoField(primary_key=True)
    acta=models.ForeignKey(actas_contratos,on_delete=models.CASCADE)
    item=models.ForeignKey(items_contrato,on_delete=models.PROTECT)
    cantidad=models.DecimalField(decimal_places=2,max_digits=15)
    
    class Meta:
        verbose_name = 'item de acta de recibido'
        verbose_name_plural = 'items de acta de recibido'
    
    def __str__(self):
        return self.item.item.nombre

class pagos_obras(models.Model):
    pago = models.OneToOneField(Pagos,on_delete=models.CASCADE,primary_key=True)
    contrato_asociado = models.ForeignKey(contratos,on_delete=models.CASCADE)
    item_informe = models.ForeignKey(ItemsInforme,on_delete=models.CASCADE,null=True,blank=True)
    proyecto_asume = models.ForeignKey(proyectos,on_delete=models.CASCADE,null=True,blank=True)
    
    class Meta:
        verbose_name = 'Pago de obra'
        verbose_name_plural = 'Pagos de obra'

class bitacora(models.Model):
    id_registro=models.AutoField(primary_key=True)
    usuario = models.ForeignKey(User,on_delete=models.PROTECT)
    fecha_bitacora = models.DateField()
    fecha_registro = models.DateTimeField(auto_now=True)
    proyecto = models.ForeignKey(proyectos,on_delete=models.PROTECT)
    observaciones = models.CharField(max_length=2000)
    
    class Meta:
        verbose_name = 'Bitacora'
        verbose_name_plural = 'Bitacoras'

class fotos_bitacora(models.Model):
    id_foto = models.AutoField(primary_key=True)
    bitacora = models.ForeignKey(bitacora,on_delete=models.CASCADE)
    foto = models.ImageField(upload_to='fotos_bitacora', storage=PRIVATE_MEDIA_STORAGE)
    
    class Meta:
        verbose_name = 'Fotos Bitacora'
        verbose_name_plural = 'Fotos Bitacoras'

class parametros(models.Model):
    id_parametro = models.AutoField(primary_key=True)
    parametro = models.CharField(max_length=255,unique=True)
    check = models.BooleanField(null=True,blank=True,
                                help_text="Esta casilla se usa solo cuando el parametro es de tipo Activado/Desactivado")
    valor = models.DecimalField(decimal_places=2,max_digits=15,null=True,blank=True,
                                help_text="Usa este campo cuando el parametro sea un valor especifico")
    
    class Meta:
        verbose_name = 'Parametro'
        verbose_name_plural = 'Parametros'
