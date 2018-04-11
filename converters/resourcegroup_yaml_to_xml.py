import urllib.parse

import anymarkup
import os
import pprint
import sys
from pathlib import Path
from typing import Dict, List, Union, Iterable

topdir = "/tmp/topology"
SCHEMA_LOCATION = "https://my.opensciencegrid.org/schema/rgsummary.xsd"


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

    def serialize(self) -> bytes:
        rgs = []
        for fval in self.data.values():
            for s, sval in fval.items():
                if s == "ID": continue
                for r, rval in sval.items():
                    if r == "ID": continue
                    rgs.append(rval)

        tree = {"ResourceSummary":
                    {"@xmlns:xsi": "http://www.w3.org/2001/XMLSchema-instance",
                     "@xsi:schemaLocation": SCHEMA_LOCATION,
                     "ResourceGroup": rgs}}
        return anymarkup.serialize(tree, "xml")

def singleton_list_to_value(a_list):
    if len(a_list) == 1:
        return a_list[0]
    return a_list


def expand_attr_list_single(data: Dict, namekey:str, valuekey: str) -> Union[Dict, List]:
    """
    Expand
        {"name1": "val1",
         "name2": "val2"}
    to
        [{namekey: "name1", valuekey: "val1"},
         {namekey: "name2", valuekey: "val2"}]
    or, if there's only one,
        {namekey: "name1", valuekey: "val1"}
    """
    newdata = []
    for name, value in data.items():
        newdata.append({namekey: name, valuekey: value})
    return singleton_list_to_value(newdata)


def expand_attr_list(data: Dict, namekey: str) -> Union[Dict, List]:
    """
    Expand
        {"name1": {"attr1": "val1", ...},
         "name2": {"attr1": "val1", ...}}
    to
        [{namekey: "name1", "attr1": "val1", ...},
         {namekey: "name2", "attr1": "val1", ...}]}
    or, if there's only one,
        {namekey: "name1", "attr1": "val1", ...}
    """
    newdata = []
    for name, value in data.items():
        value = dict(value)
        value[namekey] = name
        newdata.append(value)
    return singleton_list_to_value(newdata)


def expand_services(services: Dict) -> Dict:
    return {"Service": expand_attr_list(services, "Name")}


def get_charturl(ownership: Iterable) -> str:
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


def expand_voownership(voownership: Dict) -> Dict:
    return {
        "Ownership": expand_attr_list_single(voownership, "VO", "Percent"),
        "ChartURL": get_charturl(voownership.items())
    }


def expand_contactlists(contactlists: Dict) -> Dict:
    new_contactlists = []
    for contact_type, contact_data in contactlists.items():
        contact_data = expand_attr_list_single(contact_data, "ContactRank", "Name")
        new_contactlists.append({"ContactType": contact_type, "Contacts": {"Contact": contact_data}})
    return {"ContactList": singleton_list_to_value(new_contactlists)}


def expand_resource(name: str, res: Dict) -> Dict:
    res = dict(res)

    res["Services"] = expand_services(res["Services"])
    if res["VOOwnership"] and isinstance(res["VOOwnership"], dict):
        res["VOOwnership"] = expand_voownership(res["VOOwnership"])
    else:
        res["VOOwnership"] = "(Information not available)"
    if res["FQDNAliases"]:
        res["FQDNAliases"] = singleton_list_to_value(
            [{"FQDNAlias": a} for a in res["FQDNAliases"]]
        )
    if res["ContactLists"]:
        res["ContactLists"] = expand_contactlists(res["ContactLists"])
    res["Name"] = name
    if len(res["WLCGInformation"]) == 1:
        res["WLCGInformation"] = "(Information not available)"

    return res


def expand_resourcegroup(rg):
    rg = dict(rg)  # copy

    rg["SupportCenter"] = {"Name": rg["SupportCenterName"], "ID": rg["SupportCenterID"]}
    del rg["SupportCenterName"], rg["SupportCenterID"]

    new_resources = []
    for name, res in rg["Resources"].items():
        try:
            res = expand_resource(name, res)
            new_resources.append(res)
        except Exception:
            pprint.pprint(res, stream=sys.stderr)
            raise
    rg["Resources"] = {"Resource": singleton_list_to_value(new_resources)}

    return rg


paths = []
topology = Topology()

root = Path(topdir)
for facility_path in root.glob("*/FACILITY.yml"):
    name = facility_path.parts[-2]
    id_ = anymarkup.parse_file(facility_path)["ID"]
    topology.add_facility(name, id_)

for site_path in root.glob("*/*/SITE.yml"):
    facility, name = site_path.parts[-3:-1]
    id_ = anymarkup.parse_file(site_path)["ID"]
    topology.add_site(facility, name, id_)

for yaml_path in root.glob("*/*/*.yml"):
    facility, site, name = yaml_path.parts[-3:]
    if name == "SITE.yml": continue

    name = name.replace(".yml", "")
    rg = anymarkup.parse_file(yaml_path)

    facility_id = topology.data[facility]["ID"]
    site_id = topology.data[facility][site]["ID"]
    rg["Facility"] = {"Name": facility, "ID": facility_id}
    rg["Site"] = {"Name": site, "ID": site_id}
    rg["GroupName"] = name

    topology.add_rg(facility, site, name, expand_resourcegroup(rg))

print(topology.serialize().decode("utf-8", "ignore"))
