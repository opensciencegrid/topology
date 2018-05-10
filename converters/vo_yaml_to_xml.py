import pprint
from collections import OrderedDict

import os

import anymarkup

from typing import Dict, List

try:
    from convertlib import is_null, expand_attr_list_single, expand_attr_list, ensure_list
except ModuleNotFoundError:
    from .convertlib import is_null, expand_attr_list_single, expand_attr_list, ensure_list


VO_SCHEMA_LOCATION = "https://my.opensciencegrid.org/schema/vosummary.xsd"


def expand_contacttypes(contacts: Dict) -> Dict:
    """Expand
    {"Submitter Contact": ["a", "b"],
     "Miscellaneous Contact": ["c", "d"]}
    to
    {"ContactType": [{"Type": "Submitter Contact", {"Contacts": {"Contact": [{"Name": "a"}, {"Name": "b"}]}}},
                     {"Type": "Miscellaneous Contact", {"Contacts": {"Contact": [{"Name": "a"}, {"Name": "b"}]}}}
                    ]
    }
    """
    new_contacttypes = []
    for type_, list_ in contacts.items():
        contact_data = [{"Name": x} for x in list_]
        new_contacttypes.append({"Type": type_, "Contacts": {"Contact": contact_data}})
    return {"ContactType": new_contacttypes}


def expand_reportinggroups(reportinggroups_list: List, reportinggroups_data: Dict) -> Dict:
    """Expand
    ["XXX", "YYY", "ZZZ"]
    using data from reportinggroups_data into
    {"ReportingGroup": [{"Contacts": {"Contact": [{"Name": "a"},
                                                 {"Name": "b"}
                                     },
                         "FQANs": {"FQAN": [{"GroupName": "...",
                                             "Role": "..."}]
                                  }
                         "Name": "XXX"
                       }]
    }
    """
    new_reportinggroups = {}
    for name, data in reportinggroups_data.items():
        if name not in reportinggroups_list: continue
        new_reportinggroups[name] = {}
        newdata = new_reportinggroups[name]
        if not is_null(data, "Contacts"):
            new_contact = [{"Name": x} for x in data["Contacts"]]
            newdata["Contacts"] = {"Contact": new_contact}
        else:
            newdata["Contacts"] = None
        if not is_null(data, "FQANs"):
            fqans = []
            for fqan in data["FQANs"]:
                fqans.append(OrderedDict([("GroupName", fqan["GroupName"]), ("Role", fqan["Role"])]))
            newdata["FQANs"] = {"FQAN": fqans}
        else:
            newdata["FQANs"] = None
    new_reportinggroups = expand_attr_list(new_reportinggroups, "Name", ordering=["Name", "FQANs", "Contacts"])
    return {"ReportingGroup": new_reportinggroups}


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


def expand_vo(vo, reportinggroups_data):
    vo = vo.copy()

    if is_null(vo, "Contacts"):
        vo["ContactTypes"] = None
    else:
        vo["ContactTypes"] = expand_contacttypes(vo["Contacts"])
    vo.pop("Contacts", None)
    if is_null(vo, "ReportingGroups"):
        vo["ReportingGroups"] = None
    else:
        vo["ReportingGroups"] = expand_reportinggroups(vo["ReportingGroups"], reportinggroups_data)
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

def get_vos_xml():
    """
    Returns the serialized xml (as a string)
    """
    to_output = get_vos()

    return anymarkup.serialize(to_output, 'xml').decode()


def get_vos():
    to_output = {"VOSummary": {
        "@xmlns:xsi": "http://www.w3.org/2001/XMLSchema-instance",
        "@xsi:schemaLocation": VO_SCHEMA_LOCATION,
        "VO": []}}
    vos = []
    reportinggroups_data = anymarkup.parse_file("virtual-organizations/REPORTING_GROUPS.yaml")
    for file in os.listdir("virtual-organizations"):
        if file == "REPORTING_GROUPS.yaml": continue
        vo = anymarkup.parse_file("virtual-organizations/{0}".format(file))
        try:
            vos.append(expand_vo(vo, reportinggroups_data))
        except Exception:
            pprint.pprint(vo)
            raise
    to_output["VOSummary"]["VO"] = vos
    return to_output


if __name__ == "__main__":
    # We are running as the main script

    with open('new_vos.xml', 'w') as xml_file:
        xml_file.write(get_vos_xml())

