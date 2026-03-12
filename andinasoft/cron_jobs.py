from django_cron import CronJobBase, Schedule
from django.contrib.auth.models import User
from andinasoft.handlers_functions import envio_notificacion, envio_email_template
from andinasoft.shared_models import saldos_adj
import datetime


class job_cartera(CronJobBase):
    RUN_EVERY_MINS = 2 # every 2 hours

    schedule = Schedule(run_every_mins=RUN_EVERY_MINS)
    code = 'andinasoft.job_cartera'    # a unique code

    def do(self):
        proyectos=(
            'Tesoro Escondido',
            'Vegas de Venecia',
            'Perla del Mar',
            'Sandville Beach',
            'Sotavento',
            'Oasis',
        )
        subject='Clientes que deben pagar hoy'
        carteras=User.objects.filter(groups__name='Gestor Cartera',is_active=True).order_by('first_name')
        gestores={}
        for asesor in carteras:
            nombre=f'{asesor.first_name.upper()} {asesor.last_name.upper()}'
            email=f'{asesor.email}'
            gestores[nombre]=email
        cartera_comercial=('JORGE BLANDON','IAN GUAPACHA')
        cartera_admin=('MIRYAM MARULANDA','DARCY JULIO','NELSON SUAREZ')
        dia=datetime.date.today()
        for proyecto in proyectos:
            for gestor in gestores.keys():
                stmt=f"CALL cobro_dia('{dia}','{gestor}','')"
                obj_cobrodia=saldos_adj.objects.using(proyecto).raw(stmt)
                if len(obj_cobrodia)>0:
                    mensaje=f'Hola {gestor}, estos son los clientes de {proyecto.upper()} a los que debes cobrarle hoy:'
                    subject=f'Clientes de {proyecto} para cobro hoy!'
                    destinatarios=[gestores[gestor]]
                    template='emails/notificacion_con_lista.html'
                    variables={
                        'mensaje':mensaje,
                        'lista_clientes':obj_cobrodia
                        }
                    envio_email_template(subject,'autoreports@somosandina.co',destinatarios,template,variables)
                    if gestor in cartera_comercial:
                        mensaje=f'¡Hola!, estos son los clientes de {proyecto.upper()} a los que {gestor} debe cobrarle hoy:'
                        destinatarios=['sb@somosandina.co','jorgeavila@somosandina.co']
                        variables={
                        'mensaje':mensaje,
                        'lista_clientes':obj_cobrodia
                        }
                        envio_email_template(subject,'autoreports@somosandina.co',destinatarios,template,variables)
                        
                    elif gestor in cartera_admin:
                        mensaje=f'¡Hola! estos son los clientes de {proyecto.upper()} a los que {gestor} debe cobrarle hoy:'
                        destinatarios=['nelsonsuarez@somosandina.co','tatianamontes@somosandina.co','jorgeavila@somosandina.co']
                        variables={
                        'mensaje':mensaje,
                        'lista_clientes':obj_cobrodia
                        }
                        envio_email_template(subject,'autoreports@somosandina.co',destinatarios,template,variables)
                    
                        

