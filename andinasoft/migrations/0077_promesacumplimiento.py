from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('andinasoft', '0076_promesaotrosi'),
    ]

    operations = [
        migrations.CreateModel(
            name='PromesaCumplimiento',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('adj', models.CharField(db_index=True, max_length=255)),
                ('fecha_entrega_real', models.DateField(blank=True, null=True)),
                ('fecha_escritura_real', models.DateField(blank=True, null=True)),
                ('usuario_entrega', models.CharField(blank=True, default='', max_length=255)),
                ('usuario_escritura', models.CharField(blank=True, default='', max_length=255)),
                ('actualizado', models.DateTimeField(auto_now=True)),
                ('proyecto', models.ForeignKey(db_constraint=False, on_delete=django.db.models.deletion.CASCADE, related_name='promesa_cumplimiento', to='andinasoft.proyectos')),
            ],
            options={
                'verbose_name': 'Cumplimiento de promesa',
                'verbose_name_plural': 'Cumplimientos de promesas',
                'unique_together': {('proyecto', 'adj')},
            },
        ),
    ]
