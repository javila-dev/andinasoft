from django.contrib.auth.models import User
from django import forms
from django.core.validators import FileExtensionValidator
from django.db.models import Q
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Submit, Row, Column, Field, Div, HTML
from crispy_forms.bootstrap import StrictButton, PrependedText
from andina import customfields
from andinasoft.forms import customSelectField
from andinasoft.models import empresas, proyectos, cuentas_pagos
from accounting.models import impuestos_legalizacion, conceptos_legalizacion, Partners, Countries
from andinasoft.shared_models import formas_pago

class form_nuevo_radicado(forms.Form):
    nro_factura = forms.CharField(max_length=255,label='Nº Factura')
    fecha_factura = forms.DateField()
    fecha_vencimiento = forms.DateField()
    id_tercero = forms.CharField(max_length=255,label='NIT/CC')
    nombre_tercero = forms.CharField(max_length=255,label='Proveedor')
    empresa = forms.ModelChoiceField(empresas.objects.all())
    valor = forms.IntegerField(min_value=0)
    descripcion = forms.CharField(max_length=255,
                    widget=forms.Textarea({'rows':2}))
    oficina = forms.ChoiceField(
        choices=(
            ('','Selecciona...'),
            ('MONTERIA','MONTERIA'),
            ('MEDELLIN','MEDELLIN')
        )
    )
    soporte = forms.FileField(validators=[FileExtensionValidator(allowed_extensions=['pdf'],
                                                            message="Debes cargar un archivo pdf")])
    
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Row(
                    Field('empresa')
                ),
            Row(
                Column('id_tercero',css_class='col-sm-4'),
                Column('nombre_tercero',css_class='col-sm-8')
            ),
            Row(
                Column(
                    Field('nro_factura')
                ),
                Column(
                    customfields.datepickerField('fecha_factura',css_class='text-center')
                ),
                Column(
                    customfields.datepickerField('fecha_vencimiento',css_class='text-center'))
                ),
            Row(
                Column(
                    Field('descripcion'),
                ),
            ),
            Row(
                Column(
                    Field('valor')
                ),
                Column(
                    Field('oficina')
                ),
                css_class='mt-2'
            ),
            Row(
                Field('soporte')
            ),
            Row(
                Submit('btnRadicar','Radicar',css_class='ml-auto'),
                css_class='d-flex'
            )
            )
        
    def clean_fecha_vencimiento(self):
        field = self.cleaned_data.get('fecha_vencimiento')
        fecha_factura = self.cleaned_data.get('fecha_factura')
        if field < fecha_factura:
            self.add_error('fecha_vencimiento','La fecha de vencimiento no puede ser menor a la fecha de la factura')
        return field
    
class form_causar_rad(forms.Form):
    fecha = forms.DateField()
    nro_causacion = forms.CharField(max_length=255)
    cuenta_por_pagar = forms.ChoiceField(choices=(('',''),))
    secuencia_cxp = forms.IntegerField(min_value=1)
    pagoneto = forms.CharField(max_length=255,label='Pago neto')
    soporte = forms.FileField(label='Soporte causacion')
    proyecto_ascociado = forms.ChoiceField(choices=(
        ('','Selecciona...'),
        ('Alameda del Mar','Alameda del Mar'),
        ('Caracola del Mar','Caracola del Mar'),
        ('Bugambilias','Bugambilias'),
        ('Vegas de Venecia','Vegas de Venecia'),
        ('Sandville Beach','Sandville Beach'),
        ('Carmelo Reservado','Carmelo Reservado'),
        ('Fractal','Fractal'),
        ('Alttum Venecia','Alttum Venecia'),
        ('Alttum Caribe','Alttum Caribe'),
        ('Integral','Integral'),
    ), label='Proyecto')
    centro_costo = forms.ChoiceField(choices=(
        ('','Selecciona...'),
        ('Administracion','Administracion'),
        ('Comercial','Comercial'),
        ('Proyectos','Proyectos'),
        ('Operacion club','Operacion club'),
        ('Integral','Integral'),
        ('Impuestos','Impuestos'),
        ('Tierras','Tierras'),
    ), label='Centro de costo')
    
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.helper = FormHelper()
        self.helper.form_id = 'formCausar'
        self.helper.layout = Layout(
            Row(
                Column(customfields.datepickerField('fecha',css_class='text-center')),
                Column(Field('nro_causacion',css_class='text-center'))
            ),
            Field('cuenta_por_pagar'),
            Row(
                Column(Field('secuencia_cxp',css_class='text-center')),
                Column(Field('pagoneto',css_class='text-center'),)
            ),
            Row(
                Column(Field('proyecto_ascociado',css_class='text-center')),
                Column(Field('centro_costo',css_class='text-center'),)
            ),
            customfields.filepicker('soporte',accept='application/pdf'),
            Submit('btnRegistrarCaus','Registrar',css_class='btn-block mt-3')
        )

class form_mvtos_concil(forms.Form):
    empresa = forms.ModelChoiceField(empresas.objects.all(),empty_label='Selecciona...')
    cuenta = forms.ChoiceField(choices=(
        ("","Selecciona..."),
    ))
    fecha_desde = forms.DateField()
    fecha_hasta = forms.DateField()
    
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Row(
                Column(
                    Field('empresa',id='empresa'),
                    css_class='col-md-4'
                ),
                Column(
                    Field('cuenta',id='cuenta'),
                    css_class='col-md-3'
                ),
                Column(
                    customfields.datepickerField('fecha_desde'),
                    css_class='col-md-2'
                ),
                Column(
                    customfields.datepickerField('fecha_hasta'),
                    css_class='col-md-2'
                ),
                Column(
                    StrictButton('<i class="fa fa-search"></i>', id='btn-searchmvt',
                                 css_class='btn btn-primary btn-circle mt-4 ml-3'),
                    css_class='col-md-1'
                ),
            )            
        )

class form_nueva_planilla(forms.Form):
    
    empresa = forms.ModelChoiceField(empresas.objects.all())
    fecha = forms.DateField()
    
    
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.helper = FormHelper()
        self.helper.form_id = 'formNuevaPlanilla'
        self.helper.layout = Layout(
            Field('empresa'),
            customfields.datepickerField('fecha'),
        )

class form_nuevo_pago(forms.Form):
    
    empresa = forms.ModelChoiceField(empresas.objects.all(),label=False)
    cuenta = forms.ChoiceField(choices=(('',''),),label=False,required=True)
    valor = forms.CharField(max_length=255)
    soporte = forms.FileField()
    fecha = forms.DateField()
    empresa.widget.attrs['id']='empresa_cont'
    cuenta.widget.attrs['id']='cuenta_cont'
    soporte.widget.attrs['accept']='application/pdf'
    valor.widget.attrs['id']='valor_pago'
    
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.helper = FormHelper()
        self.helper.form_id = 'formPago'
        self.helper.layout = Layout(
            Row(
               Column(
                    PrependedText('empresa','Empresa',css_class='empresa-pago'),
                    PrependedText('cuenta','Cuenta',css_class='cuenta-pago'),
                    Row(
                        Column(customfields.datepickerField('fecha',css_class='fecha-pago')),
                        Column(Field('valor',css_class='text-right'))
                    ),
                    customfields.filepicker('soporte',accept='application/pdf'),
                    Submit('Cargar','Cargar',css_class='float-right mt-3'),
               css_class='col-md-8 pt-3'), 
            css_class='justify-content-around')
        )

class form_interfaz_egreso(forms.Form):
    empresa_egr = forms.ModelChoiceField(empresas.objects.all(),label='Empresa')
    cuentas_egr = forms.ChoiceField(choices=(
        ('',''),
    ),label='Cuentas')
    egr_desde = forms.DateField(label='Desde')
    egr_hasta = forms.DateField(label='Hasta')
    numero_inicial_egr = forms.IntegerField(min_value=1,label=False)
    
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.helper = FormHelper()
        self.helper.form_id = 'formInterfEgr'
        self.helper.layout = Layout(
            Field('empresa_egr'),
            Field('cuentas_egr',css_class='selectpicker'),
            Row(
                Column(customfields.datepickerField('egr_desde')),
                Column(customfields.datepickerField('egr_hasta'),)
            ),
            Row(
                Column(
                    PrependedText('numero_inicial_egr','Consecutivo inicio',
                                             css_class='text-center'),
                    css_class='col-md-8'
                ),
                Column(Submit('listo','Listo',css_class='float-right'),
                    css_clss='col-md-4 my-auto'
                ),
            css_class='mt-4'),
        )

class form_interfaz_notas(forms.Form):
    empresa_notas = forms.ModelChoiceField(empresas.objects.all(),label='Empresa')
    cuentas_notas = forms.ChoiceField(choices=(
        ('',''),
    ),label='Cuentas')
    fecha_nota_desde = forms.DateField(label='Desde')
    fecha_nota_hasta = forms.DateField(label='Hasta')
    numero_inicial_nota = forms.IntegerField(min_value=1,label=False)
    oficina_notas = forms.ChoiceField(choices=(
        ('MEDELLIN','MEDELLIN'),
        ('MONTERIA','MONTERIA'),
    ),label='Oficina',help_text='Selecciona la oficina para generar las cuentas por cobrar (notas) de los pagos efectuados por otras empresas.')
        
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.helper = FormHelper()
        self.helper.form_id = 'formInterfNotas'
        self.helper.layout = Layout(
            Field('empresa_notas'),
            Field('cuentas_notas',css_class='selectpicker'),
            Field('oficina_notas'),
            Row(
                Column(customfields.datepickerField('fecha_nota_desde')),
                Column(customfields.datepickerField('fecha_nota_hasta'),)
            ),
            Row(
                Column(
                    PrependedText('numero_inicial_nota','Consecutivo inicio',
                                             css_class='text-center'),css_class='col-md-8'
                ),
                Column(Submit('btnSbmtNota','Listo',css_class='float-right'),
                    css_clss='col-md-4 my-auto'
                ),
            css_class='mt-4'),
        )

class form_rad_int(forms.Form):
    oficina_rad_int = forms.ChoiceField(choices=(
        ('','Selecciona...'),
        ('MEDELLIN','MEDELLIN'),
        ('MONTERIA','MONTERIA'),
    ),label='')
    id_tercero_rad_int = forms.CharField(max_length=255,label='CC/NIT')
    nombre_tercero_rad_int = forms.CharField(max_length=255,label='Nombre')
    documento_causacion = forms.CharField(max_length=255,label=False)
    fecha_rad_int = forms.DateField(label='')
    valor_neto_rad_int = forms.CharField(max_length=255,label=False)
    tipo_cxp = forms.ChoiceField(choices=(
        ('',''),    
    ),label='CxP')
    nro_vencimientos = forms.IntegerField(min_value=1,label=False)
    proyecto = forms.ModelChoiceField(
        queryset=proyectos.objects.all(),
    required=False,label='')
    empresa_rad_int = forms.ModelChoiceField(
        queryset=empresas.objects.all(),label=''
    )
    descripcion_rad_int = forms.CharField(max_length=255,
            widget = forms.Textarea({'rows':2}),
            label = 'Descripcion'
        )
    soporte_rad_int = forms.FileField(required=True,label='Soporte radicado')
    check_pagado = forms.BooleanField(required=False,label='El radicado ya se encuentra pagado?')
    cuenta_pago_rad = forms.ChoiceField(choices=(('',''),),label='Cuenta',required=False)
    soporte_pago_rad = forms.FileField(label='Soporte pago',required=False)
    soporte_causacion = forms.FileField(label='Soporte causacion',required=False)
    fecha_pago_rad = forms.DateField(required=False,label='Fecha pago')
    empresa_pago_rad = forms.ModelChoiceField(empresas.objects.all(),required=False,label=False)
    proyecto_ascociado = forms.ChoiceField(choices=(
        ('','Selecciona...'),
        ('Perla del Mar','Perla del Mar'),
        ('Caracola del Mar','Caracola del Mar'),
        ('Bugambilias','Bugambilias'),
        ('Vegas de Venecia','Vegas de Venecia'),
        ('Carmelo Reservado','Carmelo Reservado'),
        ('Fractal','Fractal'),
        ('Alttum Venecia','Alttum Venecia'),
        ('Alttum Caribe','Alttum Caribe'),
        ('Integral','Integral'),
    ), label='Proyecto')
    centro_costo = forms.ChoiceField(choices=(
        ('','Selecciona...'),
        ('Administracion','Administracion'),
        ('Comercial','Comercial'),
        ('Proyectos','Proyectos'),
        ('Operacion club','Operacion club'),
        ('Integral','Integral'),
        ('Impuestos','Impuestos'),
        ('Tierras','Tierras'),
    ), label='Centro de costo')
    
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.helper = FormHelper()
        self.helper.form_id = 'formRadInt'
        self.helper.layout = Layout(
            PrependedText('oficina_rad_int','Oficina'),
            PrependedText('empresa_rad_int','Empresa'),
            Row(
                Column(
                    PrependedText('documento_causacion','Causacion'),
                ),
                Column(
                    customfields.customSelectField('tipo_cxp')
                ),
            ),
            Row(
                Column(
                    Field('id_tercero_rad_int'),
                    css_class = 'col-md-4'
                ),
                Column(
                    Field('nombre_tercero_rad_int'),
                    css_class = 'col-md-8'
                ),
            ),
            customfields.filepicker('soporte_causacion'),
            Field('descripcion_rad_int'),
            Row(
                Column(
                    customfields.datepickerField('fecha_rad_int',placeholder='Fecha')
                ),
                Column(
                    PrependedText('valor_neto_rad_int','Neto',css_class='text-center')
                ),
            ),
            Row(
                Column(Field('proyecto_ascociado',css_class='text-center')),
                Column(Field('centro_costo',css_class='text-center'),)
            ),
            customfields.filepicker('soporte_rad_int'),
            Div(
                customfields.CheckField('check_pagado'),
                css_class='mt-3'
            ),
            Row(
                PrependedText('empresa_pago_rad','Empresa'),
                Column(
                    Field('cuenta_pago_rad'),
                    css_class='col-md-6'
                ),
                Column(
                    customfields.datepickerField('fecha_pago_rad'),
                    css_class='col-md-6'
                ),
                customfields.filepicker('soporte_pago_rad'),
                css_class='mt-2 rowpagos'
            ),
            Submit('btnRadInt','Radicar',css_class='float-right mt-3')
        )
  
class form_otros_ingresos(forms.Form):
    fecha = forms.DateField()
    id_tercero = forms.CharField(max_length=255)
    nombre_tercero = forms.CharField(max_length=255)
    concepto = forms.CharField(max_length=255,
                               widget=forms.Textarea({'rows':2}))
    empresa = forms.ModelChoiceField(
        empresas.objects.all()
    ,label=False)  
    cuenta = forms.ModelChoiceField(
        cuentas_pagos.objects.all(),
    )
    oficina = forms.ChoiceField(choices=(
        ('MEDELLIN','MEDELLIN'),
        ('MONTERIA','MONTERIA'),
    ),label=False)
    valor = forms.CharField(max_length=255,label='')
    
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.helper = FormHelper()
        self.helper.form_id = 'formNuevoIngreso'
        self.helper.layout = Layout(
            PrependedText('oficina','Oficina'),
            PrependedText('empresa','Empresa'),
            Row(
                Column(
                    Field('cuenta')
                ),
                Column(
                    customfields.datepickerField('fecha')
                )
            ),
            Row(
                Column(Field('id_tercero'),css_class='col-md-4'),
                Column(Field('nombre_tercero'),css_class='col-md-8')
            ),
            Field('concepto'),
            PrependedText('valor','Valor',css_class='text-center'),
            Submit('btnOtroIngreso','Registrar',css_class='float-right mt-3')
        )

class form_transferencias(forms.Form):
    empresa_sale = forms.ModelChoiceField(
        empresas.objects.exclude(nombre__icontains='Alttum'),
        label=False
    )       
    cuenta_sale = forms.ChoiceField(choices=(
        ('',''),
    ),label=False)
    empresa_entra = forms.ModelChoiceField(
        empresas.objects.exclude(nombre__icontains='Alttum'),
        label=False
    )       
    cuenta_entra = forms.ChoiceField(choices=(
        ('',''),
    ),label=False)
    valor_transf = forms.CharField(max_length=255,label='Valor')
    fecha_transf = forms.DateField(label='Fecha')
    soporte = forms.FileField(required=True)
    
    
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.helper = FormHelper()
        self.helper.form_id = 'formTransfers'
        self.helper.layout = Layout(
            HTML('<p class="lead border-bottom border-gray">Sale</p>'),
            PrependedText('empresa_sale','Empresa'),
            PrependedText('cuenta_sale','Cuenta'),
            HTML('<p class="lead border-bottom border-gray">Entra</p>'),  
            PrependedText('empresa_entra','Empresa'),
            PrependedText('cuenta_entra','Cuenta'),
            Row(
                Column(
                    customfields.datepickerField('fecha_transf',css_class='text-center')
                ),
                Column(
                    Field('valor_transf',css_class='text-center')
                )
            ),
            customfields.filepicker('soporte',css_class='my-2'),
            Submit('btnRegAnt','Registrar',css_class='float-right mt-3')
        )

class form_buscar_mvto_pago(forms.Form):
    empresa_mvtos = forms.ModelChoiceField(
        empresas.objects.all()
    ,label='Empresa')  
    cuenta_mvtos = forms.ChoiceField(choices=(('',''),),label='Cuenta')
    fecha_mvtos = forms.DateField(label="Fecha")
    
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.helper = FormHelper()
        self.helper.form_id = 'formNuevoIngreso'
        self.helper.layout = Layout(
            PrependedText('oficina','Oficina'),
            PrependedText('empresa','Empresa'),
            Row(
                Column(
                    Field('empresa_mvtos'), css_class='col-md-5'
                ),
                Column(
                    Field('cuenta_mvtos')
                ),
                Column(
                    customfields.datepickerField('fecha_mvtos'), css_class='col-md-3'
                ),
                Column(StrictButton('<i class="fas fa-search"></i>',id="btnbuscarmvtos",css_class='btn btn-primary btn-circle mt-4 pt-1 ml-3')
                       , css_class='col-md-1')
            ),
                
            
            
        )
   
class form_asociar_gtt(forms.Form):
    proyecto_gtt = forms.ModelChoiceField(
        queryset = proyectos.objects.exclude(proyecto__icontains='Alttum')
    ,label='Proyecto')  
    fecha_gtt = forms.ChoiceField(choices=(
        ('',''),
    ),label='Fecha')
    empresa_gtt = forms.ModelChoiceField(empresas.objects.all(),label='Empresa')
    cuenta_gtt = forms.ChoiceField(choices=(('',''),),label='Cuenta',required=True)
    valor_gtt = forms.CharField(max_length='255',label='Valor')
    soporte_gtt = forms.FileField(label='Soporte')
    fecha_pago_gtt = forms.DateField(label='Fecha')
    
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.helper = FormHelper()
        self.helper.form_id = 'formgtt'
        self.helper.layout = Layout(
            
            Row(
                Column(
                    Field('proyecto_gtt'),
                    css_class='col-md-5'
                ),
                Column(
                    Field('fecha_gtt'),
                    css_class='col-md-5'
                ),
                Column(
                    StrictButton('<i class="fas fa-search"></i>',
                                 id='btnseachGTT',
                                 css_class='d-block ml-auto btn btn-primary btn-circle',
                                 style='margin-top: 40%!important'),
                    css_class='col-md-2'),
            ),
            HTML(
                '''
                <table id="tabladetalleGtt" class="table table-sm">
                <col width="20%">
                <col width="40%">
                <col width="20%">
                <col width="20%">
                    <thead class="thead thead-dark">
                        <tr>
                            <th>Id</th>
                            <th>Nombre</th>
                            <th>Vencimiento</th>
                            <th>Valor</th>
                        </tr>   
                    </thead>
                    <tbody>
                    </tbody>
                </table>
                '''
            ),
            Row(
                Column(
                    Row(
                        Column(
                            Field('empresa_gtt',css_class='empresa-pago'),
                        ),
                        Column(
                            Field('cuenta_gtt',css_class='cuenta-pago'),
                        )
                    ),
                    Row(
                        Column(customfields.datepickerField('fecha_pago_gtt',css_class='fecha-pago')),
                        Column(Field('valor_gtt',readonly=True,css_class='text-right'))
                    ),
                    customfields.filepicker('soporte_gtt',accept='application/pdf'),
                css_class='justify-content-around'),
            ),
        Submit('btnGtt','Registrar',css_class='float-right mt-3')
        )

class form_asociar_comision(forms.Form):
    proyecto_comis = forms.ModelChoiceField(
        queryset = proyectos.objects.exclude(proyecto__icontains='Alttum')
    ,label='Proyecto')  
    fecha_comis = forms.DateField(label='Fecha')
    empresa_comis = forms.ModelChoiceField(empresas.objects.all(),label='Empresa')
    cuenta_comis = forms.ChoiceField(choices=(('',''),),label='Cuenta',required=True)
    valor_comis = forms.CharField(max_length='255',label='Valor')
    soporte_comis = forms.FileField(label='Soporte')
    fecha_pago_comis = forms.DateField(label='Fecha')
    
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.helper = FormHelper()
        self.helper.form_id = 'formcomis'
        self.helper.layout = Layout(
            
            Row(
                Column(
                    Field('proyecto_comis'),
                    css_class='col-md-5'
                ),
                Column(
                    customfields.datepickerField('fecha_comis',css_class='text-center'),
                    css_class='col-md-5'
                ),
                Column(
                    StrictButton('<i class="fas fa-search"></i>',
                                 id='btnseachcomis',
                                 css_class='d-block ml-auto btn btn-primary btn-circle',
                                 style='margin-top: 40%!important'),
                    css_class='col-md-2'),
            ),
            HTML(
                '''
                <table id="tabladetallecomis" class="table table-sm">
                <col width="20%">
                <col width="40%">
                <col width="20%">
                <col width="20%">
                    <thead class="thead thead-dark">
                        <tr>
                            <th>Id</th>
                            <th>Nombre</th>
                            <th>Vencimiento</th>
                            <th>Valor</th>
                        </tr>   
                    </thead>
                    <tbody>
                    </tbody>
                </table>
                '''
            ),
            Row(
                Column(
                    Row(
                        Column(
                            Field('empresa_comis',css_class='empresa-pago'),
                        ),
                        Column(
                            Field('cuenta_comis',css_class='cuenta-pago'),
                        )
                    ),
                    Row(
                        Column(customfields.datepickerField('fecha_pago_comis',css_class='fecha-pago')),
                        Column(Field('valor_comis',readonly=True,css_class='text-right'))
                    ),
                    customfields.filepicker('soporte_comis',accept='application/pdf'),
                css_class='justify-content-around'),
            ),
        Submit('btncomis','Registrar',css_class='float-right mt-3')
        )

class form_asociar_otros_pagos(forms.Form):
    fecha_otros = forms.DateField(label='Fecha')
    empresa_otros = forms.ModelChoiceField(empresas.objects.all(),label='Empresa')
    cuenta_otros = forms.ChoiceField(choices=(('',''),),label='Cuenta',required=True)
    valor_otros = forms.CharField(max_length='255',label='Valor')
    soporte_otros = forms.FileField(label='Soporte')
    fecha_pago_otros = forms.DateField(label='Fecha')
    
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.helper = FormHelper()
        self.helper.form_id = 'formotrospagos'
        self.helper.layout = Layout(
            HTML(
                '''
                <table id="tabladetalleOtrosPag" class="table table-sm">
                <col width="20%">
                <col width="40%">
                <col width="20%">
                <col width="20%">
                    <thead class="thead thead-dark">
                        <tr>
                            <th>Id</th>
                            <th>Nombre</th>
                            <th>Vencimiento</th>
                            <th>Valor</th>
                        </tr>   
                    </thead>
                    <tbody>
                    </tbody>
                </table>
                '''
            ),
            Row(
                Column(
                    StrictButton('<i class="fas fa-plus"></i>',
                                 id='btnaddotros',
                                 css_class='d-block ml-auto btn btn-primary btn-circle',
                                 style='margin-top: 40%!important'),
                    css_class='col-md-2'),
            css_class='justify-content-end'),
            Row(
                Column(
                    Row(
                        Column(
                            Field('empresa_otros',css_class='empresa-pago'),
                        ),
                        Column(
                            Field('cuenta_otros',css_class='cuenta-pago'),
                        )
                    ),
                    Row(
                        Column(customfields.datepickerField('fecha_pago_otros',css_class='fecha-pago')),
                        Column(Field('valor_otros',readonly=True,css_class='text-right'))
                    ),
                    customfields.filepicker('soporte_otros',accept='application/pdf'),
                css_class='justify-content-around'),
            ),
        Submit('btnotros','Registrar',css_class='float-right mt-3')
        )

class form_asociar_nomina(forms.Form):
    empresa_nomina = forms.ModelChoiceField(empresas.objects.all(),label='Empresa')
    year_nomina = forms.IntegerField(label='Año')
    month_nomina = forms.ChoiceField(choices=(
        (1,'Enero'),
        (2,'Febrero'),
        (3,'Marzo'),
        (4,'Abril'),
        (5,'Mayo'),
        (6,'Junio'),
        (7,'Julio'),
        (8,'Agosto'),
        (9,'Septiembre'),
        (10,'Octubre'),
        (11,'Noviembre'),
        (12,'Diciembre'),
    ),label='Mes')
    empresa_pago_nomina = forms.ModelChoiceField(empresas.objects.all(),label='Empresa')
    quincena_nomina = forms.ChoiceField(choices=(
        (1,'Primera'),
        (2,'Segunda'),
    ),label='Quincena')
    cuenta_nomina = forms.ChoiceField(choices=(('',''),),label='Cuenta',required=True)
    valor_nomina = forms.CharField(max_length='255',label='Valor')
    soporte_nomina = forms.FileField(label='Soporte')
    fecha_pago_nomina = forms.DateField(label='Fecha')
    
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.helper = FormHelper()
        self.helper.form_id = 'formnomina'
        self.helper.layout = Layout(
            Row(
                Column(
                    Field('empresa_nomina'),
                    css_class='col-md-12'
                ),
                Column(
                    Field('year_nomina',css_class='text-center'),
                    css_class='col-md-3'
                ),
                Column(
                    Field('month_nomina',css_class='text-center'),
                    css_class='col-md-4'
                ),
                Column(
                    Field('quincena_nomina',css_class='text-center'),
                    css_class='col-md-3'
                ),
                Column(
                    StrictButton('<i class="fas fa-search"></i>',
                                 id='btnsearchnomina',
                                 css_class='d-block ml-auto btn btn-primary btn-circle',
                                 style='margin-top: 40%!important'),
                    css_class='col-md-2'),
            ),
            HTML(
                '''<div style="max-height:30vh;overflow-y:auto">
                <table id="tabladetallenomina" class="table table-sm">
                <col width="20%">
                <col width="40%">
                <col width="20%">
                <col width="20%">
                    <thead class="thead thead-dark">
                        <tr>
                            <th>Id</th>
                            <th>Nombre</th>
                            <th>Vencimiento</th>
                            <th>Valor</th>
                        </tr>   
                    </thead>
                    <tbody>
                    </tbody>
                </table></div>
                '''
            ),
            Row(
                Column(
                    StrictButton('<i class="fas fa-plus"></i>',
                                 id='btnsearchnomina',
                                 css_class='d-block ml-auto btn btn-primary btn-circle',
                                 style='margin-top: 40%!important'),
                    css_class='col-md-2'),
            css_class='justify-content-end'),
            Row(
                Column(
                    Row(
                        Column(
                            Field('empresa_pago_nomina',css_class='empresa-pago'),
                        ),
                        Column(
                            Field('cuenta_nomina',css_class='cuenta-pago'),
                        )
                    ),
                    Row(
                        Column(customfields.datepickerField('fecha_pago_nomina',css_class='fecha-pago')),
                        Column(Field('valor_nomina',readonly=True,css_class='text-right'))
                    ),
                    customfields.filepicker('soporte_nomina',accept='application/pdf'),
                css_class='justify-content-around'),
            ),
        Submit('btnnomina','Registrar',css_class='float-right mt-3')
        )
  
class form_anticipos_tesor(forms.Form):
    empresa_ant = forms.ModelChoiceField(empresas.objects.all(),label='Empresa')
    cuenta_ant = forms.ChoiceField(choices=(
        ('',''),
    ),label='Cuenta')
    fecha_anticip = forms.DateField(label='Fecha')
    id_tercero = forms.CharField(max_length=255)
    nombre_tercero = forms.CharField(max_length=255)
    valor_anticip = forms.CharField(max_length=255,label='')
    tipo_anticipo = forms.ChoiceField(choices=(
        ('',''),
    ))
    descripcion_ant = forms.CharField(max_length=255,label='Descripcion',
                                      widget=forms.Textarea({'rows':2}))
    soporte_pago = forms.FileField()
    
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.helper = FormHelper()
        self.helper.form_id = 'formAnticipos'
        self.helper.layout = Layout(
            Div(
                customfields.customSelectField('empresa_ant'),
                css_class='mb-3'
            ),
            Div(
                customfields.customSelectField('cuenta_ant'),
                css_class='mb-3'
            ),
            Row(
                Column(
                    Field('tipo_anticipo'),
                    css_class='col-md-7'
                ),
                Column(
                    customfields.datepickerField('fecha_anticip',css_class='text-center'),
                    css_class='col-md-5'
                ),
                css_class='mt-2'
            ),
            Row(
                Column(
                    Field('id_tercero',css_class='text-center'),
                    css_class='col-md-4'
                ),
                Column(
                    Field('nombre_tercero'),
                    css_class='col-md-8'
                ),
                css_class='mt-2'
            ),
            Field('descripcion_ant',css_class='mt-2'),
            PrependedText('valor_anticip','Valor',css_class='text-center'),
            customfields.filepicker('soporte_pago',css_class='my-2'),
            Submit('Registrar','Registrar',css_class='float-right mt-3')
        )
        
class form_solicitar_anticipos(forms.Form):
    empresa_solicita = forms.ModelChoiceField(empresas.objects.exclude(pk=901132949))
    oficina = forms.ChoiceField(choices=[
        ('MEDELLIN','MEDELLIN'),
        ('MONTERIA','MONTERIA'),
    ])
    descripcion = forms.CharField(max_length=85,widget=forms.Textarea({'rows':3}),
                                  help_text='Maximo 85 caracteres')
    valor = forms.CharField(max_length=255)
    users = User.objects.filter(is_active=True).filter(
        Q(pk=19)|Q(pk=43)|Q(pk=1)|Q(pk=22)|Q(pk=85)
    ).order_by('username')
    quien_aprueba = forms.ModelChoiceField(users)
    
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.helper = FormHelper() 
        self.helper.form_id = 'form-solicitar-anticipo'
        self.helper.layout = Layout(
            customfields.customSelectField('empresa_solicita'),
            customfields.customSelectField('oficina'),
            customfields.customSelectField('quien_aprueba'),
            Field('descripcion'),
            PrependedText('valor','$',css_class='text-center money'),
            Submit('btn-solicitar','Solicitar',css_class='btn-info float-right')
        )

class form_legalizar_anticipo(forms.Form):
    fecha = forms.DateField(
        input_formats=['%Y-%m-%d'],
        widget=forms.DateInput(
            format='%Y-%m-%d',
            attrs={'type': 'date', 'class': 'text-center form-control'}
        )
    )
    descripcion = forms.CharField(max_length=255, widget=forms.Textarea({'rows':3}))
    nit_tercero = forms.ModelChoiceField(Partners.objects.all().order_by('nombres'), empty_label="Selecciona...")
    valor = forms.CharField(max_length=255)
    soporte = forms.FileField()
    concepto = forms.ModelChoiceField(conceptos_legalizacion.objects.filter(activo=True),
                                      empty_label="Seleciona...")
    
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.helper = FormHelper() 
        self.helper.form_id = 'form-legalizar-anticipo'
        self.helper.layout = Layout(
            HTML('<div class="card" id="leg_block"><div class="card-body">'),
            Row(
                Column(Field('fecha'),
                   css_class='col-md-6'), 
                Column(PrependedText('valor','$',css_class='text-center money'),
                   css_class='col-md-6'),    
            ),
            Row(
                Column(Field('nit_tercero', css_class='fstdropdown-select'),
                   css_class='col-md-10'),
                Column(StrictButton('+',id='btn-open-add-partner',css_class='btn-circle btn-primary ml-3 mt-4'),
                   css_class='col-md-2'),    
            ),     
            customfields.customSelectField('concepto'),
            Field('descripcion'),
            customfields.filepicker('soporte'),
            HTML('</div></div>'),            
            Submit('registrar-leg','Registrar',css_class='float-right mt-2 btn-success'),
        )

class form_historic_accounting_data(forms.Form):
    empresa = forms.ModelChoiceField(empresas.objects.all())
    tipo_doc = forms.CharField(max_length=255, label=False)
    consecutivo_doc = forms.IntegerField(label=False)
    fecha_doc = forms.DateField(label='')
    doc_file = forms.FileField(help_text="Solo se admiten archivos pdf, jpg, jpeg y png",
                               label="Documento")
    
    def __init__(self, *args,**kwargs):
        super().__init__(*args,**kwargs)
        self.helper = FormHelper() 
        self.helper.form_id = 'form-hist-account-data'
        self.helper.layout = Layout(
            customfields.filepicker('doc_file',accept=".png, .jpg, .jpeg, application/pdf"),
            customfields.datepicker('fecha_doc', placeholder = 'Fecha Documento'),            
            customfields.customSelectField('empresa'),
            PrependedText('tipo_doc','Documento', css_class='mask text-center uppercase'),
            PrependedText('consecutivo_doc','Consecutivo', css_class='text-center', min=1, max = 99999),            
            Submit('cargar-doc','Cargar',css_class='float-right mt-2 btn-success'),
            StrictButton('Buscar',id="btn-search" ,css_class='btn mt-2 btn-primary')
        )

class form_taxes(forms.Form):
    subtotal = forms.CharField(max_length=255, label="")
    tipo_iva = forms.ModelChoiceField(
        impuestos_legalizacion.objects.filter(
                Q(descripcion__icontains='iva')|Q(descripcion__icontains='impuesto')),
                empty_label='Sin IVA',
                required=False, label="Tipo IVA")
    valor_iva = forms.CharField(max_length=255, required=False, label="")
    
    tipo_rte = forms.ModelChoiceField(
        impuestos_legalizacion.objects.filter(descripcion__icontains='rte'),
                                      empty_label='Sin Retención',
                                      required=False)
    valor_rte = forms.CharField(max_length=255, required=False, label="")
    rte_asumida = forms.BooleanField(required=False, label="La retención es asumida")
    total_calculado = forms.CharField(max_length=255, label="")
    
    def __init__(self, *args,**kwargs):
        super().__init__(*args,**kwargs)
        self.helper = FormHelper() 
        self.helper.form_id = 'form-taxes'
        self.helper.layout = Layout(
            PrependedText('subtotal','Subtotal', css_class='calculate money text-center'),
            customfields.customSelectField('tipo_iva'),
            PrependedText('valor_iva','Valor IVA', css_class='calculate money text-center'),
            customfields.customSelectField('tipo_rte'),
            PrependedText('valor_rte','Retención', css_class='calculate money text-center'),
            Field('rte_asumida', css_class='calculate'),
            PrependedText('total_calculado','Total', css_class='money text-center', readonly=True),
            Submit('btn-registar-taxes','Registrar',css_class='float-right'),
        )

class form_partners(forms.Form):
    idTercero=forms.CharField(max_length=255, label=False)
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
    document_type = forms.ChoiceField(choices=dc_types,label='Tipo identificacion')
    nombres=forms.CharField(max_length=255)
    apellidos=forms.CharField(max_length=255, required=False)
    telefono=forms.CharField(max_length=255)    
    pais=forms.ModelChoiceField(Countries.objects.all().order_by('country_name'))
    estado =forms.ChoiceField(choices=())
    ciudad=forms.ChoiceField(choices=())
    direccion=forms.CharField(max_length=35)
    email=forms.EmailField()
    responsabilidad_fiscal=forms.ChoiceField(choices=(
        ('R-99-PN','No Aplica - Otros*'),
        ('O-13','Gran contribuyente'),
        ('O-15','Autorretenedor'),
        ('O-23','Agente de retención IVA'),
        ('O-47','Régimen simple de tributación')
    ))    
    soporte_id = forms.FileField(label='Soporte identificación')
    
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.helper = FormHelper() 
        self.helper.form_id = 'form-partners'
        self.helper.layout = Layout(
            Row(
                Column(customfields.customSelectField('document_type'),
                    css_class='col-12'
                ),
                Column(PrependedText('idTercero','Numero',css_class="only-numbers"),
                    css_class='col-12'
                ),
            ),
            Row(
                Column(Field('nombres'),
                    css_class='col-md-6'
                ),
                Column(Field('apellidos'),
                    css_class='col-md-6'
                ),
            ),
            Row(
                Column(Field('responsabilidad_fiscal',multiple=True),
                    css_class='col-md-6'
                ),
                Column(
                    Row(
                        Column(customfields.customSelectField('pais',css_class='fs-small',label_class='fs-small'),
                            css_class='col-12'
                        ),
                        Column(customfields.customSelectField('estado',css_class='fs-small'),
                            css_class='col-12'
                        ),
                        Column(customfields.customSelectField('ciudad',css_class='fs-small'),
                            css_class='col-12'
                        ),
                    )
                ),
            ),
            Row(
                Column(Field('direccion'),
                    css_class='col-md-12'
                ),
            ),
            Row(                
                Column(Field('telefono'),
                    css_class='col-md-4'
                ),
                Column(Field('email'),
                    css_class='col-md-8'
                ),
            ),
            Row(
                Column(
                    customfields.filepicker('soporte_id'),
                    css_class='col-md-12'
                ),
            ),
            StrictButton('<i class="fas fa-check"></i>',type='submit',id='btn-create-partner',css_class='btn btn-circle btn-success float-right')
        )

class form_reg_legaliz(forms.Form):
    causacion_leg_reemb = forms.CharField(max_length=255, label='')
    valor_reemb = forms.CharField(max_length=255, label='')
    soporte_leg_reemb = forms.FileField(label='Soporte')
    
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.helper = FormHelper()
        self.helper.form_id = 'formLegalizarReemb'
        self.helper.layout = Layout(
            PrependedText('causacion_leg_reemb','Causacion',css_class='text-center'),
            PrependedText('valor_reemb','Valor a reembolsar',css_class='text-center'),
            customfields.filepicker('soporte_leg_reemb'),
        )

class form_cajas(forms.Form):
    qs = cuentas_pagos.objects.filter(es_caja = True)
    caja = forms.ModelChoiceField(qs, empty_label='Selecciona...')
    fecha_desde = forms.DateField(
        input_formats=['%Y-%m-%d'],
        widget=forms.DateInput(
            format='%Y-%m-%d',
            attrs={'type': 'date', 'class': 'text-center form-control'}
        )
    )
    fecha_hasta = forms.DateField(
        input_formats=['%Y-%m-%d'],
        widget=forms.DateInput(
            format='%Y-%m-%d',
            attrs={'type': 'date', 'class': 'text-center form-control'}
        )
    )
    
    def __init__(self,*args,**kwargs):
        user = kwargs.pop('user')
        user_type = kwargs.pop('user_type')
        super(form_cajas, self).__init__(*args, **kwargs)
        self.usuario = user
        self.user_type =  user_type
        
        if self.user_type == 'tesoreria' or self.user_type == 'contabilidad' or \
            self.user_type == 'superuser':
            qs = cuentas_pagos.objects.filter(es_caja = True)
        elif self.user_type == 'responsable' or self.user_type == 'aprobador':
            qs = cuentas_pagos.objects.filter(
                Q(usuario_responsable = self.usuario)|Q(usuario_aprobador = self.usuario),
                es_caja = True)
        else:
            qs = cuentas_pagos.objects.filter(usuario_aprobador = 0)
            
        self.fields['caja'] = forms.ModelChoiceField(qs, empty_label='Selecciona...')
        
        self.helper = FormHelper()
        self.helper.form_id = 'formCaja'
        self.helper.layout = Layout(
            Row(
                Column(
                    customSelectField('caja'), css_class='col-md-5',style='padding-top:2rem;'
                ),
                Column(
                    Field('fecha_desde'), css_class='col-md-3'
                ),
                Column(
                    Field('fecha_hasta'), css_class='col-md-3'
                ),
                Column(StrictButton('<i class="fas fa-search"></i>',id="btnbuscarmvtos",css_class='btn btn-primary btn-circle mt-4 pt-1 ml-3')
                       , css_class='col-md-1')
            ),
                
            
            
        )
