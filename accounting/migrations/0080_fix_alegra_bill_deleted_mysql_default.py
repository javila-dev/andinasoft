# MySQL strict mode (1364): alegra_bill_deleted debe tener DEFAULT 0 a nivel de servidor.

from django.db import migrations


def apply_db_default(apps, schema_editor):
    conn = schema_editor.connection
    if conn.vendor != 'mysql':
        return
    table = conn.ops.quote_name('accounting_facturas')
    col = conn.ops.quote_name('alegra_bill_deleted')
    with conn.cursor() as cursor:
        cursor.execute(
            f'ALTER TABLE {table} MODIFY COLUMN {col} tinyint(1) NOT NULL DEFAULT 0'
        )


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('accounting', '0079_facturas_alegra_webhook_fields'),
    ]

    operations = [
        migrations.RunPython(apply_db_default, noop_reverse),
    ]
