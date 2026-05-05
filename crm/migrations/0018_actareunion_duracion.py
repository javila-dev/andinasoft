from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('crm', '0017_alter_actareunion_estado'),
    ]

    operations = [
        migrations.AddField(
            model_name='actareunion',
            name='duracion_minutos',
            field=models.PositiveIntegerField(default=60),
        ),
    ]
