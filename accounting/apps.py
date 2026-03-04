import logging

from django.apps import apps as global_apps
from django.apps import AppConfig
from django.contrib.auth import management as auth_management
from django.contrib.auth import get_permission_codename
from django.contrib.contenttypes import management as contenttypes_management
from django.db import DEFAULT_DB_ALIAS, router
from django.db.utils import IntegrityError
from django.db.models.signals import post_migrate


logger = logging.getLogger(__name__)


class AccountingConfig(AppConfig):
    name = 'accounting'

    def ready(self):
        """
        Hace idempotente la creación de content types durante migrate.
        Cubre tanto post_migrate (contenttypes) como create_permissions (auth),
        que internamente también llama create_contenttypes.
        """
        if getattr(contenttypes_management, "_andina_safe_ct_patch", False):
            return

        original_create_contenttypes = contenttypes_management.create_contenttypes
        original_create_permissions = auth_management.create_permissions

        def safe_create_contenttypes(*args, **kwargs):
            try:
                return original_create_contenttypes(*args, **kwargs)
            except IntegrityError as exc:
                msg = str(exc)
                if (
                    "django_content_type_app_label_model" in msg
                    and "Duplicate entry" in msg
                ):
                    logger.warning(
                        "Ignorando colisión de ContentType en migrate: %s",
                        exc,
                    )
                    return
                raise

        contenttypes_management.create_contenttypes = safe_create_contenttypes
        auth_management.create_contenttypes = safe_create_contenttypes
        contenttypes_management._andina_safe_ct_patch = True

        def safe_create_permissions(
            app_config,
            verbosity=2,
            interactive=True,
            using=DEFAULT_DB_ALIAS,
            apps=global_apps,
            **kwargs
        ):
            if not app_config.models_module:
                return

            safe_create_contenttypes(
                app_config,
                verbosity=verbosity,
                interactive=interactive,
                using=using,
                apps=apps,
                **kwargs
            )

            app_label = app_config.label
            try:
                app_config = apps.get_app_config(app_label)
                ContentType = apps.get_model("contenttypes", "ContentType")
                Permission = apps.get_model("auth", "Permission")
            except LookupError:
                return

            if not router.allow_migrate_model(using, Permission):
                return

            searched_perms = []
            ctypes = set()
            for klass in app_config.get_models():
                ctype = ContentType.objects.db_manager(using).get_for_model(
                    klass,
                    for_concrete_model=False,
                )
                ctypes.add(ctype)
                for action in klass._meta.default_permissions:
                    searched_perms.append(
                        (
                            ctype,
                            (
                                get_permission_codename(action, klass._meta),
                                "Can %s %s" % (action, klass._meta.verbose_name_raw),
                            ),
                        )
                    )
                searched_perms.extend((ctype, perm) for perm in klass._meta.permissions)

            all_perms = set(
                Permission.objects.using(using)
                .filter(content_type__in=ctypes)
                .values_list("content_type", "codename")
            )

            perms = [
                Permission(codename=codename, name=name, content_type=ct)
                for ct, (codename, name) in searched_perms
                if (ct.pk, codename) not in all_perms
            ]
            Permission.objects.using(using).bulk_create(perms, ignore_conflicts=True)

        auth_management.create_permissions = safe_create_permissions

        post_migrate.disconnect(
            dispatch_uid="django.contrib.contenttypes.management.create_contenttypes",
        )
        post_migrate.disconnect(
            receiver=original_create_contenttypes,
        )
        post_migrate.disconnect(
            receiver=original_create_contenttypes,
            dispatch_uid="django.contrib.contenttypes.management.create_contenttypes",
        )
        post_migrate.connect(
            receiver=safe_create_contenttypes,
            dispatch_uid="django.contrib.contenttypes.management.create_contenttypes",
            weak=False,
        )
        post_migrate.disconnect(
            dispatch_uid="django.contrib.auth.management.create_permissions",
        )
        post_migrate.disconnect(
            receiver=original_create_permissions,
        )
        post_migrate.disconnect(
            receiver=original_create_permissions,
            dispatch_uid="django.contrib.auth.management.create_permissions",
        )
        post_migrate.connect(
            receiver=safe_create_permissions,
            dispatch_uid="django.contrib.auth.management.create_permissions",
            weak=False,
        )
