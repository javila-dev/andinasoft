"""
UI de gestion de usuarios: cuenta, grupos, perfil, proyectos y alcance contable.
"""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import path
from django.views.decorators.http import require_http_methods

from accounting.models import UsuarioAccountingAlcance
from andinasoft.forms_usuarios import (
    UsuarioAlcanceForm,
    UsuarioCuentaForm,
    UsuarioGruposForm,
    UsuarioNuevoForm,
    UsuarioPerfilForm,
    UsuarioProyectosForm,
)
from andinasoft.models import Avatars, Profiles, Usuarios_Proyectos, proyectos


def _require_staff(user):
    if not user.is_authenticated or not user.is_superuser:
        raise PermissionDenied('Solo un superusuario puede gestionar usuarios.')


def _ensure_profile(user):
    profile, _ = Profiles.objects.get_or_create(
        user=user,
        defaults={
            'sexo': 'M',
            'avatar_id': 9999999,
        },
    )
    return profile


def _ensure_proyectos_rel(user):
    rel = Usuarios_Proyectos.objects.filter(usuario=user).first()
    if rel is None:
        rel = Usuarios_Proyectos.objects.create(usuario=user)
    # Si hay filas extra (legacy), consolidar en la primera.
    extras = Usuarios_Proyectos.objects.filter(usuario=user).exclude(pk=rel.pk)
    if extras.exists():
        for extra in extras:
            for p in extra.proyecto.all():
                rel.proyecto.add(p)
            extra.delete()
    return rel


@login_required
def usuarios_lista(request):
    _require_staff(request.user)
    q = (request.GET.get('q') or '').strip()
    estado = (request.GET.get('estado') or 'activos').strip().lower()
    if estado not in ('todos', 'activos', 'inactivos'):
        estado = 'activos'

    users = (
        User.objects.all()
        .annotate(
            n_proyectos=Count('usuarios_proyectos__proyecto', distinct=True),
        )
        .order_by('username')
    )
    if estado == 'activos':
        users = users.filter(is_active=True)
    elif estado == 'inactivos':
        users = users.filter(is_active=False)

    if q:
        users = users.filter(
            Q(username__icontains=q)
            | Q(first_name__icontains=q)
            | Q(last_name__icontains=q)
            | Q(email__icontains=q)
        )

    alcances_qs = (
        UsuarioAccountingAlcance.objects
        .filter(user_id__in=users.values_list('pk', flat=True))
        .annotate(
            n_emp=Count('empresas', distinct=True),
            n_ofi=Count('oficinas', distinct=True),
        )
    )
    alcances = {a.user_id: a for a in alcances_qs}

    rows = []
    for u in users:
        alc = alcances.get(u.pk)
        if alc is None or not alc.activo:
            alcance_label = 'Sin acceso'
        elif (alc.n_emp or 0) == 0 and (alc.n_ofi or 0) == 0:
            alcance_label = 'Total'
        else:
            alcance_label = f'{alc.n_emp} emp / {alc.n_ofi} ofi'
        rows.append({
            'user': u,
            'n_proyectos': u.n_proyectos or 0,
            'alcance_label': alcance_label,
        })

    form_nuevo = UsuarioNuevoForm()
    if request.method == 'POST' and request.POST.get('action') == 'crear':
        form_nuevo = UsuarioNuevoForm(request.POST)
        if form_nuevo.is_valid():
            data = form_nuevo.cleaned_data
            user = User.objects.create_user(
                username=data['username'],
                email=data.get('email') or '',
                password=data['password1'],
                first_name=data.get('first_name') or '',
                last_name=data.get('last_name') or '',
            )
            user.is_active = bool(data.get('is_active'))
            user.is_staff = bool(data.get('is_staff'))
            user.is_superuser = bool(data.get('is_superuser'))
            user.save()
            _ensure_profile(user)
            _ensure_proyectos_rel(user)
            messages.success(request, f'Usuario {user.username} creado.')
            return redirect('usuarios_detalle', user_id=user.pk)

    context = {
        'rows': rows,
        'q': q,
        'estado': estado,
        'form_nuevo': form_nuevo,
    }
    return render(request, 'usuarios/lista.html', context)


@login_required
@require_http_methods(['GET', 'POST'])
def usuarios_detalle(request, user_id):
    _require_staff(request.user)
    user = get_object_or_404(User, pk=user_id)
    profile = _ensure_profile(user)
    rel = _ensure_proyectos_rel(user)
    alcance = UsuarioAccountingAlcance.objects.filter(user=user).first()

    tab = (request.GET.get('tab') or request.POST.get('tab') or 'cuenta').strip()
    if tab not in ('cuenta', 'grupos', 'perfil', 'proyectos', 'alcance'):
        tab = 'cuenta'

    form_cuenta = UsuarioCuentaForm(
        user=user,
        initial={
            'username': user.username,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'email': user.email,
            'is_active': user.is_active,
            'is_staff': user.is_staff,
            'is_superuser': user.is_superuser,
        },
    )
    form_grupos = UsuarioGruposForm(initial={'groups': user.groups.all()})
    form_perfil = UsuarioPerfilForm(
        initial={
            'identificacion': profile.identificacion,
            'fecha_nacimiento': profile.fecha_nacimiento,
            'sexo': profile.sexo or '',
            'avatar': profile.avatar_id,
        }
    )
    form_proyectos = UsuarioProyectosForm(initial={'proyectos': rel.proyecto.all()})
    form_alcance = UsuarioAlcanceForm(
        initial={
            'habilitado': bool(alcance and alcance.activo),
            'empresas': alcance.empresas.all() if alcance else [],
            'oficinas': alcance.oficinas.all() if alcance else [],
        }
    )

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'cuenta':
            form_cuenta = UsuarioCuentaForm(request.POST, user=user)
            if form_cuenta.is_valid():
                data = form_cuenta.cleaned_data
                # Evitar que un staff se quite staff/superuser a si mismo por accidente critico
                user.username = data['username']
                user.first_name = data.get('first_name') or ''
                user.last_name = data.get('last_name') or ''
                user.email = data.get('email') or ''
                user.is_active = bool(data.get('is_active'))
                user.is_staff = bool(data.get('is_staff'))
                user.is_superuser = bool(data.get('is_superuser'))
                if data.get('password1'):
                    user.set_password(data['password1'])
                user.save()
                messages.success(request, 'Cuenta actualizada.')
                return redirect(f'/configuracion/usuarios/{user.pk}/?tab=cuenta')

        elif action == 'grupos':
            form_grupos = UsuarioGruposForm(request.POST)
            if form_grupos.is_valid():
                user.groups.set(form_grupos.cleaned_data.get('groups') or [])
                messages.success(request, 'Grupos actualizados.')
                return redirect(f'/configuracion/usuarios/{user.pk}/?tab=grupos')

        elif action == 'perfil':
            form_perfil = UsuarioPerfilForm(request.POST)
            if form_perfil.is_valid():
                data = form_perfil.cleaned_data
                profile.identificacion = data.get('identificacion') or ''
                profile.fecha_nacimiento = data.get('fecha_nacimiento')
                sexo = data.get('sexo') or ''
                if sexo in ('F', 'M'):
                    profile.sexo = sexo
                if data.get('avatar'):
                    profile.avatar = data['avatar']
                elif not profile.avatar_id:
                    profile.avatar_id = 9999999
                profile.save()
                messages.success(request, 'Perfil actualizado.')
                return redirect(f'/configuracion/usuarios/{user.pk}/?tab=perfil')

        elif action == 'proyectos':
            form_proyectos = UsuarioProyectosForm(request.POST)
            if form_proyectos.is_valid():
                rel.proyecto.set(form_proyectos.cleaned_data.get('proyectos') or [])
                messages.success(request, 'Proyectos actualizados.')
                return redirect(f'/configuracion/usuarios/{user.pk}/?tab=proyectos')

        elif action == 'alcance':
            form_alcance = UsuarioAlcanceForm(request.POST)
            if form_alcance.is_valid():
                data = form_alcance.cleaned_data
                if not data.get('habilitado'):
                    if alcance:
                        alcance.activo = False
                        alcance.save(update_fields=['activo'])
                    messages.success(request, 'Alcance contable deshabilitado.')
                else:
                    if alcance is None:
                        alcance = UsuarioAccountingAlcance.objects.create(user=user, activo=True)
                    else:
                        alcance.activo = True
                        alcance.save(update_fields=['activo'])
                    alcance.empresas.set(data.get('empresas') or [])
                    alcance.oficinas.set(data.get('oficinas') or [])
                    messages.success(request, 'Alcance contable actualizado.')
                return redirect(f'/configuracion/usuarios/{user.pk}/?tab=alcance')

    context = {
        'target': user,
        'tab': tab,
        'form_cuenta': form_cuenta,
        'form_grupos': form_grupos,
        'form_perfil': form_perfil,
        'form_proyectos': form_proyectos,
        'form_alcance': form_alcance,
        'profile': profile,
        'avatars': Avatars.objects.all().order_by('name')[:40],
        'total_proyectos': proyectos.objects.count(),
    }
    return render(request, 'usuarios/detalle.html', context)


usuarios_urls = [
    path('configuracion/usuarios/', usuarios_lista, name='usuarios_lista'),
    path('configuracion/usuarios/<int:user_id>/', usuarios_detalle, name='usuarios_detalle'),
]
