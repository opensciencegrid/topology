import datetime
import logging
import os
import time
from typing import Dict, Set, List

import anymarkup

from webapp import common, contacts_reader, project_reader, rg_reader, vo_reader
from webapp.contacts_reader import ContactsData
from webapp.topology import Topology, Downtime
from webapp.vos_data import VOsData


log = logging.getLogger(__name__)


class CachedData:
    def __init__(self, data=None, timestamp=0, force_update=True, cache_lifetime=60*15,
                 retry_delay=60):
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


class GlobalData:
    def __init__(self, config):
        self.contacts_data = CachedData(cache_lifetime=config["CACHE_LIFETIME"])
        self.dn_set = CachedData(cache_lifetime=config["CACHE_LIFETIME"])
        self.projects = CachedData(cache_lifetime=config["CACHE_LIFETIME"])
        self.topology = CachedData(cache_lifetime=config["CACHE_LIFETIME"])
        self.vos_data = CachedData(cache_lifetime=config["CACHE_LIFETIME"])
        self.topology_data_dir = config["TOPOLOGY_DATA_DIR"]
        self.topology_data_repo = config.get("TOPOLOGY_DATA_REPO", "")
        self.topology_data_branch = config.get("TOPOLOGY_DATA_BRANCH", "")
        self.contacts_file = os.path.join(config["CONTACT_DATA_DIR"], "contacts.yaml")
        self.projects_dir = os.path.join(self.topology_data_dir, "projects")
        self.topology_dir = os.path.join(self.topology_data_dir, "topology")
        self.vos_dir = os.path.join(self.topology_data_dir, "virtual-organizations")
        self.config = config

    def _update_topology_repo(self):
        if not self.config["NO_GIT"]:
            parent = os.path.dirname(self.topology_data_dir)
            os.makedirs(parent, mode=0o755, exist_ok=True)
            ok = common.git_clone_or_pull(self.topology_data_repo, self.topology_data_dir,
                                          self.topology_data_branch)
            if ok:
                log.debug("topology repo update ok")
            else:
                log.error("topology repo update failed")
                return False
        for d in [self.projects_dir, self.topology_dir, self.vos_dir]:
            if not os.path.exists(d):
                log.error("%s not in topology repo", d)
                return False
        return True

    def _update_contacts_repo(self):
        if not self.config["NO_GIT"]:
            parent = os.path.dirname(self.config["CONTACT_DATA_DIR"])
            os.makedirs(parent, mode=0o700, exist_ok=True)
            ok = common.git_clone_or_pull(self.config["CONTACT_DATA_REPO"], self.config["CONTACT_DATA_DIR"],
                                   self.config["CONTACT_DATA_BRANCH"], self.config["GIT_SSH_KEY"])
            if ok:
                log.debug("contact repo update ok")
            else:
                log.error("contact repo update failed")
                return False
        if not os.path.exists(self.contacts_file):
            log.error("%s not in contact repo", self.contacts_file)
            return False
        return True

    def get_contacts_data(self) -> ContactsData:
        """
        Get the contact information from a private git repo
        """
        if self.contacts_data.should_update():
            ok = self._update_contacts_repo()
            if ok:
                self.contacts_data.update(contacts_reader.get_contacts_data(self.contacts_file))
            else:
                self.contacts_data.try_again()

        return self.contacts_data.data

    def get_dns(self) -> Set:
        """
        Get the set of DNs allowed to access "special" data (such as contact info)
        """
        if self.dn_set.should_update():
            contacts_data = self.get_contacts_data()
            self.dn_set.update(set(contacts_data.get_dns()))
        return self.dn_set.data

    def get_topology(self) -> Topology:
        if self.topology.should_update():
            ok = self._update_topology_repo()
            if ok:
                self.topology.update(rg_reader.get_topology(self.topology_dir, self.get_contacts_data()))
            else:
                self.topology.try_again()

        return self.topology.data

    def get_vos_data(self) -> VOsData:
        if self.vos_data.should_update():
            ok = self._update_topology_repo()
            if ok:
                self.vos_data.update(vo_reader.get_vos_data(self.vos_dir, self.get_contacts_data()))
            else:
                self.vos_data.try_again()

        return self.vos_data.data

    def get_projects(self) -> Dict:
        if self.projects.should_update():
            ok = self._update_topology_repo()
            if ok:
                self.projects.update(project_reader.get_projects(self.projects_dir))
            else:
                self.projects.try_again()

        return self.projects.data


def _dtid(created_datetime: datetime.datetime):
    dtid_offset = 1_535_000_000.000  # use a more recent epoch -- gives us a few years of smaller IDs
    multiplier = 10.0  # use .1s resolution

    timestamp = created_datetime.timestamp()  # seconds from the epoch as float
    return int((timestamp - dtid_offset) * multiplier)


def get_downtime_yaml(start_datetime: datetime.datetime,
                      end_datetime: datetime.datetime,
                      created_datetime: datetime.datetime,
                      description: str,
                      severity: str,
                      class_: str,
                      resource_name: str,
                      services: List[str]) -> str:
    """Return the generated YAML from the data provided.

    Renders each individual field with a YAML serializer but then writes them
    out by hand so the ordering matches what's in the downtime template.

    """

    def render(key, value):
        return anymarkup.serialize({key: value}, "yaml").decode("utf-8", errors="replace").strip()

    def indent(in_str, amount):
        spaces = ' ' * amount
        return spaces + ("\n"+spaces).join(in_str.split("\n"))

    start_time_str = Downtime.fmttime_preferred(start_datetime)
    end_time_str = Downtime.fmttime_preferred(end_datetime)
    created_time_str = Downtime.fmttime_preferred(created_datetime)

    result = "- " + render("Class", class_)
    for key, value in [
        ("ID", (_dtid(created_datetime))),
        ("Description", description),
        ("Severity", severity),
        ("StartTime", start_time_str),
        ("EndTime", end_time_str),
        ("CreatedTime", created_time_str),
        ("ResourceName", resource_name),
        ("Services", services)
    ]:
        result += "\n" + indent(render(key, value), 2)
    result += "\n# ---------------------------------------------------------\n"

    return result
