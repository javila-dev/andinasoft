from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounting', '0072_plink_wompi'),
    ]

    operations = [
        migrations.AddField(
            model_name='plinkmovement',
            name='cuenta_normalizada',
            field=models.CharField(blank=True, max_length=60, null=True),
        ),
        migrations.AddField(
            model_name='wompimovement',
            name='cuenta_normalizada',
            field=models.CharField(blank=True, max_length=60, null=True),
        ),
    ]
