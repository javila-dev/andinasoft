from client_portal.selectors.adjudications import list_business_cards, get_business_snapshot
from client_portal.selectors.payments import get_payment_plan


def list_businesses_for_client(client_id):
    return list_business_cards(client_id)


def get_business_detail_for_client(client_id, project_alias, adj_id):
    return get_business_snapshot(client_id, project_alias, adj_id)


def get_payment_plan_for_client(client_id, project_alias, adj_id):
    business = get_business_snapshot(client_id, project_alias, adj_id)
    if not business:
        return None, []
    return business, get_payment_plan(project_alias, adj_id)
