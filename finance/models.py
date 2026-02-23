from django.db import models
from django.contrib.auth.models import User
from andinasoft.ajax_request import JSONRender
from andinasoft.models import proyectos, clientes
from andinasoft.shared_models import Adjudicacion


# Create your models here.

class recibos_internos(models.Model):
    proyecto = models.ForeignKey(proyectos,on_delete=models.PROTECT)
    fecha = models.DateField(auto_now=True)
    fecha_pago = models.DateField()
    soporte = models.FileField(upload_to='soportes_recibos')
    soporte_hash = models.CharField(max_length=64, blank=True, null=True)
    valor = models.IntegerField()
    cliente = models.CharField(max_length=255,null=True,blank=True)
    condonacion = models.FloatField(default=0)
    abono_capital = models.BooleanField(null=True,blank=True)
    usuario_solicita = models.ForeignKey(User,on_delete=models.PROTECT,
                                         related_name='usuario_solicita')
    usuario_confirma = models.ForeignKey(User,on_delete=models.PROTECT,
                                         related_name='usuario_confirma',
                                         null=True,blank=True)
    fecha_confirma = models.DateField(null=True,blank=True)
    recibo_asociado = models.CharField(max_length=255,null=True,blank=True)
    anulado = models.BooleanField(default=False)
    requiere_revision_manual = models.BooleanField(default=False, help_text='Marca si la solicitud requiere revisión manual antes de procesar')
    motivo_revision = models.TextField(blank=True, null=True, help_text='Motivo por el cual la solicitud requiere revisión manual')

    class Meta:
        verbose_name = 'Recibo interno'
        verbose_name_plural = 'Recibos internos'
        
    def adj_info(self):
        obj_adj = Adjudicacion.objects.using(self.proyecto.proyecto).filter(
            pk=self.cliente
        ).values()
        return list(obj_adj)[0]

    def titular(self):
        obj_adj = Adjudicacion.objects.using(self.proyecto.proyecto).get(
            pk=self.cliente
        )
        
        clientes.objects.filter(pk=obj_adj.idtercero1).values()
        
        return list(clientes.objects.filter(pk=obj_adj.idtercero1).values())[0]
