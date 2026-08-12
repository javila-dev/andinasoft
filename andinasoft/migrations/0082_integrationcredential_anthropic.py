from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('andinasoft', '0081_integration_extraccion_fechas'),
    ]

    operations = [
        migrations.AlterField(
            model_name='integrationcredential',
            name='provider',
            field=models.CharField(
                choices=[
                    ('openai', 'OpenAI'),
                    ('gemini', 'Gemini'),
                    ('anthropic', 'Anthropic'),
                ],
                max_length=32,
            ),
        ),
        migrations.AlterField(
            model_name='integrationcredential',
            name='default_model',
            field=models.CharField(
                blank=True,
                default='',
                help_text='ID de modelo API (ver catalogo en Integraciones LLM)',
                max_length=128,
            ),
        ),
    ]
