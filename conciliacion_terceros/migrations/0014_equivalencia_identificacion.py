from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    """El mismo tercero con otra identificación en contabilidad (Alegra no admite letras: CE504122 → 504122)."""

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('conciliacion_terceros', '0013_linea_justificada'),
    ]

    operations = [
        migrations.CreateModel(
            name='EquivalenciaIdentificacion',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('identificacion', models.CharField(max_length=40, unique=True)),
                ('identificacion_contable', models.CharField(max_length=40, unique=True)),
                ('nota', models.TextField(blank=True, default='')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('created_by', models.ForeignKey(blank=True, db_constraint=False, null=True,
                                                 on_delete=django.db.models.deletion.SET_NULL, related_name='+',
                                                 to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Equivalencia de identificación',
                'verbose_name_plural': 'Equivalencias de identificación',
                'ordering': ['identificacion'],
            },
        ),
    ]
