from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('andinasoft', '0073_empresas_alegra_gasto_max_sin_aprobador'),
        ('accounting', '0091_gastos_caja_tipo_documento_soporte'),
    ]

    operations = [
        migrations.CreateModel(
            name='UsuarioAccountingAlcance',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('activo', models.BooleanField(default=True)),
                ('empresas', models.ManyToManyField(
                    blank=True,
                    db_constraint=False,
                    help_text='Vacío = todas las empresas.',
                    related_name='accounting_alcances',
                    to='andinasoft.empresas',
                )),
                ('oficinas', models.ManyToManyField(
                    blank=True,
                    help_text='Vacío = todas las oficinas.',
                    related_name='accounting_alcances',
                    to='accounting.gastonotificacionoficina',
                )),
                ('user', models.OneToOneField(
                    db_constraint=False,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='accounting_alcance',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'verbose_name': 'Alcance contable de usuario',
                'verbose_name_plural': 'Alcances contables de usuarios',
            },
        ),
    ]
