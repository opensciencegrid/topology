#!/usr/bin/env python3

import collections
import glob
import yaml
import sys
import os
import re

from urllib.request import urlopen

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


# from webapp/common.py
def safe_dict_get(item, *keys, default=None):
    """ traverse dict hierarchy without producing KeyErrors:
        safe_dict_get(item, key1, key2, ..., default=default)
        -> item[key1][key2][...] if defined and not None, else default
    """
    for key in keys:
        if isinstance(item, dict):
            item = item.get(key)
        else:
            return default
    return default if item is None else item


def rgfilter(fn):
    return not (fn.endswith("_downtime.yaml") or fn.endswith("/SITE.yaml"))

def vofilter(fn):
    return not fn.endswith("/REPORTING_GROUPS.yaml")

def rgname(fn):
    return re.search(r'/([^/]+)\.yaml$', fn).group(1)

def sumvals(d):
    return sum(d.values()) if d else 0

def vo_path_to_name(path):
    return re.search(r'([^/]+)\.yaml$', path).group(1)

def get_vo_names():
    return set(map(vo_path_to_name,
               glob.glob(_topdir + "/virtual-organizations/*.yaml")))

def contact_id_ok(ID):
    return re.search(r'^[0-9a-f]{40}$', ID) or re.search(r'^OSG\d+$', ID)

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
    txt = urlopen(_contacts_url).read().decode("utf-8", errors="replace")
    xmltree = et.fromstring(txt)
    users = xmltree.findall('User')
    d = dict(map(user_id_name, users))
    return add_cilogon_ids(users, d)

def add_cilogon_ids(users, d):
    """ add CILogonIDs to dict so they can be treated like ContactIDs """
    for u in users:
        cilogonid = u.find('CILogonID')
        if cilogonid:
            d[cilogonid] = u.find('FullName').text
    return d

def main():
    os.chdir(_topdir)
    vo_yamls = sorted(glob.glob("virtual-organizations/*.yaml"))
    vofns = list(filter(vofilter, vo_yamls))
    vos = list(map(load_yamlfile, vofns))
    vomap = dict(zip(map(vo_path_to_name, vofns), vos))

    os.chdir("topology")
    contacts = get_contacts()
    yamls = sorted(glob.glob("*/*/*.yaml"))
    rgfns = list(filter(rgfilter, yamls))
    rgs = list(map(load_yamlfile, rgfns))
    #facility_site_rg = [ fn[:-len(".yaml")].split('/') for fn in rgfns ]
    support_centers = load_yamlfile("support-centers.yaml")

    errors = 0
    warnings = 0
    if any( rg is None for rg in rgs ):
        errors += sum( rg is None for rg in rgs )
        rgs, rgfns = filter_out_None_rgs(rgs, rgfns)

    errors += test_1_rg_unique(rgs, rgfns)
    errors += test_2_res_unique(rgs, rgfns)
    errors += test_3_voownership(rgs, rgfns)
    errors += test_4_res_svcs(rgs, rgfns)
    errors += test_5_sc(rgs, rgfns, support_centers)
    errors += test_6_site()
    # re-enable fqdn errors after SOFTWARE-3330
    # warnings += test_7_fqdn_unique(rgs, rgfns)
    errors += test_8_res_ids(rgs, rgfns)
    errors += test_9_res_contact_lists(rgs, rgfns)
    warnings += test_10_res_admin_contact(rgs, rgfns)
    warnings += test_11_res_sec_contact(rgs, rgfns)
    errors += test_12_res_contact_id_fmt(rgs, rgfns)
    errors += test_12_vo_contact_id_fmt(vos, vofns)
    # per SOFTWARE-3329, we are not checking support center contacts
#   errors += test_12_sc_contact_id_fmt(support_centers)
    errors += test_13_res_contacts_exist(rgs, rgfns, contacts)
    errors += test_13_vo_contacts_exist(vos, vofns, contacts)
    # per SOFTWARE-3329, we are not checking support center contacts
#   errors += test_13_sc_contacts_exist(support_centers, contacts)
    errors += test_14_res_contacts_match(rgs, rgfns, contacts)
    errors += test_14_vo_contacts_match(vos, vofns, contacts)
    # per SOFTWARE-3329, we are not checking support center contacts
#   errors += test_14_sc_contacts_match(support_centers, contacts)
    errors += test_15_facility_site_files()
    errors += test_16_Xrootd_DNs(rgs, rgfns)
    errors += test_17_osdf_data(rgs, rgfns)
    warnings += test_18_osdf_data_cache_warnings(rgs, rgfns, vomap)
    warnings += test_19_osdf_data_origin_warnings(rgs, rgfns, vomap)
    errors += test_20_fqdn_unique_xrootd(rgs, rgfns)


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
    'ResIDUnique'   : "Resource IDs must be unique across the OSG topology",
    'ResGrpID'      : "Resource Groups must contain a numeric ID",
    'ResGrpIDUnique': "Resource Group IDs must be unique across OSG topology",
    'SiteUnique'    : "Site names must be unique across Facilities",
    'FQDNUnique'    : "FQDNs must be unique across the OSG topology",
    'FQDNUniqueXRootD'
                    : "FQDNs must be unique for XRootD services",
    'VOOwnership100': "Total VOOwnership must not exceed 100%",
    'NoServices'    : "Valid Services are listed here: %s" % _services_url,
    'NoSupCenter'   : "Valid Support Centers are listed here: %s" % _sups_url,
    'UnknownVO'     : "Valid VOs are listed here: %s" % _vos_url,

    'NoResourceContactLists' : "Resources must contain a ContactLists section",
    'NoAdminContact'         : "Resources must have an Administrative Contact",
    'NoSecContact'           : "Resources must have a Security Contact",
    'MalformedContactID'     : "Contact IDs must be exactly 40 hex digits,"
                               " or a CILogonID",
    'UnknownContactID'       : "Contact IDs must exist in contact repo",
    'ContactNameMismatch'    : "Contact names must match in contact repo",
    'NoFacility'             : "Facility directories must contain a FACILITY.yaml",
    'NoSite'                 : "Site directories must contain a SITE.yaml",
    'XrootdWithoutDN'        : "Xrootd cache server must provide a DN",
    'OSDFServiceVOsList'     : "OSDF Services must contain an AllowedVOs list",
    'CacheNotAllowed'        : "VOs in AllowedVOs for a resource with an"
                               " XRootD cache server service should list"
                               " that resource or ANY in the VO's"
                               " AllowedCaches",
    'OriginNotAllowed'       : "VOs in AllowedVOs for a resource with an"
                               " XRootD origin server service should list"
                               " that resource in the VO's AllowedOrigins",
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
            print("ERROR: Resource Group '%s' mentioned for multiple Sites:" % name)
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
            print("ERROR: Resource '%s' mentioned for multiple groups:" % r)
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
                print("ERROR: In '%s', Resource '%s' has total VOOwnership = %d%%" %
                      (rgfn, rname, total_vo_ownership))
                errors += 1
            if total_vo_ownership:
                for vo in rdict['VOOwnership']:
                    if vo not in vo_names:
                        print_emsg_once('UnknownVO')
                        print("ERROR: In '%s', Resource '%s' has unknown VO '%s'" %
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
                print("ERROR: In '%s', Resource '%s' has no Services" % (rgfn, rname))
                errors += 1
            else:
                for svc in sorted(set(rsvcs) - set(services)):
                    print_emsg_once('NoServices')
                    print("ERROR: In '%s', Resource '%s' has unknown Service '%s'" %
                          (rgfn, rname, svc))
                    errors += 1
    return errors


def test_5_sc(rgs, rgfns, support_centers):
    # 5. SupportCenter must refer to an existing SC

    errors = 0
    if support_centers is None:
        print("ERROR: File missing: 'topology/support-centers.yaml'")
        return 1

    for rg,rgfn in zip(rgs,rgfns):
        sc = rg.get('SupportCenter')
        if not sc:
            print_emsg_once('NoSupCenter')
            print("ERROR: Resource Group '%s' has no SupportCenter" % rgfn)
            errors += 1
        elif sc not in support_centers:
            print_emsg_once('NoSupCenter')
            print("ERROR: Resource Group '%s' has unknown SupportCenter '%s'" %
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
            print("ERROR: Site '%s' mentioned for multiple Facilities:" % site)
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
            print("ERROR: FQDN '%s' mentioned for multiple resources:" % fqdn)
            for rgfile,rname in rgflist:
                print(" - %s (%s)" % (rname,rgfile))
            errors += 1

    return errors


def test_8_res_ids(rgs, rgfns):
    # Check that resources/resource groups have a numeric ID/GroupID

    errors = 0
    ridres = autodict()
    gidrgs = autodict()

    for rg,rgfn in zip(rgs,rgfns):
        if not isinstance(rg.get('GroupID'), int):
            print_emsg_once('ResGrpID')
            print("ERROR: Resource Group missing numeric GroupID: '%s'" % rgfn)
            errors += 1
        else:
            gidrgs[rg['GroupID']] += [rgfn]

        for resname,res in sorted(rg['Resources'].items()):
            if not isinstance(res.get('ID'), int):
                print_emsg_once('ResID')
                print("ERROR: Resource '%s' missing numeric ID in '%s'"
                      % (resname, rgfn))
                errors += 1
            else:
                ridres[res['ID']] += [(rgfn, resname)]

    for gid,rglist in sorted(gidrgs.items()):
        if len(rglist) > 1:
            print_emsg_once('ResGrpIDUnique')
            print("ERROR: Resource Group ID '%s' used for multiple groups:" % gid)
            for rgfn in rglist:
                print(" - %s" % rgfn)
            errors += 1

    for rid,reslist in sorted(ridres.items()):
        if len(reslist) > 1:
            print_emsg_once('ResIDUnique')
            print("ERROR: Resource ID '%s' used for multiple resources:" % rid)
            for rgfn,resname in reslist:
                print(" - %s: %s" % (rgfn, resname))
            errors += 1

    return errors


def flatten_res_contacts(rcls):
    for ctype,ctype_d in sorted(rcls.items()):
        for clevel,clevel_d in sorted(ctype_d.items()):
            yield ctype, clevel, clevel_d.get("ID"), clevel_d.get("Name")


def flatten_vo_contacts(vcs):
    for ctype,ctype_l in sorted(vcs.items()):
        for cd in ctype_l:
            yield ctype, cd.get("ID"), cd.get("Name")


def flatten_sc_contacts(sccs):
    for ctype,ctype_l in sorted(sccs.items()):
        for cd in ctype_l:
            yield ctype, cd.get("ID"), cd.get("Name")


def test_9_res_contact_lists(rgs, rgfns):
    # verify resources have contact lists

    errors = 0

    for rg,rgfn in zip(rgs,rgfns):
        for rname,rdict in sorted(rg['Resources'].items()):
            rcls = rdict.get('ContactLists')
            if not rcls:
                print_emsg_once('NoResourceContactLists')
                print("ERROR: In '%s', Resource '%s' has no ContactLists"
                      % (rgfn, rname))
                errors += 1

    return errors


def test_10_res_admin_contact(rgs, rgfns):
    # verify resources have admin contact

    warnings = 0

    for rg,rgfn in zip(rgs,rgfns):
        for rname,rdict in sorted(rg['Resources'].items()):
            rcls = rdict.get('ContactLists')
            if rcls:
                ctype, etype = 'Administrative', 'NoAdminContact'
                if not rcls.get('%s Contact' % ctype):
                    print_emsg_once(etype)
                    print("WARNING: In '%s', Resource '%s' has no %s Contact"
                          % (rgfn, rname, ctype))
                    warnings += 1

    return warnings


def test_11_res_sec_contact(rgs, rgfns):
    # verify resources have security contact

    warnings = 0

    for rg,rgfn in zip(rgs,rgfns):
        for rname,rdict in sorted(rg['Resources'].items()):
            rcls = rdict.get('ContactLists')
            if rcls:
                ctype, etype = 'Security', 'NoSecContact'
                if not rcls.get('%s Contact' % ctype):
                    print_emsg_once(etype)
                    print("WARNING: In '%s', Resource '%s' has no %s Contact"
                          % (rgfn, rname, ctype))
                    warnings += 1

    return warnings


def test_12_res_contact_id_fmt(rgs, rgfns):
    # verify resource contact IDs are well-formed

    errors = 0

    for rg,rgfn in zip(rgs,rgfns):
        for rname,rdict in sorted(rg['Resources'].items()):
            rcls = rdict.get('ContactLists')
            if rcls:
                for ctype, clevel, ID, name in flatten_res_contacts(rcls):
                    if not contact_id_ok(ID):
                        print_emsg_once('MalformedContactID')
                        print("ERROR: In '%s', Resource '%s' has malformed %s %s '%s'"
                              " (%s)" % (rgfn, rname, clevel, ctype, ID, name))
                        errors += 1
    return errors


def test_12_vo_contact_id_fmt(vos, vofns):
    # verify vo contact IDs are well-formed

    errors = 0

    for vo,vofn in zip(vos,vofns):
        vcs = vo.get('Contacts')
        if vcs:
            for ctype, ID, name in flatten_vo_contacts(vcs):
                if not contact_id_ok(ID):
                    print_emsg_once('MalformedContactID')
                    print("ERROR: In '%s', malformed '%s' Contact ID '%s'"
                          " (%s)" % (vofn, ctype, ID, name))
                    errors += 1
    return errors


def test_12_sc_contact_id_fmt(support_centers):
    # verify support center contact IDs are well-formed

    errors = 0
    if support_centers is None:
        return 0

    for scname,scdict in sorted(support_centers.items()):
        sccs = scdict.get('Contacts')
        if sccs:
            for ctype, ID, name in flatten_sc_contacts(sccs):
                if not contact_id_ok(ID):
                    print_emsg_once('MalformedContactID')
                    print("ERROR: Support Center '%s' has malformed '%s'"
                          " Contact ID '%s' (%s)" % (scname, ctype, ID, name))
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
                    if contact_id_ok(ID) and ID not in contacts:
                        print_emsg_once('UnknownContactID')
                        print("ERROR: In '%s', Resource '%s' has unknown %s %s '%s'"
                              " (%s)" % (rgfn, rname, clevel, ctype, ID, name))
                        errors += 1

    return errors


def test_13_vo_contacts_exist(vos, vofns, contacts):
    # verify vo contacts exist in contact repo

    errors = 0

    for vo,vofn in zip(vos,vofns):
        vcs = vo.get('Contacts')
        if vcs:
            for ctype, ID, name in flatten_vo_contacts(vcs):
                if contact_id_ok(ID) and ID not in contacts:
                    print_emsg_once('UnknownContactID')
                    print("ERROR: In '%s', unknown '%s' Contact ID '%s'"
                          " (%s)" % (vofn, ctype, ID, name))
                    errors += 1

    return errors


def test_13_sc_contacts_exist(support_centers, contacts):
    # verify support center contacts exist in contact repo

    errors = 0
    if support_centers is None:
        return 0

    for scname,scdict in sorted(support_centers.items()):
        sccs = scdict.get('Contacts')
        if sccs:
            for ctype, ID, name in flatten_sc_contacts(sccs):
                if contact_id_ok(ID) and ID not in contacts:
                    print_emsg_once('UnknownContactID')
                    print("ERROR: Support Center '%s' has unknown '%s'"
                          " Contact ID '%s' (%s)" % (scname, ctype, ID, name))
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
                    if (contact_id_ok(ID)
                        and ID in contacts
                        and name.lower() != contacts[ID].lower()):
                        print_emsg_once('ContactNameMismatch')
                        print("ERROR: In '%s', Resource '%s' %s %s '%s' (%s) does not"
                              " match name in contact repo (%s)" % (rgfn,
                              rname, clevel, ctype, ID, name, contacts[ID]))
                        errors += 1

    return errors


def test_14_vo_contacts_match(vos, vofns, contacts):
    # verify vo contacts match contact repo

    errors = 0

    for vo,vofn in zip(vos,vofns):
        vcs = vo.get('Contacts')
        if vcs:
            for ctype, ID, name in flatten_vo_contacts(vcs):
                if (contact_id_ok(ID)
                    and ID in contacts
                    and name.lower() != contacts[ID].lower()):
                    print_emsg_once('ContactNameMismatch')
                    print("ERROR: In '%s', '%s' Contact ID '%s' (%s) does not"
                          " match name in contact repo (%s)" % (vofn, ctype,
                          ID, name, contacts[ID]))
                    errors += 1

    return errors


def test_14_sc_contacts_match(support_centers, contacts):
    # verify support center contacts match contact repo

    errors = 0
    if support_centers is None:
        return 0

    for scname,scdict in sorted(support_centers.items()):
        sccs = scdict.get('Contacts')
        if sccs:
            for ctype, ID, name in flatten_sc_contacts(sccs):
                if (contact_id_ok(ID)
                    and ID in contacts
                    and name.lower() != contacts[ID].lower()):
                    print_emsg_once('ContactNameMismatch')
                    print("ERROR: Support Center '%s': '%s' Contact ID '%s' (%s)"
                          " does not match name in contact repo (%s)" %
                          (scname, ctype, ID, name, contacts[ID]))
                    errors += 1

    return errors


def test_15_facility_site_files():
    # verify the required FACILITY.yaml and SITE.yaml files
    errors = 0

    for facdir in glob.glob("*/"):
        if not os.path.exists(facdir + "FACILITY.yaml"):
            print_emsg_once('NoFacility')
            print("ERROR: " + facdir[:-1] + " does not have required FACILITY.yaml file")
            errors += 1

    for sitedir in glob.glob("*/*/"):
        if not os.path.exists(sitedir + "SITE.yaml"):
            print_emsg_once('NoSite')
            print("ERROR: " + sitedir[:-1] + " does not have required SITE.yaml file")
            errors += 1

    return errors


def test_16_Xrootd_DNs(rgs, rgfns):
    # verify each Xrootd service has DN

    errors = 0

    for rg, rgfn in zip(rgs, rgfns):
        for rname, rdict in sorted(rg['Resources'].items()):
            if 'XRootD cache server' in rdict['Services'] and rdict['Active'] and 'DN' not in rdict:
                print_emsg_once('XrootdWithoutDN')
                print("ERROR: In '%s', Xrootd cache server Resource '%s' has no DN" %
                      (rgfn, rname))
                errors += 1

    return errors


def test_17_osdf_data(rgs, rgfns):
    # validate OSDF cache/origin services: (SOFTWARE-4167)
    # - resources with "XRootD origin server" service must have AllowedVOs list
    # - resources with "XRootD cache server" service must have AllowedVOs list
    # - AllowedVOs list items must be either:
    #   - "ANY"
    #   - "ANY_PUBLIC"
    #   - A registered VO (in the virtual-organizations directory)

    vo_names = get_vo_names()
    allowed_vo_names = vo_names | set(["ANY", "ANY_PUBLIC"])
    services = ["XRootD origin server", "XRootD cache server"]

    errors = 0

    for rg, rgfn in zip(rgs, rgfns):
        for rname, rdict in sorted(rg['Resources'].items()):
            rsvcs = rdict.get('Services', {})
            if any( svc in rsvcs for svc in services ):
                if not isinstance(rdict.get('AllowedVOs'), list):
                    print_emsg_once('OSDFServiceVOsList')
                    print("ERROR: In '%s', XRootD cache/origin server Resource '%s'"
                          " has no AllowedVOs list" % (rgfn, rname))
                    errors += 1
                else:
                    for name in rdict['AllowedVOs']:
                        if name not in allowed_vo_names:
                            print_emsg_once('UnknownVO')
                            print("ERROR: In '%s', Resource '%s', AllowedVOs has"
                                  " unknown VO name '%s'" % (rgfn, rname, name))
                            errors += 1
    return errors


def _get_vo_path_map(vomap, list_path):
    vo_allowed_map = {
        voname: safe_dict_get(vo, *list_path) for voname, vo in vomap.items()
    }
    return {
        voname: set(alist) for voname, alist in vo_allowed_map.items()
        if isinstance(alist, list)
    }


def test_18_osdf_data_cache_warnings(rgs, rgfns, vomap):
    # The following should be added as warnings: (SOFTWARE-4167)
    # - VOs in AllowedVOs for a resource with an "XRootD cache server"
    #   service should list that resource or "ANY" in the VO's AllowedCaches

    acpath = ['DataFederations', 'StashCache', 'AllowedCaches']

    vo_allowed_caches = _get_vo_path_map(vomap, acpath)
    all_allowed_caches = set.union(*vo_allowed_caches.values())
    any_cache_allowed = "ANY" in all_allowed_caches

    warnings = 0

    for rg, rgfn in zip(rgs, rgfns):
        for rname, rdict in sorted(rg['Resources'].items()):
            rsvcs = rdict.get('Services', {})
            if "XRootD cache server" in rsvcs:
                for voname in rdict.get('AllowedVOs', []):
                    if voname in ["ANY", "ANY_PUBLIC"]:
                        if any_cache_allowed:
                            continue
                        if rname not in all_allowed_caches:
                            print_emsg_once('CacheNotAllowed')
                            print("WARNING: In '%s', Resource '%s' is a Cache and"
                                  " allows %s VO; but no VO allows this"
                                  " resource in AllowedCaches"
                                  % (rgfn, rname, voname))
                            warnings += 1

                    elif not (voname in vo_allowed_caches and
                            (rname in vo_allowed_caches[voname] or
                             "ANY" in vo_allowed_caches[voname])):
                        print_emsg_once('CacheNotAllowed')
                        print("WARNING: In '%s', Resource '%s' is a Cache and lists"
                              " '%s' in AllowedVOs; but this VO does not list"
                              " that resource in AllowedCaches"
                              % (rgfn, rname, voname))
                        warnings += 1
    return warnings


def test_19_osdf_data_origin_warnings(rgs, rgfns, vomap):
    # The following should be added as warnings: (SOFTWARE-4167)
    # - VOs in AllowedVOs for a resource with an "XRootD origin server"
    #   service should list that resource or "ANY" in the VO's AllowedOrigins

    aopath = ['DataFederations', 'StashCache', 'AllowedOrigins']

    vo_allowed_origins = _get_vo_path_map(vomap, aopath)
    all_allowed_origins = set.union(*vo_allowed_origins.values())
    # do not allow ANY for AllowedOrigins
    #any_origin_allowed = "ANY" in all_allowed_origins

    warnings = 0

    for rg, rgfn in zip(rgs, rgfns):
        for rname, rdict in sorted(rg['Resources'].items()):
            rsvcs = rdict.get('Services', {})
            if "XRootD origin server" in rsvcs:
                for voname in rdict.get('AllowedVOs', []):
                    if voname in ["ANY", "ANY_PUBLIC"]:
                        if rname not in all_allowed_origins:
                            print_emsg_once('OriginNotAllowed')
                            print("WARNING: In '%s', Resource '%s' is an Origin and"
                                  " allows %s VO; but no VO allows this"
                                  " resource in AllowedOrigins"
                                  % (rgfn, rname, voname))
                            warnings += 1

                    elif not (voname in vo_allowed_origins and
                            (rname in vo_allowed_origins[voname] or
                             "ANY" in vo_allowed_origins[voname])):
                        print_emsg_once('OriginNotAllowed')
                        print("WARNING: In '%s', Resource '%s' is an Origin and lists"
                              " '%s' in AllowedVOs; but this VO does not list"
                              " that resource in AllowedOrigins"
                              % (rgfn, rname, voname))
                        warnings += 1
    return warnings


def test_20_fqdn_unique_xrootd(rgs, rgfns):
    # fqdns should be unique across all resources in all sites,
    # but in any case MUST be unique for XRootD services (SOFTWARE-5065)

    errors = 0
    n2rg = autodict()

    xrd_svcs = ("XRootD origin server", "XRootD cache server")

    for rg,rgfn in zip(rgs,rgfns):
        for rname,rdict in rg['Resources'].items():
            fqdn = rdict['FQDN']
            svcs = rdict['Services']
            n2rg[fqdn] += [(rgfn,rname,svcs)]

    for fqdn, rgflist in sorted(n2rg.items()):
        if len(rgflist) == 1:
            continue

        if any( svc in svcs for _,_,svcs in rgflist for svc in xrd_svcs ):
            print_emsg_once('FQDNUniqueXRootD')
            print("ERROR: Duplicate FQDN '%s' used for XRootD services:" % fqdn)

            for rgfn, rname, svcs in rgflist:
                print(" - %s (%s)" % (rname,rgfn))
                for svc in xrd_svcs:
                    if svc in svcs:
                        print("   - %s" % svc)

            errors += 1

    return errors


if __name__ == '__main__':
    sys.exit(main())

