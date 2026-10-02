from django import forms


class PortalLoginForm(forms.Form):
    document = forms.CharField(label='Cedula', max_length=30)
    birth_date = forms.DateField(
        label='Fecha de nacimiento',
        widget=forms.DateInput(attrs={'type': 'date'})
    )
