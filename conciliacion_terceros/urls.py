from django.urls import path

from conciliacion_terceros import views

urlpatterns = [
    path('', views.index, name='conciliacion-terceros'),
    path('muestra-formato/', views.muestra_formato, name='conciliacion-terceros-muestra'),
    path('facturacion/', views.facturacion_config, name='conciliacion-terceros-facturacion'),
    path('facturacion/referencias', views.facturacion_referencias, name='conciliacion-terceros-facturacion-referencias'),
    path('<int:pk>/facturas', views.factura_crear, name='conciliacion-terceros-factura-crear'),
    path('<int:pk>/facturas/costo-sugerido', views.factura_costo_sugerido, name='conciliacion-terceros-factura-costo'),
    path('<int:pk>/facturas/<int:factura_id>/<str:accion>', views.factura_accion, name='conciliacion-terceros-factura-accion'),
    path('<int:pk>/', views.detalle, name='conciliacion-terceros-detalle'),
    path('<int:pk>/fuentes', views.fuente_agregar, name='conciliacion-terceros-fuente-agregar'),
    path('<int:pk>/fuentes/<int:fuente_id>/cuentas', views.fuente_cuentas, name='conciliacion-terceros-cuentas'),
    path('<int:pk>/fuentes/<int:fuente_id>/quitar', views.fuente_quitar, name='conciliacion-terceros-fuente-quitar'),
    path('<int:pk>/proyectos', views.proyectos, name='conciliacion-terceros-proyectos'),
    path('<int:pk>/recalcular', views.recalcular, name='conciliacion-terceros-recalcular'),
    path('<int:pk>/estado', views.cambiar_estado, name='conciliacion-terceros-estado'),
    path('<int:pk>/exportar', views.exportar, name='conciliacion-terceros-exportar'),
    path('<int:pk>/correccion/previa', views.correccion_previa, name='conciliacion-terceros-correccion-previa'),
    path('<int:pk>/correccion', views.correccion_ejecutar, name='conciliacion-terceros-correccion'),
    path('<int:pk>/correccion/<int:correccion_id>/revertir', views.correccion_revertir, name='conciliacion-terceros-correccion-revertir'),
    path('<int:pk>/terceros/buscar', views.buscar_tercero, name='conciliacion-terceros-buscar'),
    path('<int:pk>/ajustes', views.ajuste_crear, name='conciliacion-terceros-ajuste-crear'),
    path('<int:pk>/ajustes/<int:ajuste_id>/anular', views.ajuste_anular, name='conciliacion-terceros-ajuste-anular'),
    path('<int:pk>/lineas/<int:linea_id>/revision', views.linea_revision, name='conciliacion-terceros-linea-revision'),
]
