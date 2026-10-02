from django.urls import path
from client_portal import views

app_name = 'client_portal'

urlpatterns = [
    path('', views.login_view, name='root'),
    path('login', views.login_view, name='login'),
    path('logout', views.logout_view, name='logout'),
    path('mis-negocios', views.business_list_view, name='business_list'),
    path('negocio/<str:project_alias>/<str:adj_id>', views.business_detail_view, name='business_detail'),
    path('negocio/<str:project_alias>/<str:adj_id>/plan-pagos', views.payment_plan_view, name='payment_plan'),
    path('negocio/<str:project_alias>/<str:adj_id>/documentos', views.documents_view, name='documents'),
    path('negocio/<str:project_alias>/<str:adj_id>/documentos/estado-cuenta', views.account_statement_view, name='account_statement'),
    path('negocio/<str:project_alias>/<str:adj_id>/documentos/<str:document_id>/descargar', views.document_download_view, name='document_download'),
    path('negocio/<str:project_alias>/<str:adj_id>/perfil', views.profile_view, name='profile'),
    path('negocio/<str:project_alias>/<str:adj_id>/pqrs', views.pqrs_list_view, name='pqrs_list'),
    path('negocio/<str:project_alias>/<str:adj_id>/pqrs/nueva', views.pqrs_new_view, name='pqrs_new'),
    path('negocio/<str:project_alias>/<str:adj_id>/pqrs/<int:pqrs_id>', views.pqrs_detail_view, name='pqrs_detail'),
]
