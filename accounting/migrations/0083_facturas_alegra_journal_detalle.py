from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounting', '0082_backfill_gasto_aprobacion_alegra'),
    ]

    operations = [
        migrations.AddField(
            model_name='facturas',
            name='alegra_journal_detalle',
            field=models.TextField(
                blank=True,
                help_text='JSON: líneas CxP del journal Alegra para pago detallado en tesorería.',
                null=True,
            ),
        ),
    ]
