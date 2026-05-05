from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('crm', '0016_adjuntoacta'),
    ]

    operations = [
        migrations.AlterField(
            model_name='actareunion',
            name='estado',
            field=models.CharField(
                choices=[
                    ('Programada', 'Programada'),
                    ('En curso', 'En curso'),
                    ('Realizada', 'Realizada'),
                    ('Cancelada', 'Cancelada'),
                ],
                default='Programada',
                max_length=255,
            ),
        ),
    ]
