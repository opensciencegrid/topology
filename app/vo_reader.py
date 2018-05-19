from argparse import ArgumentParser, FileType
from collections import OrderedDict
import os
import pprint
import sys
from typing import Dict, List

import anymarkup

from app.common import Filters, MaybeOrderedDict, VOSUMMARY_SCHEMA_URL, is_null, expand_attr_list, to_xml


def expand_oasis_managers(managers):
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
    return {"Manager": expand_attr_list(new_managers, "Name", ordering=["ContactID", "Name", "DNs"], ignore_missing=True)}


def expand_fields_of_science(fields_of_science):
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


class VOData(object):
    def __init__(self, contacts_data, reporting_groups_data):
        self.contacts_data = contacts_data or {}
        self.vos = []
        self.reporting_groups_data = reporting_groups_data

    def add_vo(self, vo):
        self.vos.append(vo)

    def get_tree(self, authorized=False, filters: Filters = None) -> Dict:
        if not filters:
            filters = Filters()
        expanded_vos = list(
            filter(None,
                   [self._expand_vo(vo, authorized=authorized, filters=filters) for vo in self.vos]))

        return {"VOSummary": {
            "@xmlns:xsi": "http://www.w3.org/2001/XMLSchema-instance",
            "@xsi:schemaLocation": VOSUMMARY_SCHEMA_URL,
            "VO": expanded_vos}}

    def _expand_vo(self, vo: Dict, authorized: bool, filters: Filters) -> MaybeOrderedDict:
        if filters.active is not None:
            if filters.active != vo["Active"]:
                return None

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
                oasis["Managers"] = expand_oasis_managers(vo["OASIS"]["Managers"])
            if is_null(vo["OASIS"], "OASISRepoURLs"):
                oasis["OASISRepoURLs"] = None
            else:
                oasis["OASISRepoURLs"] = {"URL": vo["OASIS"]["OASISRepoURLs"]}
            vo["OASIS"] = oasis
        if is_null(vo, "FieldsOfScience"):
            vo["FieldsOfScience"] = None
        else:
            vo["FieldsOfScience"] = expand_fields_of_science(vo["FieldsOfScience"])

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


def get_vo_data(indir="virtual-organizations", contacts_data=None) -> VOData:
    reporting_groups_data = anymarkup.parse_file(os.path.join(indir, "REPORTING_GROUPS.yaml"))
    vo_data = VOData(contacts_data=contacts_data, reporting_groups_data=reporting_groups_data)
    for file in os.listdir(indir):
        if file == "REPORTING_GROUPS.yaml": continue
        vo = anymarkup.parse_file(os.path.join(indir, file))
        try:
            vo_data.add_vo(vo)
        except Exception:
            pprint.pprint(vo)
            raise
    return vo_data


def main(argv):
    parser = ArgumentParser()
    parser.add_argument("indir", help="input dir for virtual-organizations data")
    parser.add_argument("outfile", nargs='?', type=FileType('w'), default=sys.stdout, help="output file for vosummary")
    parser.add_argument("--contacts", help="contacts yaml file")
    args = parser.parse_args(argv[1:])

    contacts_data = None
    if args.contacts:
        contacts_data = anymarkup.parse_file(args.contacts)
    args.outfile.write(to_xml(get_vo_data(args.indir, contacts_data=contacts_data).get_tree(authorized=True)))

if __name__ == '__main__':
    sys.exit(main(sys.argv))
