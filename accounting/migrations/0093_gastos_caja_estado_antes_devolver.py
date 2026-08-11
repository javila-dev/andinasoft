from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounting', '0092_usuario_accounting_alcance'),
    ]

    operations = [
        migrations.AddField(
            model_name='gastos_caja',
            name='estado_antes_devolver',
            field=models.CharField(
                blank=True,
                default='',
                help_text='Estado del gasto antes de ser marcado como Devuelto.',
                max_length=255,
            ),
        ),
    ]
