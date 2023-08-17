import copy

from collections import OrderedDict
from logging import getLogger
from typing import Dict, List, Optional

from .common import Filters, ParsedYaml, VOSUMMARY_SCHEMA_URL, is_null, expand_attr_list, order_dict, escape
from .data_federation import StashCache
from .contacts_reader import ContactsData


log = getLogger(__name__)


class VOsData(object):
    def __init__(self, contacts_data: ContactsData, reporting_groups_data: ParsedYaml):
        self.contacts_data = contacts_data
        self.vos = {}  # type: Dict[str, ParsedYaml]
        self.reporting_groups_data = reporting_groups_data
        self.stashcache_by_vo_name = {}  # type: Dict[str, StashCache]

    def get_vo_id_to_name(self) -> Dict[str, str]:
        return {self.vos[name]["ID"]: name for name in self.vos}

    def add_vo(self, vo_name: str, vo_data: ParsedYaml):
        self.vos[vo_name] = vo_data
        stashcache_data = vo_data.get('DataFederations', {}).get('StashCache')
        if stashcache_data:
            stashcache_obj = StashCache(vo_name, stashcache_data)
            if stashcache_obj.errors:
                log.exception("Problem(s) with DataFederations/StashCache data for VO %s: %s",
                              vo_name, "\n".join(stashcache_obj.errors))
            else:
                self.stashcache_by_vo_name[vo_name] = stashcache_obj

    def get_expansion(self, authorized=False, filters: Filters = None):
        if not filters:
            filters = Filters()
        expanded_vo_list = []
        for vo_name, vo_data in sorted(self.vos.items(), key=lambda x: x[0].lower()):
            try:
                expanded_vo_data = self._expand_vo(vo_name, authorized=authorized, filters=filters)

                # Add the regex pattern from the scitokens mapfile
                if not is_null(vo_data, "Credentials", "TokenIssuers"):
                    for index, token_issuer in enumerate(vo_data["Credentials"]["TokenIssuers"]):
                        url = token_issuer.get("URL")
                        subject = token_issuer.get("Subject", "")
                        pattern = ""
                        if url:
                            if subject:
                                pattern = f'/^{escape(url)},{escape(subject)}$/'
                            else:
                                pattern = f'/^{escape(url)},/'

                        if pattern:
                            expanded_vo_data["Credentials"]["TokenIssuers"]["TokenIssuer"][index]['Pattern'] = pattern

                if expanded_vo_data:
                    expanded_vo_list.append(expanded_vo_data)

            except (KeyError, ValueError, AttributeError) as err:
                log.exception("Problem with VO data for %s: %s", vo_name, err)

        return expanded_vo_list

    def get_tree(self, authorized=False, filters: Filters = None) -> Dict:
        if not filters:
            filters = Filters()
        expanded_vo_list = []
        for vo_name in sorted(self.vos.keys(), key=lambda x: x.lower()):
            try:
                expanded_vo_data = self._expand_vo(vo_name, authorized=authorized, filters=filters)
                if expanded_vo_data:
                    if 'DataFederations' in expanded_vo_data:
                        del expanded_vo_data['DataFederations']
                    expanded_vo_list.append(expanded_vo_data)
            except (KeyError, ValueError, AttributeError) as err:
                log.exception("Problem with VO data for %s: %s", vo_name, err)

        return {"VOSummary": {
            "@xmlns:xsi": "http://www.w3.org/2001/XMLSchema-instance",
            "@xsi:schemaLocation": VOSUMMARY_SCHEMA_URL,
            "VO": expanded_vo_list}}

    def _expand_vo(self, name: str, authorized: bool, filters: Filters) -> Optional[OrderedDict]:
        # Restore ordering
        new_vo = OrderedDict.fromkeys(["ID", "Name", "LongName", "CertificateOnly", "PrimaryURL",
                                       "MembershipServicesURL", "PurposeURL", "SupportURL", "AppDescription",
                                       "Community", "FieldsOfScience", "ParentVO", "ReportingGroups", "Active",
                                       "Disable", "ContactTypes", "OASIS", "Credentials"])
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
            managers = vo["OASIS"]["Managers"]
            if isinstance(managers, dict):
                oasis["Managers"] = self._expand_oasis_legacy_managers(managers)
            else:
                oasis["Managers"] = self._expand_oasis_managers(managers)
        if not is_null(vo, "OASIS", "OASISRepoURLs"):
            oasis["OASISRepoURLs"] = {"URL": vo["OASIS"]["OASISRepoURLs"]}
        new_vo["OASIS"] = oasis

        if not is_null(vo, "FieldsOfScience"):
            new_vo["FieldsOfScience"] = self._expand_fields_of_science(vo["FieldsOfScience"])

        if not is_null(vo, "ParentVO"):
            parentvo = OrderedDict.fromkeys(["ID", "Name"])
            parentvo.update(vo["ParentVO"])
            new_vo["ParentVO"] = parentvo

        if not is_null(vo, "Credentials"):
            credentials = OrderedDict.fromkeys(["TokenIssuers"])
            if not is_null(vo, "Credentials", "TokenIssuers"):
                token_issuers = vo["Credentials"]["TokenIssuers"]
                new_token_issuers = [
                    OrderedDict([
                        ("URL", x.get("URL")),
                        ("DefaultUnixUser", x.get("DefaultUnixUser")),
                        ("Description", x.get("Description")),
                        ("Subject", x.get("Subject")),
                    ])
                    for x in token_issuers
                ]
                credentials["TokenIssuers"] = {"TokenIssuer": new_token_issuers}
            new_vo["Credentials"] = credentials

        return new_vo

    def _expand_contacttypes(self, vo_contacts: Dict, authorized: bool) -> Dict:
        new_contacttypes = []
        for type_, list_ in vo_contacts.items():
            contact_items = []
            for contact in list_:
                contact_id = contact["ID"]
                new_contact = OrderedDict([("Name", contact["Name"])])
                if self.contacts_data:
                    user = self.contacts_data.users_by_id.get(contact_id)
                    if user:
                        new_contact["CILogonID"] = user.cilogon_id
                        if authorized:
                            new_contact["Email"] = user.email
                            new_contact["Phone"] = user.phone
                            new_contact["SMSAddress"] = user.sms_address
                            dns = user.dns
                            if dns:
                                new_contact["DN"] = dns[0]
                    else:
                        log.warning("id %s not found for %s", contact_id, contact["Name"])
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

    def _expand_oasis_legacy_managers(self, managers):
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

            new_managers[name]["CILogonID"] = None
            if self.contacts_data:
                user = self.contacts_data.users_by_id.get(data["ID"])
                if user:
                    new_managers[name]["CILogonID"] = user.cilogon_id
        return {"Manager": expand_attr_list(new_managers, "Name", ordering=["Name", "CILogonID", "DNs"],
                                            ignore_missing=True)}

    def _expand_oasis_managers(self, managers):
        """Expand
        [{"Name", "a", "DNs": [...]}, ...]
        into
        {"Manager": [{"Name": "a", "DNs": {"DN": [...]}}, ...]}
        """
        new_managers = copy.deepcopy(managers)
        for i, data in enumerate(managers):
            if not is_null(data, "DNs"):
                new_managers[i]["DNs"] = {"DN": data["DNs"]}
            else:
                new_managers[i]["DNs"] = None
            new_managers[i]["CILogonID"] = None
            if self.contacts_data:
                user = self.contacts_data.users_by_id.get(data["ID"])
                if user:
                    new_managers[i]["CILogonID"] = user.cilogon_id

        def order_manager_dict(m):
            return order_dict(m, ordering=["Name", "CILogonID", "DNs"], ignore_missing=True)

        return {"Manager": list(map(order_manager_dict, new_managers))}

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
