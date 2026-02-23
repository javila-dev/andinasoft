from django.contrib.auth.decorators import user_passes_test
from django.core.exceptions import PermissionDenied
from andinasoft.models import Usuarios_Proyectos

def group_perm_required(perms:list, login_url=None, raise_exception=False):
    """
    Decorator for views that checks whether a user has a particular permission
    enabled, redirecting to the log-in page if necessary.
    If the raise_exception parameter is given the PermissionDenied exception
    is raised.
    """
    def check_perms(user):
        permissions=user.get_all_permissions()
        permissions_granted=0
        permissions_required=len(perms)
        if user.is_superuser:
            return True
        for perm in perms:
            if perm in permissions:
                permissions_granted+=1
        if permissions_granted==permissions_required:
            return True
        if raise_exception:
            raise PermissionDenied
        return False
    return user_passes_test(check_perms, login_url=login_url)


def check_perms(request,perms:list,raise_exception=True):
    user=request.user
    permissions=user.get_all_permissions()
    permissions_granted=0
    permissions_required=len(perms)
    if request.user.is_superuser:
        return True
    for perm in perms:
        if perm in permissions:
            permissions_granted+=1
    if permissions_granted==permissions_required:
        return True
    if raise_exception:
        raise PermissionDenied
    return False

def check_groups(request,groups:list,raise_exception=True):
    groups_ok=0
    groups_needed=len(groups)
    user_groups=request.user.groups.all()
    for user_group in user_groups:
        if user_group.name in groups:
            groups_ok+=1
    if request.user.is_superuser:
        return True
    if groups_ok==groups_needed:
        return True
    if raise_exception:
        raise PermissionDenied
    return False

def check_project(request,proyecto,raise_exception=True):
    if request.user.is_superuser:
        return True
    user=request.user.pk
    user_projects=Usuarios_Proyectos.objects.filter(usuario=user)
    if user_projects.exists():
        user_projects=user_projects[0].proyecto.all()
        for p in user_projects:
            if p.proyecto==proyecto:
                return True
    if raise_exception:
        raise PermissionDenied
    return False