import unittest

STUB_MARKER = "omitted in this public repository"


def requires_implementation(func):
    """Skip a test class when `func` is a stub in the public repository.

    The production size parser is not published; these tests run automatically
    once a real implementation is present.
    """
    is_stub = STUB_MARKER in (func.__doc__ or "")
    return unittest.skipIf(is_stub, f"{func.__name__} is omitted from the public repository")
