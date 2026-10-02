from django.contrib import messages
from django.http import Http404
from django.shortcuts import redirect, render

from client_portal.decorators import portal_login_required
from client_portal.forms import PortalLoginForm
from client_portal.services.auth import get_current_client, logout_session, start_session
from client_portal.services.businesses import (
    get_business_detail_for_client,
    get_payment_plan_for_client,
    list_businesses_for_client,
)
from client_portal.services.documents import (
    build_account_statement_response,
    download_business_document,
    list_business_documents,
)
from client_portal.services.pqrs import list_portal_pqrs
from client_portal.services.profile import get_client_profile


def login_view(request):
    if request.session.get('portal_client_id'):
        return redirect('client_portal:business_list')

    form = PortalLoginForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        client = start_session(
            request,
            form.cleaned_data['document'],
            form.cleaned_data['birth_date'],
        )
        if client:
            return redirect('client_portal:business_list')
        messages.error(request, 'No encontramos un cliente con esa cédula y fecha de nacimiento.')

    return render(request, 'client_portal/auth/login.html', {'form': form})


@portal_login_required
def logout_view(request):
    logout_session(request)
    return redirect('client_portal:login')


@portal_login_required
def business_list_view(request):
    client = get_current_client(request)
    businesses = list_businesses_for_client(client.pk)
    return render(request, 'client_portal/dashboard/business_list.html', {
        'client': client,
        'businesses': businesses,
    })


@portal_login_required
def business_detail_view(request, project_alias, adj_id):
    client = get_current_client(request)
    business = get_business_detail_for_client(client.pk, project_alias, adj_id)
    if not business:
        raise Http404('No encontramos ese negocio para el cliente autenticado.')

    return render(request, 'client_portal/dashboard/business_detail.html', {
        'client': client,
        'business': business,
    })


@portal_login_required
def payment_plan_view(request, project_alias, adj_id):
    client = get_current_client(request)
    business, installments = get_payment_plan_for_client(client.pk, project_alias, adj_id)
    if not business:
        raise Http404('No encontramos ese negocio para el cliente autenticado.')

    return render(request, 'client_portal/dashboard/payment_plan.html', {
        'client': client,
        'business': business,
        'installments': installments,
        'summary': business.get('payment_summary', {}),
    })


@portal_login_required
def documents_view(request, project_alias, adj_id):
    client = get_current_client(request)
    business = get_business_detail_for_client(client.pk, project_alias, adj_id)
    if not business:
        raise Http404('No encontramos ese negocio para el cliente autenticado.')

    return render(request, 'client_portal/dashboard/documents.html', {
        'client': client,
        'business': business,
        'documents': list_business_documents(project_alias, adj_id),
    })


@portal_login_required
def account_statement_view(request, project_alias, adj_id):
    client = get_current_client(request)
    business = get_business_detail_for_client(client.pk, project_alias, adj_id)
    if not business:
        raise Http404('No encontramos ese negocio para el cliente autenticado.')

    response = build_account_statement_response(
        project_alias,
        adj_id,
        actor_label=getattr(client, 'nombrecompleto', 'Portal clientes'),
    )
    if response is None:
        raise Http404('No pudimos generar el estado de cuenta para este negocio.')
    return response


@portal_login_required
def document_download_view(request, project_alias, adj_id, document_id):
    client = get_current_client(request)
    business = get_business_detail_for_client(client.pk, project_alias, adj_id)
    if not business:
        raise Http404('No encontramos ese negocio para el cliente autenticado.')

    response = download_business_document(project_alias, adj_id, document_id)
    if response is None:
        raise Http404('No encontramos ese documento para este negocio.')
    return response


@portal_login_required
def profile_view(request, project_alias, adj_id):
    client = get_current_client(request)
    business = get_business_detail_for_client(client.pk, project_alias, adj_id)
    if not business:
        raise Http404('No encontramos ese negocio para el cliente autenticado.')

    return render(request, 'client_portal/dashboard/profile.html', {
        'client': get_client_profile(client.pk),
        'business': business,
    })


@portal_login_required
def pqrs_list_view(request, project_alias, adj_id):
    client = get_current_client(request)
    business = get_business_detail_for_client(client.pk, project_alias, adj_id)
    if not business:
        raise Http404('No encontramos ese negocio para el cliente autenticado.')

    return render(request, 'client_portal/dashboard/pqrs_list.html', {
        'client': client,
        'business': business,
        'pqrs_items': list_portal_pqrs(project_alias, adj_id, client.pk),
    })


@portal_login_required
def pqrs_new_view(request, project_alias, adj_id):
    client = get_current_client(request)
    business = get_business_detail_for_client(client.pk, project_alias, adj_id)
    if not business:
        raise Http404('No encontramos ese negocio para el cliente autenticado.')

    return render(request, 'client_portal/dashboard/pqrs_new.html', {
        'client': client,
        'business': business,
    })


@portal_login_required
def pqrs_detail_view(request, project_alias, adj_id, pqrs_id):
    client = get_current_client(request)
    business = get_business_detail_for_client(client.pk, project_alias, adj_id)
    if not business:
        raise Http404('No encontramos ese negocio para el cliente autenticado.')

    return render(request, 'client_portal/dashboard/pqrs_detail.html', {
        'client': client,
        'business': business,
        'pqrs_id': pqrs_id,
    })
