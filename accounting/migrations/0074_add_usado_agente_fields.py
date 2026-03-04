from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounting', '0073_plink_wompi_account'),
    ]

    operations = [
        migrations.AddField(
            model_name='plinkmovement',
            name='usado_agente',
            field=models.BooleanField(default=False, help_text='Indica si este movimiento ya fue usado por el agente de conciliación automática'),
        ),
        migrations.AddField(
            model_name='plinkmovement',
            name='fecha_uso_agente',
            field=models.DateTimeField(blank=True, help_text='Fecha en que el agente usó este movimiento', null=True),
        ),
        migrations.AddField(
            model_name='plinkmovement',
            name='recibo_asociado_agente',
            field=models.CharField(blank=True, help_text='Número de recibo con el que el agente usó este movimiento', max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='wompimovement',
            name='usado_agente',
            field=models.BooleanField(default=False, help_text='Indica si este movimiento ya fue usado por el agente de conciliación automática'),
        ),
        migrations.AddField(
            model_name='wompimovement',
            name='fecha_uso_agente',
            field=models.DateTimeField(blank=True, help_text='Fecha en que el agente usó este movimiento', null=True),
        ),
        migrations.AddField(
            model_name='wompimovement',
            name='recibo_asociado_agente',
            field=models.CharField(blank=True, help_text='Número de recibo con el que el agente usó este movimiento', max_length=255, null=True),
        ),
    ]
