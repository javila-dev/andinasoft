from django import forms
from django.contrib.auth.models import Group, User

from accounting.models import GastoNotificacionOficina
from andinasoft.models import Avatars, empresas, proyectos


class UsuarioCuentaForm(forms.Form):
    username = forms.CharField(max_length=150, label='Usuario')
    first_name = forms.CharField(max_length=150, required=False, label='Nombre')
    last_name = forms.CharField(max_length=150, required=False, label='Apellido')
    email = forms.EmailField(required=False, label='Email')
    is_active = forms.BooleanField(required=False, label='Activo')
    is_staff = forms.BooleanField(required=False, label='Staff (acceso admin)')
    is_superuser = forms.BooleanField(required=False, label='Superusuario')
    password1 = forms.CharField(
        required=False,
        widget=forms.PasswordInput(render_value=False),
        label='Nueva contrasena',
        help_text='Dejar vacio para no cambiarla.',
    )
    password2 = forms.CharField(
        required=False,
        widget=forms.PasswordInput(render_value=False),
        label='Confirmar contrasena',
    )

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._user = user

    def clean_username(self):
        username = self.cleaned_data['username'].strip()
        qs = User.objects.filter(username__iexact=username)
        if self._user:
            qs = qs.exclude(pk=self._user.pk)
        if qs.exists():
            raise forms.ValidationError('Ya existe un usuario con ese nombre.')
        return username

    def clean(self):
        cleaned = super().clean()
        p1 = cleaned.get('password1') or ''
        p2 = cleaned.get('password2') or ''
        if p1 or p2:
            if p1 != p2:
                self.add_error('password2', 'Las contrasenas no coinciden.')
            elif len(p1) < 8:
                self.add_error('password1', 'Minimo 8 caracteres.')
        return cleaned


class UsuarioNuevoForm(UsuarioCuentaForm):
    password1 = forms.CharField(
        required=True,
        widget=forms.PasswordInput(render_value=False),
        label='Contrasena',
    )
    password2 = forms.CharField(
        required=True,
        widget=forms.PasswordInput(render_value=False),
        label='Confirmar contrasena',
    )

    def __init__(self, *args, **kwargs):
        kwargs.setdefault('initial', {})
        kwargs['initial'].setdefault('is_active', True)
        super().__init__(*args, **kwargs)


class UsuarioGruposForm(forms.Form):
    groups = forms.ModelMultipleChoiceField(
        queryset=Group.objects.all().order_by('name'),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label='Grupos',
    )


class UsuarioPerfilForm(forms.Form):
    identificacion = forms.CharField(max_length=255, required=False, label='Identificacion')
    fecha_nacimiento = forms.DateField(
        required=False,
        label='Fecha de nacimiento',
        widget=forms.DateInput(attrs={'type': 'date'}),
    )
    sexo = forms.ChoiceField(
        choices=(('', 'Sin definir'), ('F', 'Femenino'), ('M', 'Masculino')),
        required=False,
        label='Sexo',
    )
    avatar = forms.ModelChoiceField(
        queryset=Avatars.objects.all().order_by('name'),
        required=False,
        label='Avatar',
    )


class UsuarioProyectosForm(forms.Form):
    proyectos = forms.ModelMultipleChoiceField(
        queryset=proyectos.objects.all().order_by('proyecto'),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label='Proyectos autorizados',
    )


class UsuarioAlcanceForm(forms.Form):
    habilitado = forms.BooleanField(
        required=False,
        label='Habilitado para el modulo contable',
        help_text=(
            'Si esta apagado, el usuario no podra operar el flujo de radicacion/pagos. '
            'Si esta encendido y no elige empresas ni oficinas, tendra acceso total.'
        ),
    )
    empresas = forms.ModelMultipleChoiceField(
        queryset=empresas.objects.all().order_by('nombre'),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label='Empresas (vacio = todas)',
    )
    oficinas = forms.ModelMultipleChoiceField(
        queryset=GastoNotificacionOficina.objects.all().order_by('codigo'),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label='Oficinas (vacio = todas)',
    )
