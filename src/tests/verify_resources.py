#!/usr/bin/env python

from __future__ import print_function

import collections
import glob
import yaml
import sys
import os
import re

_topdir = os.path.abspath(os.path.dirname(__file__) + "/../..")

class autodict(collections.defaultdict):
    def __init__(self,*other):
        collections.defaultdict.__init__(self, self.__class__, *other)
    def __add__ (self, other):
        return other
    def __repr__(self):
        return '%s(%s)' % (self.__class__.__name__, dict.__repr__(self))

def rgfilter(fn):
    return not (fn.endswith("_downtime.yaml") or fn.endswith("/SITE.yaml"))

def rgname(fn):
    return re.search(r'/([^/]+)\.yaml$', fn).group(1)

def sumvals(d):
    return sum(list(zip(*d.items()))[1]) if d else 0

def get_vo_names():
    return set( re.search(r'/([^/]+)\.yaml$', path).group(1) for path in
                glob.glob(_topdir + "/virtual-organizations/*.yaml") )

def main():
    global services
    os.chdir(_topdir + "/topology")

    yamls = sorted(glob.glob("*/*/*.yaml"))
    rgfns = list(filter(rgfilter, yamls))
    rgs = [ yaml.safe_load(open(fn)) for fn in rgfns ]
    #facility_site_rg = [ fn[:-len(".yaml")].split('/') for fn in rgfns ]

    errors  = test_1_rg_unique(rgs, rgfns)
    errors += test_2_res_unique(rgs, rgfns)
    errors += test_3_voownership(rgs, rgfns)
    errors += test_4_res_svcs(rgs, rgfns)
    errors += test_5_sc(rgs, rgfns)
    errors += test_6_site()

    print("%d Resource Group files processed." % len(rgs))
    if errors:
        print("%d error(s) encountered." % errors)
        return 1
    else:
        print("A-OK.")
        return 0


def test_1_rg_unique(rgs, rgfns):
    # 1. Name (file name) of RG must be unique across all sites

    errors = 0
    rgmap = autodict()

    for rgfile in rgfns:
        rgmap[rgname(rgfile)] += [rgfile]

    for name, rgflist in sorted(rgmap.items()):
        if len(rgflist) > 1:
            print("Resource Group '%s' mentioned for multiple Sites:" % name)
            for rgfile in rgflist:
                print(" - %s" % rgfile)
            errors += len(rgflist) - 1

    return errors


def test_2_res_unique(rgs, rgfns):
    # 2. Name of each resource must be present and
    #    unique across all resources in all sites

    errors = 0
    r2rg = autodict()

    for rg,rgfn in zip(rgs,rgfns):
        for r in rg['Resources']:
            r2rg[r] += [rgfn]

    for r, rgflist in sorted(r2rg.items()):
        if len(rgflist) > 1:
            print("Resource '%s' mentioned for multiple groups:" % r)
            for rgfile in rgflist:
                print(" - %s" % rgfile)
            errors += len(rgflist) - 1

    return errors


def test_3_voownership(rgs, rgfns):
    # 3. VOOwnership of each resource must:
    #    - add up to no greater than 100 (can be less)
    #    - refer to existing VOs or "(Other)"

    errors = 0
    vo_names = get_vo_names()

    for rg,rgfn in zip(rgs,rgfns):
        for rname,rdict in sorted(rg['Resources'].items()):
            total_vo_ownership = sumvals(rdict.get('VOOwnership'))
            if not 0 <= total_vo_ownership <= 100:
                print("In '%s', Resource '%s' has total VOOwnership = %d%%" %
                      (rgfn, rname, total_vo_ownership))
                errors += 1
            if total_vo_ownership:
                for vo in rdict['VOOwnership']:
                    if vo not in vo_names:
                        print("In '%s', Resource '%s' has unknown VO '%s'" %
                              (rgfn, rname, vo))
                        errors += 1
    return errors


def test_4_res_svcs(rgs, rgfns):
    # 4. Each Resource must have at least one Service

    errors = 0
    services = yaml.safe_load(open("services.yaml"))

    for rg,rgfn in zip(rgs,rgfns):
        for rname,rdict in sorted(rg['Resources'].items()):
            rsvcs = rdict.get('Services')
            if not rsvcs:
                print("In '%s', Resource '%s' has no Services" % (rgfn, rname))
                errors += 1
            else:
                for svc in sorted(set(rsvcs) - set(services)):
                    print("In '%s', Resource '%s' has unknown Service '%s'" %
                          (rgfn, rname, svc))
                    errors += 1
    return errors


def test_5_sc(rgs, rgfns):
    # 5. SupportCenter must refer to an existing SC

    errors = 0
    support_centers = yaml.safe_load(open("support-centers.yaml"))

    for rg,rgfn in zip(rgs,rgfns):
        sc = rg.get('SupportCenter')
        if not sc:
            print("Resource Group '%s' has no SupportCenter" % rgfn)
            errors += 1
        elif sc not in support_centers:
            print("Resource Group '%s' has unknown SupportCenter '%s'" %
                  (rgfn, sc))
            errors += 1

    return errors


def test_6_site():
    # 6. Site name (directory name) must be unique across all facilities

    errors = 0
    smap = autodict()
    fac_sites = sorted( fs.split('/')[:2] for fs in glob.glob("*/*/"))

    for fac, site in fac_sites:
        smap[site] += [fac]

    for site, faclist in sorted(smap.items()):
        if len(faclist) > 1:
            print("Site '%s' mentioned for multiple Facilities:" % site)
            for fac in faclist:
                print(" - %s" % fac)
            errors += len(faclist) - 1

    return errors

if __name__ == '__main__':
    sys.exit(main())

