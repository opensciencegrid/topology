#!/usr/bin/env python3
"""Take an rgsummary.xml file and convert it into a directory tree of yml files

An rgsummary.xml file can be downloaded from a URL such as:
https://myosg.grid.iu.edu/rgsummary/xml?summary_attrs_showhierarchy=on&summary_attrs_showwlcg=on&summary_attrs_showservice=on&summary_attrs_showfqdn=on&summary_attrs_showvoownership=on&summary_attrs_showcontact=on&gip_status_attrs_showtestresults=on&downtime_attrs_showpast=&account_type=cumulative_hours&ce_account_type=gip_vo&se_account_type=vo_transfer_volume&bdiitree_type=total_jobs&bdii_object=service&bdii_server=is-osg&all_resources=on&facility_sel%5B%5D=10009&gridtype=on&gridtype_1=on&active=on&active_value=1&disable_value=1
or by using the ``download_rgsummary.py`` script.
The layout of that page is
  <ResourceSummary>
    <ResourceGroup>
      <Facility>...</Facility>
      <Site>...</Site>
      (other attributes...)
    </ResourceGroup>
    ...
  </ResourceSummary>

The new directory layout will be

  facility/
    site/
      resourcegroup.yml
      ...
    ...
  ...
The name of the facility dir is taken from the (XPath)
``/ResourceSummary/ResourceGroup/Facility/Name`` element; the name of the site
dir is taken from the ``/ResourceSummary/ResourceGroup/Site/Name`` element;
the name of the yml file is taken from the
``/ResourceSummary/ResourceGroup/GroupName`` element.

Also, each facility dir will have a ``FACILITY.yml`` file, and each site dir
will have a ``SITE.yml`` file containing facility and site information.

Ordering is not kept.
"""
import anymarkup
import os
import pprint
import sys
from collections import OrderedDict
from typing import Dict, List, Union


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
    if not isinstance(services, dict):
        return None
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
        return None
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

    services = simplify_services(res["Services"])
    if services:
        res["Services"] = services
    else:
        del res["Services"]
    res["VOOwnership"] = simplify_voownership(res.get("VOOwnership"))
    if not res["VOOwnership"]:
        del res["VOOwnership"]
    try:
        if isinstance(res["WLCGInformation"], OrderedDict):
            res["WLCGInformation"] = dict(res["WLCGInformation"])
        else:
            del res["WLCGInformation"]
    except KeyError: pass
    try:
        if isinstance(res["FQDNAliases"], dict):
            aliases = []
            for a in ensure_list(res["FQDNAliases"]["FQDNAlias"]):
                aliases.append(a)
            res["FQDNAliases"] = aliases
        else:
            del res["FQDNAliases"]
    except KeyError: pass
    res["ContactLists"] = simplify_contactlists(res["ContactLists"])

    return res


def simplify_resourcegroup(rg: Dict) -> Dict:
    """Simplify the data structure in the ResourceGroup.  Returns the simplified ResourceGroup.

        {"Resources":
            {"Resource":
                [{"Name": "Rsrc1", ...},
                 ...
                ]
            }
        }
    is turned into:
        {"Resources":
            {"Rsrc1": {...}}
        }
    and
        {"SupportCenter": {"ID": "123", "Name": "XXX"}}
    is turned into:
        {"SupportCenterID": "123",
         "SupportCenterName": "XXX"}
    """
    rg = dict(rg)

    rg["SupportCenterID"] = rg["SupportCenter"]["ID"]
    rg["SupportCenterName"] = rg["SupportCenter"]["Name"]
    del rg["SupportCenter"]

    rg["Resources"] = simplify_attr_list(rg["Resources"]["Resource"], "Name")
    for key, val in rg["Resources"].items():
        rg["Resources"][key] = simplify_resource(val)

    return rg


def topology_from_parsed_xml(parsed) -> Dict:
    """Returns a dict of the topology created from the parsed XML file."""
    topology = {}
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
    return topology


def write_topology_to_ymls(topology, outdir):
    os.makedirs(outdir, exist_ok=True)

    for facility_name, facility_data in topology.items():
        facility_dir = os.path.join(outdir, facility_name)
        os.makedirs(facility_dir, exist_ok=True)

        anymarkup.serialize_file({"ID": facility_data["ID"]},
                                 os.path.join(facility_dir, "FACILITY.yml"))

        for site_name, site_data in facility_data.items():
            if site_name == "ID": continue

            site_dir = os.path.join(facility_dir, site_name)
            os.makedirs(site_dir, exist_ok=True)

            anymarkup.serialize_file({"ID": site_data["ID"]}, os.path.join(site_dir, "SITE.yml"))

            for rg_name, rg_data in site_data.items():
                if rg_name == "ID": continue

                anymarkup.serialize_file(rg_data, os.path.join(site_dir, rg_name))


def main(argv=sys.argv):
    try:
        infile, outdir = argv[1:3]
    except ValueError:
        print("Usage: %s <input xml> <output dir>" % argv[0], file=sys.stderr)
        return 2

    if os.path.exists(outdir):
        print("Warning: %s already exists" % outdir, file=sys.stderr)
    parsed = anymarkup.parse_file(infile)['ResourceSummary']
    topology = topology_from_parsed_xml(parsed)
    write_topology_to_ymls(topology, outdir)
    print("Topology written to", outdir)

    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))

