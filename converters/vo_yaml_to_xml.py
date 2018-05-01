import pprint

import os

import anymarkup

from typing import Dict

try:
    from convertlib import is_null, expand_attr_list_single, singleton_list_to_value, expand_attr_list, ensure_list
except ModuleNotFoundError:
    from .convertlib import is_null, expand_attr_list_single, singleton_list_to_value, expand_attr_list, ensure_list


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


def expand_reportinggroups(reportinggroups: Dict) -> Dict:
    """Expand
    {"ZZZ": {"Contacts": ["a", "b"],
             "FQANs": [{"GroupName": "XXX", "Role": "YYY"}]
            }
    }
    to
    {"ReportingGroup": [{"Contacts": {"Contact": [{"Name": "a"},
                                                 {"Name": "b"}
                                     },
                         "FQANs": {"FQAN": [{"GroupName": "XXX",
                                             "Role": "YYY"}]
                                  }
                         "Name": "ZZZ"
                       }]
    }
    """
    # {"ZZZ": {"Contacts": ..., "FQANs": ...}}
    # to
    # [{"Contacts": ..., "FQANs": ..., "Name": "ZZZ"}]

    new_reportinggroups = reportinggroups.copy()
    for name, data in new_reportinggroups.items():
        try:
            if not is_null(data, "Contacts"):
                new_contact = [{"Name": x} for x in data["Contacts"]]
                data["Contacts"] = {"Contacts": {"Contact": singleton_list_to_value(new_contact)}}
            else:
                data["Contacts"] = None
            if not is_null(data, "FQANs"):
                data["FQANs"] = {"FQAN": singleton_list_to_value(data["FQANs"])}
            else:
                data["FQANs"] = None
        except Exception:
            pprint.pprint(new_reportinggroups)
            raise
    new_reportinggroups = expand_attr_list(reportinggroups, "Name")
    return {"ReportingGroup": new_reportinggroups}


def get_vos_xml():
    """
    Returns the serailized xml (as a string)
    """

    to_output = {"VOSummary":{"VO": []}}
    vos = []

    for file in os.listdir("virtual-organizations"):
        vo = anymarkup.parse_file("virtual-organizations/{0}".format(file))
        if is_null(vo, "Contacts"):
            vo["ContactTypes"] = None
        else:
            vo["ContactTypes"] = expand_contacttypes(vo["Contacts"])
            del vo["Contacts"]
        if is_null(vo, "ReportingGroups"):
            vo["ReportingGroups"] = None
        else:
            vo["ReportingGroups"] = expand_reportinggroups(vo["ReportingGroups"])
        vos.append(vo)


    to_output["VOSummary"]["VO"] = vos

    return anymarkup.serialize(to_output, 'xml').decode()


if __name__ == "__main__":
    # We are running as the main script

    with open('new_vos.xml', 'w') as xml_file:
        xml_file.write(get_vos_xml())

