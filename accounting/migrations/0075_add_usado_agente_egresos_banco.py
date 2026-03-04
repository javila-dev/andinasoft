from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounting', '0074_add_usado_agente_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='egresos_banco',
            name='usado_agente',
            field=models.BooleanField(default=False, help_text='Indica si este movimiento ya fue usado por el agente de conciliación automática'),
        ),
        migrations.AddField(
            model_name='egresos_banco',
            name='fecha_uso_agente',
            field=models.DateTimeField(blank=True, help_text='Fecha en que el agente usó este movimiento', null=True),
        ),
        migrations.AddField(
            model_name='egresos_banco',
            name='recibo_asociado_agente',
            field=models.CharField(blank=True, help_text='Número de recibo con el que el agente usó este movimiento', max_length=255, null=True),
        ),
    ]
