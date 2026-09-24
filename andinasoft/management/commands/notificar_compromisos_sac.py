from django.core.management.base import BaseCommand
from django.utils import timezone

from crm.models import CompromisoActa
from andinasoft.sac_n8n_notify import EVENT_VENCE_HOY, EVENT_VENCIDO, notify_compromiso


class Command(BaseCommand):
    help = 'Notifica compromisos SAC que vencen hoy o ya vencieron.'

    def handle(self, *args, **options):
        today = timezone.localdate()
        qs = CompromisoActa.objects.exclude(estado__in=['Cumplido', 'Cancelado']).select_related(
            'responsable', 'acta', 'acta__cliente', 'acta__proyecto'
        )
        vence_hoy = qs.filter(fecha_compromiso=today)
        vencidos = qs.filter(fecha_compromiso__lt=today)
        enviados = 0
        for compromiso in vence_hoy:
            notify_compromiso(compromiso, event=EVENT_VENCE_HOY, trigger='cron')
            enviados += 1
        for compromiso in vencidos:
            notify_compromiso(compromiso, event=EVENT_VENCIDO, trigger='cron')
            enviados += 1
        self.stdout.write(self.style.SUCCESS(
            f'notificar_compromisos_sac: hoy={vence_hoy.count()} vencidos={vencidos.count()} avisos={enviados}'
        ))
