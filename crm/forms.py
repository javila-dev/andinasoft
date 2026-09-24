from django import forms
from django.core.validators import FileExtensionValidator
from django.core.exceptions import ValidationError
from django.contrib.auth.models import User
from django.utils import timezone
from django.db.models import Q
import datetime
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Fieldset, ButtonHolder, Submit, Row, Column, Field, Div, HTML
from crispy_forms.bootstrap import FieldWithButtons, StrictButton, FormActions, PrependedText, PrependedAppendedText, Tab, TabHolder
from andina import customfields
from crm import models as crm_models
from crm import compromiso_tipos
from andinasoft import models as andinasoft_models
from andinasoft.shared_models import titulares_por_adj

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


class ProgramarReunionForm(forms.ModelForm):
    cliente = forms.ModelChoiceField(
        queryset=andinasoft_models.clientes.objects.none(),
        required=False,
        widget=forms.HiddenInput(),
    )

    class Meta:
        model = crm_models.ActaReunion
        fields = [
            'fecha_reunion', 'hora_reunion', 'duracion_minutos', 'tipo_reunion', 'canal', 'cliente',
            'proyecto', 'adj', 'lider_reunion', 'asunto'
        ]
        widgets = {
            'fecha_reunion': forms.DateInput(attrs={'type': 'date'}),
            'hora_reunion': forms.TimeInput(attrs={'type': 'time'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['proyecto'].required = False
        self.fields['hora_reunion'].required = True
        self.fields['adj'].required = False
        self.fields['adj'].label = 'Adjudicacion'
        self.fields['adj'].help_text = 'Si el cliente tiene varios negocios, elija cual aplica a esta reunion.'
        self.fields['duracion_minutos'].help_text = 'Duracion estimada en minutos.'
        self.fields['fecha_reunion'].widget.attrs['min'] = timezone.localdate().isoformat()
        self.fields['cliente'].label_from_instance = lambda obj: f'{obj.nombrecompleto} ({obj.idTercero})'

        roles_lider = ['Atencion al cliente', 'Servicio Cliente']
        lideres_qs = User.objects.filter(
            is_active=True,
            groups__name__in=roles_lider,
        ).distinct().order_by('first_name', 'last_name', 'username')
        self.fields['lider_reunion'].queryset = lideres_qs
        self.fields['lider_reunion'].label_from_instance = (
            lambda obj: (obj.get_full_name() or obj.username).strip()
        )
        self.selected_cliente_label = ''

        cliente_id = None
        if self.is_bound:
            cliente_id = self.data.get(self.add_prefix('cliente')) or self.data.get('cliente')
        elif self.instance and self.instance.pk and self.instance.cliente_id:
            cliente_id = self.instance.cliente_id
        elif self.initial.get('cliente'):
            initial_cliente = self.initial.get('cliente')
            cliente_id = getattr(initial_cliente, 'pk', initial_cliente)

        if cliente_id:
            cliente_qs = andinasoft_models.clientes.objects.filter(pk=cliente_id)
            self.fields['cliente'].queryset = cliente_qs
            cliente_obj = cliente_qs.first()
            if cliente_obj:
                self.selected_cliente_label = f'{cliente_obj.nombrecompleto} ({cliente_obj.idTercero})'

    def clean_fecha_reunion(self):
        fecha = self.cleaned_data.get('fecha_reunion')
        if fecha and fecha < timezone.localdate():
            raise ValidationError('La fecha de la reunion no puede ser menor a hoy.')
        return fecha

    def _calcular_rango_reunion(self, cleaned_data):
        fecha = cleaned_data.get('fecha_reunion')
        hora = cleaned_data.get('hora_reunion')
        duracion = cleaned_data.get('duracion_minutos') or 0
        if not fecha or not hora or duracion <= 0:
            return None, None
        inicio = datetime.datetime.combine(fecha, hora)
        fin = inicio + datetime.timedelta(minutes=duracion)
        return inicio, fin

    def clean(self):
        cleaned_data = super().clean()
        proyecto = cleaned_data.get('proyecto')
        cliente = cleaned_data.get('cliente')
        lider = cleaned_data.get('lider_reunion')
        duracion = cleaned_data.get('duracion_minutos')

        if cliente and not proyecto:
            raise ValidationError('Debes seleccionar primero el proyecto antes de asociar un cliente.')

        if duracion is not None and duracion <= 0:
            raise ValidationError('La duracion de la reunion debe ser mayor a cero minutos.')

        if proyecto and cliente:
            existe = titulares_por_adj.objects.using(proyecto.pk).filter(
                Q(IdTercero1=cliente.pk) |
                Q(IdTercero2=cliente.pk) |
                Q(IdTercero3=cliente.pk) |
                Q(IdTercero4=cliente.pk)
            ).exists()
            if not existe:
                raise ValidationError('El cliente seleccionado no esta asociado al proyecto elegido.')
            adj = (cleaned_data.get('adj') or '').strip()
            if adj:
                adj_ok = titulares_por_adj.objects.using(proyecto.pk).filter(
                    adj=adj
                ).filter(
                    Q(IdTercero1=cliente.pk) |
                    Q(IdTercero2=cliente.pk) |
                    Q(IdTercero3=cliente.pk) |
                    Q(IdTercero4=cliente.pk)
                ).exists()
                if not adj_ok:
                    raise ValidationError('La adjudicacion no corresponde a este cliente en el proyecto.')
            cleaned_data['adj'] = adj

        inicio, fin = self._calcular_rango_reunion(cleaned_data)
        if lider and inicio and fin:
            reuniones_mismo_dia = crm_models.ActaReunion.objects.filter(
                lider_reunion=lider,
                fecha_reunion=inicio.date(),
            ).exclude(estado='Cancelada')
            if self.instance and self.instance.pk:
                reuniones_mismo_dia = reuniones_mismo_dia.exclude(pk=self.instance.pk)

            for reunion in reuniones_mismo_dia:
                otro_inicio = reunion.inicio_programado()
                otro_fin = reunion.fin_programado()
                if not otro_inicio or not otro_fin:
                    continue
                if otro_inicio < fin and otro_fin > inicio:
                    raise ValidationError(
                        f'El lider ya tiene una reunion entre {otro_inicio.strftime("%H:%M")} y {otro_fin.strftime("%H:%M")}.'
                    )

        return cleaned_data


class ActaResultadoForm(forms.ModelForm):
    class Meta:
        model = crm_models.ActaReunion
        fields = ['resumen', 'decisiones', 'proxima_reunion', 'estado']
        widgets = {
            'resumen': forms.Textarea(attrs={'rows': 4}),
            'decisiones': forms.Textarea(attrs={'rows': 3}),
            'proxima_reunion': forms.DateInput(attrs={'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['resumen'].required = False
        self.fields['decisiones'].required = False
        self.fields['proxima_reunion'].required = False
        self.fields['proxima_reunion'].widget.attrs['min'] = timezone.localdate().isoformat()
        self.fields['estado'].choices = [
            ('En curso', 'En curso'),
            ('Realizada', 'Realizada'),
            ('Cancelada', 'Cancelada'),
        ]

    def clean_proxima_reunion(self):
        fecha = self.cleaned_data.get('proxima_reunion')
        if fecha and fecha < timezone.localdate():
            raise ValidationError('La proxima reunion no puede quedar con una fecha menor a hoy.')
        return fecha


class CompromisoActaForm(forms.ModelForm):
    proyecto_destino = forms.CharField(required=False, label='Proyecto destino')
    lotes_prospecto = forms.CharField(required=False, label='Lotes prospecto')
    fecha_estimada_entrega = forms.DateField(
        required=False,
        label='Fecha estimada de entrega',
        widget=forms.DateInput(attrs={'type': 'date'}),
    )
    observaciones_cambio = forms.CharField(
        required=False,
        label='Observaciones',
        widget=forms.Textarea(attrs={'rows': 2}),
    )
    expectativa_cliente = forms.CharField(
        required=False,
        label='Que espera el cliente',
        widget=forms.Textarea(attrs={'rows': 2}),
    )
    items = forms.MultipleChoiceField(
        required=False,
        choices=compromiso_tipos.ITEMS_ENVIO,
        widget=forms.CheckboxSelectMultiple,
        label='Que se envia',
    )
    items_otro = forms.CharField(required=False, label='Otro documento')
    canal_envio = forms.ChoiceField(
        required=False,
        choices=(('', '---------'),) + compromiso_tipos.CANALES_ENVIO,
        label='Canal de envio',
    )
    lugar_tipo = forms.ChoiceField(
        required=False,
        choices=(('', '---------'),) + compromiso_tipos.LUGARES_CITA,
        label='Tipo de cita',
    )
    lugar = forms.CharField(required=False, label='Lugar / direccion')
    hora_cita = forms.TimeField(
        required=False,
        label='Hora',
        widget=forms.TimeInput(attrs={'type': 'time'}),
    )
    canal_respuesta = forms.ChoiceField(
        required=False,
        choices=(('', '---------'),) + compromiso_tipos.CANALES_RESPUESTA,
        label='Canal de respuesta',
    )
    id_pqrs = forms.CharField(required=False, label='Radicado PQRS')
    area_gestion = forms.ChoiceField(
        required=False,
        choices=(('', '---------'),) + compromiso_tipos.AREAS_GESTION,
        label='Area',
    )
    que_se_pide = forms.CharField(
        required=False,
        label='Que se pide',
        widget=forms.Textarea(attrs={'rows': 2}),
    )

    class Meta:
        model = crm_models.CompromisoActa
        fields = ['tipo', 'titulo', 'descripcion', 'responsable', 'fecha_compromiso', 'prioridad', 'estado']
        widgets = {
            'fecha_compromiso': forms.DateInput(attrs={'type': 'date'}),
            'descripcion': forms.Textarea(attrs={'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        acta = kwargs.pop('acta', None)
        super().__init__(*args, **kwargs)
        self.acta = acta
        self.fields['fecha_compromiso'].widget.attrs['min'] = timezone.localdate().isoformat()
        self.fields['titulo'].required = False
        self.fields['descripcion'].required = False
        self.fields['tipo'].initial = compromiso_tipos.TIPO_OTRO
        proyectos_qs = andinasoft_models.proyectos.objects.filter(activo=True).order_by('proyecto')
        if acta and acta.proyecto_id:
            proyectos_qs = proyectos_qs.exclude(pk=acta.proyecto_id)
        self.fields['proyecto_destino'] = forms.ChoiceField(
            required=False,
            label='Proyecto destino',
            choices=[('', '---------')] + [(p.pk, str(p)) for p in proyectos_qs],
        )
        detalle = {}
        if self.instance and self.instance.pk:
            detalle = self.instance.detalle or {}
        elif self.is_bound:
            detalle = {}
        if detalle:
            self.fields['proyecto_destino'].initial = detalle.get('proyecto_destino')
            self.fields['lotes_prospecto'].initial = detalle.get('lotes_prospecto')
            self.fields['fecha_estimada_entrega'].initial = detalle.get('fecha_estimada_entrega')
            self.fields['observaciones_cambio'].initial = detalle.get('observaciones')
            self.fields['expectativa_cliente'].initial = detalle.get('expectativa_cliente')
            self.fields['items'].initial = detalle.get('items')
            self.fields['items_otro'].initial = detalle.get('items_otro')
            self.fields['canal_envio'].initial = detalle.get('canal')
            self.fields['lugar_tipo'].initial = detalle.get('lugar_tipo')
            self.fields['lugar'].initial = detalle.get('lugar')
            self.fields['hora_cita'].initial = detalle.get('hora')
            self.fields['canal_respuesta'].initial = detalle.get('canal')
            self.fields['id_pqrs'].initial = detalle.get('id_pqrs')
            self.fields['area_gestion'].initial = detalle.get('area')
            self.fields['que_se_pide'].initial = detalle.get('que_se_pide')

    def clean_fecha_compromiso(self):
        fecha = self.cleaned_data.get('fecha_compromiso')
        if fecha and fecha < timezone.localdate():
            raise ValidationError('La fecha del compromiso no puede ser menor a hoy.')
        return fecha

    def _detalle_from_cleaned(self, tipo):
        raw = {
            'proyecto_destino': self.cleaned_data.get('proyecto_destino'),
            'lotes_prospecto': self.cleaned_data.get('lotes_prospecto'),
            'fecha_estimada_entrega': '',
            'observaciones': self.cleaned_data.get('observaciones_cambio'),
            'expectativa_cliente': self.cleaned_data.get('expectativa_cliente'),
            'items': self.cleaned_data.get('items') or [],
            'items_otro': self.cleaned_data.get('items_otro'),
            'canal': self.cleaned_data.get('canal_envio') or self.cleaned_data.get('canal_respuesta'),
            'lugar_tipo': self.cleaned_data.get('lugar_tipo'),
            'lugar': self.cleaned_data.get('lugar'),
            'hora': '',
            'id_pqrs': self.cleaned_data.get('id_pqrs'),
            'area': self.cleaned_data.get('area_gestion'),
            'que_se_pide': self.cleaned_data.get('que_se_pide'),
        }
        fecha_est = self.cleaned_data.get('fecha_estimada_entrega')
        if fecha_est:
            raw['fecha_estimada_entrega'] = fecha_est.isoformat()
        hora = self.cleaned_data.get('hora_cita')
        if hora:
            raw['hora'] = hora.strftime('%H:%M')
        if tipo == compromiso_tipos.TIPO_RESPUESTA_FORMAL:
            raw['canal'] = self.cleaned_data.get('canal_respuesta')
        elif tipo == compromiso_tipos.TIPO_ENVIO_INFORMACION:
            raw['canal'] = self.cleaned_data.get('canal_envio')
        return compromiso_tipos.normalizar_detalle(tipo, raw)

    def clean(self):
        cleaned = super().clean()
        tipo = cleaned.get('tipo') or compromiso_tipos.TIPO_OTRO
        detalle = self._detalle_from_cleaned(tipo)
        for field, message in compromiso_tipos.errores_detalle(tipo, detalle).items():
            form_field = {
                'proyecto_destino': 'proyecto_destino',
                'expectativa_cliente': 'expectativa_cliente',
                'items': 'items',
                'items_otro': 'items_otro',
                'canal': 'canal_envio' if tipo == compromiso_tipos.TIPO_ENVIO_INFORMACION else 'canal_respuesta',
                'lugar_tipo': 'lugar_tipo',
                'lugar': 'lugar',
                'area': 'area_gestion',
                'que_se_pide': 'que_se_pide',
            }.get(field, field)
            self.add_error(form_field, message)
        if tipo == compromiso_tipos.TIPO_OTRO and not (cleaned.get('titulo') or '').strip():
            self.add_error('titulo', 'Indique un titulo.')
        cleaned['detalle'] = detalle
        cleaned['titulo'] = compromiso_tipos.titulo_por_tipo(
            tipo, detalle, cleaned.get('titulo') or ''
        )
        return cleaned

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.tipo = self.cleaned_data.get('tipo') or compromiso_tipos.TIPO_OTRO
        instance.detalle = self.cleaned_data.get('detalle') or {}
        instance.titulo = self.cleaned_data.get('titulo') or instance.titulo
        if commit:
            instance.save()
        return instance


class SeguimientoCompromisoForm(forms.ModelForm):
    class Meta:
        model = crm_models.SeguimientoCompromiso
        fields = ['comentario', 'estado_nuevo', 'fecha_proxima']
        widgets = {
            'comentario': forms.Textarea(attrs={'rows': 3}),
            'fecha_proxima': forms.DateInput(attrs={'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['fecha_proxima'].required = False
        self.fields['fecha_proxima'].widget.attrs['min'] = timezone.localdate().isoformat()

    def clean_fecha_proxima(self):
        fecha = self.cleaned_data.get('fecha_proxima')
        if fecha and fecha < timezone.localdate():
            raise ValidationError('La fecha proxima no puede ser menor a hoy.')
        return fecha


class ActaParticipanteForm(forms.ModelForm):
    class Meta:
        model = crm_models.ActaParticipante
        fields = ['usuario', 'nombre_externo', 'email_externo', 'rol']

    def clean(self):
        cleaned_data = super().clean()
        usuario = cleaned_data.get('usuario')
        nombre_externo = cleaned_data.get('nombre_externo')
        if not usuario and not nombre_externo:
            raise ValidationError('Debes seleccionar un usuario o escribir el nombre del participante externo.')
        return cleaned_data


class AdjuntoActaForm(forms.ModelForm):
    class Meta:
        model = crm_models.AdjuntoActa
        fields = ['tipo', 'descripcion', 'archivo']

