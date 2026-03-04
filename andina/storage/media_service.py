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


def save_public(path, content):
    if getattr(settings, "USE_S3_MEDIA", False):
        return _save_with_backend(PublicMediaStorage(), path, content)
    return _save_with_backend(LocalMediaStorage(), path, content)


def save_private(path, content):
    if getattr(settings, "USE_S3_MEDIA", False):
        return _save_with_backend(PrivateMediaStorage(), path, content)
    return _save_with_backend(LocalMediaStorage(), path, content)


def open_media(path, mode="rb", private=True):
    if getattr(settings, "USE_S3_MEDIA", False):
        storage = PrivateMediaStorage() if private else PublicMediaStorage()
    else:
        storage = LocalMediaStorage()
    return storage.open(path, mode=mode)


def url_media(path, private=True):
    if getattr(settings, "USE_S3_MEDIA", False):
        storage = PrivateMediaStorage() if private else PublicMediaStorage()
    else:
        storage = LocalMediaStorage()
    return storage.url(path)


def delete_media(path, private=True):
    if getattr(settings, "USE_S3_MEDIA", False):
        storage = PrivateMediaStorage() if private else PublicMediaStorage()
    else:
        storage = LocalMediaStorage()
    storage.delete(path)
