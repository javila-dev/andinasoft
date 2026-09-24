from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('andinasoft', '0089_carteracartaconfig'),
    ]

    operations = [
        migrations.AddField(
            model_name='profiles',
            name='telefono',
            field=models.CharField(
                blank=True,
                default='',
                help_text='WhatsApp / SMS para n8n (ej. 573001234567, sin +).',
                max_length=32,
            ),
        ),
        migrations.AddField(
            model_name='promesacumplimiento',
            name='paso_escritura_actual',
            field=models.CharField(
                choices=[
                    ('pendiente', 'Pendiente'),
                    ('firma_cliente', 'Firma cliente'),
                    ('firma_empresa', 'Firma empresa'),
                    ('registro', 'Registro'),
                    ('facturado', 'Facturado'),
                ],
                db_index=True,
                default='pendiente',
                max_length=32,
            ),
        ),
        migrations.AddField(
            model_name='promesacumplimiento',
            name='fecha_firma_cliente',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='promesacumplimiento',
            name='fecha_firma_empresa',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='promesacumplimiento',
            name='fecha_registro',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='promesacumplimiento',
            name='fecha_facturado',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.CreateModel(
            name='PromesaHito',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('adj', models.CharField(db_index=True, max_length=255)),
                ('paso', models.CharField(
                    choices=[
                        ('pendiente', 'Pendiente'),
                        ('firma_cliente', 'Firma cliente'),
                        ('firma_empresa', 'Firma empresa'),
                        ('registro', 'Registro'),
                        ('facturado', 'Facturado'),
                    ],
                    max_length=32,
                )),
                ('fecha', models.DateField()),
                ('usuario', models.CharField(max_length=255)),
                ('documento', models.CharField(blank=True, default='', max_length=500)),
                ('nota', models.TextField(blank=True, default='')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('proyecto', models.ForeignKey(
                    db_constraint=False,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='promesa_hitos',
                    to='andinasoft.proyectos',
                )),
            ],
            options={
                'verbose_name': 'Hito de escritura',
                'verbose_name_plural': 'Hitos de escritura',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='promesahito',
            index=models.Index(fields=['proyecto', 'adj', 'paso'], name='andinasoft_pr_proyec_hito_idx'),
        ),
        migrations.CreateModel(
            name='PqrsGestion',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('id_pqrs', models.IntegerField(db_index=True)),
                ('adj', models.CharField(blank=True, default='', max_length=255)),
                ('asunto', models.CharField(max_length=255)),
                ('resumen', models.TextField(blank=True, default='')),
                ('resumen_respuesta', models.TextField(blank=True, default='')),
                ('origen', models.CharField(
                    choices=[
                        ('interno', 'Interno'),
                        ('portal', 'Portal'),
                        ('correo', 'Correo'),
                        ('whatsapp', 'WhatsApp'),
                        ('reunion', 'Reunion'),
                        ('ventanilla', 'Ventanilla'),
                    ],
                    default='interno',
                    max_length=32,
                )),
                ('canal', models.CharField(
                    blank=True,
                    choices=[
                        ('ventanilla', 'Ventanilla'),
                        ('correo', 'Correo'),
                        ('reunion', 'Reunion'),
                        ('whatsapp', 'WhatsApp'),
                        ('portal', 'Portal'),
                    ],
                    default='',
                    max_length=32,
                )),
                ('relevante_juridica', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('actualizado', models.DateTimeField(auto_now=True)),
                ('proyecto', models.ForeignKey(
                    db_constraint=False,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='pqrs_gestion',
                    to='andinasoft.proyectos',
                )),
                ('responsable', models.ForeignKey(
                    blank=True,
                    db_constraint=False,
                    null=True,
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name='pqrs_asignadas',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'verbose_name': 'Gestion PQRS',
                'verbose_name_plural': 'Gestiones PQRS',
                'unique_together': {('proyecto', 'id_pqrs')},
            },
        ),
        migrations.AddIndex(
            model_name='pqrsgestion',
            index=models.Index(fields=['proyecto', 'adj'], name='andinasoft_pq_proyec_adj_idx'),
        ),
        migrations.AddIndex(
            model_name='pqrsgestion',
            index=models.Index(fields=['relevante_juridica', 'proyecto'], name='andinasoft_pq_releva_proy_idx'),
        ),
        migrations.CreateModel(
            name='PqrsNota',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('usuario', models.CharField(max_length=255)),
                ('comentario', models.TextField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('gestion', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='notas',
                    to='andinasoft.pqrsgestion',
                )),
            ],
            options={
                'verbose_name': 'Nota PQRS',
                'verbose_name_plural': 'Notas PQRS',
                'ordering': ['-created_at'],
            },
        ),
    ]
