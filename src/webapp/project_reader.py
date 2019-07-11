#!/usr/bin/env python3
from argparse import ArgumentParser
from collections import OrderedDict

import logging
import os
import pprint
import sys

import yaml

if __name__ == "__main__" and __package__ is None:
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from webapp.common import load_yaml_file, to_xml


log = logging.getLogger(__name__)


def get_projects(indir="../projects", strict=False):
    to_output = {"Projects":{"Project": []}}
    projects = []

    mapping = load_yaml_file(os.path.join(indir, "_CAMPUS_GRIDS.yaml"))

    for file in os.listdir(indir):
        if not file.endswith(".yaml"):
            continue
        elif file.endswith("_CAMPUS_GRIDS.yaml"):
            continue
        project = OrderedDict.fromkeys(["ID", "Name", "Description", "PIName", "Organization", "Department",
                                        "FieldOfScience", "Sponsor"])
        data = None
        try:
            data = load_yaml_file(os.path.join(indir, file))
            if 'CampusGrid' in data['Sponsor']:
                name = data['Sponsor']['CampusGrid']['Name']
                ID = mapping[name]
                data['Sponsor']['CampusGrid'] = OrderedDict([("ID", ID), ("Name", name)])
        except yaml.YAMLError:
            if strict:
                raise
            else:
                # load_yaml_file() already logs the specific error
                log.error("skipping (non-strict mode)")
                continue
        except Exception as e:
            log.error("%r adding project %s", e, file)
            log.error("Data:\n%s", pprint.pformat(data))
            if strict:
                raise
            log.exception("Skipping (non-strict mode); exception info follows")
            continue
        project.update(data)
        projects.append(project)

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
