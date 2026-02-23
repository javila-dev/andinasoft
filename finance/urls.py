from django.urls import path, include
from finance import views

urlpatterns = [
    path('requirereceipts', views.solicitar_recibo_interno),
    path('requirereceiptsfractal', views.solicitud_fractal),
    path('printreceipts', views.imprimir_recibo),
    path('api/pending-receipts', views.api_pending_receipts),
    path('api/receipt-request/<int:receipt_id>/status', views.api_update_receipt_status),
    path('api/receipt-stats', views.api_receipt_stats),
]

urlpatterns
