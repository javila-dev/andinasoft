from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounting', '0089_gasto_tesoreria_notificacion'),
    ]

    operations = [
        migrations.AddField(
            model_name='facturas',
            name='gasto_es_canje',
            field=models.BooleanField(db_index=True, default=False),
        ),
    ]
