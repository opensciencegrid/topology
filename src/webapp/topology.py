from collections import OrderedDict, defaultdict
from datetime import datetime, timedelta, timezone
from enum import Enum
from logging import getLogger
import urllib.parse
from typing import Dict, List, Optional, Tuple

import icalendar

from .common import RGDOWNTIME_SCHEMA_URL, RGSUMMARY_SCHEMA_URL, Filters,\
    is_null, expand_attr_list_single, expand_attr_list, ensure_list
from .contacts_reader import ContactsData

GRIDTYPE_1 = "OSG Production Resource"
GRIDTYPE_2 = "OSG Integration Test Bed Resource"

log = getLogger(__name__)


class Timeframe(Enum):
    PAST = 1
    PRESENT = 2
    FUTURE = 3


class TopologyError(Exception): pass


class CommonData(object):
    """Global data, e.g. various mappings and contacts info"""
    def __init__(self, contacts: ContactsData, service_types: Dict, support_centers: Dict):
        self.contacts = contacts
        self.service_types = service_types
        self.support_centers = support_centers


class Facility(object):
    def __init__(self, name: str, id: int):
        self.name = name
        self.id = id

    def get_tree(self) -> OrderedDict:
        return OrderedDict([("ID", self.id), ("Name", self.name)])


class Site(object):
    # probably will have some other attributes like address, latitude, longitude, etc.
    def __init__(self, name: str, id: int, facility: Facility, site_info):
        self.name = name
        self.id = id
        self.facility = facility
        self.other_data = site_info
        if "ID" in self.other_data:
            del self.other_data["ID"]

    def get_tree(self) -> OrderedDict:
        # Sort the other_data
        sorted_other_data = sorted(list(self.other_data.items()), key=lambda tup: tup[0])
        return OrderedDict([("ID", self.id), ("Name", self.name)] + sorted_other_data)


class Resource(object):
    def __init__(self, name: str, yaml_data: Dict, common_data: CommonData):
        self.name = name
        self.service_types = common_data.service_types
        self.common_data = common_data
        if not is_null(yaml_data, "Services"):
            self.services = self._expand_services(yaml_data["Services"])
        else:
            self.services = []
        self.service_names = [n["Name"] for n in self.services if "Name" in n]
        self.data = yaml_data
        if is_null(yaml_data, "FQDN"):
            raise ValueError(f"Resource {name} does not have an FQDN")
        self.fqdn = self.data["FQDN"]
        self.id = self.data["ID"]

    def get_tree(self, authorized=False, filters: Filters = None) -> Optional[OrderedDict]:
        if filters is None:
            filters = Filters()

        defaults = {
            "Active": True,
            "Description": "(No resource description)",
            "Disable": False,
            "VOOwnership": "(Information not available)",
            "WLCGInformation": "(Information not available)",
        }

        new_res = OrderedDict.fromkeys(["ID", "Name", "Active", "Disable", "Services", "Description",
                                        "FQDN", "FQDNAliases", "VOOwnership",
                                        "WLCGInformation", "ContactLists"])
        new_res.update(defaults)
        new_res.update(self.data)

        if filters.active is not None and new_res["Active"] != filters.active:
            return
        if filters.disable is not None and new_res["Disable"] != filters.disable:
            return

        filtered_services = self.services
        if filters.service_id:
            filtered_services = [svc for svc in filtered_services
                                 if svc["ID"] in filters.service_id]
        if filters.service_hidden is not None:
            filtered_services = [svc for svc in filtered_services
                                 if not is_null(svc, "Details", "hidden")
                                 and svc["Details"]["hidden"] == filters.service_hidden]
        if not filtered_services:
            return  # all services filtered out
        new_res["Services"] = {"Service": filtered_services}

        if filters.voown_name:
            if "VOOwnership" not in self.data \
                    or set(filters.voown_name).isdisjoint(self.data["VOOwnership"].keys()):
                return
        if "VOOwnership" in self.data:
            new_res["VOOwnership"] = self._expand_voownership(self.data["VOOwnership"])
        if "FQDNAliases" in self.data:
            new_res["FQDNAliases"] = {"FQDNAlias": self.data["FQDNAliases"]}
        if not is_null(self.data, "ContactLists"):
            new_res["ContactLists"] = self._expand_contactlists(self.data["ContactLists"], authorized)
        new_res["Name"] = self.name
        if "WLCGInformation" in self.data and isinstance(self.data["WLCGInformation"], dict):
            new_res["WLCGInformation"] = self._expand_wlcginformation(self.data["WLCGInformation"])
        elif filters.has_wlcg is True:
            return

        # The topology XML schema cannot handle this additional data.  Given how inflexible
        # the XML has been (and mostly seen as there for backward compatibility), this simply
        # removes the data from the XML format.
        if 'DN' in new_res:
            del new_res['DN']
        if 'AllowedVOs' in new_res:
            del new_res['AllowedVOs']

        return new_res

    def _expand_services(self, services: Dict) -> List[OrderedDict]:
        services_list = expand_attr_list(services, "Name", ordering=["Name", "Description", "Details"])
        for svc in services_list:
            svc["ID"] = self.service_types[svc["Name"]]
            svc.move_to_end("ID", last=False)
        return services_list

    @staticmethod
    def _expand_voownership(voownership: Dict) -> OrderedDict:
        """Return the data structure for an expanded VOOwnership for a single Resource."""

        def _get_charturl(ownership):
            # Return a URL for a pie chart based on (VO, Percent) pairs.
            chd = ""
            chl = ""

            for name, percent in ownership:
                chd += "{0},".format(percent)
                if name == "(Other)":
                    name = "Other"
                chl += "{0}({1}%)|".format(percent, name)
            chd = chd.rstrip(",")
            chl = chl.rstrip("|")

            query = urllib.parse.urlencode({
                "chco": "00cc00",
                "cht": "p3",
                "chd": "t:" + chd,
                "chs": "280x65",
                "chl": chl
            })
            return "http://chart.apis.google.com/chart?" + query

        voo = voownership.copy()
        totalpercent = sum(voo.values())
        if totalpercent < 100:
            voo["(Other)"] = 100 - totalpercent
        return OrderedDict([
            ("Ownership", expand_attr_list_single(voo, "VO", "Percent", name_first=False)),
            ("ChartURL", _get_charturl(voownership.items()))
        ])

    def _expand_contactlists(self, contactlists: Dict, authorized: bool) -> Dict:
        """Return the data structure for an expanded ContactLists for a single Resource."""
        new_contactlists = []
        for contact_type, contact_data in contactlists.items():
            contact_data = expand_attr_list(contact_data, "ContactRank", ["Name", "ID", "ContactRank"], ignore_missing=True)
            for contact in contact_data:
                contact_id = contact.pop("ID", None)  # ID is for internal use - don't put it in the results
                if authorized and self.common_data.contacts:
                    if contact_id in self.common_data.contacts.users_by_id:
                        extra_data = self.common_data.contacts.users_by_id[contact_id]
                        contact["Email"] = extra_data.email
                        contact["Phone"] = extra_data.phone
                        contact["SMSAddress"] = extra_data.sms_address
                        dns = extra_data.dns
                        if dns:
                            contact["DN"] = dns[0]
                        contact.move_to_end("ContactRank", last=True)
            new_contactlists.append(
                OrderedDict([("ContactType", contact_type), ("Contacts", {"Contact": contact_data})]))
        return {"ContactList": new_contactlists}

    @staticmethod
    def _expand_wlcginformation(wlcg: Dict) -> OrderedDict:
        defaults = {
            "InteropBDII": False,
            "TapeCapacity": 0,
        }

        new_wlcg = OrderedDict.fromkeys(["InteropBDII", "LDAPURL", "InteropMonitoring", "InteropAccounting",
                                         "AccountingName", "KSI2KMin", "KSI2KMax", "StorageCapacityMin",
                                         "StorageCapacityMax", "HEPSPEC", "APELNormalFactor", "TapeCapacity"])
        new_wlcg.update(defaults)
        new_wlcg.update(wlcg)
        return new_wlcg


class ResourceGroup(object):
    def __init__(self, name: str, yaml_data: Dict, site: Site, common_data: CommonData):
        self.name = name
        self.site = site
        self.service_types = common_data.service_types
        self.common_data = common_data

        scname = yaml_data["SupportCenter"]
        scid = int(common_data.support_centers[scname]["ID"])
        self.support_center = OrderedDict([("ID", scid), ("Name", scname)])

        self.resources_by_name = {}
        for name, res in yaml_data["Resources"].items():
            try:
                if not isinstance(res, dict):
                    raise TypeError("expecting a dict")
                res = Resource(name, res, self.common_data)
                self.resources_by_name[name] = res
            except (AttributeError, KeyError, TypeError, ValueError) as err:
                log.exception("Error with resource %s: %r", name, err)
                continue

        self.data = yaml_data

    @property
    def resources(self):
        return [self.resources_by_name[k] for k in sorted(self.resources_by_name)]

    def get_tree(self, authorized=False, filters: Filters = None) -> Optional[OrderedDict]:
        if filters is None:
            filters = Filters()
        for filter_list, attribute in [(filters.facility_id, self.site.facility.id),
                                       (filters.site_id, self.site.id),
                                       (filters.support_center_id, self.support_center["ID"]),
                                       (filters.rg_id, self.id)]:
            if filter_list and attribute not in filter_list:
                return
        data_gridtype = GRIDTYPE_1 if self.data.get("Production", None) else GRIDTYPE_2
        if filters.grid_type is not None and data_gridtype != filters.grid_type:
            return

        filtered_resources = []
        for res in self.resources:
            try:
                tree = res.get_tree(authorized, filters)
                if tree:
                    filtered_resources.append(tree)
            except (AttributeError, KeyError, ValueError) as err:
                log.exception("Error with resource %s: %r", res.name, err)
                continue
        if not filtered_resources:
            return  # all resources filtered out
        try:
            filtered_data = self._expand_rg()
        except (AttributeError, KeyError, ValueError) as err:
            log.exception("Error with resource group %s/%s: %r", self.site, self.name, err)
            return
        filtered_data["Resources"] = {"Resource": filtered_resources}
        return filtered_data

    @property
    def id(self):
        return self.data["GroupID"]

    @property
    def key(self):
        return (self.site.name, self.name)

    def _expand_rg(self) -> OrderedDict:
        new_rg = OrderedDict.fromkeys(["GridType", "GroupID", "GroupName", "Disable", "Facility", "Site",
                                       "SupportCenter", "GroupDescription"])
        new_rg.update({"Disable": False})
        new_rg.update(self.data)

        new_rg["Facility"] = self.site.facility.get_tree()
        new_rg["Site"] = self.site.get_tree()
        new_rg["GroupName"] = self.name
        new_rg["SupportCenter"] = self.support_center
        production = new_rg.pop("Production")
        if production:
            new_rg["GridType"] = GRIDTYPE_1
        else:
            new_rg["GridType"] = GRIDTYPE_2

        return new_rg


class Downtime(object):
    TIME_OUTPUT_FMT = "%b %d, %Y %H:%M %p %Z"
    PREFERRED_TIME_FMT = "%b %d, %Y %H:%M %z"  # preferred format, e.g. "Mar 7, 2017 03:00 -0500"

    def __init__(self, rg: ResourceGroup, yaml_data: Dict, common_data: CommonData):
        self.rg = rg
        self.data = yaml_data
        for k in ["StartTime", "EndTime", "ID", "Class", "Severity", "ResourceName", "Services"]:
            if is_null(yaml_data, k):
                raise ValueError(k)
        self.start_time = self.parsetime(yaml_data["StartTime"])
        self.end_time = self.parsetime(yaml_data["EndTime"])
        self.created_time = None
        if not is_null(yaml_data, "CreatedTime"):
            self.created_time = self.parsetime(yaml_data["CreatedTime"])
        self.res = rg.resources_by_name[yaml_data["ResourceName"]]
        self.service_names = yaml_data["Services"]
        self.service_ids = [common_data.service_types[x] for x in yaml_data["Services"]]
        self.id = yaml_data["ID"]

    @property
    def timeframe(self) -> Timeframe:
        current_time = datetime.now(timezone.utc)
        # ^ not to be confused with datetime.utcnow(), which does not include tz info in the result

        if self.end_time < current_time:
            return Timeframe.PAST
        elif self.start_time > current_time:
            return Timeframe.FUTURE
        else:
            return Timeframe.PRESENT

    @property
    def end_age(self) -> timedelta:
        """Return timedelta elapsed since end_time.
        The value returned is negative if end_time is in the future."""
        current_time = datetime.now(timezone.utc)
        return current_time - self.end_time

    def _is_shown(self, filters) -> bool:
        if filters is None:
            filters = Filters()
        for filter_list, attribute in [(filters.facility_id, self.rg.site.facility.id),
                                       (filters.site_id, self.rg.site.id),
                                       (filters.support_center_id, self.rg.support_center["ID"]),
                                       (filters.rg_id, self.rg.id)]:
            if filter_list and attribute not in filter_list:
                return False

        rg_data_gridtype = GRIDTYPE_1 if self.rg.data.get("Production", None) else GRIDTYPE_2
        if filters.grid_type is not None and rg_data_gridtype != filters.grid_type:
            return False

        # unlike the other filters, if past_days is not specified, _no_ past downtime is shown
        if filters.past_days >= 0:
            # Filter out downtimes older than 'past_days'
            # (current & future downtimes are not filtered out)
            if self.end_age.total_seconds() > filters.past_days * 86400:
                return False

        if filters.service_id:
            if not set(filters.service_id).intersection(set(self.service_ids)):
                return False

        return True

    def get_tree(self, filters: Filters = None) -> Optional[OrderedDict]:
        if self._is_shown(filters):
            return self._expand_downtime(filters.service_id)

    def get_ical_event(self, filters: Filters = None) -> Optional[icalendar.Event]:
        if not self._is_shown(filters):
            return None

        evt = icalendar.Event()
        try:
            evt["uid"] = str(self.data.get("ID", 0))
            evt.add("dtstart", self.start_time)
            evt.add("dtend", self.end_time)
            evt["summary"] = f"{self.rg.name} / {self.res.name}"
            affected_services = ", ".join(self.service_names)
            evt["description"] = (f"Class: {self.data['Class']}\n"
                                  f"Severity: {self.data['Severity']}\n"
                                  f"Affected Services: {affected_services}\n"
                                  f"Description: {self.data['Description']}")
        except (KeyError, ValueError, AttributeError) as e:
            log.warning("Malformed downtime: %r", e)
            return None

        return evt

    def _expand_downtime(self, service_filter=None) -> Optional[OrderedDict]:
        new_downtime = OrderedDict.fromkeys(["ID", "ResourceID", "ResourceGroup", "ResourceName", "ResourceFQDN",
                                             "StartTime", "EndTime", "Class", "Severity", "CreatedTime", "UpdateTime",
                                             "Services", "Description"])
        new_downtime["ResourceGroup"] = OrderedDict([("GroupName", self.rg.name),
                                                     ("GroupID", self.rg.id)])
        new_downtime["ResourceFQDN"] = self.res.fqdn
        new_downtime["ResourceID"] = self.res.id
        new_downtime["ResourceName"] = self.res.name

        new_services = []
        for dt_service_name in self.service_names:
            for res_service in ensure_list(self.res.services):
                if res_service["Name"] == dt_service_name:
                    if not service_filter or res_service["ID"] in service_filter:
                        new_services.append(OrderedDict([
                            ("ID", res_service["ID"]),
                            ("Name", res_service["Name"]),
                            ("Description", res_service["Description"])
                        ]))
                    break

        if new_services:
            new_downtime["Services"] = {"Service": new_services}
        else:
            return None

        if not is_null(self.created_time):
            new_downtime["CreatedTime"] = self.fmttime(self.created_time)
        else:
            new_downtime["CreatedTime"] = "Not Available"
        new_downtime["UpdateTime"] = "Not Available"

        new_downtime["StartTime"] = self.fmttime(self.start_time)
        new_downtime["EndTime"] = self.fmttime(self.end_time)

        for k in ["ID", "Class", "Severity"]:
            new_downtime[k] = self.data[k]
        new_downtime["Description"] = self.data.get("Description")

        return new_downtime

    @classmethod
    def fmttime(cls, a_time: datetime) -> str:
        return a_time.strftime(cls.TIME_OUTPUT_FMT)

    @classmethod
    def fmttime_preferred(cls, a_time: datetime) -> str:
        if not a_time.tzinfo:
            a_time = a_time.replace(tzinfo=timezone.utc)
        return a_time.strftime(cls.PREFERRED_TIME_FMT)

    @classmethod
    def parsetime(cls, time_str: str) -> datetime:
        """Parse the downtime found in the YAML file; tries multiple formats,
        returns the first one that matches.

        Raises ValueError if time_str cannot be parsed with any of the formats.
        """

        fmts = [cls.PREFERRED_TIME_FMT,
                "%b %d, %Y %H:%M UTC",  # explicit UTC timezone
                "%b %d, %Y %H:%M",  # without timezone (assumes UTC)
                "%b %d, %Y %H:%M %p UTC"]  # format existing data is in, e.g. "Mar 7, 2017 03:00 AM UTC"

        time = None
        for fmt in fmts:
            try:
                time = datetime.strptime(time_str, fmt)
            except ValueError:
                pass
            if time:
                if not time.tzinfo:
                    time = time.replace(tzinfo=timezone.utc)
                else:
                    time = time.astimezone(timezone.utc)
                return time
        raise ValueError("Cannot parse time {}".format(time_str))


class Topology(object):
    def __init__(self, common_data: CommonData):
        self.downtimes_by_timeframe = {
            Timeframe.PAST: [],
            Timeframe.PRESENT: [],
            Timeframe.FUTURE: []}
        self.common_data = common_data
        self.facilities = {}
        self.sites = {}
        # rgs are keyed by (site_name, rg_name) tuple
        self.rgs = {}  # type: Dict[Tuple[str, str], ResourceGroup]
        self.resources_by_facility = defaultdict(list)
        self.service_names_by_resource = {}  # type: Dict[str, List[str]]
        self.downtime_path_by_resource = {}

    def add_rg(self, facility_name, site_name, name, parsed_data):
        try:
            rg = ResourceGroup(name, parsed_data, self.sites[site_name], self.common_data)
            self.rgs[(site_name, name)] = rg
            for r in rg.resources:
                self.resources_by_facility[facility_name].append(r)
                self.service_names_by_resource[r.name] = r.service_names
                self.downtime_path_by_resource[r.name] = f"{facility_name}/{site_name}/{name}_downtime.yaml"
        except (AttributeError, KeyError, ValueError) as err:
            log.exception("RG %s, %s error: %r; skipping", site_name, name, err)

    def add_facility(self, name, id):
        self.facilities[name] = Facility(name, id)

    def add_site(self, facility_name, name, id, site_info):
        self.sites[name] = Site(name, id, self.facilities[facility_name], site_info)

    def get_resource_group_list(self):
        """
        Simple getter for an iterator of resource group objects associated with this topology.
        """
        return self.rgs.values()

    def get_resource_summary(self, authorized=False, filters: Filters = None) -> Dict:
        if filters is None:
            filters = Filters()
        rglist = []
        for rgkey in sorted(self.rgs.keys(), key=lambda x: x[1].lower()):
            rgval = self.rgs[rgkey]
            assert isinstance(rgval, ResourceGroup)
            rgtree = rgval.get_tree(authorized, filters)
            if rgtree:
                rglist.append(rgtree)
        return {"ResourceSummary":
                {"@xmlns:xsi": "http://www.w3.org/2001/XMLSchema-instance",
                 "@xsi:schemaLocation": RGSUMMARY_SCHEMA_URL,
                 "ResourceGroup": rglist}}

    def get_downtimes(self, authorized=False, filters: Filters = None) -> Dict:
        _ = authorized
        if filters is None:
            filters = Filters()

        tree = {"Downtimes": {"@xsi:schemaLocation": RGDOWNTIME_SCHEMA_URL,
                              "@xmlns:xsi": "http://www.w3.org/2001/XMLSchema-instance"}}

        for treekey, dtkey in [("PastDowntimes", Timeframe.PAST),
                               ("CurrentDowntimes", Timeframe.PRESENT),
                               ("FutureDowntimes", Timeframe.FUTURE)]:
            dtlist = []
            for dt in self.downtimes_by_timeframe[dtkey]:
                try:
                    dttree = dt.get_tree(filters)
                except (AttributeError, KeyError, ValueError) as err:
                    log.exception("Error with downtime %s: %r", dt, err)
                    continue
                if dttree:
                    dtlist.append(dttree)
            tree["Downtimes"][treekey] = {
                "Downtime": dtlist}

        return tree

    def get_downtimes_ical(self, authorized=False, filters: Filters = None) -> icalendar.Calendar:
        _ = authorized
        if filters is None:
            filters = Filters()

        cal = icalendar.Calendar()
        cal.add("prodid", "-//Open Science Grid//Topology//EN")
        cal.add("version", "2.0")

        for tf in [Timeframe.PAST, Timeframe.PRESENT, Timeframe.FUTURE]:
            for dt in self.downtimes_by_timeframe[tf]:
                try:
                    event = dt.get_ical_event(filters)
                except (AttributeError, KeyError, ValueError) as err:
                    log.exception("Error with downtime %s: %r", dt, err)
                    continue
                if event:
                    cal.add_component(event)

        return cal

    def add_downtime(self, sitename: str, rgname: str, downtime: Dict):
        try:
            rg = self.rgs[(sitename, rgname)]
        except KeyError:
            log.warning("RG %s/%s does not exist -- skipping downtime", sitename, rgname)
            return
        try:
            dt = Downtime(rg, downtime, self.common_data)
        except (KeyError, ValueError) as err:
            log.warning("Invalid or missing data in downtime -- skipping: %r", err)
            return
        self.downtimes_by_timeframe[dt.timeframe].append(dt)
