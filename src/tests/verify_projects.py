#!/usr/bin/env python3

import glob
import os
import sys
from typing import Dict, List, Optional, Set

_topdir = os.path.abspath(os.path.dirname(__file__) + "/../..")
sys.path.append(_topdir + "/src")

from webapp.common import is_null
from webapp.models import GlobalData
from webapp.vos_data import VOsData
from webapp.topology import Resource, ResourceGroup
from webapp import project_reader


class Validation:
    global_data: GlobalData
    resource_groups: List[ResourceGroup]
    resource_group_names: Set[str]
    vos_data: VOsData
    campus_grid_ids: Dict[str, int]
    project_filenames: List[str]

    def __init__(self, topdir):
        """Constructor; loads VO and Resource Data and campus grid IDs.
        Does not load the project data, only gets a list of filenames;
        for validation, we want to load the files ourselves, one at a time.

        """
        self.global_data = GlobalData(config={"TOPOLOGY_DATA_DIR": topdir}, strict=True)
        self.resource_groups = self.global_data.get_topology().get_resource_group_list()
        self.resource_group_names = {x.name for x in self.resource_groups}
        self.vos_data = self.global_data.get_vos_data()
        projects_dir = self.global_data.projects_dir
        self.campus_grid_ids = project_reader.get_campus_grid_ids(projects_dir)
        self.project_filenames = glob.glob(os.path.join(projects_dir, "[!_]*.yaml"))

    def validate_project_file(self, project_filename: str) -> List[str]:
        """Validate one project file, returning a list of error messages for problems found with that file.

        Current validations are for ResourceAllocations:
        1. Check ResourceGroups are in the topology tree
        2. Check AllowedSchedds are Resources with "Submit Node" services

        """
        project_filebn = os.path.basename(project_filename)
        try:
            project = project_reader.get_one_project(
                project_filename, self.campus_grid_ids, self.vos_data
            )
        except Exception as err:
            return ["%s: exception while reading: %r" % (project_filebn, err)]

        errors = []

        if not is_null(project, "ResourceAllocations", "ResourceAllocation"):
            for resource_allocation in project["ResourceAllocations"]["ResourceAllocation"]:

                # Check 1
                if not is_null(resource_allocation, "ExecuteResourceGroups", "ExecuteResourceGroup"):
                    project_ergs = resource_allocation["ExecuteResourceGroups"]["ExecuteResourceGroup"]
                    project_erg_names = {x["GroupName"] for x in project_ergs}

                    errors.extend([
                        f"{project_filebn}: ExecuteResourceGroup '{missing}' not found in topology"
                        for missing in (project_erg_names - self.resource_group_names)
                    ])

                # Check 2
                if not is_null(resource_allocation, "SubmitResources", "SubmitResource"):
                    project_schedd_names = resource_allocation["SubmitResources"]["SubmitResource"]
                    for sn in project_schedd_names:
                        resource = self._get_resource_by_name(sn)
                        if not resource:
                            errors.append(
                                "%s: SubmitResource '%s' not found in topology"
                                % (project_filebn, sn)
                            )
                        elif "Submit Node" not in resource.service_names:
                            errors.append(
                                "%s: SubmitResource '%s' does not provide a Submit Node"
                                % (project_filebn, sn)
                            )

        return errors

    def _get_resource_by_name(self, name: str) -> Optional[Resource]:
        for group in self.resource_groups:
            if name in group.resources_by_name:
                return group.resources_by_name[name]
        else:
            return None


def main():
    validation = Validation(topdir=_topdir)

    errors = []
    for project_fname in validation.project_filenames:
        errors += validation.validate_project_file(project_fname)

    print("%d project files processed." % len(validation.project_filenames))
    if errors:
        print("%d errors encountered:" % len(errors))
        for e in errors:
            print("ERROR: %s" % e, file=sys.stderr)
        return 1
    else:
        print("A-OK.")
        return 0


if __name__ == "__main__":
    sys.exit(main())
