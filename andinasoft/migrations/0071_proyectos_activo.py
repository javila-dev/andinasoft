from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('andinasoft', '0070_auto_20260303_1516'),
    ]

    operations = [
        migrations.AddField(
            model_name='proyectos',
            name='activo',
            field=models.BooleanField(default=True),
        ),
    ]
