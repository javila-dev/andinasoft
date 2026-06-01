from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('finance', '0009_alter_recibos_internos_soporte'),
    ]

    operations = [
        migrations.AlterField(
            model_name='recibos_internos',
            name='fecha',
            field=models.DateField(auto_now_add=True),
        ),
    ]
