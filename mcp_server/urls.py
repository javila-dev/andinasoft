"""
URLs para el servidor MCP
"""
from django.urls import path
from mcp_server import views

app_name = 'mcp_server'

urlpatterns = [
    # Streamable HTTP (recomendado - MCP 2025)
    path('', views.mcp_streamable_endpoint, name='streamable'),

    # SSE Legacy (deprecated - para compatibilidad)
    path('sse', views.mcp_sse_endpoint, name='sse'),
    path('messages', views.mcp_messages_endpoint, name='messages'),

    # Health check
    path('health', views.mcp_health, name='health'),
]
