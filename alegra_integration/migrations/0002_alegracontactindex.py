from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('alegra_integration', '0001_initial'),
        ('andinasoft', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='AlegraContactIndex',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('identification', models.CharField(db_index=True, max_length=255)),
                ('contact_type', models.CharField(choices=[('client', 'Cliente'), ('provider', 'Proveedor')], db_index=True, max_length=20)),
                ('alegra_id', models.CharField(max_length=255)),
                ('name', models.CharField(blank=True, default='', max_length=255)),
                ('raw', models.JSONField(blank=True, default=dict)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('empresa', models.ForeignKey(db_constraint=False, on_delete=django.db.models.deletion.CASCADE, related_name='alegra_contact_index', to='andinasoft.empresas')),
            ],
            options={
                'verbose_name': 'Índice de contactos Alegra',
                'verbose_name_plural': 'Índice de contactos Alegra',
            },
        ),
        migrations.AddIndex(
            model_name='alegracontactindex',
            index=models.Index(fields=['empresa', 'contact_type', 'identification'], name='alegra_contact_idx_key'),
        ),
        migrations.AddConstraint(
            model_name='alegracontactindex',
            constraint=models.UniqueConstraint(fields=('empresa', 'contact_type', 'identification'), name='unique_alegra_contact_index'),
        ),
    ]

