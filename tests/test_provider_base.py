"""Test provider base interface and error types."""
import pytest
from src.data_sources.base import MarketDataProvider
from src.data_sources.errors import (
    ProviderAuthError, ProviderDataEmptyError, ProviderDataFormatError,
    ProviderError, ProviderRateLimitError, ProviderTimeoutError,
    ProviderUnavailableError,
)


class TestErrors:
    def test_hierarchy(self) -> None:
        assert issubclass(ProviderUnavailableError, ProviderError)
        assert issubclass(ProviderTimeoutError, ProviderError)
        assert issubclass(ProviderAuthError, ProviderError)
        assert issubclass(ProviderRateLimitError, ProviderError)
        assert issubclass(ProviderDataEmptyError, ProviderError)
        assert issubclass(ProviderDataFormatError, ProviderError)

    def test_can_raise(self) -> None:
        with pytest.raises(ProviderError):
            raise ProviderUnavailableError("test")


class TestBaseInterface:
    def test_abstract_class_exists(self) -> None:
        assert MarketDataProvider.__abstractmethods__ is not None

    def test_cannot_instantiate(self) -> None:
        with pytest.raises(TypeError):
            MarketDataProvider()  # type: ignore[abstract]
