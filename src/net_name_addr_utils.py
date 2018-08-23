#!/usr/bin/env python

# check that hostname fqdn maps to a public IP and reverse dns matches

import sys
import socket

from socket import AF_INET, NI_NAMEREQD
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
    NONPUB = "192.168/16 172.16/12 10/8 127/8".split()
    return not any( addr_in_netrange(addr, netrange) for netrange in NONPUB )

def get_fqdn_ip_public_reverse():
    port = 25
    hostname = socket.gethostname().lower()
    fqdn = socket.getfqdn(hostname)
    addr = socket.getaddrinfo(fqdn, port, AF_INET)[0][4][0]
    public = addr_is_public(addr)
    try:
        host_reverse = socket.getnameinfo((addr, port), NI_NAMEREQD)[0].lower()
        fqdn_reverse = socket.getfqdn(host_reverse).lower()
    except socket.gaierror:
        fqdn_reverse = "<UNKNOWN>"

    return fqdn, addr, public, fqdn_reverse

def main():
    fqdn, addr, public, fqdn_reverse = get_fqdn_ip_public_reverse()
    print("FQDN: %s" % fqdn)
    print("IPv4: %s" % addr)
    print("IPv4 is public? %s" % public)
    matchstr = "match" if fqdn == fqdn_reverse else "mismatch"
    print("Reverse FQDN: %s (%s)" % (fqdn_reverse, matchstr))

    return public and fqdn == fqdn_reverse

if __name__ == '__main__':
    sys.exit(not main())

