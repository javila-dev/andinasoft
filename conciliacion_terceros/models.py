from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder
from django.db import models

from andinasoft.models import empresas


class ConfigEmpresa(models.Model):
    """Lo que se recuerda de una empresa entre conciliaciones: qué cuentas de su archivo se suman."""
    empresa = models.OneToOneField(empresas, on_delete=models.CASCADE, related_name='+', db_constraint=False)
    cuentas = models.JSONField(default=list, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Configuración de empresa'
        verbose_name_plural = 'Configuración de empresas'

    def __str__(self):
        return f'{self.empresa_id}: {", ".join(self.cuentas or [])}'


class Conciliacion(models.Model):
    ESTADO_BORRADOR = 'borrador'
    ESTADO_CERRADA = 'cerrada'
    ESTADO_CHOICES = (
        (ESTADO_BORRADOR, 'En revisión'),
        (ESTADO_CERRADA, 'Cerrada'),
    )

    fecha_corte = models.DateField()
    tolerancia = models.DecimalField(max_digits=14, decimal_places=2, default=1000)
    # Proyectos de Andinasoft que no entran al cruce (p. ej. inactivos o aún no conciliables).
    proyectos_excluidos = models.JSONField(default=list, blank=True)
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default=ESTADO_BORRADOR)
    resumen = models.JSONField(default=dict, blank=True)
    notas = models.TextField(blank=True, default='')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+', db_constraint=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Conciliación de terceros'
        verbose_name_plural = 'Conciliaciones de terceros'
        ordering = ['-created_at']

    def __str__(self):
        return f'Conciliación corte {self.fecha_corte}'


class FuenteConciliacion(models.Model):
    """Archivo de saldos por tercero de una empresa (Alegra, SIIGO...) dentro de una conciliación."""
    FORMATO_ALEGRA = 'alegra_balance_tercero'
    FORMATO_SIIGO = 'siigo_terceros_cuenta'
    FORMATO_CHOICES = (
        (FORMATO_ALEGRA, 'Alegra · Balance de prueba por tercero (.xlsx)'),
        (FORMATO_SIIGO, 'SIIGO · Terceros detallado por cuenta (.xlsx)'),
    )

    conciliacion = models.ForeignKey(Conciliacion, on_delete=models.CASCADE, related_name='fuentes')
    empresa = models.ForeignKey(empresas, on_delete=models.PROTECT, related_name='+', db_constraint=False)
    formato = models.CharField(max_length=40, choices=FORMATO_CHOICES)
    archivo = models.CharField(max_length=500)
    archivo_nombre = models.CharField(max_length=255, blank=True, default='')
    fecha_corte_archivo = models.DateField(null=True, blank=True)
    # Cuentas del archivo que se suman; el resto se descarta.
    cuentas_usadas = models.JSONField(default=list, blank=True)
    confirmada = models.BooleanField(default=False)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+', db_constraint=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Fuente de conciliación'
        verbose_name_plural = 'Fuentes de conciliación'
        ordering = ['empresa__nombre']
        constraints = [
            models.UniqueConstraint(fields=['conciliacion', 'empresa'], name='unique_fuente_empresa'),
        ]

    def __str__(self):
        return f'{self.conciliacion_id} {self.empresa_id} {self.formato}'


class AjusteConciliacion(models.Model):
    """
    Traslado de saldo contable registrado durante la revisión: de (tercero, empresa, cuenta) a
    (tercero, empresa, cuenta). No modifica los archivos cargados: el saldo contable de cada tercero
    se recalcula como saldo del archivo + ajustes vigentes. Queda listo para generar el journal.
    """
    TIPO_CUENTA = 'cuenta'
    TIPO_TERCERO = 'tercero'
    TIPO_CHOICES = (
        (TIPO_CUENTA, 'Entre cuentas del mismo tercero'),
        (TIPO_TERCERO, 'Entre terceros'),
    )
    JOURNAL_PENDIENTE = 'pendiente'
    JOURNAL_ENVIADO = 'enviado'
    JOURNAL_CHOICES = (
        (JOURNAL_PENDIENTE, 'Pendiente'),
        (JOURNAL_ENVIADO, 'Enviado'),
    )

    conciliacion = models.ForeignKey(Conciliacion, on_delete=models.CASCADE, related_name='ajustes')
    grupo = models.CharField(max_length=36, db_index=True)  # movimientos guardados juntos
    tipo = models.CharField(max_length=10, choices=TIPO_CHOICES)
    origen_identificacion = models.CharField(max_length=40, db_index=True)
    origen_empresa = models.ForeignKey(empresas, on_delete=models.PROTECT, related_name='+', db_constraint=False)
    origen_cuenta = models.CharField(max_length=30)
    origen_cuenta_nombre = models.CharField(max_length=255, blank=True, default='')
    destino_identificacion = models.CharField(max_length=40, db_index=True)
    destino_empresa = models.ForeignKey(empresas, on_delete=models.PROTECT, related_name='+', db_constraint=False)
    destino_cuenta = models.CharField(max_length=30)
    destino_cuenta_nombre = models.CharField(max_length=255, blank=True, default='')
    valor = models.DecimalField(max_digits=18, decimal_places=2)
    misma_empresa = models.BooleanField(default=True)
    nota = models.TextField(blank=True, default='')
    anulado = models.BooleanField(default=False)
    anulado_por = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+', db_constraint=False)
    anulado_en = models.DateTimeField(null=True, blank=True)
    journal_estado = models.CharField(max_length=20, choices=JOURNAL_CHOICES, default=JOURNAL_PENDIENTE)
    journal_ref = models.CharField(max_length=100, blank=True, default='')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+', db_constraint=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Ajuste de conciliación'
        verbose_name_plural = 'Ajustes de conciliación'
        ordering = ['created_at', 'id']

    def __str__(self):
        return f'{self.origen_identificacion} {self.origen_cuenta} -> {self.destino_identificacion} {self.destino_cuenta}: {self.valor}'


class ConciliacionLinea(models.Model):
    """
    Un tercero: lo que le corresponde según Andinasoft (sus negocios) contra la suma de sus
    saldos en la contabilidad de todas las empresas (las cuentas seleccionadas).
    """
    ESTADO_CUADRADO = 'cuadrado'
    ESTADO_DIFERENCIA = 'diferencia'
    ESTADO_SOLO_CONTABLE = 'solo_contable'
    ESTADO_SOLO_ANDINA = 'solo_andina'
    ESTADO_CHOICES = (
        (ESTADO_CUADRADO, 'Cuadra'),
        (ESTADO_DIFERENCIA, 'Con diferencia'),
        (ESTADO_SOLO_CONTABLE, 'Solo en contabilidad'),
        (ESTADO_SOLO_ANDINA, 'Solo en Andinasoft'),
    )

    REVISION_PENDIENTE = 'pendiente'
    REVISION_OK = 'ok'
    REVISION_AJUSTE = 'ajuste'
    REVISION_ANDINA = 'corregir_andina'
    REVISION_CHOICES = (
        (REVISION_PENDIENTE, 'Pendiente'),
        (REVISION_OK, 'Revisado, sin acción'),
        (REVISION_AJUSTE, 'Requiere ajuste contable'),
        (REVISION_ANDINA, 'Corregir en Andinasoft'),
    )

    conciliacion = models.ForeignKey(Conciliacion, on_delete=models.CASCADE, related_name='lineas')
    identificacion = models.CharField(max_length=40, db_index=True)
    nombre = models.CharField(max_length=255, blank=True, default='')
    saldo_andina = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    saldo_contable = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    diferencia = models.DecimalField(max_digits=18, decimal_places=2, default=0)  # contable - Andinasoft
    capital = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    intereses = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, db_index=True)
    # Lado Andinasoft: [{proyecto, ref, situacion, ..., valor, suma}]
    negocios = models.JSONField(default=list, blank=True)
    # Lado contable: [{empresa, empresa_nombre, cuenta, cuenta_nombre, saldo_archivo, ajustes, saldo}]
    cuentas = models.JSONField(default=list, blank=True)
    alertas = models.JSONField(default=list, blank=True)  # [{codigo, texto}]
    observacion = models.TextField(blank=True, default='')
    sugerencia = models.JSONField(default=dict, blank=True)
    revision = models.CharField(max_length=20, choices=REVISION_CHOICES, default=REVISION_PENDIENTE, db_index=True)
    nota = models.TextField(blank=True, default='')
    revisado_por = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+', db_constraint=False)
    revisado_en = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Línea de conciliación'
        verbose_name_plural = 'Líneas de conciliación'
        ordering = ['identificacion']
        constraints = [
            models.UniqueConstraint(fields=['conciliacion', 'identificacion'], name='unique_linea_tercero'),
        ]
        indexes = [
            models.Index(fields=['conciliacion', 'estado'], name='conc_linea_estado_idx'),
        ]

    def __str__(self):
        return f'{self.identificacion} {self.estado}'


class CorreccionIdentificacion(models.Model):
    """Registro de una corrección de identificación de tercero (Andinasoft y, opcionalmente, Alegra)."""
    ESTADO_EJECUTADA = 'ejecutada'
    ESTADO_PARCIAL = 'parcial'
    ESTADO_REVERTIDA = 'revertida'
    ESTADO_CHOICES = (
        (ESTADO_EJECUTADA, 'Ejecutada'),
        (ESTADO_PARCIAL, 'Parcial (con error)'),
        (ESTADO_REVERTIDA, 'Revertida'),
    )

    conciliacion = models.ForeignKey(Conciliacion, null=True, blank=True, on_delete=models.SET_NULL, related_name='correcciones')
    id_errado = models.CharField(max_length=40, db_index=True)
    id_correcto = models.CharField(max_length=40, db_index=True)
    modo = models.CharField(max_length=20)  # renombrar | fusionar
    motivo = models.TextField(blank=True, default='')
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default=ESTADO_EJECUTADA)
    vista_previa = models.JSONField(default=dict, blank=True, encoder=DjangoJSONEncoder)
    # Filas cambiadas por tabla (para revertir) y snapshot de los clientes involucrados.
    detalle = models.JSONField(default=dict, blank=True, encoder=DjangoJSONEncoder)
    alegra = models.JSONField(default=list, blank=True, encoder=DjangoJSONEncoder)
    error = models.TextField(blank=True, default='')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+', db_constraint=False)
    created_at = models.DateTimeField(auto_now_add=True)
    revertido_en = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Corrección de identificación'
        verbose_name_plural = 'Correcciones de identificación'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.id_errado} -> {self.id_correcto} ({self.estado})'


class ConfigFacturacion(models.Model):
    """
    Cómo se factura cada proyecto: en qué empresa, si la factura es solo informativa o se crea en Alegra,
    y qué numeración, ítems, impuesto y cuentas usar para la factura y para cruzar el anticipo.
    """
    MODO_INFORMATIVA = 'informativa'
    MODO_ALEGRA = 'alegra'
    MODO_CHOICES = (
        (MODO_INFORMATIVA, 'Solo registro informativo'),
        (MODO_ALEGRA, 'Crear la factura en Alegra'),
    )
    EMISION_BORRADOR = 'borrador'
    EMISION_EMITIR = 'emitir'
    EMISION_CHOICES = (
        (EMISION_BORRADOR, 'Solo crear (borrador)'),
        (EMISION_EMITIR, 'Crear y emitir ante la DIAN'),
    )

    empresa = models.ForeignKey(empresas, on_delete=models.CASCADE, related_name='+', db_constraint=False)
    proyecto = models.CharField(max_length=255)
    modo = models.CharField(max_length=20, choices=MODO_CHOICES, default=MODO_INFORMATIVA)
    emision = models.CharField(max_length=20, choices=EMISION_CHOICES, default=EMISION_BORRADOR)
    forma_pago = models.CharField(max_length=10, default='CREDIT')  # CREDIT | CASH
    dias_vencimiento = models.PositiveIntegerField(default=0)
    numeracion_id = models.CharField(max_length=40, blank=True, default='')
    numeracion_nombre = models.CharField(max_length=255, blank=True, default='')
    item_venta_id = models.CharField(max_length=40, blank=True, default='')
    item_venta_nombre = models.CharField(max_length=255, blank=True, default='')
    item_intereses_id = models.CharField(max_length=40, blank=True, default='')
    item_intereses_nombre = models.CharField(max_length=255, blank=True, default='')
    impuesto_id = models.CharField(max_length=40, blank=True, default='')  # vacío = sin impuesto
    impuesto_nombre = models.CharField(max_length=255, blank=True, default='')
    centro_costo_id = models.CharField(max_length=40, blank=True, default='')
    centro_costo_nombre = models.CharField(max_length=255, blank=True, default='')
    # Cruce del anticipo: débito a la cuenta de anticipos, crédito a la cuenta por cobrar de la factura.
    cuenta_cxc_id = models.CharField(max_length=40, blank=True, default='')
    cuenta_cxc_codigo = models.CharField(max_length=30, blank=True, default='')
    cuenta_cxc_nombre = models.CharField(max_length=255, blank=True, default='')
    numeracion_journal_id = models.CharField(max_length=40, blank=True, default='')
    numeracion_journal_nombre = models.CharField(max_length=255, blank=True, default='')
    # Costo de venta: débito a costo (6) y crédito al inventario del proyecto (15), a nombre de la empresa.
    costo_m2 = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    cuenta_costo_id = models.CharField(max_length=40, blank=True, default='')
    cuenta_costo_codigo = models.CharField(max_length=30, blank=True, default='')
    cuenta_costo_nombre = models.CharField(max_length=255, blank=True, default='')
    cuenta_inventario_id = models.CharField(max_length=40, blank=True, default='')
    cuenta_inventario_codigo = models.CharField(max_length=30, blank=True, default='')
    cuenta_inventario_nombre = models.CharField(max_length=255, blank=True, default='')
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+', db_constraint=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Configuración de facturación'
        verbose_name_plural = 'Configuración de facturación'
        ordering = ['proyecto']
        constraints = [
            models.UniqueConstraint(fields=['proyecto'], name='unique_config_facturacion_proyecto'),
        ]

    def __str__(self):
        return f'{self.proyecto} -> {self.empresa_id} ({self.modo})'

    def faltantes_alegra(self):
        req = {
            'numeración': self.numeracion_id, 'ítem de venta': self.item_venta_id, 'ítem de intereses': self.item_intereses_id,
            'cuenta por cobrar': self.cuenta_cxc_id,
            'cuenta de costo': self.cuenta_costo_id, 'cuenta de inventario': self.cuenta_inventario_id,
        }
        return [k for k, v in req.items() if not v]


class FacturaConciliacion(models.Model):
    """
    Factura de un titular registrada desde la conciliación. Cierra el anticipo:
    resta del lado Andinasoft (el negocio ya se facturó) y, si el cruce no está aún en el archivo contable,
    resta el valor de la cuenta de anticipos.
    """
    TIPO_INFORMATIVA = 'informativa'
    TIPO_ALEGRA = 'alegra'
    TIPO_CHOICES = ((TIPO_INFORMATIVA, 'Informativa (ya emitida)'), (TIPO_ALEGRA, 'Creada en Alegra'))
    CONCEPTO_CHOICES = (
        ('venta_intereses', 'Venta (capital + intereses)'),
        ('venta', 'Solo capital'),
        ('intereses', 'Solo intereses'),
    )
    ESTADO_REGISTRADA = 'registrada'
    ESTADO_PENDIENTE = 'pendiente'
    ESTADO_BORRADOR = 'borrador'
    ESTADO_EMITIDA = 'emitida'
    ESTADO_ERROR = 'error'
    ESTADO_ANULADA = 'anulada'
    ESTADO_CHOICES = (
        (ESTADO_REGISTRADA, 'Registrada'),
        (ESTADO_PENDIENTE, 'Pendiente de enviar'),
        (ESTADO_BORRADOR, 'Borrador en Alegra'),
        (ESTADO_EMITIDA, 'Emitida'),
        (ESTADO_ERROR, 'Error'),
        (ESTADO_ANULADA, 'Anulada'),
    )
    CRUCE_NO_APLICA = 'no_aplica'
    CRUCE_PENDIENTE = 'pendiente'
    CRUCE_REGISTRADO = 'registrado'
    CRUCE_CHOICES = ((CRUCE_NO_APLICA, 'Ya cruzado en contabilidad'), (CRUCE_PENDIENTE, 'Pendiente'), (CRUCE_REGISTRADO, 'Journal registrado'))

    conciliacion = models.ForeignKey(Conciliacion, on_delete=models.CASCADE, related_name='facturas')
    grupo = models.CharField(max_length=36, db_index=True)  # facturas de los titulares de un mismo negocio
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES)
    empresa = models.ForeignKey(empresas, on_delete=models.PROTECT, related_name='+', db_constraint=False)
    proyecto = models.CharField(max_length=255)
    negocio_ref = models.CharField(max_length=60)
    identificacion = models.CharField(max_length=40, db_index=True)
    nombre = models.CharField(max_length=255, blank=True, default='')
    concepto = models.CharField(max_length=20, choices=CONCEPTO_CHOICES, default='venta_intereses')
    fecha = models.DateField()
    numero = models.CharField(max_length=60, blank=True, default='')
    valor_venta = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    valor_intereses = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    cruce_cuenta = models.CharField(max_length=30, blank=True, default='')
    cruce_cuenta_nombre = models.CharField(max_length=255, blank=True, default='')
    cruce_estado = models.CharField(max_length=20, choices=CRUCE_CHOICES, default=CRUCE_PENDIENTE)
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default=ESTADO_REGISTRADA)
    alegra_invoice_id = models.CharField(max_length=40, blank=True, default='')
    alegra_journal_id = models.CharField(max_length=40, blank=True, default='')
    # Costo del inmueble: uno por negocio (va en la primera factura del grupo), a nombre de la empresa.
    costo = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    costo_estado = models.CharField(max_length=20, choices=CRUCE_CHOICES, default=CRUCE_NO_APLICA)
    alegra_costo_journal_id = models.CharField(max_length=40, blank=True, default='')
    respuesta = models.JSONField(default=dict, blank=True, encoder=DjangoJSONEncoder)
    error = models.TextField(blank=True, default='')
    nota = models.TextField(blank=True, default='')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+', db_constraint=False)
    created_at = models.DateTimeField(auto_now_add=True)
    anulada_por = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+', db_constraint=False)
    anulada_en = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Factura de conciliación'
        verbose_name_plural = 'Facturas de conciliación'
        ordering = ['created_at', 'id']

    def __str__(self):
        return f'{self.identificacion} {self.proyecto} {self.negocio_ref} {self.total} ({self.estado})'

    @property
    def vigente(self):
        return self.estado not in (self.ESTADO_ANULADA, self.ESTADO_ERROR, self.ESTADO_PENDIENTE)
