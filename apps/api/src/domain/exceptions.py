"""Domain exceptions."""


class RunNotFoundError(Exception):
    """Raised when a run cannot be found by id or label."""


class MissingConfigError(Exception):
    """Raised when required configuration is missing."""


class SyncError(Exception):
    """Raised for sync/export operational errors."""
