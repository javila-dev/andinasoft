from django.urls import path, re_path

from telefonia import views

app_name = 'telefonia'

urlpatterns = [
    path('softphone/', views.softphone, name='softphone'),
    path('api/destinos/', views.api_destinos, name='api_destinos'),
    path('api/llamar/', views.api_llamar, name='api_llamar'),
    path('api/llamadas/<int:pk>/', views.api_llamada, name='api_llamada'),
    path('twilio/voz/', views.twilio_voz, name='twilio_voz'),
    path('twilio/estado/', views.twilio_estado, name='twilio_estado'),
    path('twilio/grabacion/', views.twilio_grabacion, name='twilio_grabacion'),
    path('twilio/aviso/', views.twilio_aviso, name='twilio_aviso'),
    # Twilio hace POST y APPEND_SLASH no puede redirigir un POST: también sin barra final
    # (por si la URL de la TwiML App se escribe sin ella).
    re_path(r'^twilio/voz$', views.twilio_voz),
    re_path(r'^twilio/estado$', views.twilio_estado),
]
