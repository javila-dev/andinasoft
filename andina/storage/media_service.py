from django.conf import settings
from django.core.files.base import ContentFile

from andina.storage_backends import LocalMediaStorage, PrivateMediaStorage, PublicMediaStorage


def _to_file_obj(content):
    if hasattr(content, "read"):
        return content
    if isinstance(content, str):
        content = content.encode("utf-8")
    return ContentFile(content)


def _save_with_backend(backend, path, content):
    file_obj = _to_file_obj(content)
    if hasattr(file_obj, "seek"):
        file_obj.seek(0)
    return backend.save(path, file_obj)


def _s3_configured():
    """True si hay bucket/credenciales para MinIO/S3."""
    return bool(
        getattr(settings, "AWS_STORAGE_BUCKET_NAME", None)
        and getattr(settings, "AWS_ACCESS_KEY_ID", None)
        and getattr(settings, "AWS_SECRET_ACCESS_KEY", None)
    )


def _write_to_s3():
    """Escritura: respeta USE_S3_MEDIA (igual que radicacion en produccion)."""
    return bool(getattr(settings, "USE_S3_MEDIA", False))


def _read_from_s3():
    """
    Lectura: MinIO/S3 si USE_S3_MEDIA o hay credenciales.
    Asi produccion y entornos con bucket configurado leen de MinIO,
    no solo del disco local.
    """
    return bool(getattr(settings, "USE_S3_MEDIA", False) or _s3_configured())


def save_public(path, content):
    if _write_to_s3():
        return _save_with_backend(PublicMediaStorage(), path, content)
    return _save_with_backend(LocalMediaStorage(), path, content)


def save_private(path, content):
    if _write_to_s3():
        return _save_with_backend(PrivateMediaStorage(), path, content)
    return _save_with_backend(LocalMediaStorage(), path, content)


def open_media(path, mode="rb", private=True):
    """
    Abre media. En produccion (y con credenciales S3) prioriza MinIO;
    si no esta ahi, intenta disco local.
    """
    if _read_from_s3():
        storage = PrivateMediaStorage() if private else PublicMediaStorage()
        try:
            return storage.open(path, mode=mode)
        except Exception:
            try:
                return LocalMediaStorage().open(path, mode=mode)
            except Exception:
                pass
            raise
    return LocalMediaStorage().open(path, mode=mode)


def exists_media(path, private=True):
    """Existe en MinIO/S3 (prioridad) o en disco local."""
    if _read_from_s3():
        storage = PrivateMediaStorage() if private else PublicMediaStorage()
        try:
            if storage.exists(path):
                return True
        except Exception:
            pass
        try:
            return LocalMediaStorage().exists(path)
        except Exception:
            return False
    try:
        return LocalMediaStorage().exists(path)
    except Exception:
        return False


def url_media(path, private=True):
    """URL firmada MinIO/S3 en produccion; local como respaldo."""
    if _read_from_s3():
        storage = PrivateMediaStorage() if private else PublicMediaStorage()
        try:
            if storage.exists(path):
                return storage.url(path)
        except Exception:
            pass
        try:
            local = LocalMediaStorage()
            if local.exists(path):
                return local.url(path)
        except Exception:
            pass
        return storage.url(path)
    return LocalMediaStorage().url(path)


def delete_media(path, private=True):
    if _write_to_s3():
        storage = PrivateMediaStorage() if private else PublicMediaStorage()
    else:
        storage = LocalMediaStorage()
    storage.delete(path)
