from datetime import datetime
from django.db import models
from django.db.models import Sum, Q
from django.contrib.auth.models import User

class Countries(models.Model):
    id_country = models.CharField(max_length=255, primary_key=True)
    country_name = models.CharField(max_length=255)
    
    class Meta:
        managed = False
        db_table = 'controlpanel_countries'
        
    def __str__(self):
        return self.country_name
    
class States(models.Model):
    id_state = models.CharField(max_length=255)
    country = models.ForeignKey(Countries, on_delete = models.CASCADE)
    state_name = models.CharField(max_length=255)
    
    class Meta:
        managed = False
        db_table = 'controlpanel_states'
        
    def __str__(self):
        return self.state_name

class Cities(models.Model):
    id_city = models.CharField(max_length=255)
    state = models.ForeignKey(States, on_delete= models.CASCADE)
    city_name = models.CharField(max_length=255)
    
    
    class Meta:
        managed = False
        db_table = 'controlpanel_cities'
        
    def __str__(self):
        return self.city_name

class Cliente(models.Model):
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
    apellidos=models.CharField(max_length=255)
    celular=models.CharField(max_length=255)
    telefono=models.CharField(max_length=255,null=True,blank=True)    
    pais=models.ForeignKey(Countries, on_delete =models.PROTECT)
    estado =models.ForeignKey(States, on_delete =models.PROTECT)
    ciudad=models.ForeignKey(Cities, on_delete =models.PROTECT)
    direccion_residencia=models.CharField(max_length=255)
    direccion_oficina=models.CharField(max_length=255,null=True,blank=True)
    email=models.EmailField()
    fecha_nacimiento=models.DateField()
    ocupacion=models.CharField(max_length=255, null=True, blank=True)
    numero_hijos=models.IntegerField(null=True, blank=True)
    nivel_educativo=models.CharField(max_length=255,choices=(
        ('Bachiller','Bachiller'),
        ('Tecnico','Tecnico'),
        ('Pregrado','Pregrado'),
        ('Postgrado','Postgrado'),
        ('Maestria','Maestria')
    ), null=True,blank=True)
    estado_civil=models.CharField(max_length=255,null=True,blank=True)
    nivel_ingresos=models.CharField(max_length=255,null=True,blank=True,choices=(
        ('MENOR A 3.5 MILLONES','MENOR A 3.5 MILLONES'),
        ('3.5 A 4.5 MILLONES','3.5 A 4.5 MILLONES'),
        ('4.5 A 6.5 MILLONES','4.5 A 6.5 MILLONES'),
        ('MAYOR A 6.5 MILLONES','MAYOR A 6.5 MILLONES')
        )
    )
    vehiculo=models.CharField(max_length=255,null=True,blank=True,choices=(
        ('CARRO','CARRO'),
        ('MOTO','MOTO'),
        ('CARRO/MOTO','CARRO/MOTO'),
        ('NO','NO')
    ))
    vivienda=models.CharField(max_length=255,null=True,blank=True,choices=(
        ('PROPIA','PROPIA'),
        ('FAMILIAR','FAMILIAR'),
        ('ARRENDADA','ARRENDADA')
    ))
    pasatiempos=models.CharField(max_length=255,null=True,blank=True)
    fecha_actualizacion=models.DateField(auto_now=True)
    fecha_creacion=models.DateField(auto_now_add=True)
    siigo_id = models.CharField(max_length=255, null=True,blank=True)
    ip_registro = models.CharField(max_length=255, null=True,blank=True)
    geoloc_registro = models.CharField(max_length=255, null=True,blank=True)
    
    class Meta:
        managed = False
        db_table = 'ventas_cliente'
    
    def __str__(self):
        return self.nombres.upper()+' '+self.apellidos.upper()
    
    def nombre_completo(self):
        return self.nombres.upper()+' '+self.apellidos.upper()

class Forma_pago_alttum(models.Model):
    descripcion = models.CharField(max_length=255,unique=True)
    cuenta_banco = models.CharField(max_length=255)
    cuenta_contable = models.CharField(max_length=255)
    cuenta_andinasoft = models.IntegerField(null=True, blank=True)
    id_siigo = models.CharField(max_length = 255, null=True, blank=True)
    caja_hotel = models.BooleanField(default=False)
    
    class Meta:
        managed = False
        db_table = 'ventas_forma_pago'
        
    def __str__(self):
        return self.descripcion

# Create your models here.
class Hoteles(models.Model):
    nombre = models.CharField(unique=True, max_length=255)
    logo = models.ImageField(upload_to='hoteles',null=True,blank=True)
    id_facturacion_siigo = models.CharField(max_length=255)
    administrador = models.ForeignKey(User,on_delete=models.PROTECT)
    activo = models.BooleanField(default=True)
    
    class Meta:
        managed = False
        db_table = 'hotels_hoteles'
        
    def __str__(self):
        return self.nombre
    
class Habitaciones(models.Model):
    numero = models.CharField(max_length=255)
    hotel = models.ForeignKey(Hoteles, on_delete=models.CASCADE)
    capacidad = models.IntegerField()
    
    class Meta:
        managed = False
        db_table = 'hotels_habitaciones'
        
    def __str__(self):
        return f'{self.hotel} ({self.numero})'
    

class Reservas(models.Model):
    nro_reserva = models.AutoField(primary_key=True)
    fecha_ingresa = models.DateTimeField()
    fecha_sale = models.DateTimeField()
    titular = models.CharField(max_length=255,null=True,blank=True)
    cliente = models.ForeignKey(Cliente, on_delete=models.PROTECT,
                                null=True, blank=True)
    pax = models.IntegerField()
    childs = models.IntegerField(default=0)
    tarifa_noche = models.FloatField()
    habitacion = models.ForeignKey(Habitaciones, on_delete=models.PROTECT)
    usuario = models.ForeignKey(User, on_delete=models.CASCADE)
    estado = models.CharField(max_length=255,choices=(
        ('Pendiente','Pendiente'),
        ('Activa','Activa'),
        ('Cancelada','Cancelada'),
        ('Cerrada','Cerrada')
    ))
    observaciones = models.CharField(max_length=255,null=True,blank=True)

    class Meta:
        managed = False
        db_table = 'hotels_reservas'
    
    def nombre_cliente(self):
        return self.cliente.nombre_completo()


    def consumo(self):
        cuenta = 0
        cons = Consumos.objects.filter(reserva=self.pk)
        if cons.exists():
            for c in cons:
                cuenta += c.valor * c.cantidad
        return cuenta
    
    def totales(self):
        dias = (self.fecha_sale.date() - self.fecha_ingresa.date()).days
        valor = self.tarifa_noche * dias
        
        
        anticipos = Anticipos_hotels.objects.filter(reserva=self.pk
                                         ).aggregate(Sum('valor')
                                                     ).get('valor__sum',0)
        if anticipos == None: anticipos = 0
        consumo = self.consumo()
        
        total = valor + consumo
        
        por_pagar = valor - anticipos + consumo
        
        return valor, anticipos, por_pagar, total
    
class Dias_de_sol(models.Model):
    nro_dia_sol = models.AutoField(primary_key=True)
    hotel = models.ForeignKey(Hoteles, on_delete = models.PROTECT)
    fecha = models.DateField(auto_now_add=True)
    cliente = models.ForeignKey(Cliente, on_delete=models.PROTECT,
                                null=True, blank=True)
    pax = models.IntegerField()
    childs = models.IntegerField(default=0)
    usuario = models.ForeignKey(User, on_delete=models.CASCADE)
    estado = models.CharField(max_length=255,choices=(
        ('Abierta','Abierta'),
        ('Cerrada','Cerrada'),
    ))
    pago_al_ingreso = models.CharField(max_length=255,default='0|None')
    observaciones = models.CharField(max_length=255,null=True,blank=True)
    
    class Meta:
        managed = False
        db_table = 'hotels_dias_de_sol'

    def consumo(self):
        cuenta = 0
        pago_al_ingreso = self.pago_al_ingreso.split('|')
        valor = int(pago_al_ingreso[0].replace(',',''))
        cons = Consumos.objects.filter(dia_de_sol=self.pk)
        if cons.exists():
            for c in cons:
                cuenta += c.valor * c.cantidad
        saldo = cuenta - valor
        return cuenta, saldo
    
    def abonado(self):
        pago_al_ingreso = self.pago_al_ingreso.split('|')
        valor = int(pago_al_ingreso[0].replace(',',''))
        return valor
        
    def nombre_cliente(self):
        return self.cliente.nombre_completo()

class Anticipos_hotels(models.Model):
    origen = models.CharField(max_length=255,choices=(
        ('reservas','Reservas'),
        ('dia de sol','Día de sol')
    ))
    reserva = models.ForeignKey(Reservas, on_delete=models.PROTECT,
                                null=True,blank=True)
    dia_de_sol = models.ForeignKey(Dias_de_sol, on_delete = models.PROTECT,
                                   null=True, blank =True)
    valor = models.FloatField()
    fecha = models.DateField(auto_now_add=True)
    id_siigo = models.CharField(max_length=255, blank=True, null=True)
    vencimiento_siigo = models.CharField(max_length=255, blank=True, null=True)
    usuario = models.ForeignKey(User, on_delete=models.PROTECT)
    forma_pago = models.ForeignKey(Forma_pago_alttum,on_delete=models.PROTECT)
            
    class Meta:
        managed = False
        db_table = 'hotels_anticipos'
        
    def hotel(self):
        if self.dia_de_sol:
            return self.dia_de_sol.hotel
        else:
            return self.reserva.habitacion.hotel
        
    def cliente(self):
        if self.dia_de_sol:
            cliente = self.dia_de_sol.cliente
        else:
            cliente = self.reserva.cliente
        
        try: nombre = cliente.nombre_completo()
        except: nombre = ""
        
        return nombre
    
    def nit_cliente(self):
        if self.dia_de_sol:
            cliente = self.dia_de_sol.cliente
        else:
            cliente = self.reserva.cliente
        
        try: nombre = cliente.pk
        except: nombre = ""
        
        return nombre

    def tipo(self):
        if self.dia_de_sol:
            tipo = 'Dia de sol'
            obj = self.dia_de_sol
        else:
            tipo = 'Reservas'
            obj = self.reserva
            
        return tipo, obj
        
class Facturas_hoteles(models.Model):
    dia_de_sol = models.ForeignKey(Dias_de_sol,on_delete=models.PROTECT,
                                      null=True,blank=True)
    reserva = models.ForeignKey(Reservas,on_delete=models.PROTECT,
                                   null=True,blank=True)
    total = models.FloatField()
    observaciones = models.CharField(max_length=255,null=True,blank=True)
    usuario = models.ForeignKey(User,on_delete=models.PROTECT)
    id_siigo = models.CharField(max_length=255,null=True,blank=True)
    fecha = models.DateField(auto_now_add=True)
    
    class Meta:
        managed = False
        db_table = 'hotels_facturas'
        
    def hotel(self):
        if self.dia_de_sol:
            return self.dia_de_sol.hotel
        else:
            return self.reserva.habitacion.hotel
            
    def tipo(self):
        if self.dia_de_sol:
            tipo = 'Dia de sol'
        else:
            tipo = 'Reservas'
            
        return tipo
    
    def cliente(self):
        if self.dia_de_sol:
            cliente = self.dia_de_sol.cliente
        else:
            cliente = self.reserva.cliente
        
        return cliente.nombre_completo()
    
    def nit_cliente(self):
        if self.dia_de_sol:
            cliente = self.dia_de_sol.cliente
        else:
            cliente = self.reserva.cliente
        
        return cliente.pk
    
    def is_sent_siigo(self):
        if self.id_siigo != None and self.id_siigo != "":
            return 'OK'
        return ""
    
    def consumos(self):
        
        consumos = list()
        
        if self.dia_de_sol:
            obj_cons = Consumos.objects.filter(dia_de_sol = self.dia_de_sol)
        else: 
            obj_cons = Consumos.objects.filter(reserva = self.reserva)
        
        for prod in obj_cons:
            consumos.append({
                'producto':prod.producto.nombre,
                'cantidad':prod.cantidad,
                'vr_unit':f'{prod.valor:,}',
                'total':f'{prod.cantidad * prod.valor:,}',
            })
            
        return consumos
    
    def pagos(self):
        
        obj_pagos = Pagos_facturas.objects.filter(factura = self.pk
            ).values('valor','forma_pago__descripcion',
                        'fecha')
        pagos_list = list(obj_pagos)
        
        if self.dia_de_sol != None:
            
            obj_anticipos = Anticipos_hotels.objects.filter(dia_de_sol = self.dia_de_sol)
            
        else:
            
            obj_anticipos = Anticipos_hotels.objects.filter(reserva = self.reserva)
            
        if obj_anticipos.exists():
            obj_anticipos = obj_anticipos.values('valor','forma_pago__descripcion',
                                                 'fecha')
            pagos_list += list(obj_anticipos)
        
        
        return pagos_list
            

class Pagos_facturas(models.Model):
    factura = models.ForeignKey(Facturas_hoteles, on_delete = models.CASCADE)
    valor = models.FloatField()
    forma_pago = models.ForeignKey(Forma_pago_alttum,on_delete = models.PROTECT)
    fecha = models.DateField(auto_now_add=True)
    usuario = models.ForeignKey(User,on_delete = models.PROTECT)
    
    class Meta:
        managed = False
        db_table = 'hotels_pagos_facturas'
        
class Impuestos(models.Model):
    name = models.CharField(max_length=255,unique=True)
    id_siigo = models.IntegerField()
    porcentaje = models.FloatField(default=0)

    class Meta:
        managed = False
        db_table = 'hotels_impuestos'
        
    def __str__(self):
        return self.name 
        
class Productos(models.Model):
    nombre = models.CharField(max_length=255, unique=True)
    impuestos = models.ManyToManyField(Impuestos)
    id_prod_siigo = models.CharField(max_length=255) 
    es_compuesto = models.BooleanField(default=False)
    se_vende = models.BooleanField(default = False)
    es_inventariable = models.BooleanField(default = True)
    unidad_medida = models.CharField(max_length=255, blank=True, null=True)
    activo = models.BooleanField(default=True)
    
    class Meta:
        managed = False
        db_table = 'hotels_productos'
        
    def __str__(self):
        return self.nombre
    

    
class Consumos(models.Model):
    origen = models.CharField(max_length=255,choices=(
        ('reserva','reserva'),
        ('dia de sol','dia de sol'),
    ))
    reserva = models.ForeignKey(Reservas, on_delete=models.CASCADE,
                                null=True,blank=True)
    dia_de_sol = models.ForeignKey(Dias_de_sol, on_delete=models.CASCADE,
                                null=True,blank=True)
    valor = models.FloatField()
    cantidad = models.IntegerField()
    producto = models.ForeignKey(Productos,on_delete=models.PROTECT)
    fecha_consumo = models.DateField(auto_now_add=True, null=True)
    
    class Meta:
        managed = False
        db_table = 'hotels_consumos'
    

    
        

