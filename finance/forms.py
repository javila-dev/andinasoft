from django import forms
from django.core.validators import FileExtensionValidator
from django.db.models.query_utils import Q
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Fieldset, Button, ButtonHolder, Submit, Row, Column, Field, Div, HTML
from crispy_forms.bootstrap import FieldWithButtons, StrictButton, FormActions, PrependedText, PrependedAppendedText, Tab, TabHolder
from andina import customfields
from andinasoft.models import clientes, empresas, proyectos, cuentas_pagos
from andinasoft.shared_models import Adjudicacion
from accounting.models import info_interfaces

class form_recibo_int(forms.Form):
    proyecto_solic = forms.ModelChoiceField(proyectos.objects.exclude(proyecto__icontains='alttum'),
                                      label='Proyecto')
    fecha_pago = forms.DateField()
    cliente = forms.ChoiceField(choices=
        (
            ('','Selecciona...'),
            ),
    )
    valor= forms.CharField(max_length=255)
    abono_capital = forms.BooleanField(required=False, label='¿Es abono a capital?')
    condona_mora = forms.BooleanField(required=False, label='¿Se condonará la mora?')
    not_duplicated = forms.BooleanField(required=False, label='No es duplicado')
    soporte = forms.FileField(required=False, validators=[FileExtensionValidator(allowed_extensions=['pdf'],
                                                            message="Debes cargar un archivo pdf")])
    solicitud_id = forms.CharField(required=False, widget=forms.HiddenInput())
    
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Row(
                customfields.customSelectField('proyecto_solic'),
            css_class='mb-3'),
            Row(
                Column(Field('cliente')),
            css_class='mb-3'),
            Row(
                Column(customfields.datepickerField('fecha_pago')),
                Column(Field('valor',css_class='money text-center')),
            css_class='mb-3'),
            Row(
                Column(Field('abono_capital')),
                Column(Field('condona_mora')),
                Column(Field('not_duplicated')),
                css_class='mb-3',
            ),
            Row(
               customfields.filepicker('soporte'),
               css_class='mb-3',
            ),
            Row(
               Submit('btnsubmit','Crear',css_class='ml-auto')
            ),
            Field('solicitud_id'),
        )
