from django.conf import settings

from andina.storage_backends import LocalMediaStorage, PrivateMediaStorage, PublicMediaStorage


def _build_storage(public=False):
    if getattr(settings, "USE_S3_MEDIA", False):
        return PublicMediaStorage() if public else PrivateMediaStorage()
    return LocalMediaStorage()


PUBLIC_MEDIA_STORAGE = _build_storage(public=True)
PRIVATE_MEDIA_STORAGE = _build_storage(public=False)
