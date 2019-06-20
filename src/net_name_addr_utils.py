#!/usr/bin/env python

# check that hostname fqdn maps to a public IP and reverse dns matches

import sys
import socket
import struct
import fnmatch
import collections

from socket import AF_INET, AF_INET6, inet_ntop, NI_NAMEREQD
from ctypes import (
    Structure, Union, POINTER,
    pointer, get_errno, cast,
    c_ushort, c_byte, c_void_p, c_char_p, c_uint, c_int, c_uint16, c_uint32
)
import ctypes.util
import ctypes

from functools import reduce

def ipv4_to_num(ipv4_str):
    """Compute int value of IPv4 address; partial IPs are zero-extended"""
    quads = (list(map(int, ipv4_str.split('.'))) + [0]*4)[:4]
    return reduce((lambda a,b: a<<8 | b), quads)

def netmask_num_from_size(size):
    return 0xFFFFFFFF & ~(0xFFFFFFFF >> int(size))

def addr_in_netrange(addr, netrange):
    subnet, size = netrange.split('/')
    subnet_num = ipv4_to_num(subnet)
    netmask_num = netmask_num_from_size(size)
    addr_num = ipv4_to_num(addr)

    return (addr_num & netmask_num) == subnet_num

def addr_is_public(addr):
    NONPUB = ["192.168/16", "172.16/12", "10/8", "127/8"]
    return not any( addr_in_netrange(addr, netrange) for netrange in NONPUB )

HostNetInfo = collections.namedtuple('HostNetInfo',
    ('fqdn', 'addr', 'addr_is_public',
     'addr_is_ours', 'fqdn_reverse', 'iface_addrs')
)

def hostnetinfo_good(info, bypass_dns_check=False):
    # If the arg --bypass_dns_check is set to True we will not care about
    # the outcome of info.addr_is_ours
    return info.addr_is_public and (info.addr_is_ours or bypass_dns_check) and info.fqdn == info.fqdn_reverse

def get_host_network_info():
    port = 25
    hostname = socket.gethostname().lower()
    fqdn = socket.getfqdn(hostname)
    addr = socket.getaddrinfo(fqdn, port, AF_INET)[0][4][0]
    public = addr_is_public(addr)

    iface_addrs_map = get_iface_ipv4_addrs()
    iface_addrs = setunion(iface_addrs_map.values())
    ours = addr in iface_addrs

    try:
        host_reverse = socket.getnameinfo((addr, port), NI_NAMEREQD)[0].lower()
        fqdn_reverse = socket.getfqdn(host_reverse).lower()
    except socket.gaierror:
        fqdn_reverse = "<UNKNOWN>"

    return HostNetInfo(fqdn, addr, public, ours, fqdn_reverse, iface_addrs)

def setunion(sets):
    return reduce((lambda a,b: a|b), sets)

def get_iface_ipv4_addrs():
    net_ifaces = get_network_interfaces('*')
    return dict( (x.name, x.addresses[AF_INET]) for x in net_ifaces
                                                 if AF_INET in x.addresses )

def print_net_info(info):
    print("FQDN: %s" % info.fqdn)
    print("IPv4: %s" % info.addr)
    print("IPv4 is public? %s" % info.addr_is_public)
    print("IPv4 is ours? %s"   % info.addr_is_ours)
    if info.addr_is_ours == False:
        print("The IP address to wich the hostname resolves is not and assigned")
        print("to any of the interfaces listed in this host. To skip this")
        print("check pass the argument --bypass-dns-check to this script")
    matchstr = "match" if info.fqdn == info.fqdn_reverse else "mismatch"
    print("Reverse FQDN: %s (%s)" % (info.fqdn_reverse, matchstr))

def main():
    info = get_host_network_info()
    print_net_info(info)
    return hostnetinfo_good(info)


# ***** #

# The following, used for get_network_interfaces(), was lifted from:
# https://github.com/opensciencegrid/htcondor-ce/blob/v3.1.3/src/condor_ce_host_network_check

# Based on http://programmaticallyspeaking.com/getting-network-interfaces-in-python.html
# which is, in turn, based on Based on getifaddrs.py from pydlnadms [http://code.google.com/p/pydlnadms/].

class struct_sockaddr(Structure):
    """struct sockaddr from sys/socket.h
    See socket.h in manpage section 0p

    A generic "socket" structure; can be cast into one of the other
    struct sockaddr_* types

    Fields:
    - sa_family: identifies the type of socket (e.g. AF_INET for IPv4, AF_INET6
                 for IPv6)
    - sa_data:   actual socket data - length and contents are format dependent

    """
    _fields_ = [
        ('sa_family', c_ushort),
        ('sa_data', c_byte * 14),]


class struct_sockaddr_in(Structure):
    """struct sockaddr_in from netinet/in.h
    See in.h in manpage section 0p

    Fields:
    - sin_family: always AF_INET
    - sin_port:   port number
    - sin_addr:   IP address

    """
    _fields_ = [
        ('sin_family', c_ushort),
        ('sin_port', c_uint16),
        ('sin_addr', c_byte * 4)]


class struct_sockaddr_in6(Structure):
    """struct sockaddr_in6 from netinet/in.h
    See in.h in manpage section 0p

    Fields:
    - sin6_family:   always AF_INET6
    - sin6_port:     port number
    - sin6_flowinfo: IPv6 traffic class and flow information
    - sin6_addr:     IPv6 address
    - sin6_scope_id: set of interfaces for a scope

    """
    _fields_ = [
        ('sin6_family', c_ushort),
        ('sin6_port', c_uint16),
        ('sin6_flowinfo', c_uint32),
        ('sin6_addr', c_byte * 16),
        ('sin6_scope_id', c_uint32)]


class union_ifa_ifu(Union):
    """Anonymous union used for field ifa_ifu in struct ifaddrs from ifaddrs.h
    See getifaddrs in manpage section 3

    """
    _fields_ = [
        ('ifu_broadaddr', POINTER(struct_sockaddr)),
        ('ifu_dstaddr', POINTER(struct_sockaddr)),]


class struct_ifaddrs(Structure):
    """struct ifaddrs from ifaddrs.h
    See getifaddrs in manpage section 3

    A linked list; each element describes one network interface.  The ifa_next
    field is a pointer to the next entry in the list.

    """
# _fields_ set separately: struct_ifaddrs needs to exist so it can contain a pointer to another struct_ifaddrs
struct_ifaddrs._fields_ = [
    ('ifa_next', POINTER(struct_ifaddrs)),
    ('ifa_name', c_char_p),
    ('ifa_flags', c_uint),
    ('ifa_addr', POINTER(struct_sockaddr)),
    ('ifa_netmask', POINTER(struct_sockaddr)),
    ('ifa_ifu', union_ifa_ifu),
    ('ifa_data', c_void_p),]


libc = ctypes.CDLL(ctypes.util.find_library('c'))


def ifap_iter(ifap):
    """Iterate over a pointer to a struct ifaddrs and yield the contents of the
    structure.

    Params:
    - ifap: pointer(struct_ifaddrs)
    Yields:
    - struct_ifaddrs

    """
    ifa = ifap.contents
    while True:
        yield ifa
        if not ifa.ifa_next:
            break
        ifa = ifa.ifa_next.contents


def getfamaddr(sa):
    """Extract the address family and address from a struct_sockaddr.

    Params:
    - sa: struct_sockaddr
    Returns: (family, addr)
    - family: AF_INET, AF_INET6 or one of the other AF_* constants from the
              socket module
    - addr:   if family is AF_INET, the IPv4 address as a string
              if family is AF_INET6, the IPv6 address as a string
              otherwise, None

    """
    family = sa.sa_family
    addr = None
    if family == AF_INET:
        sa = cast(pointer(sa), POINTER(struct_sockaddr_in)).contents
        addr = inet_ntop(family, sa.sin_addr)
    elif family == AF_INET6:
        sa = cast(pointer(sa), POINTER(struct_sockaddr_in6)).contents
        addr = inet_ntop(family, sa.sin6_addr)
    return family, addr


class NetworkInterface(object):
    """The name, index, and IP addresses associated with a network interface.
    - index is taken from if_nametoindex(3).
    - addresses is a dict of addresses keyed by family (e.g. the AF_INET,
      AF_INET6 constants from the socket library)

    """
    def __init__(self, name):
        self.name = name
        self.index = libc.if_nametoindex(name)
        self.addresses = {}

    def __str__(self):
        return "%s [index=%d, IPv4=%s, IPv6=%s]" % (
            self.name, self.index,
            ",".join(self.addresses.get(AF_INET)),
            ",".join(self.addresses.get(AF_INET6)))


def get_network_interfaces(pattern):
    """Return NetworkInterface objects for each network interface present on
    the machine that matches the glob in `pattern`.

    Params:
    - pattern: string containing a glob of network interfaces to match; can
               match on both interface name (e.g. eth0) or IPv4/v6 address
    Returns: list of NetworkInterface objects
    Raises: OSError if getifaddrs(3) fails

    """
    ifap = POINTER(struct_ifaddrs)()
    # getifaddrs takes a *(struct ifaddrs) as the argument to put the interfaces
    # into; the return code is just a status.
    result = libc.getifaddrs(pointer(ifap))
    if result != 0:
        raise OSError(get_errno())
    del result

    try:
        # retval is a dict of NetworkInterfaces keyed by interface name
        # Each NetworkInterface has an 'addresses' field that is a dict of
        # addresses (as strings), keyed by address family.
        retval = {}

        for ifa in ifap_iter(ifap):
            name = ifa.ifa_name
            i = retval.get(name)
            if not i:
                i = retval[name] = NetworkInterface(name)
            family, addr = getfamaddr(ifa.ifa_addr.contents)
            if addr:
                address_list = i.addresses.setdefault(family, set())
                address_list.add(addr)

        # Filter the NetworkInterfaces by pattern; return them as a list.
        filtered_values = []
        for iface in retval.values():
            if iface_matches(iface, pattern):
                filtered_values.append(iface)
        return filtered_values
    finally:
        libc.freeifaddrs(ifap)


def iface_matches(network_iface, pattern):
    """Return if a network interface's name or associated addresses match
    the glob in `pattern`.

    Params:
    - network_iface: NetworkInterface object
    - pattern:       string containing a glob to match names or IP addresses
                     against
    Returns: True if the name or at least one of the IP addresses in
    `network_iface` matches `pattern`, False otherwise

    """
    if fnmatch.fnmatch(network_iface.name, pattern):
        return True
    for family, addrs in network_iface.addresses.items():
        if fnmatch.filter(addrs, pattern):
            return True
    return False


# ***** #


if __name__ == '__main__':
    sys.exit(not main())

