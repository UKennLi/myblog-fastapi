class BindingError(Exception):
    """Spring MVC-style form/parameter binding failure (HTTP 400)."""


class CompatibilityError(Exception):
    """A confirmed original application failure retained for compatibility."""
