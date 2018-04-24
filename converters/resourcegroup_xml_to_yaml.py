#!/usr/bin/env python3
"""Take an rgsummary.xml file and convert it into a directory tree of yaml files

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
      resourcegroup.yaml
      ...
    ...
  ...
The name of the facility dir is taken from the (XPath)
``/ResourceSummary/ResourceGroup/Facility/Name`` element; the name of the site
dir is taken from the ``/ResourceSummary/ResourceGroup/Site/Name`` element;
the name of the yaml file is taken from the
``/ResourceSummary/ResourceGroup/GroupName`` element.

Also, each facility dir will have a ``FACILITY.yaml`` file, and each site dir
will have a ``SITE.yaml`` file containing facility and site information.

Ordering is lost in the YAML file but the YAML to XML converter restores it.
"""
import anymarkup
import os
import pprint
import sys
from collections import OrderedDict
from typing import Dict, List, Union

from convertlib import is_null, ensure_list, simplify_attr_list


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


class Topology(object):

    def __init__(self):
        self.data = {}
        self.services = {}
        self.support_centers = {}

    def add_rg(self, rg: Dict):
        sanfacility = to_file_name(rg["Facility"]["Name"])
        if sanfacility not in self.data:
            self.data[sanfacility] = {"ID": rg["Facility"]["ID"]}
        sansite = to_file_name(rg["Site"]["Name"])
        if sansite not in self.data[sanfacility]:
            self.data[sanfacility][sansite] = {"ID": rg["Site"]["ID"]}
        sanrg = to_file_name(rg["GroupName"]) + ".yaml"

        rg_copy = dict(rg)
        # Get rid of these fields; we're already putting them in the file/dir names.
        del rg_copy["Facility"]
        del rg_copy["Site"]
        del rg_copy["GroupName"]

        try:
            self.data[sanfacility][sansite][sanrg] = self.simplify_resourcegroup(rg_copy)
        except Exception:
            print("*** We were parsing %s/%s/%s" % (sanfacility, sansite, sanrg), file=sys.stderr)
            pprint.pprint(rg_copy, stream=sys.stderr)
            print("\n\n", file=sys.stderr)
            raise

    def simplify_services(self, services):
        """
        Simplify Services attribute and record the Name -> ID mapping
        """
        if not isinstance(services, dict):
            return None
        new_services = simplify_attr_list(services["Service"], "Name")
        for name, data in new_services.items():
            if not is_null(data, "Details"):
                new_details = dict()
                for key, val in data["Details"].items():
                    if not is_null(val):
                        new_details[key] = val
                if len(new_details) > 0:
                    data["Details"] = dict(new_details)
                else:
                    del data["Details"]
            else:
                data.pop("Details", None)
            if "ID" in data:
                if name not in self.services:
                    self.services[name] = data["ID"]
                else:
                    if data["ID"] != self.services[name]:
                        raise RuntimeError("Identical services with different IDs: %s" % name)
                del data["ID"]

        return new_services

    def simplify_voownership(self, voownership):
        """
        Simplify VOOwnership attribute
        """
        if is_null(voownership):
            return None
        voownership = dict(voownership)  # copy
        del voownership["ChartURL"]  # can be derived from the other attributes
        new_voownership = simplify_attr_list(voownership["Ownership"], "VO")
        new_voownership.pop("(Other)", None)  # can be derived from the other attributes
        for vo in new_voownership:
            new_voownership[vo] = int(new_voownership[vo]["Percent"])
        return new_voownership

    def simplify_contactlists(self, contactlists):
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
        if is_null(contactlists):
            return None
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

    def simplify_resource(self, res: Dict) -> Dict:
        res = dict(res)

        services = self.simplify_services(res["Services"])
        if is_null(services):
            res.pop("Services", None)
        else:
            res["Services"] = services
        res["VOOwnership"] = self.simplify_voownership(res.get("VOOwnership"))
        if not res["VOOwnership"]:
            del res["VOOwnership"]
        if not is_null(res, "WLCGInformation"):
            new_wlcg = {}
            for key, val in res["WLCGInformation"].items():
                if not is_null(val):
                    new_wlcg[key] = val
            if len(new_wlcg) > 0:
                res["WLCGInformation"] = new_wlcg
            else:
                del res["WLCGInformation"]
        else:
            res.pop("WLCGInformation", None)
        if not is_null(res, "FQDNAliases"):
            aliases = []
            for a in ensure_list(res["FQDNAliases"]["FQDNAlias"]):
                aliases.append(a)
            res["FQDNAliases"] = aliases
        else:
            res.pop("FQDNAliases", None)
        if not is_null(res, "ContactLists"):
            new_contactlists = self.simplify_contactlists(res["ContactLists"])
            if new_contactlists:
                res["ContactLists"] = new_contactlists
        else:
            res.pop("ContactLists", None)

        return res

    def simplify_resourcegroup(self, rg: Dict) -> Dict:
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

        Also record the SupportCenter Name -> ID mapping and turn
            {"SupportCenter": {"ID": "123", "Name": "XXX"}}
        into
            {"SupportCenter": "XXX"}
        """
        rg = dict(rg)

        scname = rg["SupportCenter"]["Name"]
        scid = rg["SupportCenter"]["ID"]
        if scname not in self.support_centers:
            self.support_centers[scname] = scid
        else:
            if self.support_centers[scname] != scid:
                raise RuntimeError("Identical support centers with different IDs: %s" % scname)
        rg["SupportCenter"] = scname

        rg["Resources"] = simplify_attr_list(rg["Resources"]["Resource"], "Name")
        for key, val in rg["Resources"].items():
            rg["Resources"][key] = self.simplify_resource(val)

        return rg


def topology_from_parsed_xml(parsed) -> Topology:
    """Returns a dict of the topology created from the parsed XML file."""
    topology = Topology()
    for rg in ensure_list(parsed["ResourceGroup"]):
        topology.add_rg(rg)
    return topology


def write_topology_to_yamls(topology: Topology, outdir):
    os.makedirs(outdir, exist_ok=True)

    for facility_name, facility_data in topology.data.items():
        facility_dir = os.path.join(outdir, facility_name)
        os.makedirs(facility_dir, exist_ok=True)

        anymarkup.serialize_file({"ID": facility_data["ID"]},
                                 os.path.join(facility_dir, "FACILITY.yaml"))

        for site_name, site_data in facility_data.items():
            if site_name == "ID": continue

            site_dir = os.path.join(facility_dir, site_name)
            os.makedirs(site_dir, exist_ok=True)

            anymarkup.serialize_file({"ID": site_data["ID"]}, os.path.join(site_dir, "SITE.yaml"))

            for rg_name, rg_data in site_data.items():
                if rg_name == "ID": continue

                anymarkup.serialize_file(rg_data, os.path.join(site_dir, rg_name))

    # We want to sort this so write it out ourselves
    for filename, data in [("support-centers.yaml", topology.support_centers),
                           ("services.yaml", topology.services)]:
        with open(os.path.join(outdir, filename), "w") as outfh:
            for name, id_ in sorted(data.items(), key=lambda x: x[1]):
                print("%s: %s" % (name, id_), file=outfh)

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
    write_topology_to_yamls(topology, outdir)
    print("Topology written to", outdir)

    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))

