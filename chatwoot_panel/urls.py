from django.urls import path

from chatwoot_panel import views

app_name = 'chatwoot_panel'

urlpatterns = [
    path('panel/', views.panel, name='panel'),
    path('conectar/', views.conectar, name='conectar'),
    path('api/yo/', views.api_yo, name='api_yo'),
    path('api/desconectar/', views.api_desconectar, name='api_desconectar'),
    path('api/contexto/', views.api_contexto, name='api_contexto'),
    path('api/buscar/', views.api_buscar, name='api_buscar'),
    path('api/vincular/', views.api_vincular, name='api_vincular'),
    path('api/negocio/<str:proyecto>/<str:adj>/cartera/', views.api_cartera, name='api_cartera'),
    path('api/negocio/<str:proyecto>/<str:adj>/estado-cuenta/', views.api_estado_cuenta, name='api_estado_cuenta'),
    path('api/negocio/<str:proyecto>/<str:adj>/promesa/', views.api_promesa, name='api_promesa'),
    path('api/negocio/<str:proyecto>/<str:adj>/documentos/', views.api_documentos, name='api_documentos'),
    path('api/negocio/<str:proyecto>/<str:adj>/documentos/<int:doc_id>/', views.api_documento, name='api_documento'),
    path('api/negocio/<str:proyecto>/<str:adj>/seguimientos/', views.api_seguimientos, name='api_seguimientos'),
]
