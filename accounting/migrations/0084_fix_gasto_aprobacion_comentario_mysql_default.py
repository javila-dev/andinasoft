# MySQL strict mode (1364): gasto_aprobacion_comentario_contable sin DEFAULT en BD si 0081 se aplicó con --fake.

from django.db import migrations


def apply_db_default(apps, schema_editor):
    conn = schema_editor.connection
    if conn.vendor != 'mysql':
        return
    table = conn.ops.quote_name('accounting_facturas')
    col = conn.ops.quote_name('gasto_aprobacion_comentario_contable')
    with conn.cursor() as cursor:
        cursor.execute(
            f'ALTER TABLE {table} MODIFY COLUMN {col} longtext NOT NULL DEFAULT %s',
            [''],
        )


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('accounting', '0083_facturas_alegra_journal_detalle'),
    ]

    operations = [
        migrations.RunPython(apply_db_default, noop_reverse),
    ]
