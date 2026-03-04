from whitenoise.storage import CompressedManifestStaticFilesStorage


class NonStrictCompressedManifestStaticFilesStorage(CompressedManifestStaticFilesStorage):
    """
    Avoid raising ValueError when a static path is missing from manifest.
    It falls back to the original path instead of breaking the request.
    """

    manifest_strict = False

    def url(self, name, force=False):
        """
        If a referenced static file is missing, return its plain static path
        instead of raising ValueError and breaking the request.
        """
        try:
            return super().url(name, force=force)
        except ValueError:
            base = (self.base_url or "/static/").rstrip("/")
            clean_name = str(name).lstrip("/")
            return f"{base}/{clean_name}"
