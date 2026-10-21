from django.http import HttpResponse, JsonResponse

from accounting.saldo_caja import CajaCerrada


class CajaCerradaMiddleware:
    """Responde con un mensaje claro cuando una vista intenta mover efectivo de un día cerrado."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_exception(self, request, exception):
        if not isinstance(exception, CajaCerrada):
            return None
        msj = str(exception)
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({
                'title': 'Caja cerrada',
                'msj': msj,
                'class': 'alert-danger',
                'detail': msj,
            })
        return HttpResponse(msj, status=409, content_type='text/plain; charset=utf-8')
