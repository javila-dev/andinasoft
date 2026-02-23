from django import forms
from django.core.validators import FileExtensionValidator
from django.core.exceptions import ValidationError
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Fieldset, ButtonHolder, Submit, Row, Column, Field, Div, HTML
from crispy_forms.bootstrap import FieldWithButtons, StrictButton, FormActions, PrependedText, PrependedAppendedText, Tab, TabHolder
from andina import customfields
from crm import models as crm_models
from andinasoft import models as andinasoft_models

class form_Leads(forms.Form):
    lead = forms.CharField(max_length=255)
    identificacion = forms.CharField(max_length=255,required=False)
    nombre = forms.CharField(max_length=255)
    celular = forms.CharField(max_length=255)
    telefono = forms.CharField(max_length=255,required=False)
    email = forms.EmailField(required=False)
    ciudad = forms.CharField(max_length=255,required=False)
    direccion =forms.CharField(max_length=255,required=False)
    estados_civiles = (
        ('','------------'),
        ('Casado(a)','Casado(a)'),
        ('Soltero(a)','Soltero(a)'),
        ('Viudo(a)','Viudo(a)'),
        ('Separado(a)','Separado(a)'),
        ('Otro','Otro')
    )
    estado_civil= forms.ChoiceField(choices=estados_civiles,required=False)
    fecha_nacimiento = forms.DateField(required=False)
    tipos =(
        ('Poco interesado/Poco adecuado','Poco interesado/Poco adecuado'),
        ('Muy interesado/Poco adecuado','Muy interesado/Poco adecuado'),
        ('Poco interesado/Muy adecuado','Poco interesado/Muy adecuado'),
        ('Muy interesado/Muy adecuado','Muy interesado/Muy adecuado')
    )
    tipo_lead = forms.ChoiceField(choices=tipos,required=False)
    fecha_capta = forms.DateField(required=False)
    gestor_capta = forms.CharField(max_length=255,required=False,label='Gestor')
    
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.helper = FormHelper()
        self.helper.form_id = 'form-lead'
        self.helper.layout = Layout(
            Row(
                Column(Field('lead',readonly=True,css_class='text-center'),css_class='col-md-3'),
                Column(Field('fecha_capta',css_class='text-center',readonly=True),css_class='col-md-3'),
                Column(Field('gestor_capta',readonly=True),css_class='col-md-6')
            ),   
            Row(
                Column(Field('tipo_lead')),
            ),
            Row(
                Column(Field('identificacion',css_class='reseteable'),css_class='col-md-4'),
                Column(Field('nombre',css_class='reseteable'),css_class='col-md-8'),
            ),
            Row(
                Column(Field('celular',css_class='reseteable')),
                Column(Field('telefono',css_class='reseteable'))
            ),
            Row(
                Column(Field('ciudad',css_class='reseteable'),css_class='col-md-4'),
                Column(Field('direccion',css_class='reseteable'),css_class='col-md-8')
            ),
            Field('email',css_class='reseteable'),
            Row(
                Column(Field('estado_civil',css_class='reseteable'),),
                Column(customfields.datepickerField('fecha_nacimiento',css_class='text-center reseteable'))
            ),   
            HTML('<hr/>'),
            ButtonHolder(
                Submit('btnGrabar','Registrar',css_class='float-right'),
                StrictButton('Archivar',id='btnConfArchivo',css_class='mr-2 btn-danger float-right')
            ) 
        )
    
    def clean_celular(self):
        value = self.cleaned_data.get('celular')
        check = crm_models.leads.objects.filter(celular=value)
        if check.exists():
            raise ValidationError('Ya existe un lead con este mismo numero de celular')
        return value
        
    def clean_email(self):
        value = self.cleaned_data.get('email')
        check = crm_models.leads.objects.filter(email=value)
        if check.exists() and value != "":
            raise ValidationError('Ya existe un lead con esta direccion de correo')
        return value
    
    def clean_gestor_capta(self):
        value = self.cleaned_data.get('gestor_capta')
        if value == 'TODOS':
            raise ValidationError('Debes escoger un gestor para crear el lead')
        return value

class formCrearEvento(forms.Form):
    fecha_evento=forms.DateField()
    hora_evento=forms.TimeField()
    
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.helper = FormHelper()
        self.helper.form_id = 'form-newevent'
        self.helper.layout=Layout(
            customfields.datepickerField('fecha_evento'),
            customfields.timepickerField('hora_evento'),
            Submit('btnCrear','Crear',css_class='float-right mt-3')
        )