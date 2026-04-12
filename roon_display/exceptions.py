"""Application-level exceptions."""


class RenderCancelledError(Exception):
    """Raised when a render is cancelled via cancel()."""

    pass
