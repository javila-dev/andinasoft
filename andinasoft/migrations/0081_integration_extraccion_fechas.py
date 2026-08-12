from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('andinasoft', '0080_carteracartageneracion'),
    ]

    operations = [
        migrations.CreateModel(
            name='IntegrationCredential',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('provider', models.CharField(choices=[('openai', 'OpenAI'), ('gemini', 'Gemini')], max_length=32)),
                ('label', models.CharField(blank=True, default='', max_length=255)),
                ('api_key', models.CharField(max_length=1024)),
                ('default_model', models.CharField(blank=True, default='', help_text='Ej: gpt-4o-mini, gemini-2.0-flash', max_length=128)),
                ('activo', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Credencial de integracion',
                'verbose_name_plural': 'Credenciales de integracion',
                'ordering': ['provider', 'label', 'id'],
            },
        ),
        migrations.CreateModel(
            name='IntegrationPurposeMapping',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('purpose', models.CharField(choices=[('extraccion_fechas_contrato', 'Extraccion fechas de contrato (PDF)')], max_length=64, unique=True)),
                ('model_override', models.CharField(blank=True, default='', help_text='Si se indica, reemplaza el modelo por defecto de la credencial', max_length=128)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('credential', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='purpose_mappings', to='andinasoft.integrationcredential')),
            ],
            options={
                'verbose_name': 'Uso de integracion',
                'verbose_name_plural': 'Usos de integracion',
            },
        ),
        migrations.CreateModel(
            name='AdjFechaDocumentoExtraccion',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('adj', models.CharField(db_index=True, max_length=255)),
                ('fecha_contrato', models.DateField(blank=True, null=True)),
                ('fecha_escritura', models.DateField(blank=True, null=True)),
                ('fecha_entrega', models.DateField(blank=True, null=True)),
                ('documento_usado', models.CharField(blank=True, default='', max_length=500)),
                ('tipo_doc_esperado', models.CharField(blank=True, default='', max_length=64)),
                ('fecha_carga_doc', models.CharField(blank=True, default='', max_length=64)),
                ('provider', models.CharField(blank=True, default='', max_length=32)),
                ('model', models.CharField(blank=True, default='', max_length=128)),
                ('raw_json', models.TextField(blank=True, default='')),
                ('estado', models.CharField(choices=[('pendiente', 'Pendiente'), ('ok', 'OK'), ('sin_documento', 'Sin documento'), ('sin_fechas', 'Sin fechas'), ('error', 'Error')], db_index=True, default='pendiente', max_length=32)),
                ('error_msg', models.CharField(blank=True, default='', max_length=1000)),
                ('synced_to_promesas', models.BooleanField(default=False)),
                ('actualizado', models.DateTimeField(auto_now=True)),
                ('creado', models.DateTimeField(auto_now_add=True)),
                ('proyecto', models.ForeignKey(db_constraint=False, on_delete=django.db.models.deletion.CASCADE, related_name='extracciones_fechas_doc', to='andinasoft.proyectos')),
            ],
            options={
                'verbose_name': 'Extraccion fechas documento',
                'verbose_name_plural': 'Extracciones fechas documentos',
                'ordering': ['proyecto_id', 'adj'],
                'unique_together': {('proyecto', 'adj')},
            },
        ),
    ]
