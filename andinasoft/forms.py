import datetime
from decimal import Decimal

from crispy_forms.bootstrap import FieldWithButtons, InlineRadios, StrictButton, PrependedText, AppendedText, PrependedAppendedText
from crispy_forms.helper import FormHelper
from crispy_forms.layout import (HTML, ButtonHolder, Column, Div, Field,
                                 Fieldset, Layout, Row, Submit)
from django import forms
from django.contrib.auth.models import User
from django.core.validators import FileExtensionValidator
from django.db.models import Q
from tempus_dominus.widgets import DatePicker, DateTimePicker, TimePicker

from andinasoft.models import (CIUU, Countries, asesores, clientes,
                               entidades_bancarias, proyectos)
from andinasoft.shared_models import (Adjudicacion, Recaudos_general, formas_pago,
                                      ventas_nuevas)
from andina import customfields

class floating_labels(Field):
    template='crispycustom/floating_labels.html'
    
class datepickerField(Field):
    template='crispycustom/datepicker.html'

class floatSelectField(Field):
    template='crispycustom/floating_select.html'

class plainInputField(Field):
    template = 'crispycustom/plain_input.html'

class customSelectField(Field):
    template = 'crispycustom/custom_select.html'
    
class SimplyField(Field):
    template = 'crispycustom/simply_field.html'
    
class CheckField(Field):
    template = 'crispycustom/check_field.html'

class registrar_asesor(forms.Form):
    Cedula=forms.IntegerField()
    Nombre=forms.CharField()
    Email=forms.EmailField()
    Direccion=forms.CharField()
    Telefono=forms.CharField()
    fecha_nacimiento=forms.DateField(label='')
    
    list_estados=(
                ('Soltero','Soltero'),
                ('Casado','Casado'),
                ('Union Libre','Union Libre'),    
                ('Otro','Otro')
                )
    Estado_civil=forms.ChoiceField(choices=list_estados,label='Estado Civil')
    list_nivel_educativo=(
                        ('Bachiller','Bachiller'),
                        ('Tecnico','Tecnico'),
                        ('Tecnologo','Tecnologo'),
                        ('Pregrado','Pregrado'),
                        ('Postgrado','Postgrado'),
                        ('Ninguno','Ninguno')
                        )
    Nivel_educativo=forms.ChoiceField(choices=list_nivel_educativo)
    list_equipos=(
        ('Fractal','Fractal'),
        ('Tesoro Escondido','Tesoro Escondido'),
        ('Vegas de Venecia','Vegas de Venecia'),
        ('Perla del mar','Perla del mar'),
                )
    Equipo=forms.ChoiceField(choices=list_equipos)
    query_bancos=entidades_bancarias.objects.all()
    Banco=forms.ModelChoiceField(query_bancos,required=False)
    choices =(
        ('Ahorros','Ahorros'),
        ('Corriente','Corriente')
    )
    tipo_cta = forms.ChoiceField(choices=choices,label='Tipo de Cuenta')
    num_cta=forms.CharField(max_length=255,label='Numero de Cuenta',required=False)
    doc_rut=forms.FileField(label='Cargar Rut',required=False,validators=[FileExtensionValidator(allowed_extensions=['pdf'],
                                                                    message="Debes cargar un archivo pdf")])
    doc_cc=forms.FileField(label='Cargar Cedula',validators=[FileExtensionValidator(allowed_extensions=['pdf'],
                                                                    message="Debes cargar un archivo pdf")])
    cert_bancaria=forms.FileField(label='Certificado Bancario',required=False,validators=[FileExtensionValidator(allowed_extensions=['pdf'],
                                                                    message="Debes cargar un archivo pdf")])
    hv = forms.FileField(label='Hoja de vida',required=True,validators=[FileExtensionValidator(allowed_extensions=['pdf'],
                                                                    message="Debes cargar un archivo pdf")])
    afiliaciones = forms.FileField(label='Afilacion EPS y Pension',required=True,help_text='Por favor carga en un solo PDF ambas afiliaciones',
                                   validators=[FileExtensionValidator(allowed_extensions=['pdf'],
                                                                    message="Debes cargar un archivo pdf")])
    politica_datos=forms.BooleanField(label='')
    
    def __init__(self,*args,**kwargs):
        super().__init__(*args,*kwargs)
        self.helper=FormHelper()
        self.helper.form_id="form-registroasesor"
        self.helper.layout=Layout(
            Div(
                Div(floating_labels('Cedula',placeholder='Cedula'),css_class='col-md-6 mb-2'),
                Div(datepickerField('fecha_nacimiento',placeholder='Fecha de Nacimiento'),css_class='col-md-6 pt-4 mb-2'),
                css_class='row mx-0'
            ),
            Div(
                Div(floating_labels('Nombre',placeholder='Nombre'),css_class='col-12 mb-2'),
                css_class='row mx-0'
            ),
            Div(
                Div(floating_labels('Telefono',placeholder='Telefono'),css_class='col-md-5 mb-2'),
                Div(floating_labels('Email',placeholder='Email'),css_class='col-md-7 mb-2'),
                css_class='row mx-0'
            ),
            Div(
                Div(floating_labels('Direccion',placeholder='Direccion'),css_class='col-md-7 mb-2'),
                Div(floatSelectField('Estado_civil',placeholder='Estado Civil'),css_class='col-md-5 mb-2'),
                css_class='row mx-0'
            ),
            Div(
                Div(floatSelectField('Nivel_educativo',placeholder='Nivel Educativo'),css_class='col-md-6 mb-2'),
                Div(floatSelectField('Equipo',placeholder='Equipo'),css_class='col-md-6 mb-2'),
                css_class='row mx-0'
            ),
            Div(
                Div(floatSelectField('Banco',placeholder='Banco'),css_class='col-md-6 mb-2'),
                Div(floatSelectField('tipo_cta',placeholder='Tipo de cuenta'),css_class='col-md-6 mb-2'),
                css_class='row mx-0'
            ),
            Div(
                Div(floating_labels('num_cta',placeholder='Numero de cuenta'),css_class='col-12 mb-2'),
                css_class='row mx-0'
            ),
            Div(
                Div(Field('doc_cc'),css_class='col-12 mb-1'),
                Div(Field('doc_rut'),css_class='col-12 mb-1'),
                Div(Field('cert_bancaria'),css_class='col-12 mb-1'),
                Div(Field('hv'),css_class='col-12 mb-1'),
                Div(Field('afiliaciones'),css_class='col-12 mb-1'),
                css_class='row mx-0 mb-2'
            ),
            Div(CheckField('politica_datos',css_class='col-12 mb-1'),
                css_class='row mx-0 ps-3'
            ),
            Div(
                Submit('btnRegistrar','Registrar',css_class='btn btn-andina btn-lg btn-block'),
                css_class='row mx-0 px-3 pt-2',
            )
        )
    
    def clean_Cedula(self):
        field =self.cleaned_data.get('Cedula')
        sc=asesores.objects.filter(cedula=field).exists()
        if sc:
            self.add_error('Cedula','Ya existe un asesor registrado con este numero de cedula')
        return field
    
    def clean_Nombre(self):
        field = self.cleaned_data['Nombre']
        return field.upper()
    
class detalle_adjudicacion(forms.Form):
    titular1=forms.CharField(label='Titular 1',required=False,
                             widget=forms.TextInput(attrs={
                                 'size':'40',
                                 'id':'titular1',
                                 'append': 'fa fa-calendar',
                                 'readonly':True,
                                 }))
    titular2=forms.CharField(label='Titular 2',required=False,
                             widget=forms.TextInput(attrs={'size':'40','id':'titular2','readonly':True,}))
    titular3=forms.CharField(label='Titular 3',required=False,
                             widget=forms.TextInput(attrs={'size':'40','id':'titular3','readonly':True,}))
    titular4=forms.CharField(label='Titular 4',required=False,
                             widget=forms.TextInput(attrs={'size':'40','id':'titular4','readonly':True,}))
    oficina=forms.CharField(label='Oficina',required=False,
                             widget=forms.TextInput(attrs={'size':'40','id':'oficina','readonly':True,}))
    cartera=forms.CharField(disabled=True,label='Cartera',required=False,
                            widget=forms.TextInput(attrs={'id':'cartera'}))
    inmueble=forms.CharField(disabled=True,label='Inmueble',required=False,
                             widget=forms.TextInput(attrs={'id':'inmueble'}))
    estado=forms.CharField(disabled=True,label='Estado',required=False,
                           widget=forms.TextInput(attrs={'id':'estado'}))
    tipo_venta=forms.CharField(disabled=True,label='Tipo Venta',required=False,
                               widget=forms.TextInput(attrs={'id':'origen'}))
    valor=forms.CharField(disabled=True,label='Valor',required=False,localize=True,
                          widget=forms.TextInput(attrs={'id':'valor','class':'text-align-center'}))
    
    cuota_inicial=forms.CharField(disabled=True,label='Cuota Inicial',required=False,localize=True,
                                  widget=forms.TextInput(attrs={'id':'cta_inicial'}))
    saldo=forms.CharField(disabled=True,label='Cartera Admin',required=False,
                          widget=forms.TextInput(attrs={'id':'saldo'}))
    pagado=forms.CharField(disabled=True,label='Capital Pagado',required=False,
                              widget=forms.TextInput(attrs={'id':'capital_pagado','class':'text-align-center'}))
    por_pagar=forms.CharField(disabled=True,label='Capital por Pagar',required=False,
                              widget=forms.TextInput(attrs={'id':'capital_por_pagar','class':'text-align-center'}))
    
class documentos_contrato(forms.Form):
    documento_cargar=forms.FileField(label='Documento')
    tipos_docs=(
        ('Opcion','Opcion'),
        ('Promesa','Promesa'),
        ('Cedula','Cedula'),
        ('Admision','Admision'),
        ('Verificacion','Verificacion'),
        ('Pagare','Pagare'),
        ('Carta de Cobro','Carta de Cobro'),
        ('Centrales de Riesgo','Centrales de Riesgo'),
        ('Pago devolucion','Pago devolucion'),
        ('Acta de entrega','Acta de entrega'),
        ('Reestructuracion','Reestructuracion'),
        ('Cesion','Cesion'),
        ('Peticion','Peticion'),
        ('Respuesta Peticion','Respuesta Peticion'),
        ('Comunicados','Comunicados'),
        ('Otros','Otros'),
        ('Carga Inicial','Carga Inicial'),
    )
    tipo_doc=forms.ChoiceField(choices=tipos_docs)
    documento_cargar.widget.attrs.update(id='nombredoc')
    
    def clean_documento_cargar(self):
        nombre_doc=str(self.cleaned_data['documento_cargar'])
        if not nombre_doc.endswith('.pdf'):
            raise forms.ValidationError('Por favor adjunta un documento PDF')
        return nombre_doc
    
class form_lista_proyectos(forms.Form):
    project_list=proyectos.objects.using('default').all()
    proyecto=forms.ModelChoiceField(project_list,label='Proyecto')

class form_nuevo_cliente(forms.Form):
    nombres=forms.CharField(max_length=255,label='Nombres')
    apellidos=forms.CharField(max_length=255,label='Apellidos')
    idTercero=forms.CharField(max_length=255, label='Numero Documento')
    tipo_doc_id = forms.ChoiceField(choices=[
        ('',  'Selecciona...'),
        ('13',  'Cédula de ciudadanía'),
        ('31',	'NIT'),
        ('22',	'Cédula de extranjería'),
        ('50',	'NIT de otro país'),
        ('41',	'Pasaporte'),
        ('47',	'Permiso especial de permanencia PEP'),
        ('21',	'Tarjeta de extranjería'),
    ], label = 'Tipo de Documento')
    fecha_exp_id = forms.DateField(label = 'Fecha de expedición')
    lugar_expedicion_id = forms.CharField(max_length=255, label = 'Lugar de Expedición')
    fecha_nac=forms.DateField(label="Fecha de nacimiento")
    fecha_nac.widget.attrs.update(id='fecha_nac_titular')
    lugar_nacimiento = forms.CharField(max_length=255, label = 'Lugar de nacimiento')
    nacionalidad = forms.CharField(max_length=255, label = "Nacionalidad")
    domicilio=forms.CharField(max_length=255,label='Dirección Domicilio')
    pais = forms.ModelChoiceField(Countries.objects.all().order_by('country_name'))
    estado = forms.ChoiceField(choices = (('','Selecciona...'),), label = 'Departamento/Estado')
    ciudad = forms.ChoiceField(choices = (('','Selecciona...'),))
    celular1=forms.CharField(max_length=255,label='Celular')
    telefono1=forms.CharField(max_length=255,label='Telefono Fijo',required=False)
    email=forms.EmailField()
    
    tipo_ocupacion = forms.ChoiceField(choices = [
        ('','Selecciona...'),
        ('D','Dependiente'),
        ('I','Independiente'),
        ('EP','Empleado Público'),
        ('P','Pensionado'),
        ('FP','Miembro Fuerza Publica'),
        ('O','Otro'),
    ], label='Ocupación')    
    cargo_ocupacion = forms.CharField(max_length=255, label ='Cargo actual')
    ocupacion=forms.CharField(max_length=255,label='Empresa/Organismo')
    ocupacion.widget.attrs.update(id='ocupacion_titular')
    otro_ocupacion = forms.CharField(max_length=255, label = '¿Cual?', required=False)
    
    
    list_nivel_educativo=(
        ('','Selecciona...'),
        ('BACHILLER','Bachiller'),
        ('TECNICO','Tecnico'),
        ('TECNOLOGO','Tecnologo'),
        ('PROFESIONAL','Profesional'),
        ('POSTGRADO','Postgrado'),
        ('NINGUNO','Ninguno')
    )
    nivel_educativo=forms.ChoiceField(choices=list_nivel_educativo)
    nivel_educativo.widget.attrs.update(id='nivel_educativo_titular')
    list_estado_civil=(        
        ('','Selecciona...'),
        ('S','Soltero(a)'),
        ('C','Casado(a)'),
        ('UL','Union Libre'),
        ('O','Otro'),
    )
    estado_civil=forms.ChoiceField(choices=list_estado_civil)
    estado_civil.widget.attrs.update(id='estado_civil')
    list_nivel_ingresos=(
        ('','Selecciona...'),
        ('<3.5','Menor a 3.5 millones'),
        ('3.5-4.5','3.5 a 4.5 millones'),
        ('4.5-6.5','4.5 a 6.5 millones'),
        ('>6.5','Mayor a 6.5 millones')
    )
    nivel_ingresos=forms.ChoiceField(choices=list_nivel_ingresos)
    nivel_ingresos.widget.attrs.update(id='nivel_ingresos_titular')
    list_vehiculo=(
        ('','Selecciona...'),
        ('CRR','Carro'),
        ('MT','Moto'),
        ('CRRMT','Carro y Moto'),
        ('NO','No')
    )
    vehiculo=forms.ChoiceField(choices=list_vehiculo,required=False)
    vehiculo.widget.attrs.update(id='vehiculo_titular')
    list_vivienda=(
        ('','Selecciona...'),
        ('PROPIA','Propia'),
        ('FAMILIAR','Familiar'),
        ('ARRENDADA','Arrendada')
    )
    vivienda=forms.ChoiceField(choices=list_vivienda)
    vivienda.widget.attrs.update(id='vivienda_titular')
    
    
    
    
    
    ingresos_provienen_de = forms.CharField(max_length=255, label = 'Sus ingresos provienen de')
    declara_renta = forms.ChoiceField(choices=[('','Selecciona...'),(False,'No'),(True,'Si')],
                                      label='¿Declara renta?')
    tiene_rut = forms.ChoiceField(choices=[('','Selecciona...'),(False,'No'),(True,'Si')],
                                  label='¿Tiene RUT?')
    ciuu = forms.ModelChoiceField(CIUU.objects.all(), empty_label='Selecciona...',label='Codigo CIIU',
                                  required=False)
    p_compl_1 = forms.ChoiceField(label='', choices=[(True,'Si'),(False,'No')])
    compl_p_compl_1 = forms.CharField(max_length=255, label = 'Indique el pais o paises', required=False, )
    p_compl_2 = forms.ChoiceField(label='', choices=[(True,'Si'),(False,'No')])
    compl_p_compl_2 = forms.CharField(max_length=255, label = 'Indique en que moneda', required=False)
    p_compl_3 = forms.ChoiceField(label='', choices=[(True,'Si'),(False,'No')])
    compl_p_compl_3 = forms.CharField(max_length=255, label = 'Indique que tipo de inversión', required=False)
    p_compl_4 = forms.ChoiceField(label='', choices=[(True,'Si'),(False,'No')])
    compl_p_compl_4 = forms.CharField(max_length=255, label = 'Indique en que entidad', required=False)
    p_compl_5 = forms.ChoiceField(label='', choices=[(True,'Si'),(False,'No')])
    compl_p_compl_5 = forms.CharField(max_length=255, label = 'Indique de que pais o paises', required=False)
    p_compl_6 = forms.ChoiceField(label='', choices=[(True,'Si'),(False,'No')], required= True)
    compl_p_compl_6 = forms.CharField(max_length=255, label = 'Indique a que pais o paises', required=False)
    
    es_peps = forms.ChoiceField(choices=[('','Selecciona...'),(True,'Si'),(False,'No')],
                                      label='¿Es usted un PEPS?')
    peps_desde = forms.DateField(required=False, label = 'Peps desde')
    peps_hasta = forms.DateField(required=False, label = 'Peps hasta')
    entidad_peps = forms.CharField(max_length=255, label = 'Entidad', required=False)
    cargo_peps = forms.CharField(max_length=255, label = 'Cargo', required=False)
    es_familiar_peps = forms.ChoiceField(choices=[('','Selecciona...'),(True,'Si'),(False,'No')],
                                      label='¿Es familar o asociado de un PEPS?')
    parentesco_familiar_peps = forms.CharField(max_length=255, label = 'Parentesco', required=False)
    entidad_familiar_peps = forms.CharField(max_length=255, label = 'Entidad', required=False)
    cargo_familiar_peps = forms.CharField(max_length=255, label = 'Cargo', required=False)
    ref_familiar_nombre = forms.CharField(max_length=255, label = 'Nombres y Apellidos')
    ref_familiar_telefono = forms.CharField(max_length=255, label = 'Telefono')
    ref_personal_nombre = forms.CharField(max_length=255, label = 'Nombres y Apellidos')
    ref_personal_telefono = forms.CharField(max_length=255, label = 'Telefono')
    tratamiento_datos = forms.BooleanField(label='Confirmo que he leido y aceptado la politica de tratamiento de datos personales')
    
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.helper = FormHelper()
        self.helper.form_id = 'form-cliente'
        self.helper.layout = Layout(
            HTML(
                "<p class='lead border-bottom border-gray fw-bold pt-3'>Informacion Básica</p> "
            ),
            Div(
                Div(floating_labels('nombres',placeholder='Nombre'), css_class='col-md-12 col-lg-6 pt-2'),
                Div(floating_labels('apellidos',placeholder='Apellidos'), css_class='col-md-12 col-lg-6 pt-2'),
                css_class='row'
            ),
            Div(
                Div(floatSelectField('tipo_doc_id',placeholder='Tipo documento'), css_class='col-md-6 pt-2'),
                Div(floating_labels('idTercero',placeholder='Numero documento'), css_class='col-md-6 pt-2'),
                
                Div(datepickerField('fecha_exp_id',css_class='',readonly=True, data_text='Fecha de expedición'),
                                        css_class='col-md-4'),
                Div(floating_labels('lugar_expedicion_id',placeholder='Lugar expedición'), css_class='col-md-4 pt-2'),
                 Div(floating_labels('nacionalidad',placeholder='Nacionalidad'), css_class='col-md-4 col-lg-4 pt-2'),
                
                css_class='row justify-content-between'
            ),
            Div(
                
                Div(datepickerField('fecha_nac',css_class='', readonly=True,
                                    data_text="Fecha de Nacimiento"), css_class='col-md-4 col-lg-4'),
                 Div(floating_labels('lugar_nacimiento',placeholder='Lugar de Nacimiento (Pais, Dpto/Estado, Ciudad)'), css_class='col-md-8 col-lg-8 pt-2'),
               
                css_class='row justify-content-between'
            ),
            Div(
                Div(floating_labels('domicilio',placeholder='Direccion domicilio'), css_class='col-md-12 pt-2'),
                css_class='row',id='rowDomicilio'
            ),
            Div(
                Div(floatSelectField('pais',placeholder='Pais'), css_class='col-sm-12 col-md-6 col-lg-4 pt-2'),
                Div(floatSelectField('estado',placeholder='Estado/Dpto'), css_class='col-sm-12 col-md-6 col-lg-4 pt-2'),
                Div(floatSelectField('ciudad',placeholder='Ciudad'), css_class='col-sm-12 col-md-6 col-lg-4 pt-2'),
                css_class='row'
            ),
            
            Div(
                Div(floating_labels('celular1',placeholder='Celular'), css_class='col-sm-12 col-md-3 pt-2'),
                Div(floating_labels('telefono1',placeholder='Telefono 1'), css_class='col-sm-12 col-md-3 pt-2'),
                Div(floating_labels('email',placeholder='Email'), css_class='col-sm-12 col-md-6 pt-2'),
                css_class='row'
            ),
            HTML(
                '''<p class='lead border-bottom border-gray fw-bold pt-3'>
                    Informacion complementaria requerida SAGRILAFT 
                    <span>
                        <button class='btn btn-outline-secondary' type='button' id='id_btn_wti'
                        data-bs-toggle="tooltip" data-bs-placement="bottom" style="border-color:white;"
                            title="¿Porqué necesitamos esta información?">    
                            <i class="fas fa-question-circle"></i></button></span></p>'''
            ),
            Div(
                Div(floatSelectField('tipo_ocupacion',placeholder='Ocupación'), css_class='col-sm-12 col-md-6 col-lg-4 pt-2'),
                Div(floating_labels('ocupacion',placeholder='Empresa/Organismo'), css_class='col-md-12 col-lg-4 pt-2'),
                Div(floating_labels('cargo_ocupacion',placeholder='Cargo actual'), css_class='col-md-12 col-lg-4 pt-2'),
                Div(floating_labels('otro_ocupacion',placeholder='¿Cual?'), css_class='col-md-12 col-lg-8 pt-2'),
                Div(floatSelectField('vivienda',placeholder='Vivienda'), css_class='col-md-6 col-lg-4 pt-2'),
                Div(floatSelectField('estado_civil',placeholder='Estado Civil'), css_class='col-md-6 col-lg-4 pt-2'),
                Div(floatSelectField('nivel_educativo',placeholder='Nivel Educativo'), css_class='col-md-6 col-lg-4 pt-2'),
                css_class='row'
            ),
            Div(
                Div(floatSelectField('nivel_ingresos',placeholder='Nivel Ingresos'), css_class='col-md-6 col-lg-4 pt-2'),
                Div(floating_labels('ingresos_provienen_de',placeholder='Sus ingresos provienen de'), css_class='col-md-6 col-lg-8 pt-2'),
                Div(floatSelectField('declara_renta',placeholder='¿Declara renta?'), css_class='col-md-6 pt-2'),
                Div(floatSelectField('tiene_rut',placeholder='¿Tiene RUT?'), css_class='col-md-6 pt-2'),
                Div(Field('ciuu',placeholder='Coidgo CIUU', css_class='fstdropdown-select', data_text="Codigo CIUU"), css_class='col-md-6 col-lg-4 pt-2'),
                                
                css_class='row'
            ),
            Div(
                Div(HTML('<p class="mb-1">¿Es usted sujeto de obligaciones tributarias en otro país o grupo de paises?</p>'), css_class='col-md-5 pt-2'),
                Div(InlineRadios('p_compl_1', css_class=''), css_class='col-md-3 pt-2'),
                Div(floating_labels('compl_p_compl_1', css_class='compl_p_compl', placeholder = 'Indique el pais o paises'), css_class='col-md-4 pt-2'),
                css_class='row'
            ),
            Div(
                Div(HTML('<p class="mb-1">¿Realiza transacciones en moneda extrajera?</p>'), css_class='col-md-5 pt-2'),
                Div(InlineRadios('p_compl_2', css_class=''), css_class='col-md-3 pt-2'),
                Div(floating_labels('compl_p_compl_2', css_class='compl_p_compl', placeholder = 'Indique en que moneda'), css_class='col-md-4 pt-2'),
                css_class='row'
            ),
            Div(
                Div(HTML('<p class="mb-1">¿Posee inversiones en el exterior?</p>'), css_class='col-md-5 pt-2'),
                Div(InlineRadios('p_compl_3', css_class=''), css_class='col-md-3 pt-2'),
                Div(floating_labels('compl_p_compl_3', css_class='compl_p_compl', placeholder = 'Indique que tipo de inversión'), css_class='col-md-4 pt-2'),
                css_class='row'
            ),
            Div(
                Div(HTML('<p class="mb-1">¿Posee cuentas en moneda extranjera?</p>'), css_class='col-md-5 pt-2'),
                Div(InlineRadios('p_compl_4', css_class=''), css_class='col-md-3 pt-2'),
                Div(floating_labels('compl_p_compl_4', css_class='compl_p_compl', placeholder = 'Indique en que entidad'), css_class='col-md-4 pt-2'),
                css_class='row'
            ),
            Div(
                Div(HTML('<p class="mb-1">¿Realiza transferencias al extranjero?</p>'), css_class='col-md-5 pt-2'),
                Div(InlineRadios('p_compl_5', css_class=''), css_class='col-md-3 pt-2'),
                Div(floating_labels('compl_p_compl_5', css_class='compl_p_compl', placeholder = 'Indique de que pais o paises'), css_class='col-md-4 pt-2'),
                css_class='row'
            ),
            Div(
                Div(HTML('<p class="mb-1">¿Recibe transferencias del extranjero?</p>'), css_class='col-md-5 pt-2'),
                Div(InlineRadios('p_compl_6', css_class=''), css_class='col-md-3 pt-2'),
                Div(floating_labels('compl_p_compl_6', css_class='compl_p_compl', placeholder = 'Indique a que pais o paises'), css_class='col-md-4 pt-2'),
                css_class='row'
            ),
            HTML(
                '''<p class='pt-2 mb-1 border-bottom border-gray fw-bold'>Persona Expuesta Politicamente (PEPS)
                    <span>
                        <button class='btn btn-outline-secondary' type='button' id="id_btn_peps"
                        data-bs-toggle="tooltip" data-bs-placement="bottom" style="border-color:white;"
                            title="¿Qué es un PEPS?">    
                            <i class="fas fa-question-circle"></i></button></span></p> '''
            ),
            Div(
                Div(floatSelectField('es_peps',placeholder='¿Es usted un PEPS?'), css_class='col-md-4 pt-2'),
                Div(datepickerField('peps_desde', css_class= 'initial-hide',readonly = True, data_text="Peps desde"), css_class='col-md-4 pt-2 peps-col'),  
                Div(datepickerField('peps_hasta', css_class= 'initial-hide', readonly = True, data_text="Peps Hasta"), css_class='col-md-4 pt-2 peps-col'),
                Div(floating_labels('entidad_peps', css_class= 'initial-hide', placeholder = 'Entidad'), css_class='col-md-6 pt-2 peps-col'),
                Div(floating_labels('cargo_peps', css_class= 'initial-hide', placeholder = 'Cargo'), css_class='col-md-6 pt-2 peps-col'),
                Div(floatSelectField('es_familiar_peps',placeholder='¿Es familar o asociado de un PEPS?'), css_class='col-md-6 pt-2'),
                Div(floating_labels('parentesco_familiar_peps', css_class= 'initial-hide', placeholder='Parentesco'), css_class='col-md-6 pt-2 familiar-peps-col'),
                Div(floating_labels('entidad_familiar_peps', css_class= 'initial-hide', placeholder = 'Entidad'), css_class='col-md-6 pt-2 familiar-peps-col'),
                Div(floating_labels('cargo_familiar_peps', css_class= 'initial-hide', placeholder = 'Cargo'), css_class='col-md-6 pt-2 familiar-peps-col'),
                css_class='row'
            ),
            HTML(
                "<p class='pt-2 mb-1 border-bottom border-gray fw-bold'>Referencia familiar</p> "
            ),
            Div(
                Div(floating_labels('ref_familiar_nombre', placeholder='Nombres y Apellidos'), css_class='col-md-8 pt-2'),
                Div(floating_labels('ref_familiar_telefono', placeholder='Telefono'), css_class='col-md-4 pt-2'),
                css_class='row'
            ),
            HTML(
                "<p class='pt-2 mb-1 border-bottom border-gray fw-bold'>Referencia personal</p> "
            ),
            Div(
                Div(floating_labels('ref_personal_nombre', placeholder='Nombres y Apellidos'), css_class='col-md-8 pt-2'),
                Div(floating_labels('ref_personal_telefono', placeholder='Telefono'), css_class='col-md-4 pt-2'),
                css_class='row mb-3'
            ),
            CheckField('tratamiento_datos'),
            ButtonHolder(
                Submit('registar','Registrar',css_class='btn btn-primary float-end'),
            css_class='pt-3 pb-4 mb-1')
        )
    
    def clean_idTercero(self):
        field = self.cleaned_data.get('idTercero')
        control = clientes.objects.filter(pk=field)
        if control.exists():
            self.add_error('idTercero','Ya existe un tercero registrado con este numero de cedula')
        return field        

class form_nuevo_cliente_PJ(forms.Form):
    idTercero=forms.CharField(max_length=255, label='Nit')
    idTercero.widget.attrs.update(id='cc_titular')
    nombrecompleto=forms.CharField(max_length=255,label='Razon social',required=False)
    nombres=forms.CharField(max_length=255,label='Razon social')
    nombres.widget.attrs.update(id='nombres_titular')
    apellidos=forms.CharField(max_length=255,label='Representante legal')
    apellidos.widget.attrs.update(id='apellidos_titular')
    celular1=forms.CharField(max_length=255,label='Celular',required=False)
    celular1.widget.attrs.update(id='celular_titular')
    telefono1=forms.CharField(max_length=255,label='Telefono 1',required=False)
    telefono1.widget.attrs.update(id='telefono1_titular')
    telefono2=forms.CharField(max_length=255,label='Telefono 2',required=False)
    telefono2.widget.attrs.update(id='telefono2_titular')
    domicilio=forms.CharField(max_length=255,label='Dir. Domicilio',required=False)
    domicilio.widget.attrs.update(id='domicilio_titular')
    ciudad=forms.CharField(required=False)
    email=forms.EmailField(required=False)
    email.widget.attrs.update(id='email_titular')
    fecha_creac=forms.DateField(label="")
    fecha_creac.widget.attrs.update(id='fecha_creac')
    ocupacion=forms.CharField(max_length=255,required=False,label='Descripcion actividad')
    ocupacion.widget.attrs.update(id='ocupacion_titular')


    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.helper = FormHelper()
        self.helper.form_id = 'form-cliente'
        self.helper.layout = Layout(
            Div(
                Div(floating_labels('idTercero',placeholder='Nit'), css_class='col-md-6 col-lg-3 pt-2'),
                Div(datepickerField('fecha_creac',placeholder='Fecha creacion',css_class='pt-3'), css_class='col-md-6 col-lg-3 pt-4'),
                css_class='row justify-content-between'
            ),
            Div(
                Div(floating_labels('nombres',placeholder='Razon social'), css_class='col-md-12 col-lg-6 pt-2'),
                Div(floating_labels('apellidos',placeholder='Representante legal'), css_class='col-md-12 col-lg-6 pt-2'),
                css_class='row'
            ),
            Div(
                Div(floating_labels('celular1',placeholder='Celular'), css_class='col-sm-12 col-md-6 col-lg-4 pt-2'),
                Div(floating_labels('telefono1',placeholder='Telefono 1'), css_class='col-sm-12 col-md-6 col-lg-4 pt-2'),
                Div(floating_labels('telefono2',placeholder='Telefono 2'), css_class='col-sm-12 col-md-6 col-lg-4 pt-2'),
                css_class='row'
            ),
            Div(
                Div(floating_labels('email',placeholder='Email'), css_class='col-12 pt-2'),
                css_class='row'
            ),
            Div(
                Div(floating_labels('domicilio',placeholder='Direccion domicilio'), css_class='col-md-12 col-lg-6 pt-2'),
                css_class='row',id='rowDomicilioPJ'
            ),
            Div(
                Div(floating_labels('ocupacion',placeholder='Descripcion actividad'), css_class='col-12 pt-2'),
                css_class='row'
            ),
            ButtonHolder(
                Submit('registar','Registrar',css_class='btn btn-primary float-end'),
            css_class='pt-3 pb-4 mb-1')
        )
    
    def clean_idTercero(self):
        field = self.cleaned_data.get('idTercero')
        control = clientes.objects.filter(pk=field)
        if control.exists():
            self.add_error('idTercero','Ya existe un tercero registrado con este numero de cedula')
        return field        


class form_info_titular(forms.Form):
    idTercero=forms.CharField(max_length=255, label='Cedula')
    idTercero.widget.attrs.update(id='cc_titular')
    nombrecompleto=forms.CharField(max_length=255,label='Nombre',required=False)
    nombres=forms.CharField(max_length=255,label='Nombres')
    nombres.widget.attrs.update(id='nombres_titular')
    apellidos=forms.CharField(max_length=255,label='Apellidos')
    apellidos.widget.attrs.update(id='apellidos_titular')
    celular1=forms.CharField(max_length=255,label='Celular',required=False)
    celular1.widget.attrs.update(id='celular_titular')
    celular2=forms.CharField(max_length=255,label='Ceular 2',required=False)
    telefono1=forms.CharField(max_length=255,label='Telefono 1',required=False)
    telefono1.widget.attrs.update(id='telefono1_titular')
    telefono2=forms.CharField(max_length=255,label='Telefono 2',required=False)
    telefono2.widget.attrs.update(id='telefono2_titular')
    domicilio=forms.CharField(max_length=255,label='Dir. Domicilio',required=False)
    domicilio.widget.attrs.update(id='domicilio_titular')
    oficina=forms.CharField(max_length=255,label='Dir. Oficina',required=False)
    oficina.widget.attrs.update(id='oficina_titular')
    ciudad=forms.CharField(required=False)
    email=forms.EmailField(required=False)
    email.widget.attrs.update(id='email_titular')
    fecha_nac=forms.DateField(required=False,label="Fecha Nacimiento",widget=DatePicker(
        options={
                'useCurrent': True,
                'collapse': False,
                'format':'YYYY-MM-DD',
            },
            attrs={
                'append': 'fa fa-calendar',
                'icon_toggle': True,
            }),initial=datetime.datetime.today())
    fecha_nac.widget.attrs.update(id='fecha_nac_titular')
    ocupacion=forms.CharField(max_length=255,required=False,label='Ocupacion')
    ocupacion.widget.attrs.update(id='ocupacion_titular')
    hijos=forms.IntegerField(required=False,label='Hijos',min_value=0)
    hijos.widget.attrs.update(id='hijos_titular')
    list_nivel_educativo=(
                        ('',''),
                        ('BACHILLER','BACHILLER'),
                        ('TECNICO','TECNICO'),
                        ('TECNOLOGO','TECNOLOGO'),
                        ('PROFESIONAL','PROFESIONAL'),
                        ('POSTGRADO','POSTGRADO'),
                        ('NINGUNO','NINGUNO')
                        )
    nivel_educativo=forms.ChoiceField(choices=list_nivel_educativo,required=False)
    nivel_educativo.widget.attrs.update(id='nivel_educativo_titular')
    list_estado_civil=(
        ('SOLTERO','SOLTERO'),
        ('CASADO','CASADO'),
        ('UNION LIBRE','UNION LIBRE'),
        ('OTRO','OTRO'),
        ('',''),
    )
    estado_civil=forms.ChoiceField(choices=list_estado_civil,required=False)
    estado_civil.widget.attrs.update(id='estado_civil')
    list_nivel_ingresos=(
        ('',''),
        ('MENOR A 3.5 MILLONES','MENOR A 3.5 MILLONES'),
        ('3.5 A 4.5 MILLONES','3.5 A 4.5 MILLONES'),
        ('4.5 A 6.5 MILLONES','4.5 A 6.5 MILLONES'),
        ('MAYOR A 6.5 MILLONES','MAYOR A 6.5 MILLONES')
    )
    nivel_ingresos=forms.ChoiceField(choices=list_nivel_ingresos,required=False)
    nivel_ingresos.widget.attrs.update(id='nivel_ingresos_titular')
    list_vehiculo=(
        ('',''),
        ('CARRO','CARRO'),
        ('MOTO','MOTO'),
        ('CARRO,MOTO','CARRO,MOTO'),
        ('NO','NO')
    )
    vehiculo=forms.ChoiceField(choices=list_vehiculo,required=False)
    vehiculo.widget.attrs.update(id='vehiculo_titular')
    list_vivienda=(
        ('',''),
        ('PROPIA','PROPIA'),
        ('FAMILIAR','FAMILIAR'),
        ('ARRENDADA','ARRENDADA')
    )
    vivienda=forms.ChoiceField(choices=list_vivienda,required=False)
    vivienda.widget.attrs.update(id='vivienda_titular')
    pasatiempos=forms.CharField(max_length=255,required=False)
    pasatiempos.widget.attrs.update(id='pasatiempos_titular')
    id_conyuge=forms.CharField(max_length=255,required=False,label='Cedula')
    id_conyuge.widget.attrs.update(id='id_conyuge')
    nombre_cony=forms.CharField(max_length=255,required=False,label='Nombres')
    nombre_cony.widget.attrs.update(id='nombre_cony')
    apellido_cony=forms.CharField(max_length=255,required=False,label='Apellidos')
    apellido_cony.widget.attrs.update(id='apellido_cony')
    celular_cony=forms.CharField(max_length=255,required=False,label='Celular')
    celular_cony.widget.attrs.update(id='celular_cony')
    email_cony=forms.EmailField(required=False,label='Email')
    email_cony.widget.attrs.update(id='email_cony')
    fechanac_cony=forms.CharField(max_length=255,required=False,label='Fecha Nacimiento',
                                  widget=DatePicker(
                                    options={
                                            'useCurrent': True,
                                            'collapse': False,
                                            'format':'YYYY-MM-DD',
                                    },
                                    attrs={
                                            'append': 'fa fa-calendar',
                                            'icon_toggle': True,
                                    }),initial=datetime.datetime.today())
    fechanac_cony.widget.attrs.update(id='fechanac_cony')
    ocupacion_cony=forms.CharField(max_length=255,required=False,label='Ocupacion')
    ocupacion_cony.widget.attrs.update(id='ocupacion_cony')

    
class form_lista_recaudos(forms.Form):
    proyect_choices=proyectos.objects.exclude(Q(pk__icontains='Alttum')|Q(pk__icontains='sol'))
    Proyecto=forms.ModelChoiceField(proyect_choices,label='Proyecto: ')
    Proyecto.widget.attrs.update(id='proyecto')
    Fecha_Desde=forms.DateField(label='Fecha Desde: ',widget=DatePicker(
                options={
                'useCurrent': True,
                'collapse': False,
                'format':'YYYY-MM-DD',
                },
                attrs={
                    'id':'desde',
                    'append': 'fa fa-calendar',
                    'icon_toggle': True,
                }))
    Fecha_Hasta=forms.DateField(label='Fecha Hasta: ',widget=DatePicker(
                options={
                'useCurrent': True,
                'collapse': False,
                'format':'YYYY-MM-DD',
                },
                attrs={
                    'id':'hasta',
                    'append': 'fa fa-calendar',
                    'icon_toggle': True,
                }))
    
    def clean_Fecha_Hasta(self):
        fd=self.cleaned_data['Fecha_Desde']
        fh=self.cleaned_data['Fecha_Hasta']
        if fd>fh:
            raise forms.ValidationError('La fecha inicial no puede ser mayor a la final')
        return self.cleaned_data['Fecha_Hasta']
    
class form_nuevo_recibo(forms.Form):
        
    id_adj=numrecibo=forms.CharField(max_length=255,label='Adj')
    id_adj.widget.attrs.update(readonly=True,id='adj')
    nombre_cliente=forms.CharField(max_length=255)
    nombre_cliente.widget.attrs.update(readonly=True,id='nombre_cliente')
    concepto=forms.CharField(max_length=255)
    concepto.widget.attrs.update(id='concepto')
    abonocapital=forms.BooleanField(required=False,label='Abono a Capital')
    abonocapital.widget.attrs.update(id='abonocapital')
    fecha=forms.DateField(label='Fecha registro',widget=DatePicker(
            options={
                'useCurrent': True,
                'collapse': False,
                'format':'YYYY-MM-DD',
                
            },
            attrs={
                'id':'fecha_de_recibo',
                'append': 'fa fa-calendar',
                'icon_toggle': True,
            }))
    fecha_pago=forms.DateField(label='Fecha de pago',widget=DatePicker(
            options={
                'useCurrent': True,
                'collapse': False,
                'format':'YYYY-MM-DD',
                
            },
            attrs={
                'id':'fecha_de_pago',
                'append': 'fa fa-calendar',
                'icon_toggle': True,
            }))
    """ fecha.widget.attrs.update(id='fecha_recibo') """
    numsolicitud=forms.CharField(max_length=255,label='Numero Solicitud',required=False)
    numsolicitud.widget.attrs.update(readonly=True)
    movimiento_banco_id=forms.CharField(max_length=255,label='ID Movimiento Banco',required=False)
    movimiento_banco_id.widget.attrs.update(style='display:none;')
    numrecibo=forms.CharField(max_length=255,label='Numero Recibo')
    numrecibo.widget.attrs.update(readonly=True,id='numrecibo')
    idtercero=forms.CharField(max_length=255)
    idtercero.widget.attrs.update(readonly=True,id='idtercero')
    valor=forms.CharField(max_length=255)
    valor.widget.attrs.update(id='valor_recibo')
    tipos_condonacion=(
        ('No','No'),
        ('Si','Si')
    )
    condonacion_mora=forms.ChoiceField(choices=tipos_condonacion,label='Cond. Mora',required=False)
    condonacion_mora.widget.attrs.update(id='condonacion_mora')
    condonacion_porc=forms.DecimalField(max_value=100,min_value=0,decimal_places=2,required=False,label='Porcentaje')
    condonacion_porc.widget.attrs.update(id='cond_porc')
    
    def __init__(self, *args, **kwargs):
       my_arg = kwargs.pop('proyecto')
       super(form_nuevo_recibo, self).__init__(*args, **kwargs)
       self.proyecto = my_arg
       choices_fp=formas_pago.objects.using(self.proyecto).all()
       self.fields['forma_pago']=forms.ModelChoiceField(choices_fp,label='Forma de Pago')
       self.fields['forma_pago'].widget.attrs.update(id='forma_pago')

class form_modificar_recibo(forms.Form):
    proyecto=forms.CharField(max_length=255,required=False)
    nrorecibo=forms.CharField(max_length=255,required=False)
    fecha_modif=forms.DateField(required=False,label='Nueva Fecha',widget=DatePicker(
            options={
                'useCurrent': True,
                'collapse': False,
                'format':'YYYY-MM-DD',
                
            },
            attrs={
                'id':'fecha_de_recibo',
                'append': 'fa fa-calendar',
                'icon_toggle': True,
            }))
    consecutivo_modif=forms.CharField(max_length=255,required=False,label='Nuevo Consecutivo')
    forma_pago_modif=forms.ChoiceField(required=False,label='Nueva forma de pago')
    valor_modif=forms.DecimalField(max_digits=15,decimal_places=2,required=False,label='Nuevo Valor')
    nrorecibo.widget.attrs.update(id='nrorecibo',hidden=True)
    proyecto.widget.attrs.update(id='proyecto_modif',hidden=True)
    fecha_modif.widget.attrs.update(id='fecha_modif')
    consecutivo_modif.widget.attrs.update(id='consecutivo_modif')
    forma_pago_modif.widget.attrs.update(id='forma_pago_modif', **{'class':'form-control'})
    valor_modif.widget.attrs.update(id='valor_modif', **{'class':'form-control'})
    
    def clean_consecutivo_modif(self):
        consecutivo = self.cleaned_data.get('consecutivo_modif')
        proyecto = self.cleaned_data.get('proyecto')
        if not consecutivo or not proyecto:
            return consecutivo
        verif_recibo=Recaudos_general.objects.using(proyecto).filter(numrecibo=consecutivo).exists()
        if verif_recibo:
            raise forms.ValidationError('Este consecutivo ya existe')
        return consecutivo
    
    def __init__(self,*args,**kwargs):
        formas_pago_choices = kwargs.pop('formas_pago_choices', [])
        super(form_modificar_recibo,self).__init__(*args,**kwargs)
        base_choices = [('', 'Selecciona una forma de pago')]
        if formas_pago_choices:
            self.fields['forma_pago_modif'].choices = base_choices + formas_pago_choices
        else:
            self.fields['forma_pago_modif'].choices = base_choices
    
class form_nueva_venta(forms.Form):
    #Titulares
    titular1=forms.CharField(max_length=255,label='Titular 1')
    titular2=forms.CharField(max_length=255,label='Titular 2',required=False)
    titular3=forms.CharField(max_length=255,label='Titular 3',required=False)
    titular4=forms.CharField(max_length=255,label='Titular 4',required=False)
    #inmueble y precio
    inmueble=forms.CharField(max_length=255,label='Inmueble')
    valor=forms.IntegerField(min_value=0,label='Valor de Venta')
    valor_letras=forms.CharField(max_length=255,label='Valor en Letras',required=False)
    #Forma de Pago
    porc_cta_ini=forms.IntegerField(label='% CI',max_value=100,min_value=0)
    porc_saldo=forms.IntegerField(label='% Saldo',max_value=100,min_value=0)
    vr_ci=forms.IntegerField(label='Valor CI',min_value=0)
    vr_saldo=forms.IntegerField(label='Valor Saldo',min_value=0)
    fecha_entrega=forms.DateField(required=False,label='Fecha Entrega',widget=DatePicker(
            options={
                'useCurrent': True,
                'collapse': False,
                'format':'YYYY-MM-DD',
                
            },
            attrs={
                'id':'fecha_entrega',
                'append': 'fa fa-calendar',
                'icon_toggle': True,
            }))
    fecha_escritura=forms.DateField(required=False,label='Fecha Escritura',widget=DatePicker(
            options={
                'useCurrent': True,
                'collapse': False,
                'format':'YYYY-MM-DD',
                
            },
            attrs={
                'id':'fecha_escritura',
                'append': 'fa fa-calendar',
                'icon_toggle': True,
            }))
    ciudades=(
        ('Medellin','Medellin'),
        ('Monteria','Monteria'),
    )
    oficina=forms.ChoiceField(choices=ciudades,label='Oficina',required=False)
    #detalle Pagos
    cant_ci_1=forms.IntegerField(required=False,label='Cantidad',min_value=1)
    cant_ci_2=forms.IntegerField(required=False,label='Cantidad',min_value=1)
    cant_ci_3=forms.IntegerField(required=False,label='Cantidad',min_value=1)
    cant_ci_4=forms.IntegerField(required=False,label='Cantidad',min_value=1)
    cant_ci_5=forms.IntegerField(required=False,label='Cantidad',min_value=1)
    cant_ci_6=forms.IntegerField(required=False,label='Cantidad',min_value=1)
    cant_ci_7=forms.IntegerField(required=False,label='Cantidad',min_value=1)
    fecha_ini_ci1=forms.DateField(required=False,label='Fecha Inicio',widget=DatePicker(
            options={
                'useCurrent': True,
                'collapse': False,
                'format':'YYYY-MM-DD',
                
            },
            attrs={
                'id':'fecha_ini_ci1',
                'append': 'fa fa-calendar',
                'icon_toggle': True,
            }))
    fecha_ini_ci2=forms.DateField(required=False,label='Fecha Inicio',widget=DatePicker(
            options={
                'useCurrent': True,
                'collapse': False,
                'format':'YYYY-MM-DD',
                
            },
            attrs={
                'id':'fecha_ini_ci2',
                'append': 'fa fa-calendar',
                'icon_toggle': True,
            }))
    fecha_ini_ci3=forms.DateField(required=False,label='Fecha Inicio',widget=DatePicker(
            options={
                'useCurrent': True,
                'collapse': False,
                'format':'YYYY-MM-DD',
                
            },
            attrs={
                'id':'fecha_ini_ci3',
                'append': 'fa fa-calendar',
                'icon_toggle': True,
            }))
    fecha_ini_ci4=forms.DateField(required=False,label='Fecha Inicio',widget=DatePicker(
            options={
                'useCurrent': True,
                'collapse': False,
                'format':'YYYY-MM-DD',
                
            },
            attrs={
                'id':'fecha_ini_ci4',
                'append': 'fa fa-calendar',
                'icon_toggle': True,
            }))
    fecha_ini_ci5=forms.DateField(required=False,label='Fecha Inicio',widget=DatePicker(
            options={
                'useCurrent': True,
                'collapse': False,
                'format':'YYYY-MM-DD',
                
            },
            attrs={
                'id':'fecha_ini_ci5',
                'append': 'fa fa-calendar',
                'icon_toggle': True,
            }))
    fecha_ini_ci6=forms.DateField(required=False,label='Fecha Inicio',widget=DatePicker(
            options={
                'useCurrent': True,
                'collapse': False,
                'format':'YYYY-MM-DD',
                
            },
            attrs={
                'id':'fecha_ini_ci6',
                'append': 'fa fa-calendar',
                'icon_toggle': True,
            }))
    fecha_ini_ci7=forms.DateField(required=False,label='Fecha Inicio',widget=DatePicker(
            options={
                'useCurrent': True,
                'collapse': False,
                'format':'YYYY-MM-DD',
                
            },
            attrs={
                'id':'fecha_ini_ci7',
                'append': 'fa fa-calendar',
                'icon_toggle': True,
            }))
    valor_ci1=forms.IntegerField(required=False,label='Valor Cuota',min_value=0)
    valor_ci2=forms.IntegerField(required=False,label='Valor Cuota',min_value=0)
    valor_ci3=forms.IntegerField(required=False,label='Valor Cuota',min_value=0)
    valor_ci4=forms.IntegerField(required=False,label='Valor Cuota',min_value=0)
    valor_ci5=forms.IntegerField(required=False,label='Valor Cuota',min_value=0)
    valor_ci6=forms.IntegerField(required=False,label='Valor Cuota',min_value=0)
    valor_ci7=forms.IntegerField(required=False,label='Valor Cuota',min_value=0)
    cant_fn=forms.IntegerField(label='Cantidad',min_value=1)
    fecha_ini_fn=forms.DateField(label='Fecha Inicio',widget=DatePicker(
            options={
                'useCurrent': True,
                'collapse': False,
                'format':'YYYY-MM-DD',
                
            },
            attrs={
                'id':'fecha_ini_fn',
                'append': 'fa fa-calendar',
                'icon_toggle': True,
            }))
    valor_fn=forms.IntegerField(label='Valor Cuota',min_value=0,required=False)
    cant_ce=forms.IntegerField(required=False,label='Cantidad',min_value=1)
    fecha_ini_ce=forms.DateField(required=False,label='Fecha Inicio',widget=DatePicker(
            options={
                'useCurrent': True,
                'collapse': False,
                'format':'YYYY-MM-DD',
                
            },
            attrs={
                'id':'fecha_ini_ce',
                'append': 'fa fa-calendar',
                'icon_toggle': True,
            }))
    valor_ce=forms.IntegerField(required=False,label='Valor Cuota',min_value=0)
    periodosce=(
        ('------','------'),
        ('Mensual','Mensual'),
        ('Trimestral','Trimestral'),
        ('Semestral','Semestral'),
        ('Anual','Anual')
    )
    periodo_ce=forms.ChoiceField(choices=periodosce,label='Periodo',required=False)
    formas_de_pago=(
        ('Contado','Contado'),
        ('Credicontado','Credicontado'),
        ('Amortizacion','Amortizacion'),
        ('Canje','Canje')
    )
    forma_pago=forms.ChoiceField(choices=formas_de_pago,label='Forma de Pago')
    pago_saldo=(
        ('Regular','Regular'),
        ('Extraordinario','Extraordinario')
    )
    forma_plan_pagos=forms.ChoiceField(choices=pago_saldo,label='Tipo Plan de Pagos')
    observaciones=forms.CharField(max_length=500,required=False,label='Observaciones',widget=forms.Textarea(attrs={"rows":2}))
    #widgets
    titular1.widget.attrs.update(id='titular1',readonly=True)
    titular2.widget.attrs.update(id='titular2',readonly=True)
    titular3.widget.attrs.update(id='titular3',readonly=True)
    titular4.widget.attrs.update(id='titular4',readonly=True)
    inmueble.widget.attrs.update(id='inmueble',readonly=True)
    valor.widget.attrs.update(id='valor')
    valor_letras.widget.attrs.update(id='valor_letras',readonly=True)
    porc_cta_ini.widget.attrs.update(id='porc_cta_ini',step=1)
    porc_saldo.widget.attrs.update(id='porc_saldo',readonly=True)
    vr_ci.widget.attrs.update(id='vr_ci')
    vr_saldo.widget.attrs.update(id='vr_saldo',readonly=True)
    forma_pago.widget.attrs.update(id='formas_de_pago')
    forma_plan_pagos.widget.attrs.update(id='forma_plan_pagos')
    cant_ci_1.widget.attrs.update(id='cant_ci_1')
    cant_ci_2.widget.attrs.update(id='cant_ci_2')
    cant_ci_3.widget.attrs.update(id='cant_ci_3')
    cant_ci_4.widget.attrs.update(id='cant_ci_4')
    cant_ci_5.widget.attrs.update(id='cant_ci_5')
    cant_ci_6.widget.attrs.update(id='cant_ci_6')
    cant_ci_7.widget.attrs.update(id='cant_ci_7')
    cant_fn.widget.attrs.update(id='cant_fn')
    cant_ce.widget.attrs.update(id='cant_ce')
    valor_ci1.widget.attrs.update(id='valor_ci1')
    valor_ci2.widget.attrs.update(id='valor_ci2')
    valor_ci3.widget.attrs.update(id='valor_ci3')
    valor_ci4.widget.attrs.update(id='valor_ci4')
    valor_ci5.widget.attrs.update(id='valor_ci5')
    valor_ci6.widget.attrs.update(id='valor_ci6')
    valor_ci7.widget.attrs.update(id='valor_ci7')
    valor_fn.widget.attrs.update(id='valor_fn')
    valor_ce.widget.attrs.update(id='valor_ce')
    periodo_ce.widget.attrs.update(id='periodo_ce')
    observaciones.widget.attrs.update(id='observaciones')

class form_inv_admin(forms.Form):
    choices_estados=(
        ('Libre','Libre'),
        ('Bloqueado','Bloqueado'),
        ('Sin Liberar','Sin Liberar'),
    )
    lote=forms.CharField(required=False,max_length=300)
    Estado_Lote=forms.ChoiceField(choices=choices_estados,required=False)
    Observaciones_Bloqueo=forms.CharField(required=False,max_length=300,widget=forms.Textarea(attrs={'rows':2}))
    nuevo_valor_lote=forms.DecimalField(required=False,label='Valor m2')
    Meses_Entrega=forms.IntegerField(required=False)
    Estado_Lote.widget.attrs.update(id='estados_lote')
    Observaciones_Bloqueo.widget.attrs.update(id='obs_bloqueo')
    nuevo_valor_lote.widget.attrs.update(id='nuevo_val_lote')
    lote.widget.attrs.update(id='lote')
    fecha_entrega=forms.DateField(required=False,label='Fecha Entrega',widget=DatePicker(
            options={
                'useCurrent': True,
                'collapse': False,
                'format':'YYYY-MM-DD',
                
            },
            attrs={
                'id':'fecha_entrega',
                'append': 'fa fa-calendar',
                'icon_toggle': True,
            }))
    
class form_procesabilidad(forms.Form):
    Enmendaduras=forms.BooleanField(required=False)
    Documentacion_Incompleta=forms.BooleanField(required=False)
    Valores_Incorrectos=forms.BooleanField(required=False)
    Observaciones=forms.CharField(required=False,max_length=300,widget=forms.Textarea(attrs={'rows':2}))
    Enmendaduras.widget.attrs.update(id='proc_enmendaduras')
    Documentacion_Incompleta.widget.attrs.update(id='proc_documentacion')
    Valores_Incorrectos.widget.attrs.update(id='proc_valores')
    Observaciones.widget.attrs.update(id='proc_observaciones')

class form_reestructuracion(forms.Form):
    valor_credito=forms.DecimalField(required=False,label='Valor Credito',min_value=1)
    saldo_capital=forms.DecimalField(required=False,label='Saldo Capital',min_value=1)
    pendiente_ci=forms.DecimalField(required=False,label='Pendiente CI',min_value=0)
    pendiente_saldo=forms.DecimalField(required=False,label='Pendiente Saldo',min_value=0)
    nuevo_valor=forms.DecimalField(required=False,label='Valor Restructurar',min_value=1)
    ajuste=forms.DecimalField(required=False,label='Ajuste Valor')
    cant_ci_1=forms.IntegerField(required=False,label='Cantidad',min_value=1)
    cant_ci_2=forms.IntegerField(required=False,label='Cantidad',min_value=1)
    cant_ci_3=forms.IntegerField(required=False,label='Cantidad',min_value=1)
    cant_ci_4=forms.IntegerField(required=False,label='Cantidad',min_value=1)
    fecha_ini_ci1=forms.DateField(required=False,label='Fecha Inicio',widget=DatePicker(
            options={
                'useCurrent': True,
                'collapse': False,
                'format':'YYYY-MM-DD',
                
            },
            attrs={
                'id':'fecha_ini_ci1',
                'append': 'fa fa-calendar',
                'icon_toggle': True,
            }))
    fecha_ini_ci2=forms.DateField(required=False,label='Fecha Inicio',widget=DatePicker(
            options={
                'useCurrent': True,
                'collapse': False,
                'format':'YYYY-MM-DD',
                
            },
            attrs={
                'id':'fecha_ini_ci2',
                'append': 'fa fa-calendar',
                'icon_toggle': True,
            }))
    fecha_ini_ci3=forms.DateField(required=False,label='Fecha Inicio',widget=DatePicker(
            options={
                'useCurrent': True,
                'collapse': False,
                'format':'YYYY-MM-DD',
                
            },
            attrs={
                'id':'fecha_ini_ci3',
                'append': 'fa fa-calendar',
                'icon_toggle': True,
            }))
    fecha_ini_ci4=forms.DateField(required=False,label='Fecha Inicio',widget=DatePicker(
            options={
                'useCurrent': True,
                'collapse': False,
                'format':'YYYY-MM-DD',
                
            },
            attrs={
                'id':'fecha_ini_ci4',
                'append': 'fa fa-calendar',
                'icon_toggle': True,
            }))
    valor_ci1=forms.IntegerField(required=False,label='Valor Cuota',min_value=0)
    valor_ci2=forms.IntegerField(required=False,label='Valor Cuota',min_value=0)
    valor_ci3=forms.IntegerField(required=False,label='Valor Cuota',min_value=0)
    valor_ci4=forms.IntegerField(required=False,label='Valor Cuota',min_value=0)
    cant_fn=forms.IntegerField(label='Cantidad',min_value=1)
    fecha_ini_fn=forms.DateField(label='Fecha Inicio',widget=DatePicker(
            options={
                'useCurrent': True,
                'collapse': False,
                'format':'YYYY-MM-DD',
                
            },
            attrs={
                'id':'fecha_ini_fn',
                'append': 'fa fa-calendar',
                'icon_toggle': True,
            }))
    valor_fn=forms.IntegerField(label='Valor Cuota',min_value=0,required=False)
    cant_ce=forms.IntegerField(required=False,label='Cantidad',min_value=1)
    fecha_ini_ce=forms.DateField(required=False,label='Fecha Inicio',widget=DatePicker(
            options={
                'useCurrent': True,
                'collapse': False,
                'format':'YYYY-MM-DD',
                
            },
            attrs={
                'id':'fecha_ini_ce',
                'append': 'fa fa-calendar',
                'icon_toggle': True,
            }))
    valor_ce=forms.IntegerField(required=False,label='Valor Cuota',min_value=0)
    periodosce=(
        ('------','------'),
        ('Mensual','Mensual'),
        ('Trimestral','Trimestral'),
        ('Semestral','Semestral'),
        ('Anual','Anual')
    )
    periodo_ce=forms.ChoiceField(choices=periodosce,label='Periodo',required=False)
    formas_de_pago=(
        ('Contado','Contado'),
        ('Credicontado','Credicontado'),
        ('Amortizacion','Amortizacion'),
        ('Canje','Canje')
    )
    forma_pago=forms.ChoiceField(choices=formas_de_pago,label='Forma de Pago')
    pago_saldo=(
        ('Regular','Regular'),
        ('Extraordinario','Extraordinario')
    )
    forma_plan_pagos=forms.ChoiceField(choices=pago_saldo,label='Tipo Plan de Pagos')
    correos_notificacion=forms.CharField(max_length=255,label='Destinatarios',required=False)
    notificar=forms.CharField(max_length=255,label='notifica',required=False)
    #widgets
    notificar.widget.attrs.update(id='notificar',hidden=True)
    correos_notificacion.widget.attrs.update(id='correos_notificacion',hidden=True)
    valor_credito.widget.attrs.update(id='valor_credito',readonly=True)
    saldo_capital.widget.attrs.update(id='saldo_capital',readonly=True)
    pendiente_ci.widget.attrs.update(id='pendiente_ci')
    pendiente_saldo.widget.attrs.update(id='pendiente_saldo')
    ajuste.widget.attrs.update(id='ajuste')
    nuevo_valor.widget.attrs.update(id='nuevo_valor',readonly=True)
    forma_pago.widget.attrs.update(id='formas_de_pago')
    forma_plan_pagos.widget.attrs.update(id='forma_plan_pagos')
    cant_ci_1.widget.attrs.update(id='cant_ci_1')
    cant_ci_2.widget.attrs.update(id='cant_ci_2')
    cant_ci_3.widget.attrs.update(id='cant_ci_3')
    cant_ci_4.widget.attrs.update(id='cant_ci_4')
    cant_fn.widget.attrs.update(id='cant_fn')
    cant_ce.widget.attrs.update(id='cant_ce')
    valor_ci1.widget.attrs.update(id='valor_ci1')
    valor_ci2.widget.attrs.update(id='valor_ci2')
    valor_ci3.widget.attrs.update(id='valor_ci3')
    valor_ci4.widget.attrs.update(id='valor_ci4')
    valor_fn.widget.attrs.update(id='valor_fn')
    valor_ce.widget.attrs.update(id='valor_ce')
    periodo_ce.widget.attrs.update(id='periodo_ce')
    
class form_escala_comision(forms.Form):
    cc_generador=forms.CharField(required=False,max_length=255,label='Generador')
    porc_generador=forms.DecimalField(required=False,label='%',
                                      decimal_places=2,min_value=0,max_value=4.00)
    cc_linea=forms.CharField(required=False,max_length=255,label='Linea')
    porc_linea=forms.DecimalField(required=False,label='%',
                                      decimal_places=2,min_value=0,max_value=4.00)
    cc_cerrador=forms.CharField(required=False,max_length=255,label='Cierre')
    porc_cerrador=forms.DecimalField(required=False,label='%',
                                      decimal_places=2,min_value=0,max_value=4.00)
    cc_jefep=forms.CharField(required=False,max_length=255,label='Coordinador de ventas')
    porc_jefep=forms.DecimalField(required=False,label='%',
                                      decimal_places=2,min_value=0,max_value=0.17)
    cc_jefev=forms.CharField(required=False,max_length=255,label='Lider de ventas')
    porc_jefev=forms.DecimalField(required=False,label='%',decimal_places=2,
                                  min_value=0,max_value=0.5)
    cc_gerventas=forms.CharField(required=False,max_length=255,label='Gerente de ventas regional')
    porc_gerventas=forms.DecimalField(required=False,label='%',decimal_places=2,
                                  min_value=0,max_value=0.5)
    cc_generador.widget.attrs.update(id='cc_generador',readonly=True)
    porc_generador.widget.attrs.update(id='porc_generador')
    cc_linea.widget.attrs.update(id='cc_linea',readonly=True)
    porc_linea.widget.attrs.update(id='porc_linea')
    cc_cerrador.widget.attrs.update(id='cc_cerrador',readonly=True)
    porc_cerrador.widget.attrs.update(id='porc_cerrador')
    cc_jefev.widget.attrs.update(id='cc_jefev',readonly=True)
    porc_jefev.widget.attrs.update(id='porc_jefev',default=0.5)
    cc_jefep.widget.attrs.update(id='cc_jefep',readonly=True)
    porc_jefep.widget.attrs.update(id='porc_jefep',default=0.17)
    cc_gerventas.widget.attrs.update(id='cc_tlmk',readonly=True)
    porc_gerventas.widget.attrs.update(id='porc_tlmk',default=0.5)    

class form_seguimiento(forms.Form):
    formas_contacto=(
        ('Presencial','Presencial'),
        ('Whatsapp','Whatsapp'),
        ('Correo Electronico','Correo Electronico'),
        ('LLamada','Llamada'),
        ('Mensajeria','Mensajeria'),
        ('No aplica','No aplica')
    )
    tipos_seguimientos=(
        ('Cobro','Cobro'),
        ('Envio informacion','Envio Informacion'),
        ('Peticion','Peticion'),
        ('Saludo','Saludo'),
        ('Anotacion','Anotacion')
    )
    tipo_seguimiento=forms.ChoiceField(choices=tipos_seguimientos,label='Tipo de Seguimiento')
    forma_contacto=forms.ChoiceField(choices=formas_contacto,label='Formas de Contacto')
    comentarios=forms.CharField(max_length=500,label='Comentarios',widget=forms.Textarea(attrs={"rows":3}))
    tiene_compromiso=forms.BooleanField(required=False,label='Compromiso de Pago?')
    fecha_compromiso=forms.DateField(required=False,label='Fecha Compromiso',widget=DatePicker(
                                    options={
                                        'useCurrent': True,
                                        'collapse': False,
                                        'format':'YYYY-MM-DD',
                                        
                                    },
                                    attrs={
                                        'id':'fecha_compromiso',
                                        'append': 'fa fa-calendar',
                                        'icon_toggle': True,
                                    }))
    valor_compromiso=forms.IntegerField(required=False,label='Valor Compromiso')

class form_revision_op(forms.Form):
    origenes=(
        ('Normal','Normal'),
        ('Novacion','Novacion'),
        ('Canje','Canje')
    )
    oficinas=(
        ('Medellin','Medellin'),
        ('Monteria','Monteria')
    )
    tiposdocs=(
        ('Opcion de Promesa','Opcion de Promesa'),
        ('Promesa','Promesa')
    )
    carteras=User.objects.filter(groups__name='Gestor Cartera',is_active=True).order_by('first_name')
    asesores=[]
    for asesor in carteras:
        nombre=f'{asesor.first_name.upper()} {asesor.last_name.upper()}'
        asesores.append(
            (nombre,nombre)
        )
    Tipo_Contrato=forms.ChoiceField(choices=tiposdocs)
    Oficina=forms.ChoiceField(choices=oficinas)
    Origen_Venta=forms.ChoiceField(choices=origenes)
    Cartera_Asignar=forms.ChoiceField(choices=asesores,label='Asignar a Cartera')
    Enmendaduras=forms.BooleanField(required=False)
    Documentacion_Incompleta=forms.BooleanField(required=False)
    Valores_Incorrectos=forms.BooleanField(required=False)
    Observaciones=forms.CharField(required=False,max_length=300,widget=forms.Textarea(attrs={'rows':2}))
    fecha_dcto=forms.DateField(required=False,label='Fecha Condicion',widget=DatePicker(
            options={
                'useCurrent': True,
                'collapse': False,
                'format':'YYYY-MM-DD',
                
            },
            attrs={
                'append': 'fa fa-calendar',
                'icon_toggle': True,
            }))
    valor_pagodcto=forms.IntegerField(required=False,min_value=0,label='Pago para Descuento')
    valor_dcto=forms.IntegerField(required=False,min_value=0,label='Valor Descuento')
    nuevo_ci=forms.IntegerField(required=False,min_value=0,label='Nueva Cuota Inicial')
    nuevo_saldo=forms.IntegerField(required=False,min_value=0,label='Nuevo Saldo')

class form_radicar_recibo(forms.Form):
    def __init__(self, *args, **kwargs):
       my_arg = kwargs.pop('proyecto')
       super(form_radicar_recibo, self).__init__(*args, **kwargs)
       self.proyecto =my_arg
       choices_fp=formas_pago.objects.using(self.proyecto).all()
       self.fields['forma_pago']=forms.ModelChoiceField(choices_fp,label='Forma de Pago',required=False)

class form_recaudo_noradicado(forms.Form):
    Concepto=forms.CharField(max_length=255)
    Valor=forms.IntegerField(min_value=0)
    formas_de_pago=(
        ('Efectivo','Efectivo'),
        ('Tarjeta Debito','Tarjeta Debito'),
        ('Tarjeta Credito','Tarjeta Credito'),
        ('Transferencia','Transferencia'),
        ('CDT','CDT'),
        ('Cheque','Cheque')
    )
    formapago=forms.ChoiceField(choices=formas_de_pago,label='Forma de Pago')
    soporte = forms.FileField(
        label='Soporte de pago (PDF)',
        validators=[FileExtensionValidator(allowed_extensions=['pdf'])],
        help_text='Adjunta el soporte del pago en formato PDF.'
    )
    soporte.widget.attrs.update(accept='application/pdf,.pdf')

class form_nuevo_recaudoNR(forms.Form):
    
    nro_recibo=forms.CharField(label='Numero recibo')
    fecha_recibo=forms.DateField(label='Fecha',widget=DatePicker(
                                    options={
                                        'useCurrent': True,
                                        'collapse': False,
                                        'format':'YYYY-MM-DD',
                                        
                                    },
                                    attrs={
                                        'append': 'fa fa-calendar',
                                        'icon_toggle': True,
                                    }))
    valor=forms.IntegerField(min_value=0,label='Valor Pagado')
    concepto=forms.CharField(label='Concepto')
    formapago=forms.CharField(label='Forma de Pago')
    nro_recibo.widget.attrs.update(placeholder='N+1ª letra del proyecto+ - + ADJ proyecto')
    formapago.widget.attrs.update(placeholder='Novacion +N+1ª letra del proyecto')
    
    
    def __init__(self, *args, **kwargs):
        my_arg = kwargs.pop('proyecto')
        super(form_nuevo_recaudoNR, self).__init__(*args, **kwargs)
        self.proyecto =my_arg
        contratos_activos=ventas_nuevas.objects.using(my_arg).filter(Q(estado='Pendiente')|Q(estado='Aprobado'))
        self.fields['contrato']=forms.ModelChoiceField(contratos_activos,label='Contrato')
    
class form_detalle_comisiones(forms.Form):
    valor_buscado=forms.CharField(required=False,max_length=255,label='A Buscar')
    valor_buscado.widget.attrs.update(id='valor_buscado')
    fecha_desde=forms.DateField(required=False,label='Desde',widget=DatePicker(
                                    options={
                                        'useCurrent': True,
                                        'collapse': False,
                                        'format':'YYYY-MM-DD',
                                        
                                    },
                                    attrs={
                                        'id':'fecha_desde_asesor',
                                        'append': 'fa fa-calendar',
                                        'icon_toggle': True,
                                    }))
    fecha_hasta=forms.DateField(required=False,label='Hasta',widget=DatePicker(
                                    options={
                                        'useCurrent': True,
                                        'collapse': False,
                                        'format':'YYYY-MM-DD',
                                        
                                    },
                                    attrs={
                                        'id':'fecha_hasta_asesor',
                                        'append': 'fa fa-calendar',
                                        'icon_toggle': True,
                                    }))

class form_radicar_factura(forms.Form):
    num_factura=forms.CharField(max_length=255, label='Numero de Factura')
    idtercero=forms.CharField(max_length=255,label='Id Tercero')
    nombretercero=forms.CharField(max_length=255,label='Nombre Tercero')
    choices_empresa=(
        ('Promotora Sandville','Promotora Sandville'),
        ('Status Comercializadora','Status Comercializadora'),
        ('Quadrata Construcciones','Quadrata Construcciones'),
        ('Terranova Desarrolladora Turistica','Terranova Desarrolladora Turistica'),
        ('Promotora Westville','Promotora Westville')
    )
    empresa_radicado=forms.ChoiceField(choices=choices_empresa,label='Empresa')
    valor=forms.IntegerField(min_value=1,label='Valor')
    fecha_vencimiento=forms.DateField(label='Fecha Vencimiento',widget=DatePicker(
                                    options={
                                        'useCurrent': True,
                                        'collapse': False,
                                        'format':'YYYY-MM-DD',
                                        
                                    },
                                    attrs={
                                        'id':'fecha_vencimiento',
                                        'append': 'fa fa-calendar',
                                        'icon_toggle': True,
                                    }))
    fecha_factura=forms.DateField(label='Fecha Factura',widget=DatePicker(
                                    options={
                                        'useCurrent': True,
                                        'collapse': False,
                                        'format':'YYYY-MM-DD',
                                        
                                    },
                                    attrs={
                                        'id':'fecha_factura',
                                        'append': 'fa fa-calendar',
                                        'icon_toggle': True,
                                    }))
    documento_cargar=forms.FileField(required=False,label='Documento')
    documento_cargar.widget.attrs.update(id='nombredoc')
    
class form_causar(forms.Form):
    fecha_causacion=forms.DateField(label='Fecha Causacion',widget=DatePicker(
                                    options={
                                        'useCurrent': True,
                                        'collapse': False,
                                        'format':'YYYY-MM-DD',
                                        
                                    },
                                    attrs={
                                        'id':'fecha_causacion',
                                        'append': 'fa fa-calendar',
                                        'icon_toggle': True,
                                    }))
    nrocausacion=forms.CharField(max_length=255,label='Numero de Causacion')
    pagoneto=forms.IntegerField(min_value=0,label='Pago Neto')

class form_pagar(forms.Form):
    fecha_causacion=forms.DateField(label='Fecha Pago',widget=DatePicker(
                                    options={
                                        'useCurrent': True,
                                        'collapse': False,
                                        'format':'YYYY-MM-DD',
                                        
                                    },
                                    attrs={
                                        'id':'fecha_causacion',
                                        'append': 'fa fa-calendar',
                                        'icon_toggle': True,
                                    }))
    valorpago=forms.IntegerField(min_value=0,label='Valor Pagado')
    empresa_choices=(
        ('','Elegir...'),
        ('Promotora Sandville','Promotora Sandville'),
        ('Status Comercializadora','Status Comercializadora'),
        ('Quadrata Constructores','Quadrata Constructores'),
        ('Promotora Westville','Promotora Westville'),
    )
    empresapago=forms.ChoiceField(choices=empresa_choices,label='Empresa Pagadora')
    empresapago.widget.attrs.update(id='empresapago')
    
class form_ver_ppto(forms.Form):
    Año=forms.IntegerField(min_value=2015,max_value=2099)
    meses=(
        ('01','Enero'),
        ('02','Febrero'),
        ('03','Marzo'),
        ('04','Abril'),
        ('05','Mayo'),
        ('06','Junio'),
        ('07','Julio'),
        ('08','Agosto'),
        ('09','Septiempre'),
        ('10','Octubre'),
        ('11','Noviembre'),
        ('12','Diciembre')
    )
    Mes=forms.ChoiceField(choices=meses)

class form_int_comi_banco(forms.Form):
    proyecto = forms.ModelChoiceField(proyectos.objects.all().exclude(proyecto__icontains='Alttum'))
    empresas =(
        (None,'Seleccionar'),
        ('Promotora Sandville','Promotora Sandville'),
        ('Status Comercializadora','Status Comercializadora'),
        ('Quadrata Constructores','Quadrata Constructores'),
        ('Promotora Westville','Promotora Westville'),
    )
    empresa = forms.ChoiceField(choices=empresas)
    
    cuenta = forms.ChoiceField(choices=empresas)
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_id = 'form-interfazComisionesBanco'
        self.helper.layout = Layout(
            Div(
                Div(
                    Div(customSelectField('proyecto'),css_class='pb-3'),
                    Div(customSelectField('empresa'),css_class='pb-3'),
                    Div(customSelectField('cuenta')),
                    css_class='container'
                ),
                css_class='modal-body'
            ),
            Div(
                Submit('generar',value='Generar',css_class='btn btn-primary'),
                css_class='modal-footer'
            ),
        )
        
    def clean_cuenta(self):
        return self.cleaned_data['cuenta']

class form_retiro_asesor(forms.Form):
    cedula = forms.IntegerField()
    fecha_retiro = forms.DateField(label='')
    
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.helper=FormHelper()
        self.helper.form_id='form-retiro'
        self.helper.layout=Layout(
            Div(
                SimplyField('cedula',hidden=True),
                datepickerField('fecha_retiro',placeholder='Fecha retiro')),
            Div(
                Submit('btnRetirar','Retirar',css_class='btn btn-primary ml-auto'),
                css_class='row mt-3 mx-0'
            )
            
        )

class form_buscar_reestr(forms.Form):
    proyecto = forms.ModelChoiceField(proyectos.objects.all(),
                                      empty_label='Selecciona...')
    fecha_desde = forms.DateField()
    fecha_hasta = forms.DateField()
    
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.helper = FormHelper()
        self.helper.form_id = 'formreestr'
        self.helper.layout = Layout(
            Div(
                Column(
                    customSelectField('proyecto'), css_class='col-md-5',style='padding-top:2rem;'
                ),
                Column(
                    customfields.datepicker('fecha_desde', css_class='text-center'), css_class='col-md-2'
                ),
                Column(
                    customfields.datepicker('fecha_hasta', css_class='text-center'), css_class='col-md-2'
                ),
                Column(StrictButton('<i class="fas fa-search"></i>',id="btnbuscarmvtos",css_class='btn btn-primary btn-circle mt-4 pt-1 ml-3')
                       , css_class='col-md-1'),
                Column(StrictButton('<i class="fas fa-plus"></i>',id="btnnuevareestr",css_class='btn btn-success btn-circle mt-4 pt-1 ml-3')
                       , css_class='col-md-1'),
                css_class='row'
            ),
        )
        
class form_nueva_reestr(forms.Form):
    adj = forms.ChoiceField(choices=(
        ('','Cargando...'),
    ))
    nro_reestructuraciones = forms.IntegerField(label='Cantidad Otrosi')
    ultima_reestructuracion = forms.CharField(max_length=255, label='Fecha ultimo Otrosi')
    valor_contrato = forms.CharField(max_length=255)
    capital_pagado = forms.CharField(max_length=255)
    capital_vigente = forms.CharField(max_length=255)
    int_cte_causado = forms.CharField(max_length=255,label="Intereses corrientes")
    int_mora_causado = forms.CharField(max_length=255,label="Intereses mora")
    total_int_pdte = forms.CharField(max_length=255,label="Total intereses")
    
    
    tipo_reestructuracion = forms.ChoiceField(choices=(
        ('Normal','Normal'),
        ('Descuento','Descuento'),
        ('Especial','Especial'),
    ),label='Tipo reestructuracion')
    
    
    ci_pendiente = forms.CharField(max_length=255, label='Cuota inicial pendiente')
    saldo_pendiente = forms.CharField(max_length=255)
    
    descuento = forms.CharField(max_length=255, required=False)  # Quitar el label
    nuevo_valor = forms.CharField(max_length=255, required=False, label = 'Nuevo valor contrato')  # Quitar el label
    nuevo_saldo = forms.CharField(max_length=255, required=False)  # Quitar el label
    ci_reestructurar = forms.CharField(max_length=255, required=False, label='Ci a reestructurar')  # Quitar el label
    diff_ci = forms.CharField(max_length=255, required=False, label='Diferencia CI')  # Quitar el label
    cant_ci = forms.IntegerField(required=False, label='Cantidad')
    fecha_ci = forms.DateField(required=False, label = 'Fecha')
    valor_ci = forms.CharField(max_length=255, required=False, label='Valor')
    forma_pago = forms.ChoiceField(
        choices=(
            ('Regular', 'Regular'),
            ('Extraordinario', 'Extraordinario'),
        ),
        label='Forma pago'  # Quitar el label
    )
    tasa = forms.ChoiceField(
        choices=(
            (0, '0%'),
            (0.8, '0.8%'),
            (0.99, '0.99%'),
            (1.5, '1.5%'),
        ),
        label='Tasa'  # Quitar el label
    )
    fn_reestructurar = forms.CharField(max_length=255, required=False, label='FN a reestructurar')  # Quitar el label
    int_a_cobrar = forms.CharField(max_length=255, label='Interes a cobrar')  # Quitar el label
    nro_ctas_dividir = forms.IntegerField(label='Dividir en')  # Quitar el label
    vr_final_ctas_reg = forms.CharField(max_length=255, label='Valor final cuotas')
    cantidad_fn = forms.IntegerField(required=False, label='Cantidad')
    fecha_fn = forms.DateField(required=False, label = 'Fecha')
    valor_reg = forms.CharField(max_length=255, required=False, label='Valor')  # Quitar el label
    cantidad_extra = forms.IntegerField(required=False, label='Cantidad')  # Quitar el label
    periodo_extra = forms.ChoiceField(
        choices=(
            (1, 'Mensual'),
            (3, 'Trimestral'),
            (6, 'Semestral'),
        ),
        label='Periodo'  # Quitar el label
    )
    fecha_extra = forms.DateField(required=False)
    valor_extra = forms.CharField(max_length=255, required=False)  # Quitar el label
    archivo_fp_especial = forms.FileField(required=False)
    
    
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.helper = FormHelper()
        self.helper.form_id = 'form-reestructuracion'
        self.helper.layout = Layout(
            Row(
                Column(
                    Field('adj',css_class='fstdropdown-select'), css_class='col-md-6'
                ),
                Column(
                    Field('nro_reestructuraciones', css_class='text-center', readonly=True), css_class='col-md-3'
                ),
                Column(
                    Field('ultima_reestructuracion', css_class='text-center', readonly=True), css_class='col-md-3'
                ),
            ),
            Row(
                Column(
                    PrependedText('valor_contrato','$',css_class='text-center', readonly=True), css_class='col-md-4'
                ),
                Column(
                    PrependedText('capital_pagado','$',css_class='text-center', readonly=True), css_class='col-md-4'
                ),
                Column(
                    PrependedText('capital_vigente','$',css_class='text-center', readonly=True), css_class='col-md-4'
                ),
            ),
            Row(
                Column(
                    PrependedText('int_cte_causado','$',css_class='text-center', readonly=True), css_class='col-md-4'
                ),
                Column(
                    PrependedText('int_mora_causado','$',css_class='text-center', readonly=True), css_class='col-md-4'
                ),
                Column(
                    PrependedText('total_int_pdte','$',css_class='text-center', readonly=True), css_class='col-md-4'
                ),
            ),
            Row(
                Column(
                    PrependedText('ci_pendiente','$', css_class='text-center', readonly=True), css_class='col-md-4'
                ),
                Column(
                    PrependedText('saldo_pendiente','$', css_class='text-center', readonly=True), css_class='col-md-4'
                ),
                Column(
                    Field('tipo_reestructuracion'), css_class='col-md-4'
                ),
            ),
            Div(
                # Primera fila: Descuento, Nuevo Valor y Nuevo Saldo
                Div(
                    Column(
                        PrependedText('descuento', '$', 
                                      css_class='money text-center reestructuracion-descuento reestructuracion-especial'),
                        css_class='col-md-4'
                    ),
                    Column(
                        PrependedText('nuevo_valor', '$', readonly=True,
                                      css_class='money text-center reestructuracion-descuento reestructuracion-especial'),
                        css_class='col-md-4'
                    ),
                    Column(
                        PrependedText('nuevo_saldo', '$', readonly=True,
                                      css_class='money text-center reestructuracion-descuento reestructuracion-especial'),
                        css_class='col-md-4'
                    ),
                    css_class='row'
                ),
                # Segunda fila: CI (Cuota inicial)
                Div(
                    Column(
                        Div(
                            Column(
                                PrependedText('ci_reestructurar', '$',
                                              css_class='text-center money reestructuracion-normal reestructuracion-descuento reestructuracion-especial'),
                                css_class='col-md-5'
                            ),
                            Column(
                                StrictButton(
                                    '<i class="fas fa-plus"></i>',
                                    id="btn-add-ci",
                                    css_class='btn btn-success btn-circle mt-1 pt-1 ml-3 reestructuracion-normal reestructuracion-descuento',
                                    onclick='add_ci();',
                                    data_bs_toggle="tooltip", data_bs_placement="top",
                                    title="Agregar nueva linea de CI"
                                ),
                                css_class='col-md-1 pt-4'
                            ),
                            Column(
                                StrictButton(
                                    '<i class="fas fa-minus"></i>',
                                    id="btn-remove-ci",
                                    css_class='btn btn-danger btn-circle mt-1 pt-1 ml-3 reestructuracion-normal reestructuracion-descuento',
                                    onclick='remove_ci();',
                                    data_bs_toggle="tooltip", data_bs_placement="top",
                                    title="Eliminar ultima linea de CI"
                                ),
                                css_class='col-md-1 pt-4'
                            ),
                            Column(
                                PrependedText('diff_ci', '$', readonly=True,
                                              css_class='text-center money reestructuracion-normal reestructuracion-descuento'),
                                css_class='col-md-5'
                            ),
                            css_class='d-flex justify-content-center'
                        ),
                        Div(
                            Div(
                                Field('cant_ci', min=1,
                                      css_class='text-center reestructuracion-normal reestructuracion-descuento'),
                                onkeyup='updateDiffCi()',onchange='updateDiffCi()',
                                css_class='col-md-2'
                            ),
                            Div(
                                customfields.datepicker('fecha_ci', readonly = True,
                                                        css_class='text-center reestructuracion-normal reestructuracion-descuento'),
                                css_class='col-md-3'
                            ),
                            Div(
                                PrependedText('valor_ci', '$',
                                              onkeyup='updateDiffCi()',onchange='updateDiffCi()',
                                      css_class='text-center money reestructuracion-normal reestructuracion-descuento'),
                                css_class='col-md-4'
                            ),
                            css_class='d-flex justify-content-center',
                            id='block-ci'
                        ),
                        id='div-ci'
                    ),
                    css_class='row cuota_inicial'
                ),
                # Tercera fila: FN (Financiacion)
                Div(
                    Column(
                        PrependedText('fn_reestructurar', '$', 
                                      css_class='text-center money reestructuracion-normal reestructuracion-descuento reestructuracion-especial' ),
                        css_class='col-md-6'
                    ),
                    Column(
                        Field('tasa', 
                            css_class='text-center reestructuracion-normal reestructuracion-descuento reestructuracion-especial' ),
                        css_class='col-md-3'
                    ),
                    Column(
                        Field('forma_pago', 
                            css_class='text-center reestructuracion-normal reestructuracion-descuento reestructuracion-especial' ),
                        css_class='col-md-3'
                    ),
                    css_class='row'
                ),
                # Cuarta fila: FN Regular
                Div(
                    Column(
                        Field('cantidad_fn', 
                              css_class='text-center reestructuracion-normal reestructuracion-descuento'),
                        css_class='col-md-4'
                    ),
                    Column(
                        customfields.datepicker('fecha_fn', 
                                                css_class='text-center reestructuracion-normal reestructuracion-descuento'),
                        css_class='col-md-4'
                    ),
                    Column(
                        PrependedText('valor_reg', '$', readonly=True,
                                      css_class='text-center money reestructuracion-normal reestructuracion-descuento'),
                        css_class='col-md-4'
                    ),
                    css_class='row'
                ),
                # Quinta fila: Interés a cobrar y Dividir en
                Div(
                    Column(
                        Field('int_a_cobrar', 
                                      css_class='text-center money reestructuracion-normal reestructuracion-descuento reestructuracion-especial'),
                        css_class='col-md-4'
                    ),
                    Column(
                        AppendedText('nro_ctas_dividir', 'cuotas',
                                      css_class='text-center reestructuracion-normal reestructuracion-descuento reestructuracion-especial'),
                        css_class='col-md-4'
                    ),
                    Column(
                        PrependedText('vr_final_ctas_reg', '$', readonly = True,
                                      css_class='text-center money reestructuracion-normal reestructuracion-descuento reestructuracion-especial'),
                        css_class='col-md-4'
                    ),
                    css_class='row'
                ),
                # Sexta fila: Extraordinario
                Div(
                    Column(
                        Field('cantidad_extra', 
                              css_class='text-center extra-fields'),
                        css_class='col-md-2'
                    ),
                    Column(
                        Field('periodo_extra', 
                              css_class='text-center extra-fields'),
                        css_class='col-md-3'
                    ),
                    Column(
                        customfields.datepicker('fecha_extra', 
                                                css_class='text-center extra-fields'),
                        css_class='col-md-3'
                    ),
                    Column(
                        PrependedText('valor_extra','$', readonly = True,
                                      css_class='text-center money extra-fields'),
                        css_class='col-md-4'
                    ),
                    css_class='row'
                ),
                # Octava fila: Archivo especial
                Div(
                    Column(
                        Field('archivo_fp_especial', 
                              css_class='form-control-file reestructuracion-especial'),
                        css_class='col-md-12'
                    ),
                    css_class='row'
                ),
                css_class='container-fluid'
            ),
            HTML('<div class="border-bottom my-1"></div>'),
            StrictButton('Registrar',id='btn-add-reestructuration',type='submit',
                         css_class='btn btn-primary float-right my-2')
        )
        
