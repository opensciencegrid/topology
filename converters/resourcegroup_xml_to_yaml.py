import anymarkup
import copy
import os
import pprint
import shutil
import sys
from collections import OrderedDict
from typing import Dict, List, Union

# Example URL: https://myosg.grid.iu.edu/rgsummary/xml?summary_attrs_showhierarchy=on&summary_attrs_showwlcg=on&summary_attrs_showservice=on&summary_attrs_showfqdn=on&summary_attrs_showvoownership=on&summary_attrs_showcontact=on&gip_status_attrs_showtestresults=on&downtime_attrs_showpast=&account_type=cumulative_hours&ce_account_type=gip_vo&se_account_type=vo_transfer_volume&bdiitree_type=total_jobs&bdii_object=service&bdii_server=is-osg&all_resources=on&facility_sel%5B%5D=10009&gridtype=on&gridtype_1=on&active=on&active_value=1&disable_value=1
# Layout in that URL is
# <ResourceGroup>
#   <Facility>
#   <Site>
#   <Resources>
#     <Resource>
#     ...

# Layout we want is
# facility/
#   site/
#     site.yml
#     resourcegroup1.yml
#     ...
# (where "facility", "site", and "resourcegroup1" but _not_ "site.yml" are
# named after the facility, site, and resource group (sanitized).


def ensure_list(x):
    if isinstance(x, list):
        return x
    return [x]


def to_file_name(name: str) -> str:
    """Replaces characters in ``name`` that shouldn't be used for file or
    dir names.

    """
    filename = ""
    for char in name:
        if char in '/:.\\':
            filename += "_"
        else:
            filename += char
    return filename


parsed = anymarkup.parse_file('../examples/rgsummary1.xml')['ResourceSummary']

topology = {}


def simplify_attr_list(data: Union[Dict, List], namekey: str) -> Dict:
    """
    Simplify
        [{namekey: "name1", "attr1": "val1", ...},
         {namekey: "name2", "attr1": "val1", ...}]}
    or, if there's only one,
        {namekey: "name1", "attr1": "val1", ...}
    to
      {"name1": {"attr1": "val1", ...},
       "name2": {"attr1": "val1", ...}}
    """
    new_data = {}
    for d in ensure_list(data):
        new_d = dict(d)
        name = new_d[namekey]
        del new_d[namekey]
        new_data[name] = new_d
    return new_data


def simplify_services(services):
    """
    Simplify Services attribute
    """
    new_services = simplify_attr_list(services["Service"], "Name")
    for service in new_services.values():
        if service["Details"]:
            service["Details"] = dict(service["Details"])  # OrderedDict -> dict
    return new_services


def simplify_voownership(voownership):
    """
    Simplify VOOwnership attribute
    """
    if not isinstance(voownership, dict):
        return voownership
    voownership = dict(voownership)  # copy
    del voownership["ChartURL"]  # can be derived from the other attributes
    new_voownership = simplify_attr_list(voownership["Ownership"], "VO")
    for vo in new_voownership:
        new_voownership[vo] = int(new_voownership[vo]["Percent"])
    return new_voownership


def simplify_contactlists(contactlists):
    """Simplify ContactLists attribute

    Turn e.g.
    {"ContactList":
        [{"ContactType": "Administrative Contact",
            {"Contacts":
                {"Contact":
                    [{"Name": "Andrew Malone Melo", "ContactRank": "Primary"},
                     {"Name": "Paul Sheldon", "ContactRank": "Secondary"}]
                }
            }
         }]
    }

    into

    {"Administrative Contact":
        {"Primary": "Andrew Malone Melo",
         "Secondary": "Paul Sheldon"}
    }
    """
    if not isinstance(contactlists, dict):
        return contactlists
    contactlists_simple = simplify_attr_list(contactlists["ContactList"], "ContactType")
    new_contactlists = {}
    for contact_type, contact_data in contactlists_simple.items():
        contacts = simplify_attr_list(contact_data["Contacts"]["Contact"], "ContactRank")
        new_contacts = {}
        for contact_rank in contacts:
            if contact_rank in new_contacts and contacts[contact_rank]["Name"] != new_contacts[contact_rank]:
                # Multiple people with the same rank -- hope this never happens.
                # Duplicates are fine though -- we collapse them into one.
                raise RuntimeError("dammit %s" % contacts[contact_rank]["Name"])
            new_contacts[contact_rank] = contacts[contact_rank]["Name"]
        new_contactlists[contact_type] = new_contacts
    return new_contactlists

def simplify_resource(res: Dict) -> Dict:
    res = dict(res)

    res["Services"] = simplify_services(res["Services"])
    res["VOOwnership"] = simplify_voownership(res["VOOwnership"])
    if isinstance(res["WLCGInformation"], OrderedDict):
        res["WLCGInformation"] = dict(res["WLCGInformation"])
    if isinstance(res["FQDNAliases"], dict):
        aliases = []
        for a in ensure_list(res["FQDNAliases"]["FQDNAlias"]):
            aliases.append(a)
        res["FQDNAliases"] = aliases
    res["ContactLists"] = simplify_contactlists(res["ContactLists"])

    return res


def simplify_resourcegroup(rg: Dict) -> Dict:
    """Simplify the data structure in the ResourceGroup.  Returns the simplified ResourceGroup."""
    rg = dict(rg)

    # {"SupportCenter": {"ID": XXX, "Name": YYY}} -> {"SupportCenterID": XXX, "SupportCenterName": YYY}
    rg["SupportCenterID"] = rg["SupportCenter"]["ID"]
    rg["SupportCenterName"] = rg["SupportCenter"]["Name"]
    del rg["SupportCenter"]

    rg["Resources"] = simplify_attr_list(rg["Resources"]["Resource"], "Name")
    for key, val in rg["Resources"].items():
        rg["Resources"][key] = simplify_resource(val)

    return rg

for rg in ensure_list(parsed["ResourceGroup"]):
    sanfacility = to_file_name(rg["Facility"]["Name"])
    if sanfacility not in topology:
        topology[sanfacility] = {"ID": rg["Facility"]["ID"]}
    sansite = to_file_name(rg["Site"]["Name"])
    if sansite not in topology[sanfacility]:
        topology[sanfacility][sansite] = {"ID": rg["Site"]["ID"]}
    sanrg = to_file_name(rg["GroupName"]) + ".yml"

    rg_copy = dict(rg)
    # Get rid of these fields; we're already putting them in the file/dir names.
    del rg_copy["Facility"]
    del rg_copy["Site"]
    del rg_copy["GroupName"]

    try:
        topology[sanfacility][sansite][sanrg] = simplify_resourcegroup(rg_copy)
    except Exception:
        print("*** We were parsing %s/%s/%s" % (sanfacility, sansite, sanrg), file=sys.stderr)
        pprint.pprint(rg_copy, stream=sys.stderr)
        print("\n\n", file=sys.stderr)
        raise


topdir = "/tmp/topology"
if os.path.isdir(topdir):
    shutil.rmtree(topdir)
os.makedirs(topdir)

for facility_name, facility_data in topology.items():
    facility_dir = os.path.join(topdir, facility_name)
    os.makedirs(facility_dir)

    anymarkup.serialize_file({"ID": facility_data["ID"]},
                             os.path.join(facility_dir, "FACILITY.yml"))

    for site_name, site_data in facility_data.items():
        if site_name == "ID": continue

        site_dir = os.path.join(facility_dir, site_name)
        os.makedirs(site_dir)

        anymarkup.serialize_file({"ID": site_data["ID"]}, os.path.join(site_dir, "SITE.yml"))

        for rg_name, rg_data in site_data.items():
            if rg_name == "ID": continue

            anymarkup.serialize_file(rg_data, os.path.join(site_dir, rg_name))

print("take a look in", topdir)
