#!/usr/bin/env python3

import glob
import os
import sys
from typing import Dict, List

_topdir = os.path.abspath(os.path.dirname(__file__) + "/../..")
sys.path.append(_topdir + "/src")

import webapp.models
from webapp.common import is_null
from webapp.vos_data import VOsData
from webapp.topology import ResourceGroup
from webapp import project_reader


def validate_project_file(
    project_fname: str,
    resource_groups: List[str],
    campus_grid_ids: Dict,
    vos_data: VOsData,
) -> List[str]:
    try:
        project = project_reader.get_one_project(
            project_fname, campus_grid_ids, vos_data
        )
    except Exception as err:
        return ["%s: exception while reading: %r" % (project_fname, err)]

    errors = []

    # Check 1: Check XRAC ResourceGroups are in topology
    if not is_null(project, "ResourceAllocation", "XRAC", "ResourceGroups", "ResourceGroup"):
        project_rgs = project["ResourceAllocation"]["XRAC"]["ResourceGroups"]["ResourceGroup"]
        project_rg_names = [x["Name"] for x in project_rgs]

        for rg in project_rg_names:
            if rg not in resource_groups:
                errors.append("%s: ResourceGroup '%s' not found in topology" % (project_fname, rg))

    return errors


def main():
    os.chdir(_topdir)
    global_data = webapp.models.GlobalData(strict=True)
    resource_groups: List[ResourceGroup] = global_data.get_topology().get_resource_group_list()
    resource_group_names = [x.name for x in resource_groups]
    vos_data = global_data.get_vos_data()
    campus_grid_ids = project_reader.get_campus_grid_ids("projects/")

    os.chdir("projects/")
    errors = []
    project_filenames = sorted(glob.glob("[!_]*.yaml"))
    for project_fname in project_filenames:
        errors += validate_project_file(
            project_fname, resource_group_names, campus_grid_ids, vos_data
        )

    print("%d project files processed." % len(project_filenames))
    if errors:
        print("%d errors encountered:" % len(errors))
        for e in errors:
            print(e, file=sys.stderr)
        return 1
    else:
        print("A-OK.")
        return 0


if __name__ == "__main__":
    sys.exit(main())
