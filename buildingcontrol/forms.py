from django import forms
from django.core.validators import FileExtensionValidator
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Fieldset, ButtonHolder, Submit, Row, Column, Field, Div, HTML
from crispy_forms.bootstrap import FieldWithButtons, StrictButton, FormActions, PrependedText, PrependedAppendedText, Tab, TabHolder
from andina import customfields
from buildingcontrol import models as building_models
from andinasoft import models as andinasoft_models

class formContrato(forms.Form):
    idcontrato = forms.IntegerField(label='Id Contrato')
    proveedorid = forms.CharField(max_length=255,label='Proveedor')
    empresa_contrata = forms.ModelChoiceField(andinasoft_models.empresas.objects.all(),label='Empresa contratante')
    nombreproveedor = forms.CharField(max_length=255,initial='Selecciona un proveedor',required=False)
    proyecto = forms.ModelChoiceField(andinasoft_models.proyectos.objects.all())
    valor = forms.CharField(max_length=255,label="",initial=0)
    canje = forms.DecimalField(min_value=0,max_value=100,label="",initial=0)
    vr_canje = forms.CharField(max_length=255,label="",initial=0)
    pago_efectivo = forms.CharField(max_length=255,label="",initial=0)
    anticipo = forms.DecimalField(min_value=0,max_value=100,decimal_places=2,label="",initial=0)
    vr_anticipo = forms.CharField(max_length=255,label="",initial=0)
    fecha_inicio = forms.DateField()
    fecha_fin = forms.DateField()
    item_obra = forms.CharField()
    descripcion_item = forms.CharField()
    unidad_item = forms.CharField()
    cantidad_item = forms.IntegerField()
    valor_item = forms.DecimalField(decimal_places=2)
    total_item = forms.CharField(max_length=255)
    descripcion_contrato = forms.CharField(max_length=255,widget=forms.Textarea({'rows':3}),label='Descripcion contrato')
    descripcion_adicionales = forms.CharField(max_length=255,widget=forms.Textarea({'rows':3}),label='Descripcion adicionales',required=False)
    adiciones = forms.CharField(max_length=255,label="",initial=0,required=False)
    total_contratado = forms.CharField(max_length=255,label="",initial=0,required=False)
    retenciones = forms.ModelChoiceField(building_models.retenciones.objects.all(),label='Concepto Retencion',
                                         to_field_name='valor')
    vr_retenciones = forms.CharField(max_length=255,label="",initial=0)
    iva = forms.DecimalField(min_value=0,decimal_places=2,max_value=19,label="",initial=19)
    vr_iva = forms.CharField(max_length=255,label="",initial=0)
    a = forms.DecimalField(min_value=0,decimal_places=2,max_value=11,label="",initial=0)
    i = forms.DecimalField(min_value=0,decimal_places=2,max_value=11,label="",initial=0)
    u = forms.DecimalField(min_value=0,decimal_places=2,max_value=11,label="",initial=0)
    aiu = forms.DecimalField(min_value=0,decimal_places=2,max_value=11,label="",initial=0)
    vr_aiu = forms.CharField(max_length=255,label="",initial=0) 
    total_acta = forms.CharField(max_length=255,label="",initial=0)
    req_cruce = forms.CharField(max_length=255,required=False,label="")
    
    
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.helper = FormHelper(self)
        self.helper.form_id = 'form-contrato'
        self.helper.layout = Layout(
            Div(
                Div(
                    Field('idcontrato',readonly=True,css_class='text-center'),
                    css_class='col-md-2'
                ),
                Div(
                    FieldWithButtons('proveedorid',
                                     StrictButton('<i class="fas fa-search"></i>',id='btnsearchProv',css_class='btn btn-secondary')
                                ),
                    css_class='col-md-3 pr-sm-0'
                ),
                Div(
                    customfields.plainInputField('nombreproveedor',readonly=True,css_class='mt-4'),
                    css_class='col-md-7 mt-2'
                ),
                css_class='row mx-3'
            ),
            Div(
                Div(
                    Field('empresa_contrata',css_class='text-center'),
                    css_class='col-md-3'
                ),
                Div(Field('proyecto'),css_class='col-md-3'),
                Div(customfields.datepickerField('fecha_inicio',css_class='text-center'),css_class='col-md-3'),
                Div(customfields.datepickerField('fecha_fin',css_class='text-center'),css_class='col-md-3'),
                Div(Field('descripcion_contrato'),css_class='col-12'),
                css_class='row mx-3'
            ),
            Div(
                Div(
                    HTML('<p class="text-center mb-0 px-0 h-100">Item</p>'),
                    css_class='col-1 m-0 p-0'
                ),
                Div(
                    HTML('<p class="text-center mb-0 px-0 h-100">Descripcion</p>'),
                    css_class='col-5 m-0'
                ),
                Div(
                    HTML('<p class="text-center mb-0 px-0 h-100">Unidad</p>'),
                    css_class='col-1 m-0'
                ),
                Div(
                    HTML('<p class="text-center mb-0 px-0 h-100">Cantidad</p>'),
                    css_class='col-1 m-0'
                ),
                Div(
                    HTML('<p class="text-center mb-0 px-0 h-100">Vr Unit</p>'),
                    css_class='col-2 m-0'
                ),
                Div(
                    HTML('<p class="text-center mb-0 px-0 h-100">Total</p>'),
                    css_class='col-2 m-0'
                ),
                css_class='row bg-dark text-white'
            ),
            Div(
                id='detaildiv'
            ),
            Div(
                StrictButton('<i class="fas fa-plus"></i> Agregar Tipo Obra',id='btnAddObra',css_class='ml-auto mt-2'),
                css_class='row'
            ),
            HTML(
                '<hr/>'
            ),
            Div(
                Div(
                    PrependedText('valor', '<strong>Subtotal</strong>',css_class='text-right',readonly=True),
                    Row(
                        Column(PrependedText('a', '<strong>%A</strong>',css_class='text-center')),
                        Column(PrependedText('i', '<strong>%I</strong>',css_class='text-center')),
                        Column(PrependedText('u', '<strong>%U</strong>',css_class='text-center')),
                    ),
                    Row(
                        Column(PrependedText('aiu', '<strong>% AIU</strong>',css_class='text-right',readonly=True)),
                        Column(customfields.SimplyField('vr_aiu',css_class='text-right',readonly=True))
                    ),
                    Row(
                        Column(PrependedText('iva', '<strong>% IVA</strong>',css_class='text-center')),
                        Column(customfields.SimplyField('vr_iva',css_class='text-right',readonly=True))
                    ),
                    PrependedText('total_acta', '<strong>Total orden</strong>',css_class='text-right',readonly=True),
                    Row(
                        Column(PrependedText('canje', '<strong>% Canje</strong>',css_class='text-center')),
                        Column(customfields.SimplyField('vr_canje',css_class='text-right',readonly=True))
                    ),
                    Row(
                        Column(Field('retenciones',style='font-size:small')),
                    ),
                    PrependedText('vr_retenciones', '<strong>Retencion</strong>',css_class='text-right',readonly=True),
                    PrependedText('pago_efectivo', '<strong>Pago efectivo</strong>',css_class='text-right',readonly=True),
                    Row(
                        Column(PrependedText('anticipo', '<strong>Anticipo</strong>',css_class='text-center')),
                        Column(customfields.SimplyField('vr_anticipo',css_class='text-right',readonly=True))
                    ),
                    css_class='col-md-10 col-lg-6 col-xl-4 ml-auto order-lg-2'
                ),
                css_class='row mx-1'
            ),
            Div(
                Div(
                    Submit('btnCrear','Crear orden'),
                    css_class='ml-auto',role='group'
                ),css_class='row mx-3 pb-2'
            ),
            customfields.plainInputField('req_cruce')            
        )

class formActaRecibido(forms.Form):
    idacta = forms.IntegerField(label='Id Acta')
    proveedorid = forms.CharField(max_length=255,label='Proveedor')
    nombreproveedor = forms.CharField(max_length=255,initial='Selecciona un proveedor',required=False)
    proyecto = forms.CharField(max_length=255)
    valor = forms.CharField(max_length=255,label="",initial=0)
    canje = forms.DecimalField(min_value=0,decimal_places=2,max_value=100,label="",initial=0)
    vr_canje = forms.CharField(max_length=255,label="",initial=0)
    pago_efectivo = forms.CharField(max_length=255,label="",initial=0)
    anticipo = forms.DecimalField(min_value=0,decimal_places=2,label="",initial=0)
    vr_anticipo = forms.CharField(max_length=255,label="",initial=0)
    fecha_corte = forms.DateField()
    fecha_contrato = forms.CharField(max_length=255)
    descripcion_contrato = forms.CharField(max_length=255,widget=forms.Textarea({'rows':3}),label='Descripcion')
    observaciones = forms.CharField(max_length=255,required=False,widget=forms.Textarea({'rows':6}),label='Observaciones')
    retenciones = forms.ModelChoiceField(building_models.retenciones.objects.all(),label='Concepto Retencion',to_field_name='valor')
    vr_retenciones = forms.CharField(max_length=255,label="",initial=0)
    iva = forms.DecimalField(min_value=0,decimal_places=2,max_value=19,label="",initial=0)
    vr_iva = forms.CharField(max_length=255,label="",initial=0)
    a = forms.DecimalField(min_value=0,decimal_places=2,max_value=11,label="",initial=0)
    i = forms.DecimalField(min_value=0,decimal_places=2,max_value=11,label="",initial=0)
    u = forms.DecimalField(min_value=0,decimal_places=2,max_value=11,label="",initial=0)
    aiu = forms.DecimalField(min_value=0,decimal_places=2,max_value=11,label="",initial=0)
    vr_aiu = forms.CharField(max_length=255,label="",initial=0) 
    total_acta = forms.CharField(max_length=255,label="",initial=0)
    empresa_contrata = forms.CharField(max_length=255,label="Empresa contratante")
    
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.helper = FormHelper()
        self.helper.form_id = 'form-contrato'
        self.helper.layout = Layout(
            Div(
                Div(
                    Field('idacta',readonly=True,css_class='text-center'),
                    css_class='col-md-2'
                ),
                Div(
                    Field('proveedorid'),
                    css_class='col-md-3'
                ),
                Div(
                    customfields.plainInputField('nombreproveedor',readonly=True,css_class='mt-4'),
                    css_class='col-md-7 mt-2'
                ),
                css_class='row mx-3'
            ),
            Div(
                Div(Field('proyecto',readonly=True),css_class='col-md-3'),
                Div(Field('empresa_contrata',readonly=True),css_class='col-md-3'),
                Div(Field('fecha_contrato',css_class='text-center',readonly=True),css_class='col-md-3'),
                Div(customfields.datepickerField('fecha_corte',css_class='text-center'),css_class='col-md-3'),
                Div(Field('descripcion_contrato',readonly=True),css_class='col-12'),
                css_class='row mx-3'
            ),
            Div(
                Div(
                    HTML('<p class="text-center mb-0 px-0 h-100">Item</p>'),
                    css_class='col-1 m-0 p-0'
                ),
                Div(
                    HTML('<p class="text-center mb-0 px-0 h-100">Descripcion</p>'),
                    css_class='col-5 m-0'
                ),
                Div(
                    HTML('<p class="text-center mb-0 px-0 h-100">Unidad</p>'),
                    css_class='col-1 m-0'
                ),
                Div(
                    HTML('<p class="text-center mb-0 px-0 h-100">Cantidad</p>'),
                    css_class='col-1 m-0'
                ),
                Div(
                    HTML('<p class="text-center mb-0 px-0 h-100">Vr Unit</p>'),
                    css_class='col-2 m-0'
                ),
                Div(
                    HTML('<p class="text-center mb-0 px-0 h-100">Total</p>'),
                    css_class='col-2 m-0'
                ),
                css_class='row bg-dark text-white'
            ),
            Div(
                id='detaildiv'
            ),
            Div(
                StrictButton('<i class="fas fa-plus"></i> Agregar item',id='btnAddDetalle',css_class='ml-auto'),
                css_class='row'
            ),
            HTML(
                '<hr/>'
            ),
            Div(
                Div(
                    Field('observaciones'),
                    css_class='col-md-12 col-lg-5 col-xl-4'
                ),
                Div(
                    PrependedText('valor', '<strong>Subtotal</strong>',css_class='text-right',readonly=True),
                    Row(
                        Column(PrependedText('a', '<strong>%A</strong>',css_class='text-center',readonly=True)),
                        Column(PrependedText('i', '<strong>%I</strong>',css_class='text-center',readonly=True)),
                        Column(PrependedText('u', '<strong>%U</strong>',css_class='text-center',readonly=True)),
                    ),
                    Row(
                        Column(PrependedText('aiu', '<strong>% AIU</strong>',css_class='text-center',readonly=True)),
                        Column(customfields.SimplyField('vr_aiu',css_class='text-right',readonly=True))
                    ),
                    Row(
                        Column(PrependedText('iva', '<strong>% IVA</strong>',css_class='text-center',readonly=True)),
                        Column(customfields.SimplyField('vr_iva',css_class='text-right',readonly=True))
                    ),
                    PrependedText('total_acta', '<strong>Total Acta</strong>',css_class='text-right',readonly=True),
                    Row(
                        Column(PrependedText('canje', '<strong>% Canje</strong>',css_class='text-center')),
                        Column(customfields.SimplyField('vr_canje',css_class='text-right',readonly=True))
                    ),
                    Row(
                        Column(PrependedText('anticipo', '<strong>Anticipo</strong>',css_class='text-center')),
                        Column(customfields.SimplyField('vr_anticipo',css_class='text-right',readonly=True))
                    ),
                    Row(
                        Column(Field('retenciones',disabled=True,readonly=True,style='font-size:small;')),
                    ),
                    PrependedText('vr_retenciones', '<strong>Retencion</strong>',css_class='text-right',readonly=True),
                    PrependedText('pago_efectivo', '<strong>Pago efectivo</strong>',css_class='text-right',readonly=True),
                    css_class='col-md-10 col-lg-6 col-xl-4 ml-auto'
                ),
                css_class='row mx-1'
            ),
            Div(
                Div(
                    Submit('btnCrear','Crear acta'),
                    css_class='ml-auto',role='group'
                ),css_class='row mx-3 pb-2'
            ),
        )

class formProveedores(forms.Form):
    Nit = forms.CharField(max_length=255)
    Nombre = forms.CharField(max_length=255)
    Telefono = forms.CharField(max_length=255)
    Direccion = forms.CharField(max_length=255,required=False)
    Rut = forms.FileField(required=False,validators=[FileExtensionValidator(allowed_extensions=['pdf'],
                                                            message="Debes cargar un archivo pdf")])
    Certificacion_bancaria = forms.FileField(required=False,validators=[FileExtensionValidator(allowed_extensions=['pdf'],
                                                            message="Debes cargar un archivo pdf")])
    
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Fieldset(
                '',
                'Nit',
                'Nombre',
                'Telefono',
                'Direccion',
                'Rut',
                'Certificacion_bancaria'
            ),
            ButtonHolder(
                Submit('grabar','Registrar',css_class='btn btn-primary btn-block')
            )
        )

class formProductos(forms.Form):
    id_producto=forms.CharField(max_length=255,initial='Nuevo')
    nombre = forms.CharField(max_length=255)
    tipo = forms.ChoiceField(choices=(
        ('Producto','Producto'),
        ('Servicio','Servicio'),
    ))
    unidad = forms.ModelChoiceField(building_models.unidades_medida.objects.all())
    
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Fieldset(
                '',
                'id_producto',
                'nombre',
                'tipo',
                'unidad',
            )
            ,
            ButtonHolder(
                Submit('grabar','Registrar',css_class='btn btn-primary btn-block')
            )
        )

class formBitacora(forms.Form):
    id_bitacora = forms.CharField(max_length=255,initial='Nuevo',label='Id Registro')
    fecha = forms.DateField()
    proyecto = forms.ModelChoiceField(andinasoft_models.proyectos.objects.all())
    Observaciones = forms.CharField(max_length=2000,widget=forms.Textarea({'rows':6}),label='Informacion')
    registro_foto = forms.ImageField(label='')
    
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            TabHolder(
                Tab('Informacion',
                    Field('id_bitacora',readonly=True,css_class='text-center'),
                    customfields.datepickerField('fecha',css_class='text-center'),
                    Field('proyecto'),
                    Field('Observaciones'),
                    HTML(
                        "<p class='lead border-bottom border-gray pb-1'>Registro fotografico <button type='button' id='nuevaFoto' class='btn btn-primary btn-circle float-right'><i class='fas fa-plus'></i></button></p>"
                    ),
                    Div(
                        Field('registro_foto',css_class='pb-2'),
                        id='photosContainer'
                    ),            
                    ButtonHolder(
                        Submit('grabar','Registrar',css_class='btn btn-primary btn-block')
                    )
                ),
                Tab('Evidencia fotografica',
                    Div(
                        css_class='row', id='container-photo'
                    )
                ),
                css_class='mx-0'
            )
            
        )
        
class formSoporteContratos(forms.Form):
    contrato = forms.CharField(max_length=255)
    soporte_contrato = forms.FileField(validators=[FileExtensionValidator(allowed_extensions=['pdf'],
                                                            message="Debes cargar un archivo pdf")])
    
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Field('contrato',readonly=True,css_class='text-center'),
            Field('soporte_contrato'),
            ButtonHolder(
                Submit('grabar','Cargar',css_class='btn btn-primary btn-block')
            )
        )

class formRequisicion(forms.Form):
    idReq = forms.CharField(max_length=255,label='Id Requisicion')
    proyecto = forms.ModelChoiceField(andinasoft_models.proyectos.objects.all())
    descripcion = forms.CharField(max_length=255,widget=forms.Textarea({'rows':3}),label='Descripcion')
    
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.helper = FormHelper(self)
        self.helper.form_id = 'form-contrato'
        self.helper.layout = Layout(
            Div(
                Div(
                    Field('idReq',readonly=True,css_class='text-center'),
                    css_class='col-md-4'
                ),
                Div(Field('proyecto'),css_class='col-md-8'),
                css_class='row mx-3'
            ),
            Div(
                Div(
                    Field('descripcion'),
                    css_class='col-12'
                ),css_class='row mx-3'
            ),
            Div(
                Div(
                    HTML('<p class="text-center mb-0 px-0 h-100">Item</p>'),
                    css_class='col-2 m-0 p-0'
                ),
                Div(
                    HTML('<p class="text-center mb-0 px-0 h-100">Descripcion</p>'),
                    css_class='col-6 m-0'
                ),
                Div(
                    HTML('<p class="text-center mb-0 px-0 h-100">Unidad</p>'),
                    css_class='col-2 m-0'
                ),
                Div(
                    HTML('<p class="text-center mb-0 px-0 h-100">Cantidad</p>'),
                    css_class='col-2 m-0'
                ),
                css_class='row bg-dark text-white'
            ),
            Div(
                id='detaildiv'
            ),
            Div(
                StrictButton('<i class="fas fa-plus"></i> Agregar Tipo Obra',id='btnAddObra',css_class='ml-auto mt-2'),
                css_class='row'
            ),
            HTML(
                '<hr/>'
            ),
            Div(
                Div(
                    Submit('btnCrear','Crear'),
                    Submit('btnAprobar','Aprobar',css_class='btn-success ml-2'),
                    css_class='row ml-auto',role='group'
                ),css_class='row mx-3 pb-2'
            ),
        )
