from django.db import models
from django.contrib.auth.models import User
#------Otros modelos---------
from andinasoft.models import proyectos,empresas,Pagos,asesores
#Universal packages
import datetime

class Operaciones(models.Model):
    id_operacion = models.AutoField(primary_key=True)
    descripcion = models.CharField(max_length=255)
    proyecto = models.ForeignKey(proyectos,on_delete=models.CASCADE)
    asesores = models.ManyToManyField(asesores)
    lider = models.ForeignKey(User,on_delete=models.PROTECT)
    
    class Meta:
        verbose_name = 'Operacion'
        verbose_name_plural = 'Operaciones'

    def __str__(self):
        return self.proyecto.proyecto +" - "+self.descripcion
    
class leads(models.Model):
    id_lead = models.AutoField(primary_key=True)
    cedula = models.CharField(max_length=255,null=True,blank=True)
    nombre = models.CharField(max_length=255)
    celular = models.CharField(max_length=255,unique=True)
    telefono = models.CharField(max_length=255,blank=True,null=True)
    email = models.EmailField(null=True,blank=True)
    direccion = models.CharField(max_length=255,null=True,blank=True)
    ciudad = models.CharField(max_length=255,null=True,blank=True)
    estados_civiles = (
        ('Casado(a)','Casado(a)'),
        ('Soltero(a)','Soltero(a)'),
        ('Viudo(a)','Viudo(a)'),
        ('Separado(a)','Separado(a)'),
        ('Otro','Otro')
    )
    estado_civil = models.CharField(max_length=255,choices=estados_civiles,null=True,blank=True)
    fecha_nacimiento = models.DateField(null=True,blank=True)
    observaciones = models.CharField(max_length=255,null=True,blank=True)
    gestor_capta = models.ForeignKey(asesores,on_delete=models.PROTECT,related_name='gestor_capta')
    gestor_aseginado = models.ForeignKey(asesores,on_delete=models.PROTECT,related_name='gestor_asignado',null=True,blank=True)
    operador = models.ForeignKey(User,on_delete=models.PROTECT,related_name='operador',null=True,blank=True)
    estados = (
        ('Activo','Activo'),
        ('En evento','En evento'),
        ('Asistio','Asistio'),
        ('Archivado','Archivado'),
    )
    estado = models.CharField(max_length=255,choices=estados)
    tipos =(
        ('Poco interesado/Poco adecuado','Poco interesado/Poco adecuado'),
        ('Muy interesado/Poco adecuado','Muy interesado/Poco adecuado'),
        ('Poco interesado/Muy adecuado','Poco interesado/Muy adecuado'),
        ('Muy interesado/Muy adecuado','Muy interesado/Muy adecuado')
    )
    tipo = models.CharField(max_length=255,choices=tipos)
    fecha_capta = models.DateField(null=True,blank=True)

class eventos(models.Model):
    id_evento = models.AutoField(primary_key=True)
    horas_evento = (
        ('9:00AM','9:00AM'),
        ('10:00AM','10:00AM'),
        ('11:00AM','11:00AM'),
        ('12:00AM','12:00AM'),
        ('1:00PM','1:00PM'),
        ('2:00PM','2:00PM'),
        ('3:00PM','3:00PM'),
        ('4:00PM','4:00PM'),
    )
    hora_evento = models.TimeField(null=True,blank=True)
    fecha_evento = models.DateField()
    usuario_crea = models.ForeignKey(User,on_delete=models.PROTECT)
    operacion = models.ForeignKey(Operaciones,on_delete=models.PROTECT)
    estados =(
        ('Abierto','Abierto'),
        ('Cerrado','Cerrado'),
    )
    estado_evento = models.CharField(max_length=255,choices=estados)
    usuario_cierra = models.ForeignKey(User,on_delete=models.PROTECT,related_name='usuario_cierra',null=True,blank=True)
    
    class Meta:
        unique_together = ('operacion','fecha_evento','hora_evento')
        verbose_name = 'Evento'
        verbose_name_plural = 'Eventos'

class asistentes_evento(models.Model):
    id_asistente=models.AutoField(primary_key=True)
    evento=models.ForeignKey(eventos,on_delete=models.PROTECT)
    asistente=models.ForeignKey(leads,on_delete=models.PROTECT)
    usuario_asigna = models.ForeignKey(User,on_delete=models.PROTECT,related_name='usuario_asigna')
    cupos = models.IntegerField(null=True,blank=True)
    estados = (
        ('Pendiente','Pendiente'),
        ('Asistio','Asistio'),
        ('No Asistio','No Asistio'),
    )
    estado_cliente = models.CharField(max_length=255,choices=estados)

    class Meta:
        unique_together = ('evento','asistente')
    
class historyline_lead(models.Model):
    id_history = models.AutoField(primary_key=True)
    lead = models.ForeignKey(leads,on_delete=models.PROTECT)
    observacion = models.CharField(max_length=255)
    usuario = models.ForeignKey(User,on_delete=models.PROTECT)
    fecha = models.DateTimeField()
    
class usuario_gestor(models.Model):
    asesor = models.OneToOneField(asesores,on_delete=models.PROTECT)
    usuario = models.OneToOneField(User,on_delete=models.PROTECT)
    
    class Meta:
        verbose_name = 'Usuario gestor'
        verbose_name_plural = 'Usuarios gestores'
        
    def __str__(self):
        return self.usuario.username    
    
    
    
    
    