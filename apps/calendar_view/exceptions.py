"""Custom exceptions for calendar aggregation."""


class CalendarProviderError(RuntimeError):
    """Raised when a provider fails to produce events."""

    def __init__(self, provider: str, message: str):
        super().__init__(message)
        self.provider = provider


__all__ = ["CalendarProviderError"]
