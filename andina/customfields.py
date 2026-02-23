from crispy_forms.layout import Field

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

class timepickerField(Field):
    template = 'crispycustom/timepicker.html'

class filepicker(Field):
    template = 'crispycustom/custom_filepicker.html'
    
class datepicker(Field):
    template = 'crispycustom/datepickerjs.html'