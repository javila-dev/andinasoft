from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('finance', '0010_alter_recibos_internos_fecha'),
    ]

    operations = [
        migrations.CreateModel(
            name='SaldoFavorCliente',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('proyecto', models.CharField(db_index=True, max_length=255)),
                ('adjudicacion', models.CharField(db_index=True, max_length=255)),
                ('recibo', models.CharField(db_index=True, max_length=255)),
                ('valor', models.IntegerField(help_text='Positivo = genera saldo a favor')),
                ('fecha', models.DateField(auto_now_add=True)),
                ('usuario', models.CharField(blank=True, max_length=150, null=True)),
                ('nota', models.CharField(blank=True, max_length=255, null=True)),
            ],
            options={
                'verbose_name': 'Saldo a favor cliente',
                'verbose_name_plural': 'Saldos a favor clientes',
            },
        ),
        migrations.AddIndex(
            model_name='saldofavorcliente',
            index=models.Index(fields=['proyecto', 'adjudicacion'], name='finance_sal_proyect_3f8b25_idx'),
        ),
    ]
