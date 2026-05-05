# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounting', '0078_auto_20260303_1516'),
    ]

    operations = [
        migrations.AddField(
            model_name='facturas',
            name='alegra_bill_deleted',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='facturas',
            name='alegra_bill_deleted_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='facturas',
            name='alegra_bill_id',
            field=models.CharField(blank=True, db_index=True, max_length=64, null=True, unique=True),
        ),
        migrations.AlterField(
            model_name='facturas',
            name='origen',
            field=models.CharField(
                choices=[
                    ('Radicado', 'Radicado'),
                    ('Proyectos', 'Proyectos'),
                    ('Comisiones', 'Comisiones'),
                    ('GTT', 'GTT'),
                    ('Otros', 'Otros'),
                    ('Interno', 'Interno'),
                    ('Anticipos', 'Anticipos'),
                    ('Alegra', 'Alegra'),
                ],
                db_column='Origen',
                default='Radicado',
                max_length=255,
            ),
        ),
    ]
