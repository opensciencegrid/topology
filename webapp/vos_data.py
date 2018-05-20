from collections import OrderedDict
from typing import Dict, List


from .common import Filters, MaybeOrderedDict, VOSUMMARY_SCHEMA_URL, is_null, expand_attr_list


class VOsData(object):
    def __init__(self, contacts_data, reporting_groups_data):
        self.contacts_data = contacts_data or {}
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
            expanded_vo_data = self._expand_vo(self.vos[vo_name], authorized=authorized, filters=filters)
            if expanded_vo_data:
                expanded_vo_list.append(expanded_vo_data)

        return {"VOSummary": {
            "@xmlns:xsi": "http://www.w3.org/2001/XMLSchema-instance",
            "@xsi:schemaLocation": VOSUMMARY_SCHEMA_URL,
            "VO": expanded_vo_list}}

    def _expand_vo(self, vo: Dict, authorized: bool, filters: Filters) -> MaybeOrderedDict:
        if filters.active is not None and filters.active != vo["Active"]:
            return
        if filters.disable is not None and filters.disable != vo["Disable"]:
            return
        if filters.oasis is not None and (is_null(vo, "OASIS", "UseOASIS") or
                                          filters.oasis != vo["OASIS"]["UseOASIS"]):
            return
        if filters.vo_id and vo["ID"] not in filters.vo_id:
            return

        vo = vo.copy()

        if is_null(vo, "Contacts"):
            vo["ContactTypes"] = None
        else:
            vo["ContactTypes"] = self._expand_contacttypes(vo["Contacts"], authorized)
        vo.pop("Contacts", None)
        if is_null(vo, "ReportingGroups"):
            vo["ReportingGroups"] = None
        else:
            vo["ReportingGroups"] = self._expand_reporting_groups(vo["ReportingGroups"], authorized)
        if is_null(vo, "OASIS"):
            vo["OASIS"] = None
        else:
            oasis = OrderedDict()
            oasis["UseOASIS"] = vo["OASIS"].get("UseOASIS", False)
            if is_null(vo["OASIS"], "Managers"):
                oasis["Managers"] = None
            else:
                oasis["Managers"] = self._expand_oasis_managers(vo["OASIS"]["Managers"])
            if is_null(vo["OASIS"], "OASISRepoURLs"):
                oasis["OASISRepoURLs"] = None
            else:
                oasis["OASISRepoURLs"] = {"URL": vo["OASIS"]["OASISRepoURLs"]}
            vo["OASIS"] = oasis
        if is_null(vo, "FieldsOfScience"):
            vo["FieldsOfScience"] = None
        else:
            vo["FieldsOfScience"] = self._expand_fields_of_science(vo["FieldsOfScience"])

        # Restore ordering
        if not is_null(vo, "ParentVO"):
            parentvo = OrderedDict()
            for elem in ["ID", "Name"]:
                if elem in vo["ParentVO"]:
                    parentvo[elem] = vo["ParentVO"][elem]
            vo["ParentVO"] = parentvo
        else:
            vo["ParentVO"] = None

        for key in ["MembershipServicesURL", "PrimaryURL", "PurposeURL", "SupportURL"]:
            if key not in vo:
                vo[key] = None


        # TODO: Recreate <MemeberResources> [sic]
        #  should look like
        #  <MemeberResources>
        #    <Resource><ID>75</ID><Name>NERSC-PDSF</Name></Resource>
        #    ...
        #  </MemeberResources>

        # Restore ordering
        new_vo = OrderedDict()
        for elem in ["ID", "Name", "LongName", "CertificateOnly", "PrimaryURL", "MembershipServicesURL", "PurposeURL",
                     "SupportURL", "AppDescription", "Community",
                     # TODO "MemeberResources",
                     "FieldsOfScience", "ParentVO", "ReportingGroups", "Active", "Disable", "ContactTypes", "OASIS"]:
            if elem in vo:
                new_vo[elem] = vo[elem]

        return new_vo

    def _expand_contacttypes(self, vo_contacts: Dict, authorized: bool) -> Dict:
        new_contacttypes = []
        for type_, list_ in vo_contacts.items():
            contact_data = []
            for contact in list_:
                new_contact = OrderedDict([("Name", contact["Name"])])
                if authorized:
                    if contact["ID"] in self.contacts_data:
                        extra_data = self.contacts_data[contact["ID"]]
                        new_contact["Email"] = extra_data["Email"]
                        new_contact["Phone"] = extra_data.get("Phone", "")
                        new_contact["SMSAddress"] = extra_data.get("SMS", "")
                contact_data.append(new_contact)
            new_contacttypes.append({"Type": type_, "Contacts": {"Contact": contact_data}})
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
        new_managers = managers.copy()
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
                    if authorized:
                        if contact["ID"] in self.contacts_data:
                            extra_data = self.contacts_data[contact["ID"]]
                            new_contact["Email"] = extra_data["Email"]
                            new_contact["Phone"] = extra_data.get("Phone", "")
                            new_contact["SMSAddress"] = extra_data.get("SMS", "")
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


