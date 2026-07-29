from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('andinasoft', '0075_configdocumento'),
    ]

    operations = [
        migrations.CreateModel(
            name='PromesaOtrosi',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('adj', models.CharField(db_index=True, max_length=255)),
                ('tipo', models.CharField(choices=[('entrega', 'Entrega'), ('escritura', 'Escritura'), ('ambos', 'Entrega y escritura')], max_length=20)),
                ('fecha_entrega_anterior', models.DateField(blank=True, null=True)),
                ('fecha_entrega_nueva', models.DateField(blank=True, null=True)),
                ('fecha_escritura_anterior', models.DateField(blank=True, null=True)),
                ('fecha_escritura_nueva', models.DateField(blank=True, null=True)),
                ('observaciones', models.TextField(blank=True, default='')),
                ('documento', models.CharField(blank=True, default='', help_text='Nombre/ruta del PDF del otrosi en documentos del contrato', max_length=500)),
                ('usuario', models.CharField(max_length=255)),
                ('fecha_registro', models.DateTimeField(auto_now_add=True)),
                ('proyecto', models.ForeignKey(db_constraint=False, on_delete=django.db.models.deletion.CASCADE, related_name='promesa_otrosi', to='andinasoft.proyectos')),
            ],
            options={
                'verbose_name': 'Otrosi de promesa',
                'verbose_name_plural': 'Otrosi de promesas',
                'ordering': ['-fecha_registro'],
            },
        ),
    ]
