"""Domain exceptions for db-sync."""


class RunNotFoundError(Exception):
    """Raised when a run cannot be found by id or label."""

    pass


class MissingConfigError(Exception):
    """Raised when required configuration (e.g. Supabase credentials) is missing."""

    pass


class SyncError(Exception):
    """Raised for sync/export operational errors (missing files, no clips, etc.)."""

    pass
