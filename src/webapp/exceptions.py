from .topology import Resource


class DataError(Exception):
    """Base exception for some problem with the Topology data itself."""


class NotRegistered(DataError):
    """Base exception for something not being registered."""


class ResourceNotRegistered(NotRegistered):
    def __init__(self, name=None, fqdn=None):
        self.name = name
        self.fqdn = fqdn
        if name:
            text = f"Resource with name {name} not registered"
        elif fqdn:
            text = f"Resource with FQDN {fqdn} not registered"
        else:
            text = "Resource not registered"  # caller really should have specified one though
        super().__init__(text)


class ResourceDataError(DataError):
    def __init__(self, resource: Resource, text: str):
        self.resource = resource
        super().__init__(f"Resource {resource.name}, FQDN {resource.fqdn}: {text}")


class ResourceMissingService(ResourceDataError):
    def __init__(self, resource: Resource, service_name: str):
        self.service_name = service_name
        super().__init__(resource=resource, text=f"Missing expected service {service_name}")


class VODataError(DataError):
    def __init__(self, vo_name, text):
        DataError.__init__(self, f"VO {vo_name}: {text}")
        self.vo_name = vo_name
