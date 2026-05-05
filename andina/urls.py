"""andina URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/3.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.conf.urls import url
from django.views.generic.base import TemplateView
from andinasoft import views, ajax_request
from buildingcontrol import views as building_views, pdf as building_pdf
from crm import views as crm_views
from accounting import views as account_views
from mcp_server import urls as mcp_urls

urlpatterns = [

    path('mcp/', include(mcp_urls)),
    path('portal/', include('client_portal.urls')),
    path('admin/', admin.site.urls),
    path('welcome',views.welcome,name='welcome'),
    path('pago_exitoso',views.pago_exitoso,name='pago exitoso'),
    path('pago_proceso',views.pago_proceso,name='pago proceso'),
    path('',views.welcome,name='welcome'),
    path('finance/',include('finance.urls')),
    path('ajax/getavatars',views.get_avatars),
    path('user/change_avatar/<avatar>',views.cambiar_avatar),
    url(r'^$', TemplateView.as_view(template_name='base.html'), name='home'),
    path('advisersarea/landing',views.advisersarea),
    path('accounts/', include('registration.backends.default.urls')),
    path('reg_asesor',views.registro_asesor, name='registrar asesor'),
    path('buildingcontrol/',include(building_views.urls)),
    path('accounting/',include(account_views.urls)),
    path('andinasoftajx/',include(views.Ajax_URL)),
    path('fractal',views.landing_fractal),
    path('crm/',include(crm_views.urls)),
    path('ajax_request/',include(ajax_request.urls)),
    path('reports/',include(building_pdf.urls)),
    path('reg_asesor/success',views.registro_exitoso, name='reg_asesor_exitoso'),
    path('comercial/lista_asesores/<proyecto>',views.lista_asesores,name='lista asesores'),
    path('comercial/lista_asesores_general/<proyecto>',views.lista_asesores_general,name='lista general asesores'),
    path('comercial/gtt/<proyecto>',views.lista_gtt),
    path('comercial/gtt/nuevo/<proyecto>',views.nuevo_gtt),
    path('downloads/gtt/<proyecto>/<gtt>',views.printGtt),
    path('downloads/gtt/<proyecto>/<desde>/<hasta>',views.printComisiones),
    path('adjudicaciones/<proyecto>',views.lista_adjudicaciones,name='lista adjudicaciones'),
    path('adjudicaciones/<proyecto>/<adj>/',views.detalle_adjudicacion,name='detalle adjudicacion'),
    path('nuevo_recaudo/<proyecto>/<adj>',views.nuevo_recaudo,name='nuevo recaudo'),
    path('api/receipts/validate',views.api_validate_recaudo,name='api_validate_recaudo'),
    path('api/receipts/create',views.api_crear_recaudo,name='api_crear_recaudo'),
    path('api/formas-pago',views.api_formas_pago,name='api_formas_pago'),
    path('api/adjudicaciones',views.api_adjudicaciones,name='api_adjudicaciones'),
    path('api/terceros',views.api_terceros,name='api_terceros'),
    path('reg_cliente',views.registrar_cliente,name='registro cliente'),
    path('reg_cliente/success',views.registro_exitoso,name='registro cliente exitoso'),
    path('tesoreria/lista_recaudos',views.lista_recaudos,name='lista recaudos'),
    path('venta/seleccionar_proyecto',views.seleccionar_proyecto, name='seleccionar proyecto'),
    path('venta/inventario/<proyecto>',views.inventario_comercial,name='inventario comercial'),
    path('venta/<proyecto>/<inmueble>',views.nueva_venta,name='nueva venta'),
    path('comercial/ventas_sin_aprobar/<proyecto>',views.ventas_sin_aprobar,name='ventassinaprobar'),
    path('projectselector/<redireccion>',views.proyecto_popup,name='selector de proyecto'),
    path('comercial/acciones_venta/<proyecto>/<contrato>',views.acciones_venta,name='acciones venta'),
    path('operaciones/adjudicar_contrato/<proyecto>/<contrato>',views.adjudicar_venta,name='adjudicar venta'),
    path('operaciones/por_adjudicar/<proyecto>',views.ventas_aprobadas,name='ventas sin adjudicar'),
    path('tesoreria/recaudos_nr/<proyecto>',views.recaudos_noradicados,name='recaudos no radicados'),
    path('desistidos/<proyecto>',views.lista_desistidos,name='desistidos'),
    path('operaciones/reestructuraciones/<proyecto>/<adj>',views.reestructuraciones,name='reestructuraciones'),
    path('operaciones/comisiones/<proyecto>',views.comisiones,name='comisiones'),
    path('operaciones/inventario_administrativo/<proyecto>',views.inventario_admin,name='inventario administrativo'),
    path('cartera/ver_presupuesto/<proyecto>',views.ver_presupuesto,name='ver presupuesto'),
    path('cartera/ver_presupuesto/<proyecto>/<periodo>',views.presupuesto_cartera,name='pptomes'),
    path('cartera/edades_cartera/<proyecto>',views.edades_cartera),
    path('cartera/otrosi',views.reestructuraciones_cartera),
    path('cartera/reporteov',views.cartera_month_results),
    path('comercial/detalle_comisiones/<proyecto>',views.detalle_comisiones,name='detalle comisiones'),
    path('correspondencia/facturas/nueva',views.radicar_factura,name='radicar factura'),
    path('correspondencia/facturas/todas',views.lista_facturas,name='lista facturas'),
    path('correspondencia/facturas/causar',views.causar_facturas,name='causar factura'),
    path('correspondencia/facturas/pagar',views.pagar_facturas,name='pagar factura'),
    path('correspondencia/facturas/pagos_efectuados',views.lista_pagos,name='lista pagos'),
    path('contabilidad/interfaces/<proyecto>',views.interfaces_contabilidad,name='interfaz recibos'),
    path('operaciones/descuentos_condicionados/<proyecto>',views.descuentos_condicionados,name='descuentos condicionados'),
    path('operaciones/promesas/<proyecto>',views.promesas,name='promesas'),
    path('operaciones/informes/<proyecto>',views.informe_mes,name='informes'),
    path('contabilidad/informes/gastos/cargar',views.informe_gastos,name='gastos'),
    path('contabilidad/gastos/detalle/<empresa>/<año>/<mes>',views.detalle_gastos,name='detalle gastos'),
    path('contabilidad/informes/gastos',views.general_gastos,name='general gastos'),
    path('contabilidad/informes/gastos/asociar_cuentas/<empresa>',views.asociar_cuentas,name='asociar cuentas'),
    path('contabilidad/informes/gastos/asociar_cc/<empresa>',views.asociar_cc,name='asociar cc'),
    path('operaciones/cambio_fechas/<proyecto>/<adj>',views.mover_fechas,name='mover fechas'),
    path('operaciones/parametros/<proyecto>',views.parametros,name='parametros'),
    path('graphs/recaudos/<proyecto>',views.graphs,name='grafica recaudos'),
    path('graphs/ventas/<proyecto>',views.graph_ventas_anuales),
    path('graphs/recaudos/comparativo/<proyecto>',views.graph_rcdo_com_año),
    path('graphs/cartera/year/<proyecto>',views.graph_cartera_anual),
    path('operaciones/buscar_cliente',views.buscar_cliente,name='buscar cliente'),
    path('blank_request',views.blank_request),
    path('servicio_cliente/pqrs/<proyecto>',views.lista_pqrs),
    path('tesoreria/adjudicaciones/<proyecto>',views.lista_adj_recaudos),
    path('tesoreria/interfaces_tesoreria',views.interfaces_bancarias),
    path('cartera/reporte_year/<proyecto>/<año>',views.reporte_cartera),
    path('simulador',views.simulador),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
handler403 = 'andinasoft.views.handler403'
handler500 = 'andinasoft.views.handler500'
