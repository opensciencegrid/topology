#!/usr/bin/env python3
"""Converts a directory tree containing resource topology data to a single
XML document.

Usage as a script:

    resourcegroup_yaml_to_xml.py <input directory> [<output file>] [<downtime output file>]

If output file not specified or downtime output file not specified, results are printed to stdout.

Usage as a module

    from converters.resourcegroup_yaml_to_xml import get_rgsummary_rgdowntime_xml
    rgsummary_xml, rgdowntime_xml = get_rgsummary_rgdowntime_xml(input_dir[, output_file, downtime_output_file])

where the return value `xml` is a string.

"""
import argparse
import urllib.parse
from argparse import ArgumentParser

import anymarkup
import re
from collections import OrderedDict
from datetime import datetime, timezone
import pprint
import sys
from pathlib import Path
from typing import Dict, Iterable, Union

import dateparser

try:
    from convertlib import is_null, expand_attr_list_single, expand_attr_list, to_xml, to_xml_file, ensure_list
except ModuleNotFoundError:
    from .convertlib import is_null, expand_attr_list_single, expand_attr_list, to_xml, to_xml_file, ensure_list

RG_SCHEMA_LOCATION = "https://my.opensciencegrid.org/schema/rgsummary.xsd"
DOWNTIME_SCHEMA_LOCATION = "https://my.opensciencegrid.org/schema/rgdowntime.xsd"


class RGError(Exception):
    """An error with converting a specific RG"""
    def __init__(self, rg, *args, **kwargs):
        Exception.__init__(self, *args, **kwargs)
        self.rg = rg


class DowntimeError(Exception):
    """An error with converting a specific piece of downtime info"""
    def __init__(self, downtime, rg, *args, **kwargs):
        Exception.__init__(self, *args, **kwargs)
        self.downtime = downtime
        self.rg = rg


class TopologyError(Exception): pass


class Topology(object):
    def __init__(self, service_types: Dict, support_centers: Dict):
        self.data = {}
        self.past_downtimes = []
        self.current_downtimes = []
        self.future_downtimes = []
        self.service_types = service_types
        self.support_centers = support_centers

    def add_rg(self, facility, site, rgname, rgdata):
        if facility not in self.data:
            raise TopologyError("Unknown facility %s -- call add_facility first" % facility)
        if site not in self.data[facility]:
            raise TopologyError("Unknown site %s in facility %s -- call add_site first" % (site, facility))
        if rgname not in self.data[facility][site]:
            self.data[facility][site][rgname] = self._expand_rg(facility, site, rgname, rgdata)

    def add_facility(self, name, id):
        if name not in self.data:
            self.data[name] = {}
        self.data[name]["ID"] = id

    def add_site(self, facility, name, id):
        if facility not in self.data:
            raise TopologyError("Unknown facility %s -- call add_facility first" % facility)
        if name not in self.data[facility]:
            self.data[facility][name] = {}
        self.data[facility][name]["ID"] = id

    def _expand_rg(self, facility: str, site: str, rgname: str, rg: Dict) -> OrderedDict:
        """Expand a single ResourceGroup from the format in a yaml file to the xml format.

        {"SupportCenterName": ...} and {"SupportCenterID": ...} are turned into
        {"SupportCenter": {"Name": ...}, {"ID": ...}} and each individual Resource is expanded and collected in a
        <Resources> block.

        Return the data structure for the expanded ResourceGroup, as an OrderedDict,
        with the ordering to fit the xml schema for rgsummary.
        """
        rg = dict(rg)  # copy

        facility_id = self.data[facility]["ID"]
        site_id = self.data[facility][site]["ID"]

        rg["Facility"] = OrderedDict([("ID", facility_id), ("Name", facility)])
        rg["Site"] = OrderedDict([("ID", site_id), ("Name", site)])
        rg["GroupName"] = rgname

        scname, scid = rg["SupportCenter"], self.support_centers[rg["SupportCenter"]]
        rg["SupportCenter"] = OrderedDict([("ID", scid), ("Name", scname)])

        new_resources = []
        for name, res in rg["Resources"].items():
            try:
                res = self._expand_resource(name, res)
                new_resources.append(res)
            except Exception:
                pprint.pprint(res, stream=sys.stderr)
                raise
        new_resources.sort(key=lambda x: x["Name"])
        rg["Resources"] = {"Resource": new_resources}

        new_rg = OrderedDict()

        for elem in ["GridType", "GroupID", "GroupName", "Disable", "Facility", "Site", "SupportCenter",
                     "GroupDescription",
                     "Resources"]:
            if elem in rg:
                new_rg[elem] = rg[elem]

        return new_rg

    def _expand_resource(self, name: str, res: Dict) -> OrderedDict:
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
            res["Services"] = self._expand_services(res["Services"])
        else:
            res.pop("Services", None)
        if "VOOwnership" in res:
            res["VOOwnership"] = self._expand_voownership(res["VOOwnership"])
        if "FQDNAliases" in res:
            res["FQDNAliases"] = {"FQDNAlias": res["FQDNAliases"]}
        if not is_null(res, "ContactLists"):
            res["ContactLists"] = self._expand_contactlists(res["ContactLists"])
        res["Name"] = name
        if "WLCGInformation" in res and isinstance(res["WLCGInformation"], dict):
            res["WLCGInformation"] = self._expand_wlcginformation(res["WLCGInformation"])
        new_res = OrderedDict()
        for elem in ["ID", "Name", "Active", "Disable", "Services", "Description", "FQDN", "FQDNAliases", "VOOwnership",
                     "WLCGInformation", "ContactLists"]:
            if elem in res:
                new_res[elem] = res[elem]
            elif elem in defaults:
                new_res[elem] = defaults[elem]

        return new_res

    def _expand_services(self, services: Dict) -> Dict:
        services_list = expand_attr_list(services, "Name", ordering=["Name", "Description", "Details"])
        for svc in services_list:
            svc["ID"] = self.service_types[svc["Name"]]
            svc.move_to_end("ID", last=False)
        return {"Service": services_list}

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

    @staticmethod
    def _expand_voownership(voownership: Dict) -> OrderedDict:
        """Return the data structure for an expanded VOOwnership for a single Resource."""

        def _get_charturl(ownership):
            # Return a URL for a pie chart based on (VO, Percent) pairs.
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

        voo = voownership.copy()
        totalpercent = sum(voo.values())
        if totalpercent < 100:
            voo["(Other)"] = 100 - totalpercent
        return OrderedDict([
            ("Ownership", expand_attr_list_single(voo, "VO", "Percent", name_first=False)),
            ("ChartURL", _get_charturl(voownership.items()))
        ])

    @staticmethod
    def _expand_contactlists(contactlists: Dict) -> Dict:
        """Return the data structure for an expanded ContactLists for a single Resource."""
        new_contactlists = []
        for contact_type, contact_data in contactlists.items():
            contact_data = expand_attr_list_single(contact_data, "ContactRank", "Name", name_first=False)
            new_contactlists.append(
                OrderedDict([("ContactType", contact_type), ("Contacts", {"Contact": contact_data})]))
        return {"ContactList": new_contactlists}

    @staticmethod
    def _expand_wlcginformation(wlcg: Dict) -> OrderedDict:
        defaults = {
            "AccountingName": None,
            "InteropBDII": False,
            "LDAPURL": None,
            "TapeCapacity": 0,
        }

        new_wlcg = OrderedDict()
        for elem in ["InteropBDII", "LDAPURL", "InteropMonitoring", "InteropAccounting", "AccountingName", "KSI2KMin",
                     "KSI2KMax", "StorageCapacityMin", "StorageCapacityMax", "HEPSPEC", "APELNormalFactor",
                     "TapeCapacity"]:
            if elem in wlcg:
                new_wlcg[elem] = wlcg[elem]
            elif elem in defaults:
                new_wlcg[elem] = defaults[elem]
        return new_wlcg

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
                 "@xsi:schemaLocation": RG_SCHEMA_LOCATION,
                 "ResourceGroup": rgs}}

    def get_downtimes(self) -> Dict:
        return {"Downtimes":
                    {"@xsi:schemaLocation": DOWNTIME_SCHEMA_LOCATION,
                     "@xmlns:xsi": "http://www.w3.org/2001/XMLSchema-instance",
                     "PastDowntimes": {"Downtime": self.past_downtimes},
                     "CurrentDowntimes": {"Downtime": self.current_downtimes},
                     "FutureDowntimes": {"Downtime": self.future_downtimes}}}

    def to_xml(self):
        return to_xml(self.get_resource_summary())

    def serialize_file(self, outfile):
        return to_xml_file(self.get_resource_summary(), outfile)

    @staticmethod
    def _parsetime(time_str: str) -> datetime:
        # get rid of stupid times like "00:00 AM" or "17:00 PM"
        if re.search(r"\s+00:\d\d\s+AM", time_str):
            time_str = time_str.replace(" AM", "")
        elif re.search(r"\s+(1[3-9]|2[0-3]):\d\d\s+PM", time_str):
            time_str = time_str.replace(" PM", "")
        time = dateparser.parse(time_str)
        if not time:
            raise ValueError("Invalid time %s" % time_str)
        if not time.tzinfo:
            time = time.replace(tzinfo=timezone.utc)
        return time

    def add_downtime(self, facility: str, site: str, rgname: str, downtime: Dict):
        downtime_expanded = self._expand_downtime(facility, site, rgname, downtime)
        if downtime_expanded is None:
            return
        start_time = self._parsetime(downtime_expanded["StartTime"])
        end_time = self._parsetime(downtime_expanded["EndTime"])
        current_time = datetime.now(timezone.utc)
        # ^ not to be confused with datetime.utcnow(), which does not include tz info in the result

        if end_time < current_time:
            self.past_downtimes.append(downtime_expanded)
        elif start_time > current_time:
            self.future_downtimes.append(downtime_expanded)
        else:
            self.current_downtimes.append(downtime_expanded)

    def _expand_downtime(self, facility: str, site: str, rgname: str, downtime: Dict) -> Union[OrderedDict, None]:
        rg_expanded = self.data[facility][site][rgname]
        new_downtime = OrderedDict.fromkeys(["ID", "ResourceID", "ResourceGroup", "ResourceName", "ResourceFQDN",
                                             "StartTime", "EndTime", "Class", "Severity", "CreatedTime", "UpdateTime",
                                             "Services", "Description"])
        new_downtime["ResourceGroup"] = OrderedDict([("GroupName", rg_expanded["GroupName"]),
                                                     ("GroupID", rg_expanded["GroupID"])])
        resources = ensure_list(rg_expanded["Resources"]["Resource"])
        for r in resources:
            if r["Name"] == downtime["ResourceName"]:
                new_downtime["ResourceFQDN"] = r["FQDN"]
                new_downtime["ResourceID"] = r["ID"]
                new_downtime["ResourceName"] = r["Name"]
                services = ensure_list(r["Services"]["Service"])
                break
        else:
            # print("Resource %s does not exist" % downtime["ResourceName"], file=sys.stderr)
            return None

        new_services = []
        for dts in downtime["Services"]:
            for s in services:
                if s["Name"] == dts:
                    new_services.append(OrderedDict([
                        ("ID", s["ID"]),
                        ("Name", s["Name"]),
                        ("Description", s["Description"])
                    ]))
                    break
            else:
                # print("Service %s does not exist in resource %s" % (dts, downtime["ResourceName"]), file=sys.stderr)
                pass

        if new_services:
            new_downtime["Services"] = {"Service": new_services}
        else:
            # print("No existing services listed for downtime; skipping downtime")
            return None

        new_downtime["CreatedTime"] = "Not Available"
        new_downtime["UpdateTime"] = "Not Available"

        for k in ["ID", "StartTime", "EndTime", "Class", "Severity", "Description"]:
            new_downtime[k] = downtime[k]

        return new_downtime


def get_rgsummary_rgdowntime_xml(indir="topology", outfile=None, downtime_outfile=None):
    """Convert a directory tree of topology data into a single XML document.
    `indir` is the name of the directory tree. The document is written to a
    file at `outfile`, if `outfile` is specified.

    Returns the text of the XML document.
    """
    rgsummary, rgdowntime = get_rgsummary_rgdowntime(indir)

    if outfile:
        to_xml_file(rgsummary, outfile)
    if downtime_outfile:
        to_xml_file(rgdowntime, downtime_outfile)

    return to_xml(rgsummary), to_xml(rgdowntime)


def get_rgsummary_rgdowntime(indir="topology"):
    root = Path(indir)
    support_centers = anymarkup.parse_file(root / "support-centers.yaml")
    service_types = anymarkup.parse_file(root / "services.yaml")
    topology = Topology(service_types, support_centers)
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
        if name.endswith("_downtime.yaml"): continue

        name = name.replace(".yaml", "")
        rg = anymarkup.parse_file(yaml_path)
        downtime_yaml_path = yaml_path.with_name(name + "_downtime.yaml")
        downtimes = None
        if downtime_yaml_path.exists():
            downtimes = ensure_list(anymarkup.parse_file(downtime_yaml_path))

        topology.add_rg(facility, site, name, rg)
        if downtimes:
            for downtime in downtimes:
                topology.add_downtime(facility, site, name, downtime)

    return topology.get_resource_summary(), topology.get_downtimes()


def main(argv):
    parser = ArgumentParser()
    parser.add_argument("indir", help="input dir for topology data")
    parser.add_argument("outfile", nargs='?', type=argparse.FileType('w'), default=sys.stdout, help="output file for rgsummary")
    parser.add_argument("downtimefile", nargs='?', type=argparse.FileType('w'), default=sys.stdout, help="output file for rgdowntime")
    args = parser.parse_args(argv[1:])

    try:
        rgsummary_xml, rgdowntime_xml = get_rgsummary_rgdowntime_xml(args.indir)
        print(rgsummary_xml, file=args.outfile)
        print(rgdowntime_xml, file=args.downtimefile)
    except RGError as e:
        print("Error happened while processing RG:", file=sys.stderr)
        pprint.pprint(e.rg, stream=sys.stderr)
        raise
    except DowntimeError as e:
        print("Error happened while processing downtime:", file=sys.stderr)
        pprint.pprint(e.downtime, stream=sys.stderr)
        print("RG:", file=sys.stderr)
        pprint.pprint(e.rg, stream=sys.stderr)
        raise

    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
