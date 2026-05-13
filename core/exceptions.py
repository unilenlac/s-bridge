"""
Custom exceptions for s-bridge remote service calls.
Each exception clearly labels the failing service so that error messages
persisted in Job.error_message are immediately actionable by the end client.
"""


class DtsError(RuntimeError):
    """Raised when a DTS API call fails (collection fetch, navigation, document retrieval)."""


class CollatexError(RuntimeError):
    """Raised when the CollateX collation service returns an error or is unreachable."""


class StemmarestError(RuntimeError):
    """Raised when the Stemmarest service returns an error or is unreachable."""
