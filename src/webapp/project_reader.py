#!/usr/bin/env python3
from argparse import ArgumentParser
from collections import OrderedDict

import logging
import os
import pprint
import sys
from typing import Dict

import yaml

if __name__ == "__main__" and __package__ is None:
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from webapp.common import load_yaml_file, to_xml, is_null
from webapp.vo_reader import get_vos_data
from webapp.vos_data import VOsData


log = logging.getLogger(__name__)


class DataError(Exception): pass


def get_resource_allocation(data):
    if "ResourceAllocation" not in data:
        return
    ra = OrderedDict()
    if not is_null(data, "ResourceAllocation", "XRAC"):
        xrac = data["ResourceAllocation"]["XRAC"]
        if is_null(xrac, "AllowedSchedds"):
            raise DataError("Missing ResourceAllocation/XRAC/AllowedSchedds")
        if is_null(xrac, "ResourceGroups"):
            raise DataError("Missinc ResourceAllocation/XRAC/ResourceGroups")
        new_xrac = OrderedDict()
        new_xrac["AllowedSchedds"] = {"AllowedSchedd": xrac["AllowedSchedds"]}
        new_rgs = []
        for rg in xrac["ResourceGroups"]:
            new_rg = OrderedDict()
            new_rg["Name"] = rg["Name"]
            new_rg["LocalAllocationID"] = rg["LocalAllocationID"]
            new_rgs.append(new_rg)
        new_xrac["ResourceGroups"] = {"ResourceGroup": new_rgs}
        ra["XRAC"] = new_xrac
    return ra


def get_one_project(file: str, campus_grid_ids: Dict, vos_data: VOsData) -> Dict:
    project = OrderedDict.fromkeys(["ID", "Name", "Description", "PIName", "Organization", "Department",
                                    "FieldOfScience", "Sponsor", "ResourceAllocation"])
    data = None
    try:
        data = load_yaml_file(file)
        if 'CampusGrid' in data['Sponsor']:
            name = data['Sponsor']['CampusGrid']['Name']
            ID = campus_grid_ids[name]
            data['Sponsor']['CampusGrid'] = OrderedDict([("ID", ID), ("Name", name)])
        elif 'VirtualOrganization' in data['Sponsor']:
            name = data['Sponsor']['VirtualOrganization']['Name']
            ID = vos_data.vos[name]['ID']
            data['Sponsor']['VirtualOrganization'] = OrderedDict([("ID", ID), ("Name", name)])

        if 'ResourceAllocation' in data:
            data['ResourceAllocation'] = get_resource_allocation(data)
    except Exception as e:
        log.error("%r adding project %s", e, file)
        log.error("Data:\n%s", pprint.pformat(data))
        raise
    project.update(data)
    return project


def get_campus_grid_ids(indir="."):
    return load_yaml_file(os.path.join(indir, "_CAMPUS_GRIDS.yaml"))


def get_projects(indir="../projects", strict=False):
    to_output = {"Projects":{"Project": []}}
    projects = []

    campus_grid_ids = get_campus_grid_ids(indir)
    vos_data = get_vos_data(os.path.join(indir, "../virtual-organizations"), None)

    for file in os.listdir(indir):
        if not file.endswith(".yaml"):
            continue
        elif file.endswith("_CAMPUS_GRIDS.yaml"):
            continue
        try:
            project = get_one_project(os.path.join(indir, file), campus_grid_ids, vos_data)
            projects.append(project)
        except yaml.YAMLError:
            if strict:
                raise
            else:
                # load_yaml_file() already logs the specific error
                log.error("skipping (non-strict mode)")
                continue
        except Exception as e:
            if strict:
                raise
            log.exception("Skipping (non-strict mode); exception info follows")
            continue

    to_output["Projects"]["Project"] = projects

    return to_output


def get_projects_xml(indir="../projects", strict=False):
    """Returns the serialized XML as a string"""
    return to_xml(get_projects(indir, strict=strict))


if __name__ == "__main__":
    logging.basicConfig()
    parser = ArgumentParser()
    parser.add_argument("indir", help="input dir for projects data")
    parser.add_argument("outfile", nargs='?', default=None, help="output file for miscproject")
    parser.add_argument("--nostrict", action='store_false', dest='strict', help="Skip files with parse errors (instead of exiting)")
    args = parser.parse_args()

    xml = get_projects_xml(args.indir, strict=args.strict)
    if args.outfile:
        with open(args.outfile, "w") as fh:
            fh.write(xml)
    else:
        print(xml)
