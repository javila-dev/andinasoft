from django.contrib import admin
from api_auth.models import APIToken


@admin.register(APIToken)
class APITokenAdmin(admin.ModelAdmin):
    list_display = ('display_name', 'user', 'is_active', 'created_at', 'last_used')
    search_fields = ('name', 'key', 'user__username', 'user__email')
    list_filter = ('is_active', 'created_at')
    readonly_fields = ('key', 'created_at', 'last_used')
