from whitenoise.storage import CompressedManifestStaticFilesStorage


class NonStrictCompressedManifestStaticFilesStorage(CompressedManifestStaticFilesStorage):
    """
    Avoid raising ValueError when a static path is missing from manifest.
    It falls back to the original path instead of breaking the request.
    """

    manifest_strict = False
