import secrets
from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone

User = get_user_model()


def generate_token_key():
    return secrets.token_hex(32)


class APIToken(models.Model):
    key = models.CharField(max_length=64, unique=True, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='api_tokens')
    name = models.CharField(max_length=255, blank=True, null=True)
    is_active = models.BooleanField(default=True)
    allowed_ips = models.CharField(max_length=500, blank=True, null=True,
                                   help_text='Lista separada por comas de IPs permitidas (opcional)')
    created_at = models.DateTimeField(auto_now_add=True)
    last_used = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'API Token'
        verbose_name_plural = 'API Tokens'

    def __str__(self):
        return f'{self.user} - {self.display_name}'

    @property
    def display_name(self):
        return self.name or self.key[-8:]

    def save(self, *args, **kwargs):
        if not self.key:
            self.key = generate_token_key()
        super().save(*args, **kwargs)

    def touch(self):
        self.last_used = timezone.now()
        self.save(update_fields=['last_used'])
