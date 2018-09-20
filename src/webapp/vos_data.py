import copy

from collections import OrderedDict
from logging import getLogger
from typing import Dict, List


from .common import Filters, MaybeOrderedDict, VOSUMMARY_SCHEMA_URL, is_null, expand_attr_list
from .contacts_reader import ContactsData


log = getLogger(__name__)


class VOsData(object):
    def __init__(self, contacts_data: ContactsData, reporting_groups_data):
        self.contacts_data = contacts_data
        self.vos = {}
        self.reporting_groups_data = reporting_groups_data

    def get_vo_id_to_name(self) -> Dict:
        return {self.vos[name]["ID"]: name for name in self.vos}

    def add_vo(self, vo_name, vo_data):
        self.vos[vo_name] = vo_data

    def get_tree(self, authorized=False, filters: Filters = None) -> Dict:
        if not filters:
            filters = Filters()
        expanded_vo_list = []
        for vo_name in sorted(self.vos.keys(), key=lambda x: x.lower()):
            try:
                expanded_vo_data = self._expand_vo(vo_name, authorized=authorized, filters=filters)
                if expanded_vo_data:
                    expanded_vo_list.append(expanded_vo_data)
            except (KeyError, ValueError, AttributeError) as err:
                log.exception("Problem with VO data for %s: %s", vo_name, err)

        return {"VOSummary": {
            "@xmlns:xsi": "http://www.w3.org/2001/XMLSchema-instance",
            "@xsi:schemaLocation": VOSUMMARY_SCHEMA_URL,
            "VO": expanded_vo_list}}

    def _expand_vo(self, name: str, authorized: bool, filters: Filters) -> MaybeOrderedDict:
        # Restore ordering
        new_vo = OrderedDict.fromkeys(["ID", "Name", "LongName", "CertificateOnly", "PrimaryURL",
                                       "MembershipServicesURL", "PurposeURL", "SupportURL", "AppDescription",
                                       "Community", "FieldsOfScience", "ParentVO", "ReportingGroups", "Active",
                                       "Disable", "ContactTypes", "OASIS"])
        new_vo.update({
            "Disable": False,
            "Active": True,
        })
        vo = self.vos[name]
        new_vo.update(vo)

        if filters.active is not None and filters.active != new_vo["Active"]:
            return
        if filters.disable is not None and filters.disable != new_vo["Disable"]:
            return
        if filters.oasis is not None and (is_null(vo, "OASIS", "UseOASIS") or
                                          filters.oasis != vo["OASIS"]["UseOASIS"]):
            return
        if filters.vo_id and vo["ID"] not in filters.vo_id:
            return

        new_vo["Name"] = name

        if not is_null(vo, "Contacts"):
            new_vo["ContactTypes"] = self._expand_contacttypes(vo["Contacts"], authorized)
        new_vo.pop("Contacts", None)

        if not is_null(vo, "ReportingGroups"):
            new_vo["ReportingGroups"] = self._expand_reporting_groups(vo["ReportingGroups"], authorized)

        oasis = OrderedDict.fromkeys(["UseOASIS", "Managers", "OASISRepoURLs"])
        oasis["UseOASIS"] = vo.get("OASIS", {}).get("UseOASIS", False)
        if not is_null(vo, "OASIS", "Managers"):
            oasis["Managers"] = self._expand_oasis_managers(vo["OASIS"]["Managers"])
        if not is_null(vo, "OASIS", "OASISRepoURLs"):
            oasis["OASISRepoURLs"] = {"URL": vo["OASIS"]["OASISRepoURLs"]}
        new_vo["OASIS"] = oasis

        if not is_null(vo, "FieldsOfScience"):
            new_vo["FieldsOfScience"] = self._expand_fields_of_science(vo["FieldsOfScience"])

        if not is_null(vo, "ParentVO"):
            parentvo = OrderedDict.fromkeys(["ID", "Name"])
            parentvo.update(vo["ParentVO"])
            new_vo["ParentVO"] = parentvo

        return new_vo

    def _expand_contacttypes(self, vo_contacts: Dict, authorized: bool) -> Dict:
        new_contacttypes = []
        for type_, list_ in vo_contacts.items():
            contact_items = []
            for contact in list_:
                new_contact = OrderedDict([("Name", contact["Name"])])
                if authorized and self.contacts_data:
                    if contact["ID"] in self.contacts_data.users_by_id:
                        extra_data = self.contacts_data.users_by_id[contact["ID"]]
                        new_contact["Email"] = extra_data.email
                        new_contact["Phone"] = extra_data.phone
                        new_contact["SMSAddress"] = extra_data.sms_address
                        dns = extra_data.dns
                        if dns:
                            new_contact["DN"] = dns[0]
                    else:
                        log.warning("id %s not found for %s", contact["ID"], contact["Name"])
                contact_items.append(new_contact)
            new_contacttypes.append({"Type": type_, "Contacts": {"Contact": contact_items}})
        return {"ContactType": new_contacttypes}

    @staticmethod
    def _expand_fields_of_science(fields_of_science):
        """Turn
        {"PrimaryFields": ["P1", "P2", ...],
         "SecondaryFields": ["S1", "S2", ...]}
        into
        {"PrimaryFields": {"Field": ["P1", "P2", ...]},
         "SecondaryFields": {"Field": ["S1", "S2", ...]}}
        """
        if is_null(fields_of_science, "PrimaryFields"):
            return None
        new_fields = OrderedDict()
        new_fields["PrimaryFields"] = {"Field": fields_of_science["PrimaryFields"]}
        if not is_null(fields_of_science, "SecondaryFields"):
            new_fields["SecondaryFields"] = {"Field": fields_of_science["SecondaryFields"]}
        return new_fields

    @staticmethod
    def _expand_oasis_managers(managers):
        """Expand
        {"a": {"DNs": [...]}}
        into
        {"Manager": [{"Name": "a", "DNs": {"DN": [...]}}]}
        """
        new_managers = copy.deepcopy(managers)
        for name, data in managers.items():
            if not is_null(data, "DNs"):
                new_managers[name]["DNs"] = {"DN": data["DNs"]}
            else:
                new_managers[name]["DNs"] = None
        return {"Manager": expand_attr_list(new_managers, "Name", ordering=["ContactID", "Name", "DNs"],
                                            ignore_missing=True)}

    def _expand_reporting_groups(self, reporting_groups_list: List, authorized: bool) -> Dict:
        new_reporting_groups = {}
        for name, data in self.reporting_groups_data.items():
            if name not in reporting_groups_list: continue
            new_reporting_groups[name] = {}
            newdata = new_reporting_groups[name]
            if not is_null(data, "Contacts"):
                new_contacts = []
                for contact in data["Contacts"]:
                    new_contact = OrderedDict([("Name", contact["Name"])])
                    if authorized and self.contacts_data:
                        if contact["ID"] in self.contacts_data.users_by_id:
                            extra_data = self.contacts_data.users_by_id[contact["ID"]]
                            new_contact["Email"] = extra_data.email
                            new_contact["Phone"] = extra_data.phone
                            new_contact["SMSAddress"] = extra_data.sms_address
                    new_contacts.append(new_contact)
                newdata["Contacts"] = {"Contact": new_contacts}
            else:
                newdata["Contacts"] = None
            if not is_null(data, "FQANs"):
                fqans = []
                for fqan in data["FQANs"]:
                    fqans.append(OrderedDict([("GroupName", fqan["GroupName"]), ("Role", fqan["Role"])]))
                newdata["FQANs"] = {"FQAN": fqans}
            else:
                newdata["FQANs"] = None
        new_reporting_groups = expand_attr_list(new_reporting_groups, "Name", ordering=["Name", "FQANs", "Contacts"])
        return {"ReportingGroup": new_reporting_groups}
