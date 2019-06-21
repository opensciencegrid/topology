#!/usr/bin/env python

from __future__ import print_function

import collections
import glob
import yaml
import sys
import os
import re

try:
    from urllib.request import urlopen
except ImportError:
    from urllib2 import urlopen

try:
    from yaml import CSafeLoader as SafeLoader
except ImportError:
    from yaml import SafeLoader

import xml.etree.ElementTree as et

_topdir = os.path.abspath(os.path.dirname(__file__) + "/../..")

# autodict is a defaultdict returning a new autodict for missing keys.
# __add__ allows `d[k] += v` to work automatically before `d` contains `k`.
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
    return sum(d.values()) if d else 0

def get_vo_names():
    return set( re.search(r'/([^/]+)\.yaml$', path).group(1) for path in
                glob.glob(_topdir + "/virtual-organizations/*.yaml") )

def load_yamlfile(fn):
    with open(fn) as f:
        try:
            yml = yaml.load(f, Loader=SafeLoader)
            if yml is None:
                print("YAML file is empty or invalid: %s", fn)
            return yml
        except yaml.error.YAMLError as e:
            print("Failed to parse YAML file: %s\n%s" % (fn, e))

def filter_out_None_rgs(rgs, rgfns):
    return zip(*( (rg,rgfn) for rg,rgfn in zip(rgs, rgfns) if rg is not None ))

def user_id_name(u):
    return u.find('ID').text, u.find('FullName').text

def get_contacts():
    txt = urlopen(_contacts_url).read()
    xmltree = et.fromstring(txt)
    users = xmltree.findall('User')
    return dict(map(user_id_name, users))

def main():
    os.chdir(_topdir + "/topology")

    contacts = get_contacts()
    yamls = sorted(glob.glob("*/*/*.yaml"))
    rgfns = list(filter(rgfilter, yamls))
    rgs = list(map(load_yamlfile, rgfns))
    #facility_site_rg = [ fn[:-len(".yaml")].split('/') for fn in rgfns ]
    errors = 0
    warnings = 0
    if any( rg is None for rg in rgs ):
        errors += sum( rg is None for rg in rgs )
        rgs, rgfns = filter_out_None_rgs(rgs, rgfns)

    errors += test_1_rg_unique(rgs, rgfns)
    errors += test_2_res_unique(rgs, rgfns)
    errors += test_3_voownership(rgs, rgfns)
    errors += test_4_res_svcs(rgs, rgfns)
    errors += test_5_sc(rgs, rgfns)
    errors += test_6_site()
    # re-enable fqdn errors after SOFTWARE-3330
    # warnings += test_7_fqdn_unique(rgs, rgfns)
    errors += test_8_res_ids(rgs, rgfns)
    errors += test_9_res_contact_lists(rgs, rgfns)
    warnings += test_10_res_admin_contact(rgs, rgfns)
    warnings += test_11_res_sec_contact(rgs, rgfns)
    errors += test_12_res_contact_id_fmt(rgs, rgfns)
    errors += test_13_res_contacts_exist(rgs, rgfns, contacts)
    errors += test_14_res_contacts_match(rgs, rgfns, contacts)
    errors += test_15_facility_site_files()


    print("%d Resource Group files processed." % len(rgs))
    if errors:
        print("%d error(s) encountered." % errors)
        return 1
    elif warnings:
        print("%d warning(s) encountered." % warnings)
        return 0
    else:
        print("A-OK.")
        return 0

_contacts_url = 'https://topology.opensciencegrid.org/miscuser/xml'

_gh_baseurl   = 'https://github.com/opensciencegrid/topology/tree/master/'
_services_url = _gh_baseurl + 'topology/services.yaml'
_sups_url     = _gh_baseurl + 'topology/support-centers.yaml'
_vos_url      = _gh_baseurl + 'virtual-organizations'

_emsgs = {
    'RGUnique'      : "Resource Group names must be unique across all Sites",
    'ResUnique'     : "Resource names must be unique across the OSG topology",
    'ResID'         : "Resources must contain a numeric ID",
    'ResGrpID'      : "Resource Groups must contain a numeric ID",
    'SiteUnique'    : "Site names must be unique across Facilities",
    'FQDNUnique'    : "FQDNs must be unique across the OSG topology",
    'VOOwnership100': "Total VOOwnership must not exceed 100%",
    'NoServices'    : "Valid Services are listed here: %s" % _services_url,
    'NoSupCenter'   : "Valid Support Centers are listed here: %s" % _sups_url,
    'UnknownVO'     : "Valid VOs are listed here: %s" % _vos_url,

    'NoResourceContactLists' : "Resources must contain a ContactLists section",
    'NoAdminContact'         : "Resources must have an Administrative Contact",
    'NoSecContact'           : "Resources must have a Security Contact",
    'MalformedContactID'     : "Contact IDs must be exactly 40 hex digits",
    'UnknownContactID'       : "Contact IDs must exist in contact repo",
    'ContactNameMismatch'    : "Contact names must match in contact repo",
    'NoFacility'             : "Facility directories must contain a FACILITY.yaml",
    'NoSite'                 : "Site directories must contain a SITE.yaml"
}

def print_emsg_once(msgtype):
    if msgtype in _emsgs:
        print("*** %s" % _emsgs[msgtype])
        del _emsgs[msgtype]

def test_1_rg_unique(rgs, rgfns):
    # 1. Name (file name) of RG must be unique across all sites

    errors = 0
    rgmap = autodict()

    for rgfile in rgfns:
        rgmap[rgname(rgfile)] += [rgfile]

    for name, rgflist in sorted(rgmap.items()):
        if len(rgflist) > 1:
            print_emsg_once('RGUnique')
            print("Resource Group '%s' mentioned for multiple Sites:" % name)
            for rgfile in rgflist:
                print(" - %s" % rgfile)
            errors += 1

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
            print_emsg_once('ResUnique')
            print("Resource '%s' mentioned for multiple groups:" % r)
            for rgfile in rgflist:
                print(" - %s" % rgfile)
            errors += 1

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
                print_emsg_once('VOOwnership100')
                print("In '%s', Resource '%s' has total VOOwnership = %d%%" %
                      (rgfn, rname, total_vo_ownership))
                errors += 1
            if total_vo_ownership:
                for vo in rdict['VOOwnership']:
                    if vo not in vo_names:
                        print_emsg_once('UnknownVO')
                        print("In '%s', Resource '%s' has unknown VO '%s'" %
                              (rgfn, rname, vo))
                        errors += 1
    return errors


def test_4_res_svcs(rgs, rgfns):
    # 4. Each Resource must have at least one Service

    errors = 0
    services = load_yamlfile("services.yaml")
    if services is None:
        return 1

    for rg,rgfn in zip(rgs,rgfns):
        for rname,rdict in sorted(rg['Resources'].items()):
            rsvcs = rdict.get('Services')
            if not rsvcs:
                print_emsg_once('NoServices')
                print("In '%s', Resource '%s' has no Services" % (rgfn, rname))
                errors += 1
            else:
                for svc in sorted(set(rsvcs) - set(services)):
                    print_emsg_once('NoServices')
                    print("In '%s', Resource '%s' has unknown Service '%s'" %
                          (rgfn, rname, svc))
                    errors += 1
    return errors


def test_5_sc(rgs, rgfns):
    # 5. SupportCenter must refer to an existing SC

    errors = 0
    support_centers = load_yamlfile("support-centers.yaml")
    if support_centers is None:
        return 1

    for rg,rgfn in zip(rgs,rgfns):
        sc = rg.get('SupportCenter')
        if not sc:
            print_emsg_once('NoSupCenter')
            print("Resource Group '%s' has no SupportCenter" % rgfn)
            errors += 1
        elif sc not in support_centers:
            print_emsg_once('NoSupCenter')
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
            print_emsg_once('SiteUnique')
            print("Site '%s' mentioned for multiple Facilities:" % site)
            for fac in faclist:
                print(" - %s" % fac)
            errors += 1

    return errors

def test_7_fqdn_unique(rgs, rgfns):
    # fqdns should be unique across all resources in all sites
    # Just warning for now until we are able to enforce it (SOFTWARE-3374)

    errors = 0
    n2rg = autodict()

    for rg,rgfn in zip(rgs,rgfns):
        for rname,rdict in rg['Resources'].items():
            fqdn = rdict['FQDN']
            n2rg[fqdn] += [(rgfn,rname)]

    for fqdn, rgflist in sorted(n2rg.items()):
        if len(rgflist) > 1:
            print_emsg_once('FQDNUnique')
            print("FQDN '%s' mentioned for multiple resources:" % fqdn)
            for rgfile,rname in rgflist:
                print(" - %s (%s)" % (rname,rgfile))
            errors += 1

    return errors

def test_8_res_ids(rgs, rgfns):
    # Check that resources/resource groups have a numeric ID/GroupID

    errors = 0

    for rg,rgfn in zip(rgs,rgfns):
        if not isinstance(rg.get('GroupID'), int):
            print_emsg_once('ResGrpID')
            print("Resource Group missing numeric GroupID: '%s'" % rgfn)
            errors += 1

        for resname,res in sorted(rg['Resources'].items()):
            if not isinstance(res.get('ID'), int):
                print_emsg_once('ResID')
                print("Resource '%s' missing numeric ID in '%s'"
                      % (resname, rgfn))
                errors += 1

    return errors

def flatten_res_contacts(rcls):
    for ctype,ctype_d in sorted(rcls.items()):
        for clevel,clevel_d in sorted(ctype_d.items()):
            yield ctype, clevel, clevel_d.get("ID"), clevel_d.get("Name")


def test_9_res_contact_lists(rgs, rgfns):
    # verify resources have contact lists

    errors = 0

    for rg,rgfn in zip(rgs,rgfns):
        for rname,rdict in sorted(rg['Resources'].items()):
            rcls = rdict.get('ContactLists')
            if not rcls:
                print_emsg_once('NoResourceContactLists')
                print("In '%s', Resource '%s' has no ContactLists"
                      % (rgfn, rname))
                errors += 1

    return errors


def test_10_res_admin_contact(rgs, rgfns):
    # verify resources have admin contact

    errors = 0

    for rg,rgfn in zip(rgs,rgfns):
        for rname,rdict in sorted(rg['Resources'].items()):
            rcls = rdict.get('ContactLists')
            if rcls:
                ctype, etype = 'Administrative', 'NoAdminContact'
                if not rcls.get('%s Contact' % ctype):
                    print_emsg_once(etype)
                    print("In '%s', Resource '%s' has no %s Contact"
                          % (rgfn, rname, ctype))
                    errors += 1

    return errors


def test_11_res_sec_contact(rgs, rgfns):
    # verify resources have security contact

    errors = 0

    for rg,rgfn in zip(rgs,rgfns):
        for rname,rdict in sorted(rg['Resources'].items()):
            rcls = rdict.get('ContactLists')
            if rcls:
                ctype, etype = 'Security', 'NoSecContact'
                if not rcls.get('%s Contact' % ctype):
                    print_emsg_once(etype)
                    print("In '%s', Resource '%s' has no %s Contact"
                          % (rgfn, rname, ctype))
                    errors += 1

    return errors


def test_12_res_contact_id_fmt(rgs, rgfns):
    # verify resource contact IDs are well-formed

    errors = 0

    for rg,rgfn in zip(rgs,rgfns):
        for rname,rdict in sorted(rg['Resources'].items()):
            rcls = rdict.get('ContactLists')
            if rcls:
                for ctype, clevel, ID, name in flatten_res_contacts(rcls):
                    if not re.search(r'^[0-9a-f]{40}$', ID):
                        print_emsg_once('MalformedContactID')
                        print("In '%s', Resource '%s' has malformed %s %s '%s'"
                              " (%s)" % (rgfn, rname, clevel, ctype, ID, name))
                        errors += 1
    return errors


def test_13_res_contacts_exist(rgs, rgfns, contacts):
    # verify resource contacts exist in contact repo

    errors = 0

    for rg,rgfn in zip(rgs,rgfns):
        for rname,rdict in sorted(rg['Resources'].items()):
            rcls = rdict.get('ContactLists')
            if rcls:
                for ctype, clevel, ID, name in flatten_res_contacts(rcls):
                    if re.search(r'^[0-9a-f]{40}$', ID) and ID not in contacts:
                        print_emsg_once('UnknownContactID')
                        print("In '%s', Resource '%s' has unknown %s %s '%s'"
                              " (%s)" % (rgfn, rname, clevel, ctype, ID, name))
                        errors += 1

    return errors


def test_14_res_contacts_match(rgs, rgfns, contacts):
    # verify resource contacts match contact repo

    errors = 0

    for rg,rgfn in zip(rgs,rgfns):
        for rname,rdict in sorted(rg['Resources'].items()):
            rcls = rdict.get('ContactLists')
            if rcls:
                for ctype, clevel, ID, name in flatten_res_contacts(rcls):
                    if (re.search(r'^[0-9a-f]{40}$', ID)
                        and ID in contacts and name != contacts[ID]):
                        print_emsg_once('ContactNameMismatch')
                        print("In '%s', Resource '%s' %s %s '%s' (%s) does not"
                              " match name in contact repo (%s)" % (rgfn,
                              rname, clevel, ctype, ID, name, contacts[ID]))
                        errors += 1

    return errors

def test_15_facility_site_files():
    # verify the required FACILITY.yaml and SITE.yaml files
    errors = 0

    for facdir in glob.glob("*/"):
        if not os.path.exists(facdir + "FACILITY.yaml"):
            print_emsg_once('NoFacility')
            print(facdir[:-1] + " does not have required FACILITY.yaml file")
            errors += 1

    for sitedir in glob.glob("*/*/"):
        if not os.path.exists(sitedir + "SITE.yaml"):
            print_emsg_once('NoSite')
            print(sitedir[:-1] + " does not have required SITE.yaml file")
            errors += 1

    return errors

if __name__ == '__main__':
    sys.exit(main())

