import pprint

import os

import anymarkup

from typing import Dict, List

try:
    from convertlib import is_null, expand_attr_list_single, singleton_list_to_value, expand_attr_list, ensure_list
except ModuleNotFoundError:
    from .convertlib import is_null, expand_attr_list_single, singleton_list_to_value, expand_attr_list, ensure_list


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
        contact_data = singleton_list_to_value([{"Name": x} for x in list_])
        new_contacttypes.append({"Type": type_, "Contacts": {"Contact": contact_data}})
    return {"ContactType": singleton_list_to_value(new_contacttypes)}


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
            newdata["Contacts"] = {"Contacts": {"Contact": singleton_list_to_value(new_contact)}}
        else:
            newdata["Contacts"] = None
        if not is_null(data, "FQANs"):
            newdata["FQANs"] = {"FQAN": singleton_list_to_value(data["FQANs"])}
        else:
            newdata["FQANs"] = None
    new_reportinggroups = expand_attr_list(new_reportinggroups, "Name")
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
            new_managers[name]["DNs"] = {"DN": singleton_list_to_value(data["DNs"])}
        else:
            new_managers[name]["DNs"] = None
    return {"Manager": expand_attr_list(new_managers, "Name")}


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
    new_fields = {"PrimaryFields": {"Field": singleton_list_to_value(fields_of_science["PrimaryFields"])}}
    if not is_null(fields_of_science, "Secondary"):
        new_fields["SecondaryFields"] = {"Field": singleton_list_to_value(fields_of_science["SecondaryFields"])}
    return new_fields


def expand_vo(vo, reportinggroups_data):
    vo = vo.copy()

    if is_null(vo, "Contacts"):
        vo["ContactTypes"] = None
    else:
        vo["ContactTypes"] = expand_contacttypes(vo["Contacts"])
        del vo["Contacts"]
    if is_null(vo, "ReportingGroups"):
        vo["ReportingGroups"] = None
    else:
        vo["ReportingGroups"] = expand_reportinggroups(vo["ReportingGroups"], reportinggroups_data)
    if is_null(vo, "OASIS"):
        vo["OASIS"] = None
    else:
        if is_null(vo["OASIS"], "Managers"):
            vo["OASIS"]["Managers"] = None
        else:
            vo["OASIS"]["Managers"] = expand_oasis_managers(vo["OASIS"]["Managers"])
        if is_null(vo["OASIS"], "OASISRepoURLs"):
            vo["OASIS"]["OASISRepoURLs"] = None
        else:
            vo["OASIS"]["OASISRepoURLs"] = {"URL": singleton_list_to_value(vo["OASIS"]["OASISRepoURLs"])}
    if is_null(vo, "FieldsOfScience"):
        vo["FieldsOfScience"] = None
    else:
        vo["FieldsOfScience"] = expand_fields_of_science(vo["FieldsOfScience"])

    for key in ["MembershipServicesURL", "ParentVO", "PrimaryURL", "PurposeURL", "SupportURL"]:
        if key not in vo:
            vo[key] = None


    # TODO: Recreate <MemeberResources> [sic]
    #  should look like
    #  <MemeberResources>
    #    <Resource><ID>75</ID><Name>NERSC-PDSF</Name></Resource>
    #    ...
    #  </MemeberResources>

    return vo

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

