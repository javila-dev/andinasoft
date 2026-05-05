from django.urls import path

from alegra_integration import views


urlpatterns = [
    path('webhooks/bills/', views.webhooks_bills_ingest, name='alegra-webhook-bills-ingest'),
    path('webhooks/bills/<str:empresa_id>/', views.webhooks_bills_ingest, name='alegra-webhook-bills-ingest-by-empresa'),
    path('webhooks/subscribe', views.webhooks_subscribe, name='alegra-webhooks-subscribe'),
    path('webhooks/subscriptions', views.webhooks_subscriptions_list, name='alegra-webhooks-subscriptions-list'),
    path('webhooks/subscriptions/delete', views.webhooks_subscriptions_delete, name='alegra-webhooks-subscriptions-delete'),
    path('webhooks/', views.webhooks_console, name='alegra-webhooks-console'),
    path('', views.dashboard, name='alegra-dashboard'),
    path('references', views.references, name='alegra-references'),
    path('references/data', views.references_data, name='alegra-references-data'),
    path('references/mappings', views.references_mappings, name='alegra-references-mappings'),
    path('references/local-accounts', views.references_local_accounts, name='alegra-references-local-accounts'),
    path('references/save-bank-mapping', views.references_save_bank_mapping, name='alegra-references-save-bank-mapping'),
    path('references/save-category-mapping', views.references_save_category_mapping, name='alegra-references-save-category-mapping'),
    path('references/interfaces', views.references_interfaces, name='alegra-references-interfaces'),
    path('references/intercompany', views.references_intercompany, name='alegra-references-intercompany'),
    path('references/save-numeration-mapping', views.references_save_numeration_mapping, name='alegra-references-save-numeration-mapping'),
    path('references/categories/search', views.references_categories_search, name='alegra-references-categories-search'),
    path('preview', views.preview, name='alegra-preview'),
    path('send', views.send, name='alegra-send'),
    path('batches/', views.batch_list, name='alegra-batch-list'),
    path('batches/<int:batch_id>', views.batch_detail, name='alegra-batch-detail'),
    path('contact-sync', views.contact_sync, name='alegra-contact-sync'),
    path('contact-link', views.contact_link, name='alegra-contact-link'),
    path('contact-link/lookup-local', views.contact_link_lookup_local, name='alegra-contact-link-lookup-local'),
    path('contact-link/validate-alegra', views.contact_link_validate_alegra, name='alegra-contact-link-validate-alegra'),
    path('contacts/bulk-create-from-batch', views.contacts_bulk_create_from_batch, name='alegra-contacts-bulk-create-from-batch'),
    path('contacts/missing-in-alegra-from-batch', views.contacts_missing_in_alegra_from_batch, name='alegra-contacts-missing-in-alegra-from-batch'),
    path('reference-sync', views.reference_sync, name='alegra-reference-sync'),
    path('debug/mapping-check', views.debug_mapping_check, name='alegra-debug-mapping-check'),
]
