import datetime
import logging
import os
import time
from typing import Dict, Set, List, Optional

import yaml

from webapp import common, contacts_reader, ldap_data, mappings, project_reader, rg_reader, vo_reader
from webapp.common import readfile
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
    def __init__(self, config=None, strict=False):
        if not config:
            config = {}
        config.setdefault("TOPOLOGY_DATA_DIR", ".")
        config.setdefault("CONTACT_DATA_DIR", None)
        config.setdefault("CILOGON_LDAP_URL", "ldaps://ldap.cilogon.org")
        config.setdefault("CILOGON_LDAP_USER",
                "uid=readonly_user,ou=system,o=OSG,o=CO,dc=cilogon,dc=org")
        config.setdefault("LIGO_LDAP_URL", "ldaps://ldap.ligo.org")
        config.setdefault("LIGO_LDAP_USER", "uid=osg-services-brian-lin,ou=system,dc=ligo,dc=org")
        config.setdefault("NO_GIT", True)
        contact_cache_lifetime = config.get("CONTACT_CACHE_LIFETIME", config.get("CACHE_LIFETIME", 60*15))
        topology_cache_lifetime = config.get("TOPOLOGY_CACHE_LIFETIME", config.get("CACHE_LIFETIME", 60*15))
        self.contacts_data = CachedData(cache_lifetime=contact_cache_lifetime)
        self.comanage_data = CachedData(cache_lifetime=contact_cache_lifetime)
        self.merged_contacts_data = CachedData(cache_lifetime=contact_cache_lifetime)
        self.ligo_dn_list = CachedData(cache_lifetime=contact_cache_lifetime)
        self.dn_set = CachedData(cache_lifetime=topology_cache_lifetime)
        self.projects = CachedData(cache_lifetime=topology_cache_lifetime)
        self.topology = CachedData(cache_lifetime=topology_cache_lifetime)
        self.vos_data = CachedData(cache_lifetime=topology_cache_lifetime)
        self.mappings = CachedData(cache_lifetime=topology_cache_lifetime)
        self.topology_data_dir = config["TOPOLOGY_DATA_DIR"]
        self.topology_data_repo = config.get("TOPOLOGY_DATA_REPO", "")
        self.topology_data_branch = config.get("TOPOLOGY_DATA_BRANCH", "")
        self.webhook_data_dir = config.get("WEBHOOK_DATA_DIR", "")
        self.webhook_data_repo = config.get("WEBHOOK_DATA_REPO", "")
        self.webhook_data_branch = config.get("WEBHOOK_DATA_BRANCH", "")
        self.webhook_state_dir = config.get("WEBHOOK_STATE_DIR", "")
        self.webhook_secret_key = config.get("WEBHOOK_SECRET_KEY")
        self.webhook_gh_api_user = config.get("WEBHOOK_GH_API_USER")
        self.webhook_gh_api_token = config.get("WEBHOOK_GH_API_TOKEN")
        self.cilogon_ldap_passfile = config.get("CILOGON_LDAP_PASSFILE")
        self.cilogon_ldap_url = config.get("CILOGON_LDAP_URL")
        self.cilogon_ldap_user = config.get("CILOGON_LDAP_USER")
        self.ligo_ldap_passfile = config.get("LIGO_LDAP_PASSFILE")
        self.ligo_ldap_url = config.get("LIGO_LDAP_URL")
        self.ligo_ldap_user = config.get("LIGO_LDAP_USER")
        self.github_oauth_client_secret = config.get("GITHUB_OAUTH_CLIENT_SECRET")
        self.auto_pr_gh_api_user = config.get("AUTO_PR_GH_API_USER")
        self.auto_pr_gh_api_token = config.get("AUTO_PR_GH_API_TOKEN")
        self.csrf_secret_key = config.get("CSRF_SECRET_KEY")
        if config["CONTACT_DATA_DIR"]:
            self.contacts_file = os.path.join(config["CONTACT_DATA_DIR"], "contacts.yaml")
        else:
            self.contacts_file = None
        self.projects_dir = os.path.join(self.topology_data_dir, "projects")
        self.topology_dir = os.path.join(self.topology_data_dir, "topology")
        self.vos_dir = os.path.join(self.topology_data_dir, "virtual-organizations")
        self.mappings_dir = os.path.join(self.topology_data_dir, "mappings")
        self.config = config
        self.strict = strict

    def update_webhook_repo(self):
        if not self.config["NO_GIT"]:
            parent = os.path.dirname(self.webhook_data_dir)
            os.makedirs(parent, mode=0o755, exist_ok=True)
            ssh_key = self.config["GIT_SSH_KEY"]
            ok = common.git_clone_or_fetch_mirror(repo=self.webhook_data_repo,
                                               git_dir=self.webhook_data_dir,
                                               ssh_key=ssh_key)
            if ok:
                log.debug("webhook repo update ok")
            else:
                log.error("webhook repo update failed")
                return False
        return True

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

    def get_contact_db_data(self) -> Optional[ContactsData]:
        """
        Get the contact information from a private git repo

        Returns an empty ContactsData if CONTACT_DATA_DIR is not specified.
        May return None if we fail to get the data for the first time.
        """
        if not self.config.get("CONTACT_DATA_DIR", None):
            log.debug("CONTACT_DATA_DIR not specified; getting empty contacts")
            data = contacts_reader.get_contacts_data(None)
            self.contacts_data.update(data)
        elif self.contacts_data.should_update():
            ok = self._update_contacts_repo()
            if ok:
                try:
                    self.contacts_data.update(contacts_reader.get_contacts_data(self.contacts_file))
                except Exception:
                    if self.strict:
                        raise
                    log.exception("Failed to update contacts data")
                    self.contacts_data.try_again()
            else:
                self.contacts_data.try_again()

        return self.contacts_data.data

    def get_comanage_data(self) -> Optional[ContactsData]:
        """
        Get the contact information from comanage / cilogon ldap
        May return None if we fail to get the data for the first time.
        """
        if not (self.cilogon_ldap_url and self.cilogon_ldap_user and
                self.cilogon_ldap_passfile):
            log.debug("CILOGON_LDAP_{URL|USER|PASSFILE} not specified; "
                      "getting empty contacts")
            data = contacts_reader.get_contacts_data(None)
            self.comanage_data.update(data)
        elif self.comanage_data.should_update():
            try:
                idmap = self.get_cilogon_ldap_id_map()
                data = ldap_data.cilogon_id_map_to_yaml_data(idmap)
                self.comanage_data.update(ContactsData(data))
            except Exception:
                if self.strict:
                    raise
                log.exception("Failed to update comanage data")
                self.comanage_data.try_again()

        return self.comanage_data.data

    def get_cilogon_ldap_id_map(self):
        url = self.cilogon_ldap_url
        user = self.cilogon_ldap_user
        ldappass = readfile(self.cilogon_ldap_passfile, log)
        return ldap_data.get_cilogon_ldap_id_map(url, user, ldappass)

    def get_contacts_data(self) -> Optional[ContactsData]:
        """
        Get the contact information from a private git repo
        May return None if we fail to get the data for the first time.
        """
        if self.merged_contacts_data.should_update():
            try:
                yd1 = self.get_comanage_data().yaml_data
                yd2 = self.get_contact_db_data().yaml_data
                yd_merged = ldap_data.merge_yaml_data(yd1, yd2)
                self.merged_contacts_data.update(ContactsData(yd_merged))
            except Exception:
                if self.strict:
                    raise
                log.exception("Failed to update merged contacts data")
                self.merged_contacts_data.try_again()

        return self.merged_contacts_data.data

    def get_ligo_dn_list(self) -> Optional[List[str]]:
        """
        Get list of DNs of authorized LIGO users from their LDAP
        May return None if we fail to get the data for the first time.
        """
        if not (self.ligo_ldap_url and self.ligo_ldap_user and
                self.ligo_ldap_passfile):
            log.debug("LIGO_LDAP_{URL|USER|PASSFILE} not specified; "
                      "getting empty list")
            return []
        elif self.ligo_dn_list.should_update():
            try:
                ligo_ldap_pass = readfile(self.ligo_ldap_passfile, log)
                new_dn_list = ldap_data.get_ligo_ldap_dn_list(self.ligo_ldap_url, self.ligo_ldap_user, ligo_ldap_pass)
                self.ligo_dn_list.update(new_dn_list)
            except Exception:
                if self.strict:
                    raise
                log.exception("Failed to update LIGO data")
                self.ligo_dn_list.try_again()

        return self.ligo_dn_list.data

    def get_dns(self) -> Optional[Set]:
        """
        Get the set of DNs allowed to access "special" data (such as contact info)
        May return None if we fail to get the data for the first time.
        """
        if self.dn_set.should_update():
            contacts_data = self.get_contacts_data()
            try:
                self.dn_set.update(set(contacts_data.get_dns()))
            except Exception:
                if self.strict:
                    raise
                log.exception("Failed to update DNs")
                self.contacts_data.try_again()
        return self.dn_set.data

    def get_topology(self) -> Optional[Topology]:
        """
        Get Topology data.
        May return None if we fail to get the data for the first time.
        """
        if self.topology.should_update():
            ok = self._update_topology_repo()
            if ok:
                try:
                    self.topology.update(rg_reader.get_topology(self.topology_dir, self.get_contacts_data(), strict=self.strict))
                except Exception:
                    if self.strict:
                        raise
                    log.exception("Failed to update topology")
                    self.topology.try_again()
            else:
                self.topology.try_again()

        return self.topology.data

    def get_vos_data(self) -> Optional[VOsData]:
        """
        Get VO Data.
        May return None if we fail to get the data for the first time.
        """
        if self.vos_data.should_update():
            ok = self._update_topology_repo()
            if ok:
                try:
                    self.vos_data.update(vo_reader.get_vos_data(self.vos_dir, self.get_contacts_data(), strict=self.strict))
                except Exception:
                    if self.strict:
                        raise
                    log.exception("Failed to update VOs")
                    self.vos_data.try_again()
            else:
                self.vos_data.try_again()

        return self.vos_data.data

    def get_projects(self) -> Optional[Dict]:
        """
        Get Project data.
        May return None if we fail to get the data for the first time.
        """
        if self.projects.should_update():
            ok = self._update_topology_repo()
            if ok:
                try:
                    self.projects.update(project_reader.get_projects(self.projects_dir, strict=self.strict))
                except Exception:
                    if self.strict:
                        raise
                    log.exception("Failed to update projects")
                    self.projects.try_again()
            else:
                self.projects.try_again()

        return self.projects.data

    def get_mappings(self) -> Optional[mappings.Mappings]:
        """
        Get mappings data.
        May return None if we fail to get the data for the first time.
        """
        if self.mappings.should_update():
            ok = self._update_topology_repo()
            if ok:
                try:
                    self.mappings.update(mappings.get_mappings(indir=self.mappings_dir, strict=self.strict))
                except Exception:
                    if self.strict:
                        raise
                    log.exception("Failed to update mappings")
                    self.mappings.try_again()
            else:
                self.mappings.try_again()

        return self.mappings.data


def _dtid(created_datetime: datetime.datetime):
    dtid_offset = 1_535_000_000.000  # use a more recent epoch -- gives us a few years of smaller IDs
    multiplier = 10.0  # use .1s resolution

    timestamp = created_datetime.timestamp()  # seconds from the epoch as float
    return int((timestamp - dtid_offset) * multiplier)


def get_downtime_yaml(id: int,
                      start_datetime: datetime.datetime,
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
        return yaml.safe_dump({key: value}, default_flow_style=False).strip()

    def indent(in_str, amount):
        spaces = ' ' * amount
        return spaces + ("\n"+spaces).join(in_str.split("\n"))

    start_time_str = Downtime.fmttime_preferred(start_datetime)
    end_time_str = Downtime.fmttime_preferred(end_datetime)
    created_time_str = Downtime.fmttime_preferred(created_datetime)

    result = "- " + render("Class", class_)
    for key, value in [
        ("ID", id),
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
