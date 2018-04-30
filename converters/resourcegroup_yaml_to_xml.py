#!/usr/bin/env python3
"""Converts a directory tree containing resource topology data to a single
XML document.

Usage as a script:

    resourcegroup_yaml_to_xml.py <input directory> [<output file>]

If output file not specified, results are printed to stdout.

Usage as a module

    xml = resourcegroup_yaml_to_xml(input_dir[, output_file])

where the return value `xml` is a string.

"""


import urllib.parse

import anymarkup
from collections import OrderedDict
import pprint
import sys
from pathlib import Path
from typing import Dict, Iterable

try:
    from convertlib import is_null, expand_attr_list_single, singleton_list_to_value, expand_attr_list
except ModuleNotFoundError:
    from .convertlib import is_null, expand_attr_list_single, singleton_list_to_value, expand_attr_list

SCHEMA_LOCATION = "https://my.opensciencegrid.org/schema/rgsummary.xsd"


class RGError(Exception):
    """An error with converting a specifig RG"""
    def __init__(self, rg, *args, **kwargs):
        Exception.__init__(self, *args, **kwargs)
        self.rg = rg


class Topology(object):
    def __init__(self):
        self.data = {}

    def add_rg(self, facility, site, rg, rgdata):
        if facility not in self.data:
            self.data[facility] = {}
        if site not in self.data[facility]:
            self.data[facility][site] = {}
        if rg not in self.data[facility][site]:
            self.data[facility][site][rg] = rgdata

    def add_facility(self, name, id):
        if name not in self.data:
            self.data[name] = {}
        self.data[name]["ID"] = id

    def add_site(self, facility, name, id):
        if facility not in self.data:
            self.data[facility] = {}
        if name not in self.data[facility]:
            self.data[facility][name] = {}
        self.data[facility][name]["ID"] = id

    def pprint(self):
        for f in self.data:
            print("[%s %s]" % (f, self.data[f]["ID"]), end=" ")
            for s in self.data[f]:
                if s == "ID": continue
                print("[%s %s]" % (s, self.data[f][s]["ID"]), end=" ")
                for r in self.data[f][s]:
                    if r == "ID": continue
                    print("[%s]" % r)
                    pprint.pprint(self.data[f][s][r])
                    print("")

    def get_resource_summary(self) -> Dict:
        rgs = []
        for fval in self.data.values():
            for s, sval in fval.items():
                if s == "ID": continue
                for r, rval in sval.items():
                    if r == "ID": continue
                    rgs.append(rval)

        rgs.sort(key=lambda x: x["GroupName"].lower())
        return {"ResourceSummary":
                {"@xmlns:xsi": "http://www.w3.org/2001/XMLSchema-instance",
                 "@xsi:schemaLocation": SCHEMA_LOCATION,
                 "ResourceGroup": rgs}}

    def to_xml(self):
        return anymarkup.serialize(self.get_resource_summary(), "xml").decode("utf-8")

    def serialize_file(self, outfile):
        return anymarkup.serialize_file(self.get_resource_summary(), outfile, "xml")


def expand_services(services: Dict, service_name_to_id: Dict[str, int]) -> Dict:

    def _expand_svc(svc):
        svc["ID"] = service_name_to_id[svc["Name"]]
        svc.move_to_end("ID", last=False)

    services_list = expand_attr_list(services, "Name", ordering=["Name", "Description", "Details"])
    if isinstance(services_list, list):
        for svc in services_list:
            _expand_svc(svc)
    else:
        _expand_svc(services_list)
    return {"Service": services_list}


def get_charturl(ownership: Iterable) -> str:
    """Return a URL for a pie chart based on VOOwnership data.
    ``ownership`` consists of (VO, Percent) pairs.
    """
    chd = ""
    chl = ""

    for name, percent in ownership:
        chd += "%s," % percent
        if name == "(Other)":
            name = "Other"
        chl += "%s(%s%%)|" % (percent, name)
    chd = chd.rstrip(",")
    chl = chl.rstrip("|")

    query = urllib.parse.urlencode({
        "chco": "00cc00",
        "cht": "p3",
        "chd": "t:" + chd,
        "chs": "280x65",
        "chl": chl
    })
    return "http://chart.apis.google.com/chart?%s" % query


def expand_voownership(voownership: Dict) -> OrderedDict:
    """Return the data structure for an expanded VOOwnership for a single Resource."""
    voo = voownership.copy()
    totalpercent = sum(voo.values())
    if totalpercent < 100:
        voo["(Other)"] = 100 - totalpercent
    return OrderedDict([
        ("Ownership", expand_attr_list_single(voo, "VO", "Percent", name_first=False)),
        ("ChartURL", get_charturl(voownership.items()))
    ])


def expand_contactlists(contactlists: Dict) -> Dict:
    """Return the data structure for an expanded ContactLists for a single Resource."""
    new_contactlists = []
    for contact_type, contact_data in contactlists.items():
        contact_data = expand_attr_list_single(contact_data, "ContactRank", "Name", name_first=False)
        new_contactlists.append(OrderedDict([("ContactType", contact_type), ("Contacts", {"Contact": contact_data})]))
    return {"ContactList": singleton_list_to_value(new_contactlists)}


def expand_wlcginformation(wlcg: Dict) -> OrderedDict:
    defaults = {
        "AccountingName": None,
        "InteropBDII": False,
        "LDAPURL": None,
        "TapeCapacity": 0,
    }

    new_wlcg = OrderedDict()
    for elem in ["InteropBDII", "LDAPURL", "InteropMonitoring", "InteropAccounting", "AccountingName", "KSI2KMin",
                 "KSI2KMax", "StorageCapacityMin", "StorageCapacityMax", "HEPSPEC", "APELNormalFactor", "TapeCapacity"]:
        if elem in wlcg:
            new_wlcg[elem] = wlcg[elem]
        elif elem in defaults:
            new_wlcg[elem] = defaults[elem]
    return new_wlcg


def expand_resource(name: str, res: Dict, service_name_to_id: Dict[str, int]) -> OrderedDict:
    """Expand a single Resource from the format in a yaml file to the xml format.

    Services, VOOwnership, FQDNAliases, ContactLists are expanded;
    ``name`` is inserted into the Resource as the "Name" attribute;
    Defaults are added for VOOwnership, FQDNAliases, and WLCGInformation if they're missing from the yaml file.

    Return the data structure for the expanded Resource as an OrderedDict to fit the xml schema.
    """
    defaults = {
        "ContactLists": None,
        "FQDNAliases": None,
        "Services": "no applicable service exists",
        "VOOwnership": "(Information not available)",
        "WLCGInformation": "(Information not available)",
    }

    res = dict(res)

    if not is_null(res, "Services"):
        res["Services"] = expand_services(res["Services"], service_name_to_id)
    else:
        res.pop("Services", None)
    if "VOOwnership" in res:
        res["VOOwnership"] = expand_voownership(res["VOOwnership"])
    if "FQDNAliases" in res:
        res["FQDNAliases"] = {"FQDNAlias": singleton_list_to_value(res["FQDNAliases"])}
    if not is_null(res, "ContactLists"):
        res["ContactLists"] = expand_contactlists(res["ContactLists"])
    res["Name"] = name
    if "WLCGInformation" in res and isinstance(res["WLCGInformation"], dict):
        res["WLCGInformation"] = expand_wlcginformation(res["WLCGInformation"])
    new_res = OrderedDict()
    for elem in ["ID", "Name", "Active", "Disable", "Services", "Description", "FQDN", "FQDNAliases", "VOOwnership",
                 "WLCGInformation", "ContactLists"]:
        if elem in res:
            new_res[elem] = res[elem]
        elif elem in defaults:
            new_res[elem] = defaults[elem]

    return new_res


def expand_resourcegroup(rg: Dict, service_name_to_id: Dict[str, int], support_center_name_to_id: Dict[str, int]) -> OrderedDict:
    """Expand a single ResourceGroup from the format in a yaml file to the xml format.

    {"SupportCenterName": ...} and {"SupportCenterID": ...} are turned into
    {"SupportCenter": {"Name": ...}, {"ID": ...}} and each individual Resource is expanded and collected in a
    <Resources> block.

    Return the data structure for the expanded ResourceGroup, as an OrderedDict,
    with the ordering to fit the xml schema for rgsummary.
    """
    rg = dict(rg)  # copy

    scname, scid = rg["SupportCenter"], support_center_name_to_id[rg["SupportCenter"]]
    rg["SupportCenter"] = OrderedDict([("ID", scid), ("Name", scname)])

    new_resources = []
    for name, res in rg["Resources"].items():
        try:
            res = expand_resource(name, res, service_name_to_id)
            new_resources.append(res)
        except Exception:
            pprint.pprint(res, stream=sys.stderr)
            raise
    new_resources.sort(key=lambda x: x["Name"])
    rg["Resources"] = {"Resource": singleton_list_to_value(new_resources)}

    new_rg = OrderedDict()

    for elem in ["GridType", "GroupID", "GroupName", "Disable", "Facility", "Site", "SupportCenter", "GroupDescription",
                 "Resources"]:
        if elem in rg:
            new_rg[elem] = rg[elem]

    return new_rg


def convert(indir, outfile=None):
    """Convert a directory tree of topology data into a single XML document.
    `indir` is the name of the directory tree. The document is written to a
    file at `outfile`, if `outfile` is specified.

    Returns the text of the XML document.
    """
    topology = Topology()
    root = Path(indir)

    support_center_name_to_id = anymarkup.parse_file(root / "support-centers.yaml")
    service_name_to_id = anymarkup.parse_file(root / "services.yaml")

    for facility_path in root.glob("*/FACILITY.yaml"):
        name = facility_path.parts[-2]
        id_ = anymarkup.parse_file(facility_path)["ID"]
        topology.add_facility(name, id_)

    for site_path in root.glob("*/*/SITE.yaml"):
        facility, name = site_path.parts[-3:-1]
        id_ = anymarkup.parse_file(site_path)["ID"]
        topology.add_site(facility, name, id_)

    for yaml_path in root.glob("*/*/*.yaml"):
        facility, site, name = yaml_path.parts[-3:]
        if name == "SITE.yaml": continue

        name = name.replace(".yaml", "")
        rg = anymarkup.parse_file(yaml_path)

        try:
            facility_id = topology.data[facility]["ID"]
            site_id = topology.data[facility][site]["ID"]
            rg["Facility"] = OrderedDict([("ID", facility_id), ("Name", facility)])
            rg["Site"] = OrderedDict([("ID", site_id), ("Name", site)])
            rg["GroupName"] = name

            topology.add_rg(facility, site, name, expand_resourcegroup(rg, service_name_to_id, support_center_name_to_id))
        except Exception as e:
            if not isinstance(e, RGError):
                raise RGError(rg) from e

    if outfile:
        topology.serialize_file(outfile)

    return topology.to_xml()


def main(argv=sys.argv):
    if len(argv) < 2:
        print("Usage: %s <input dir> [<output xml>]" % argv[0], file=sys.stderr)
        return 2
    indir = argv[1]
    outfile = None
    if len(argv) > 2:
        outfile = argv[2]

    try:
        xml = convert(indir, outfile)
        if not outfile:
            print(xml)
    except RGError as e:
        print("Error happened while processing RG:", file=sys.stderr)
        pprint.pprint(e.rg, stream=sys.stderr)
        raise

    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
