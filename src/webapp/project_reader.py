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


def get_resource_allocation(ra: Dict, idx: int) -> OrderedDict:
    new_ra = OrderedDict()
    for attrib in ["SubmitResources", "ExecuteResourceGroups", "Type"]:
        if is_null(ra, attrib):
            raise DataError(f"Missing ResourceAllocations[{idx}].{attrib}")

    new_ra["Type"] = ra["Type"]

    new_ra["SubmitResources"] = {"SubmitResource": ra["SubmitResources"]}

    new_ergs = []
    for erg in ra["ExecuteResourceGroups"]:
        new_erg = OrderedDict()
        new_erg["GroupName"] = erg["GroupName"]
        new_erg["LocalAllocationID"] = erg["LocalAllocationID"]
        new_ergs.append(new_erg)
    new_ra["ExecuteResourceGroups"] = {"ExecuteResourceGroup": new_ergs}

    return new_ra


def get_one_project(file: str, campus_grid_ids: Dict, vos_data: VOsData) -> Dict:
    project = OrderedDict.fromkeys(["ID", "Name", "Description", "PIName", "Organization", "Department",
                                    "FieldOfScience", "Sponsor", "ResourceAllocations"])
    data = None
    try:
        data = load_yaml_file(file)
        if 'Sponsor' in data:
            if 'CampusGrid' in data['Sponsor']:
                name = data['Sponsor']['CampusGrid']['Name']
                ID = campus_grid_ids[name]
                data['Sponsor']['CampusGrid'] = OrderedDict([("ID", ID), ("Name", name)])
            elif 'VirtualOrganization' in data['Sponsor']:
                name = data['Sponsor']['VirtualOrganization']['Name']
                ID = vos_data.vos[name]['ID']
                data['Sponsor']['VirtualOrganization'] = OrderedDict([("ID", ID), ("Name", name)])

        if 'ResourceAllocations' in data:
            resource_allocations = [get_resource_allocation(ra, idx) for idx, ra in enumerate(data['ResourceAllocations'])]
            data['ResourceAllocations'] = {"ResourceAllocation": resource_allocations}
        if 'ID' not in data:
            del project['ID']

        name_from_filename = os.path.basename(file)[:-5]  # strip '.yaml'
        if not is_null(data, 'Name'):
            if data['Name'] != name_from_filename:
                log.warning("%s: 'Name' %r does not match filename" % (file, data['Name']))
        else:
            data['Name'] = name_from_filename

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
