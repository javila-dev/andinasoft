from django.db import models
from django.contrib.auth.models import User
#------Otros modelos---------
from andinasoft.models import clientes, proyectos, empresas, Pagos, asesores
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


class ActaReunion(models.Model):
    TIPOS_REUNION = (
        ('Servicio al cliente', 'Servicio al cliente'),
        ('Gerencia', 'Gerencia'),
        ('Comercial', 'Comercial'),
        ('Otro', 'Otro'),
    )
    CANALES = (
        ('Presencial', 'Presencial'),
        ('Llamada', 'Llamada'),
        ('Meet', 'Meet'),
        ('WhatsApp', 'WhatsApp'),
        ('Correo', 'Correo'),
    )
    ESTADOS = (
        ('Programada', 'Programada'),
        ('En curso', 'En curso'),
        ('Realizada', 'Realizada'),
        ('Cancelada', 'Cancelada'),
    )

    id_acta = models.AutoField(primary_key=True)
    fecha_reunion = models.DateField()
    hora_reunion = models.TimeField(null=True, blank=True)
    duracion_minutos = models.PositiveIntegerField(default=60)
    tipo_reunion = models.CharField(max_length=255, choices=TIPOS_REUNION)
    canal = models.CharField(max_length=255, choices=CANALES)
    cliente = models.ForeignKey(clientes, on_delete=models.PROTECT, null=True, blank=True, db_constraint=False)
    proyecto = models.ForeignKey(proyectos, on_delete=models.PROTECT, null=True, blank=True, db_constraint=False)
    creado_por = models.ForeignKey(User, on_delete=models.PROTECT, related_name='actas_creadas', db_constraint=False)
    lider_reunion = models.ForeignKey(User, on_delete=models.PROTECT, related_name='actas_lideradas', db_constraint=False)
    asunto = models.CharField(max_length=255)
    resumen = models.TextField()
    decisiones = models.TextField(null=True, blank=True)
    proxima_reunion = models.DateField(null=True, blank=True)
    estado = models.CharField(max_length=255, choices=ESTADOS, default='Programada')
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Acta de reunion'
        verbose_name_plural = 'Actas de reunion'
        ordering = ['-fecha_reunion', '-id_acta']

    def __str__(self):
        return f'Acta #{self.id_acta} - {self.asunto}'


    def inicio_programado(self):
        if self.fecha_reunion and self.hora_reunion:
            return datetime.datetime.combine(self.fecha_reunion, self.hora_reunion)
        return None

    def fin_programado(self):
        inicio = self.inicio_programado()
        if inicio is None:
            return None
        return inicio + datetime.timedelta(minutes=self.duracion_minutos or 0)

    def titulo_calendario(self):
        cliente = self.cliente.nombrecompleto if self.cliente_id else 'Cliente'
        proyecto = self.proyecto_id or 'Proyecto'
        return f'{cliente} · {proyecto}'



class ActaParticipante(models.Model):
    ROLES = (
        ('Interno', 'Interno'),
        ('Cliente', 'Cliente'),
        ('Invitado', 'Invitado'),
    )

    id_participante = models.AutoField(primary_key=True)
    acta = models.ForeignKey(ActaReunion, on_delete=models.CASCADE, related_name='participantes')
    usuario = models.ForeignKey(User, on_delete=models.PROTECT, null=True, blank=True, db_constraint=False)
    nombre_externo = models.CharField(max_length=255, null=True, blank=True)
    email_externo = models.EmailField(null=True, blank=True)
    rol = models.CharField(max_length=255, choices=ROLES)

    class Meta:
        verbose_name = 'Participante de acta'
        verbose_name_plural = 'Participantes de acta'

    def __str__(self):
        if self.usuario_id:
            return f'{self.usuario.get_full_name() or self.usuario.username} - {self.acta}'
        return f'{self.nombre_externo or "Participante externo"} - {self.acta}'


class CompromisoActa(models.Model):
    PRIORIDADES = (
        ('Alta', 'Alta'),
        ('Media', 'Media'),
        ('Baja', 'Baja'),
    )
    ESTADOS = (
        ('Pendiente', 'Pendiente'),
        ('En proceso', 'En proceso'),
        ('Cumplido', 'Cumplido'),
        ('Vencido', 'Vencido'),
        ('Cancelado', 'Cancelado'),
    )

    id_compromiso = models.AutoField(primary_key=True)
    acta = models.ForeignKey(ActaReunion, on_delete=models.CASCADE, related_name='compromisos')
    titulo = models.CharField(max_length=255)
    descripcion = models.TextField()
    responsable = models.ForeignKey(User, on_delete=models.PROTECT, related_name='compromisos_asignados', db_constraint=False)
    fecha_compromiso = models.DateField()
    prioridad = models.CharField(max_length=255, choices=PRIORIDADES, default='Media')
    estado = models.CharField(max_length=255, choices=ESTADOS, default='Pendiente')
    fecha_cierre = models.DateField(null=True, blank=True)
    resultado_cierre = models.TextField(null=True, blank=True)
    creado_por = models.ForeignKey(User, on_delete=models.PROTECT, related_name='compromisos_creados', db_constraint=False)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Compromiso de acta'
        verbose_name_plural = 'Compromisos de acta'
        ordering = ['estado', 'fecha_compromiso', '-id_compromiso']
        indexes = [
            models.Index(fields=['responsable', 'estado', 'fecha_compromiso']),
            models.Index(fields=['estado', 'fecha_compromiso']),
        ]

    def __str__(self):
        return f'{self.titulo} - {self.responsable}'


class SeguimientoCompromiso(models.Model):
    id_seguimiento = models.AutoField(primary_key=True)
    compromiso = models.ForeignKey(CompromisoActa, on_delete=models.CASCADE, related_name='seguimientos')
    usuario = models.ForeignKey(User, on_delete=models.PROTECT, db_constraint=False)
    comentario = models.TextField()
    estado_nuevo = models.CharField(max_length=255, choices=CompromisoActa.ESTADOS, null=True, blank=True)
    fecha_proxima = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Seguimiento de compromiso'
        verbose_name_plural = 'Seguimientos de compromisos'
        ordering = ['-created_at']

    def __str__(self):
        return f'Seguimiento #{self.id_seguimiento} - {self.compromiso}'


class AdjuntoActa(models.Model):
    TIPOS = (
        ('Nota', 'Nota'),
        ('Audio', 'Audio'),
        ('Documento', 'Documento'),
        ('Imagen', 'Imagen'),
        ('Otro', 'Otro'),
    )

    id_adjunto = models.AutoField(primary_key=True)
    acta = models.ForeignKey(ActaReunion, on_delete=models.CASCADE, related_name='adjuntos')
    tipo = models.CharField(max_length=255, choices=TIPOS, default='Documento')
    descripcion = models.CharField(max_length=255, null=True, blank=True)
    archivo = models.FileField(upload_to='crm/actas')
    cargado_por = models.ForeignKey(User, on_delete=models.PROTECT, related_name='adjuntos_acta_cargados', db_constraint=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Adjunto de acta'
        verbose_name_plural = 'Adjuntos de acta'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.tipo} - {self.acta}'

