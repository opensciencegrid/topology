#!/usr/bin/env python3
"""Converts a directory tree containing resource topology data to a single
XML document.

Usage as a script:

    resourcegroup_yaml_to_xml.py <input directory> [<output file>] [<downtime output file>]

If output file not specified or downtime output file not specified, results are printed to stdout.

"""
from argparse import ArgumentParser

import os
import logging
import pprint
import sys
from pathlib import Path
import yaml


# thanks stackoverflow
if __name__ == "__main__" and __package__ is None:
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from webapp.common import ensure_list, to_xml, Filters, load_yaml_file
from webapp.contacts_reader import get_contacts_data
from webapp.topology import CommonData, Topology


log = logging.getLogger(__name__)


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


def get_rgsummary_rgdowntime(indir, contacts_file=None, authorized=False, strict=False):
    contacts_data = None
    if contacts_file:
        contacts_data = get_contacts_data(contacts_file)
    topology = get_topology(indir, contacts_data, strict=strict)
    filters = Filters()
    filters.past_days = -1
    return topology.get_resource_summary(authorized=authorized, filters=filters), \
           topology.get_downtimes(authorized=authorized, filters=filters)


def get_topology(indir="../topology", contacts_data=None, strict=False):
    root = Path(indir)
    support_centers = load_yaml_file(root / "support-centers.yaml")
    service_types = load_yaml_file(root / "services.yaml")
    tables = CommonData(contacts=contacts_data, service_types=service_types, support_centers=support_centers)
    topology = Topology(tables)

    for facility_path in root.glob("*/FACILITY.yaml"):
        name = facility_path.parts[-2]
        id_ = load_yaml_file(facility_path)["ID"]
        topology.add_facility(name, id_)
    for site_path in root.glob("*/*/SITE.yaml"):
        facility, name = site_path.parts[-3:-1]
        site_info = load_yaml_file(site_path)
        id_ = site_info["ID"]
        topology.add_site(facility, name, id_, site_info)
    for yaml_path in root.glob("*/*/*.yaml"):
        facility, site, name = yaml_path.parts[-3:]
        if name == "SITE.yaml": continue
        if name.endswith("_downtime.yaml"): continue

        name = name.replace(".yaml", "")
        try:
            rg = load_yaml_file(yaml_path)
        except yaml.YAMLError:
            if strict:
                raise
            else:
                # load_yaml_file() already logs the specific error
                log.error("skipping (non-strict mode)")
                continue
        downtime_yaml_path = yaml_path.with_name(name + "_downtime.yaml")
        downtimes = None
        if downtime_yaml_path.exists():
            try:
                downtimes = ensure_list(load_yaml_file(downtime_yaml_path))
            except yaml.YAMLError:
                if strict:
                    raise
                # load_yaml_file() already logs the specific error
                log.error("skipping (non-strict mode)")
                # keep going with downtimes=None

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
    parser.add_argument("--nostrict", action='store_false', dest='strict', help="Skip files with parse errors (instead of exiting)")
    args = parser.parse_args(argv[1:])

    rgsummary, rgdowntime = get_rgsummary_rgdowntime(args.indir, args.contacts,
                                                     authorized=True, strict=args.strict)
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

    return 0


if __name__ == '__main__':
    logging.basicConfig()
    sys.exit(main(sys.argv))
