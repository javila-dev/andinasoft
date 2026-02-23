from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounting', '0075_add_usado_agente_egresos_banco'),
    ]

    operations = [
        migrations.AddField(
            model_name='egresos_banco',
            name='proyecto_asociado_agente',
            field=models.CharField(blank=True, help_text='Proyecto del recibo con el que el agente usó este movimiento', max_length=255, null=True),
        ),
    ]
