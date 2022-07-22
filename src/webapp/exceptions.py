class DataError(Exception):
    """Base exception for some problem with the Topology data itself."""


class NotRegistered(DataError):
    """Base exception for something not being registered."""
