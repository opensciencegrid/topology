#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
A script to get the DNs needed to authorize by the given VO
"""

import os
import sys

if __name__ == "__main__" and __package__ is None:
    _parent = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.append(_parent + "/src")

import webapp.models

import argparse

parser = argparse.ArgumentParser(description="Return the DNs of the given VOs' AllowedCache.")
parser.add_argument("VO", help="enter the VO you want to look up", nargs=1)

args = parser.parse_args()

vo = args.VO[0]

global_data = webapp.models.GlobalData()
vo_data = global_data.get_vos_data()

try:
    allowed_caches = vo_data.vos[vo]['DataFederations']['StashCache'].get('AllowedCaches')
except KeyError:
    print("No DNs need to authorize")

xrootd_dn = dict()
resource_groups = global_data.get_topology().get_resource_group_list()
for group in resource_groups:
    for resource in group.resources:
        dn = resource.data.get('DN')
        if 'XRootD cache server' in resource.service_names and dn:
            xrootd_dn[resource.name] = resource.data.get('DN')

for cache in allowed_caches:
    if cache == 'ANY':
        for dn in xrootd_dn.values():
            print(dn)
    else:
        print(xrootd_dn[cache])