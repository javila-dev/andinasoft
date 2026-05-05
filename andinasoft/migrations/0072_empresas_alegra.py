from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('andinasoft', '0071_proyectos_activo'),
    ]

    operations = [
        migrations.AddField(
            model_name='empresas',
            name='alegra_enabled',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='empresas',
            name='alegra_token',
            field=models.CharField(blank=True, max_length=1024, null=True),
        ),
    ]
