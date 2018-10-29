#!/usr/bin/env python3
from argparse import ArgumentParser
from collections import OrderedDict

import os
import sys

if __name__ == "__main__" and __package__ is None:
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from webapp.common import load_yaml_file, to_xml


def get_projects(indir="../projects"):
    to_output = {"Projects":{"Project": []}}
    projects = []

    for file in os.listdir(indir):
        if not file.endswith(".yaml"):
            continue
        project = OrderedDict.fromkeys(["ID", "Name", "Description", "PIName", "Organization", "Department",
                                        "FieldOfScience", "Sponsor"])
        project.update(load_yaml_file(os.path.join(indir, file)))
        projects.append(project)

    to_output["Projects"]["Project"] = projects

    return to_output


def get_projects_xml(indir="../projects"):
    """Returns the serialized XML as a string"""
    return to_xml(get_projects(indir))


if __name__ == "__main__":
    # We are running as the main script
    parser = ArgumentParser()
    parser.add_argument("indir", help="input dir for projects data")
    parser.add_argument("outfile", nargs='?', default=None, help="output file for vosummary")
    args = parser.parse_args()

    xml = get_projects_xml(args.indir)
    if args.outfile:
        with open(args.outfile, "w") as fh:
            fh.write(xml)
    else:
        print(xml)
