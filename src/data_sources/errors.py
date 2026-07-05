"""V1.4.1 unified provider error types."""


class ProviderError(Exception):
    """Base class for all provider exceptions."""


class ProviderUnavailableError(ProviderError):
    """Provider is unreachable (network, not installed, not running)."""


class ProviderTimeoutError(ProviderError):
    """Provider request timed out."""


class ProviderAuthError(ProviderError):
    """Authentication / token / permission denied."""


class ProviderRateLimitError(ProviderError):
    """Rate limit exceeded."""


class ProviderDataEmptyError(ProviderError):
    """Provider returned no data (empty result, not an error per se)."""


class ProviderDataFormatError(ProviderError):
    """Provider returned unexpected data format / missing fields."""
