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
from argparse import ArgumentParser

import anymarkup
import os
import pprint
import sys
from pathlib import Path

# thanks stackoverflow
if __name__ == "__main__" and __package__ is None:
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from webapp.common import ensure_list, to_xml, Filters
from webapp.contacts_reader import get_contacts_data
from webapp.topology import CommonData, Topology

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


def get_rgsummary_rgdowntime(indir, contacts_file=None, authorized=False):
    contacts_data = None
    if contacts_file:
        contacts_data = get_contacts_data(contacts_file)
    topology = get_topology(indir, contacts_data)
    filters = Filters()
    filters.past_days = -1
    return topology.get_resource_summary(authorized=authorized, filters=filters), \
           topology.get_downtimes(authorized=authorized, filters=filters)


def get_topology(indir="../topology", contacts_data=None):
    root = Path(indir)
    support_centers = anymarkup.parse_file(root / "support-centers.yaml")
    service_types = anymarkup.parse_file(root / "services.yaml")
    tables = CommonData(contacts=contacts_data, service_types=service_types, support_centers=support_centers)
    topology = Topology(tables)

    for facility_path in root.glob("*/FACILITY.yaml"):
        name = facility_path.parts[-2]
        id_ = anymarkup.parse_file(facility_path)["ID"]
        topology.add_facility(name, id_)
    for site_path in root.glob("*/*/SITE.yaml"):
        facility, name = site_path.parts[-3:-1]
        site_info = anymarkup.parse_file(site_path)
        id_ = site_info["ID"]
        topology.add_site(facility, name, id_, site_info)
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
                topology.add_downtime(site, name, downtime)

    return topology


def main(argv):
    parser = ArgumentParser()
    parser.add_argument("indir", help="input dir for topology data")
    parser.add_argument("outfile", nargs='?', default=None, help="output file for rgsummary")
    parser.add_argument("downtimefile", nargs='?', default=None, help="output file for rgdowntime")
    parser.add_argument("--contacts", help="contacts yaml file")
    args = parser.parse_args(argv[1:])

    try:
        rgsummary, rgdowntime = get_rgsummary_rgdowntime(args.indir, args.contacts,
                                                         authorized=True)
        if args.outfile:
            with open(args.outfile, "w") as fh:
                fh.write(to_xml(rgsummary))
        else:
            print(to_xml(rgsummary))
        if args.downtimefile:
            with open(args.downtimefile, "w") as fh:
                fh.write(to_xml(rgdowntime))
        else:
            print(to_xml(rgdowntime))
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
