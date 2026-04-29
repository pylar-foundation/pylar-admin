"""Admin module exception hierarchy."""


class AdminError(Exception):
    """Base exception for all admin-related errors."""


class ModelNotRegisteredError(AdminError):
    """Raised when accessing a model that has not been registered with the admin."""

    def __init__(self, slug: str) -> None:
        super().__init__(f"No model registered with slug {slug!r}")
        self.slug = slug


class AdminConfigError(AdminError):
    """Raised when a ModelAdmin configuration is invalid."""
