from django.db import migrations, models
import django.db.models.deletion

DEFAULT_EMPRESA_CONTABLE = '901018375'


class Migration(migrations.Migration):

    dependencies = [
        ('andinasoft', '0073_empresas_alegra_gasto_max_sin_aprobador'),
    ]

    operations = [
        migrations.AddField(
            model_name='asesores',
            name='empresa_contable',
            field=models.ForeignKey(
                db_column='EmpresaContable',
                default=DEFAULT_EMPRESA_CONTABLE,
                help_text='Empresa que contabiliza y paga las comisiones de este asesor (envío Alegra).',
                on_delete=django.db.models.deletion.PROTECT,
                related_name='asesores_contables',
                to='andinasoft.empresas',
            ),
        ),
    ]
