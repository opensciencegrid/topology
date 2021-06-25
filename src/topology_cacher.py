#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Download resource and project XML data from Topology;
use the data to create a JSON file for looking up resource allocations for projects,
and save everything in a local directory.
"""
from argparse import ArgumentParser
from collections import namedtuple
import json
import logging
import os
import sys
import time
import xml.etree.ElementTree as ET


from urllib.request import urlopen

from typing import Tuple, Optional


TOPOLOGY = "https://topology.opensciencegrid.org"
PROJECTS_CACHE_LIFETIME = 300.0
RESOURCES_CACHE_LIFETIME = 300.0
RETRY_DELAY = 60.0


log = logging.getLogger(__name__)


class ResourceInfo(namedtuple("ResourceInfo", "group_name name fqdn service_ids")):
    SERVICE_ID_CE = "1"
    SERVICE_ID_SCHEDD = "109"

    def is_ce(self):
        return self.SERVICE_ID_CE in self.service_ids

    def is_schedd(self):
        return self.SERVICE_ID_SCHEDD in self.service_ids


# took this code from Topology
class CachedData:
    def __init__(
        self,
        data=None,
        timestamp=0.0,
        force_update=True,
        cache_lifetime=60.0 * 15,
        retry_delay=60.0,
    ):
        self.data = data
        self.timestamp = timestamp
        self.force_update = force_update
        self.cache_lifetime = cache_lifetime
        self.retry_delay = retry_delay
        self.next_update = self.timestamp + self.cache_lifetime

    def should_update(self):
        return self.force_update or not self.data or time.time() > self.next_update

    def try_again(self):
        self.next_update = time.time() + self.retry_delay

    def update(self, data):
        self.data = data
        self.timestamp = time.time()
        self.next_update = self.timestamp + self.cache_lifetime
        self.force_update = False


class TopologyData:
    def __init__(
        self,
        topology_host=TOPOLOGY,
        projects_cache_lifetime=PROJECTS_CACHE_LIFETIME,
        resources_cache_lifetime=RESOURCES_CACHE_LIFETIME,
        retry_delay=RETRY_DELAY,
    ):
        self.topology_host = topology_host
        self.retry_delay = retry_delay
        self.projects_cache = CachedData(
            cache_lifetime=projects_cache_lifetime, retry_delay=retry_delay
        )
        self.resources_cache = CachedData(
            cache_lifetime=resources_cache_lifetime, retry_delay=retry_delay
        )
        self.resinfo_table = []
        self.grouped_resinfo = {}
        self.resinfo_by_name = {}
        self.resinfo_by_fqdn = {}

    def get_projects(self) -> Optional[ET.Element]:
        data, _ = self._get_data(self.projects_cache, "/miscproject/xml", "projects")
        return data

    def get_resources(self) -> Optional[ET.Element]:
        data, updated = self._get_data(
            self.resources_cache, "/rgsummary/xml", "resources"
        )
        if updated and data:
            self.resinfo_table = []
            self.grouped_resinfo = {}
            self.resinfo_by_name = {}
            self.resinfo_by_fqdn = {}

            #
            # Build tables and indices for easier lookup
            #
            for eResourceGroup in data.findall("./ResourceGroup"):
                group_name = safe_element_text(eResourceGroup.find("./GroupName"))
                if not group_name:
                    log.warning(
                        "Skipping malformed ResourceGroup: %s", elem2str(eResourceGroup)
                    )
                    continue
                self.grouped_resinfo[group_name] = []

                for eResource in eResourceGroup.findall("./Resources/Resource"):
                    resource_name = safe_element_text(eResource.find("./Name"))
                    fqdn = safe_element_text(eResource.find("./FQDN"))
                    service_ids = list(
                        filter(
                            None,
                            [
                                safe_element_text(svc)
                                for svc in eResource.findall("./Services/Service/ID")
                            ],
                        )
                    )
                    if not resource_name or not fqdn or not service_ids:
                        log.warning(
                            "Skipping malformed Resource: %s", elem2str(eResource)
                        )
                        continue
                    resinfo = ResourceInfo(group_name, resource_name, fqdn, service_ids)
                    self.resinfo_table.append(resinfo)
                    self.grouped_resinfo[group_name].append(resinfo)
                    self.resinfo_by_name[resource_name] = resinfo
                    self.resinfo_by_fqdn[fqdn] = resinfo

        return data

    def get_project_resource_allocations(self):
        """Convert
        <Projects>
            <Project>
                <Name>MyProject</Name>
                <ResourceAllocations>
                    <ResourceAllocation>
                    <Type>Other</Type>
                    <SubmitResources>
                        <SubmitResource>Submit1</SubmitResource>
                        <SubmitResource>Submit2</SubmitResource>
                    </SubmitResources>
                    <ExecuteResourceGroups>
                        <ExecuteResourceGroup>
                            <GroupName>ExampleNetCEs</GroupName>
                            <LocalAllocationID>ID1</LocalAllocationID>
                        </ExecuteResourceGroup>
                    </ExecuteResourceGroups>
                    </ResourceAllocation>
                </ResourceAllocations>
            </Project>
        </Projects>

        into

        {
            "MyProject": [
                {
                    "type": "Other",
                    "submit_resources": [
                        { "group_name": "ExampleNetSubmits", "name": "Submit1", "fqdn": "submit1.example.net" },
                        { "group_name": "ExampleNetSubmits", "name": "Submit2", "fqdn": "submit2.example.net" }
                    ],
                    "execute_resource_groups": [
                        {
                            "group_name": "ExampleNetCEs",
                            "local_allocation_id": "ID1",
                            "ces": [
                                { "name": "CE1", "fqdn": "ce1.example.net" }
                                { "name": "CE2", "fqdn": "ce2.example.net" }
                            ]
                        }
                    ]
                }
            ]
        }

        looking up resource name, group name, ces, and fqdn info from the rg summary.
        """
        eProjects = self.get_projects()
        eResourceSummary = self.get_resources()
        if not eProjects or not eResourceSummary:
            return {}

        ret = {}
        for eProject in eProjects.findall("./Project"):
            project_name = safe_element_text(eProject.find("./Name"))
            if not project_name:
                log.warning("Skipping malformed Project: %s", elem2str(eProject))
                continue

            ret[project_name] = allocations = []
            for eResourceAllocation in eProject.findall(
                "./ResourceAllocations/ResourceAllocation"
            ):
                allocation = {}

                #
                # Get ResourceAllocation elements and verify they're nonempty
                #
                type_ = safe_element_text(eResourceAllocation.find("./Type"))
                eExecuteResourceGroup_list = eResourceAllocation.findall(
                    "./ExecuteResourceGroups/ExecuteResourceGroup"
                )
                eSubmitResource_list = eResourceAllocation.findall(
                    "./SubmitResources/SubmitResource"
                )
                if (
                    not type_
                    or not eExecuteResourceGroup_list
                    or not eSubmitResource_list
                ):
                    log.warning(
                        "Skipping malformed ResourceAllocation: %s",
                        elem2str(eResourceAllocation),
                    )
                    continue

                allocation["type"] = type_

                #
                # Transform the list of SubmitResource elements
                #
                allocation["submit_resources"] = []
                for eSubmitResource in eSubmitResource_list:
                    resinfo = self.resinfo_by_name.get(
                        safe_element_text(eSubmitResource)
                    )
                    if not resinfo:
                        log.warning(
                            "Skipping missing or malformed SubmitResource: %s",
                            elem2str(eSubmitResource),
                        )
                        continue

                    allocation["submit_resources"].append(
                        {
                            "fqdn": resinfo.fqdn,
                            "group_name": resinfo.group_name,
                            "name": resinfo.name,
                        }
                    )

                #
                # Transform the list of ExecuteResourceGroup elements
                #
                allocation["execute_resource_groups"] = []
                for eExecuteResourceGroup in eExecuteResourceGroup_list:
                    group_name = safe_element_text(
                        eExecuteResourceGroup.find("./GroupName")
                    )
                    local_allocation_id = safe_element_text(
                        eExecuteResourceGroup.find("./LocalAllocationID")
                    )
                    if not group_name or not local_allocation_id:
                        log.warning(
                            "Skipping malformed ExecuteResourceGroup: %s",
                            elem2str(eExecuteResourceGroup),
                        )
                        continue

                    resinfo_list = self.grouped_resinfo.get(group_name)
                    if not resinfo_list:
                        log.warning(
                            "Skipping missing or empty ExecuteResourceGroup %s",
                            group_name,
                        )
                        continue

                    ces = [
                        {"fqdn": x.fqdn, "name": x.name}
                        for x in resinfo_list
                        if x.is_ce()
                    ]
                    allocation["execute_resource_groups"].append(
                        {
                            "ces": ces,
                            "group_name": group_name,
                            "local_allocation_id": local_allocation_id,
                        }
                    )

                # Done with this allocation
                allocations.append(allocation)

        # Done with all projects
        return ret

    #
    #
    # Internal
    #
    #

    def _get_data(
        self, cache: CachedData, endpoint: str, label: str
    ) -> Tuple[Optional[ET.Element], bool]:
        """Get parsed topology XML data from `cache`.  If necessary download from `endpoint`
        (a path under the topology host, e.g. "/miscproject/xml").
        Log messages will be labeled with `label`.

        Returns the data if available and True if the data is new; return None, False if we can't download/parse
        _and_ there is no cached data.

        """
        if not cache.should_update():
            log.debug(
                "%s cache lifetime / retry delay not expired, returning cached data (if any)",
                label,
            )
            return cache.data, False

        try:
            with urlopen(self.topology_host + endpoint) as response:
                xml_bytes = response.read()  # type: bytes
        except EnvironmentError as err:
            log.warning(
                "Topology %s query failed, will retry in %f: %s",
                label,
                self.retry_delay,
                err,
            )
            cache.try_again()
            if cache.data:
                log.debug("Returning cached data")
                return cache.data, False
            else:
                log.error("Failed to update and no cached data")
                return None, False

        if not xml_bytes:
            log.warning(
                "Topology %s query returned no data, will retry in %f",
                label,
                self.retry_delay,
            )
            cache.try_again()
            if cache.data:
                log.debug("Returning cached data")
                return cache.data, False
            else:
                log.error("Failed to update and no cached data")
                return None, False

        try:
            element = ET.fromstring(xml_bytes)
        except (ET.ParseError, UnicodeDecodeError) as err:
            log.warning(
                "Topology %s query couldn't be parsed, will retry in %f: %s",
                label,
                self.retry_delay,
                err,
            )
            cache.try_again()
            if cache.data:
                log.debug("Returning cached data")
                return cache.data, False
            else:
                log.error("Failed to update and no cached data")
                return None, False

        log.debug(
            "Caching and returning new %s data, will update again in %f",
            label,
            cache.cache_lifetime,
        )
        cache.update(element)
        return cache.data, True


def safe_element_text(element: Optional[ET.Element]) -> str:
    return getattr(element, "text", "").strip()


def elem2str(element: ET.Element) -> str:
    return ET.tostring(element, encoding="unicode")


def main(argv):
    parser = ArgumentParser(description=__doc__, prog=argv[0])
    parser.add_argument(
        "--verbose",
        "-v",
        action="count",
        default=0,
        help="Say more; can specify twice.",
    )
    parser.add_argument(
        "--quiet", "-q", action="count", default=0, help="Say less; can specify twice."
    )
    parser.add_argument(
        "--outdir",
        metavar="DIR",
        default="/run/topology-cache",
        help="Directory to write topology files to. [%(default)s]",
    )

    args = parser.parse_args(argv[1:])
    log.setLevel(max(logging.DEBUG, logging.WARNING + 10 * (args.quiet - args.verbose)))

    try:
        os.makedirs(args.outdir, exist_ok=True)
    except OSError as e:
        pass  # ¯\_(ツ)_/¯
    data = TopologyData()
    projects = data.get_projects()
    if not projects:
        return "Could not get project information"
    resources = data.get_resources()
    if not resources:
        return "Could not get resource information"

    path = ""
    try:
        path = os.path.join(args.outdir, "miscproject.xml")
        with open(path, "w", encoding="utf-8") as projects_xml:
            projects_xml.write(elem2str(projects))
            log.info("Wrote %s", path)
        path = os.path.join(args.outdir, "rgsummary.xml")
        with open(path, "w", encoding="utf-8") as resources_xml:
            resources_xml.write(elem2str(resources))
            log.info("Wrote %s", path)
    except OSError as e:
        return f"Couldn't write {path}: {str(e)}"

    project_resource_allocations = data.get_project_resource_allocations()
    path = os.path.join(args.outdir, "project_resource_allocations.json")
    try:
        with open(path, "w", encoding="utf-8") as ra_file:
            json.dump(
                project_resource_allocations,
                ra_file,
                skipkeys=True,
                indent=2,
                sort_keys=True,
            )
            log.info("Wrote %s", path)
    except OSError as e:
        return f"Couldn't write {path}: {str(e)}"

    return 0


if __name__ == "__main__":
    logging.basicConfig(format="%(message)s")
    sys.exit(main(sys.argv))
