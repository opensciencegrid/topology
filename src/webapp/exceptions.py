class DataError(Exception):
    """Base exception for some problem with the Topology data itself."""


class NotRegistered(DataError):
    """Base exception for something not being registered."""


class VODataError(DataError):
    def __init__(self, vo_name, text):
        DataError.__init__(self, f"VO {vo_name}: {text}")
        self.vo_name = vo_name
