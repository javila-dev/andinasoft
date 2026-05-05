class AlegraIntegrationError(Exception):
    """Base error for Alegra integration."""


class AlegraConfigurationError(AlegraIntegrationError):
    """Raised when company credentials or mappings are missing."""


class AlegraBuildError(AlegraIntegrationError):
    """Raised when a local document cannot be transformed into an Alegra payload."""


class AlegraClientError(AlegraIntegrationError):
    """Raised when Alegra returns an error response."""
