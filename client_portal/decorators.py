from functools import wraps
from django.shortcuts import redirect
from django.utils import timezone


PORTAL_SESSION_TIMEOUT_MINUTES = 20


def _portal_session_alive(request):
    portal_client_id = request.session.get('portal_client_id')
    if not portal_client_id:
        return False

    last_seen = request.session.get('portal_last_seen_at')
    if not last_seen:
        return False

    try:
        last_seen_dt = timezone.datetime.fromisoformat(last_seen)
    except ValueError:
        return False

    if timezone.is_naive(last_seen_dt):
        last_seen_dt = timezone.make_aware(last_seen_dt, timezone.get_current_timezone())

    delta = timezone.now() - last_seen_dt
    if delta.total_seconds() > PORTAL_SESSION_TIMEOUT_MINUTES * 60:
        return False

    request.session['portal_last_seen_at'] = timezone.now().isoformat()
    return True


def portal_login_required(view_func):
    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        if not _portal_session_alive(request):
            request.session.pop('portal_client_id', None)
            request.session.pop('portal_authenticated_at', None)
            request.session.pop('portal_last_seen_at', None)
            request.session.pop('portal_allowed_businesses', None)
            return redirect('client_portal:login')
        return view_func(request, *args, **kwargs)

    return wrapped
