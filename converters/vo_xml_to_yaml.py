import pprint
import xmltodict
import yaml

from typing import Dict, List, Union
from convertlib import is_null, simplify_attr_list, ensure_list

with open('vos.xml', 'r') as vo_xml_file:
    # Use dict_constructore = dict so we don't get ordered dicts, we don't really care about ordering
    parsed = xmltodict.parse(vo_xml_file.read(), dict_constructor=dict)



# Multiline string to look nice'er
def str_presenter(dumper, data):
    if len(data.splitlines()) > 1:  # check for multiline string
        return dumper.represent_scalar('tag:yaml.org,2002:str', data, style='|')
    return dumper.represent_scalar('tag:yaml.org,2002:str', data)

yaml.add_representer(str, str_presenter)


def simplify_contacttypes(contacttypes):
    """Simplify ContactTypes attribute

    Turn e.g.
    {"ContactTypes":
        {"ContactType":
            [{"Contacts":
                {"Contact": [{"Name": "Steve Timm"},
                             {"Name": "Joe Boyd"}]},
              "Type": "Miscellaneous Contact"}
            ]
        }
    }

    into

    {"Contacts":
        {"Miscellanous Contact":
            [ "Steve Timm", "Joe Boyd" ]
        }
    }
    """
    if is_null(contacttypes):
        return None
    contacttypes_simple = simplify_attr_list(contacttypes["ContactType"], "Type")
    new_contacts = {}

    for contact_type, contact_data in contacttypes_simple.items():
        contacts_list = []
        for contact in ensure_list(contact_data["Contacts"]["Contact"]):
            if contact["Name"] not in contacts_list:
                contacts_list.append(contact["Name"])
        new_contacts[contact_type] = contacts_list

    return new_contacts


def simplify_reportinggroups(reportinggroups):
    """Simplify ReportingGroups attributes

    Turn e.g.
    {"ReportingGroup": [{"Contacts": {"Contact": [{"Name": "a"},
                                                  {"Name": "b"}
                                     },
                         "FQANs": {"FQAN": [{"GroupName": "XXX",
                                             "Role": "YYY"}]
                                  }
                         "Name": "ZZZ"
                        }]
    }

    into
    {"ZZZ": {"Contacts": ["a", "b"],
             "FQANs": [{"GroupName": "XXX", "Role": "YYY"}]
            }
    }

    """
    if is_null("ReportingGroup"):
        return None

    # [{"Name": "XXX", <...>}, {"Name": "YYY", <...>}]  becomes
    #  {"XXX": {<...>}, "YYY": {<...>}>
    new_reportinggroups = simplify_attr_list(reportinggroups["ReportingGroup"], "Name")
    if not new_reportinggroups:  # only null entries found
        return None

    for rgname, rgdata in new_reportinggroups.items():
        if not is_null(rgdata["Contacts"], "Contact"):
            # {"Contacts": {"Contact": [{"Name": "a"}, {"Name": "b"}]}} becomes
            # {"Contacts": ["a", "b"]}
            new_contacts = []
            for c in ensure_list(rgdata["Contacts"]["Contact"]):
                if not is_null(c, "Name") and c["Name"] not in new_contacts:
                    new_contacts.append(c["Name"])
            rgdata["Contacts"] = new_contacts

        if not is_null(rgdata["FQANs"], "FQAN"):
            rgdata["FQANs"] = ensure_list(rgdata["FQANs"]["FQAN"])

    return new_reportinggroups


def simplify_oasis_managers(managers):
    """Simplify OASIS/Managers attributes

    Turn
    {"Manager": [{"Name": "a", "DNs": {"DN": [...]}}]}
    into
    {"a": {"DNs": [...]}}
    """
    if is_null(managers, "Manager"):
        return None
    new_managers = simplify_attr_list(managers["Manager"], "Name")
    for manager, data in new_managers.items():
        if not is_null(data, "DNs"):
            data["DNs"] = data["DNs"]["DN"]
        if not is_null(data, "ContactID"):
            data["ContactID"] = int(data["ContactID"])
    return new_managers


def simplify_fields_of_science(fos: Dict) -> Union[Dict, None]:
    """Turn
    {"PrimaryFields": {"Field": ["P1", "P2", ...]},
     "SecondaryFields": {"Field": ["S1", "S2", ...]}}
    into
    {"Primary": ["P1", "P2", ...],
     "Secondary": ["S1", "S2", ...]}
    """
    if is_null(fos, "PrimaryFields") or is_null(fos["PrimaryFields"], "Field"):
        return None
    new_fields = {"Primary": ensure_list(fos["PrimaryFields"]["Field"])}
    if not is_null(fos, "SecondaryFields", "Field"):
        new_fields["Secondary"] = ensure_list(fos["SecondaryFields"]["Field"])
    return new_fields


for vo in parsed['VOSummary']['VO']:
    if "ID" in vo:
        vo["ID"] = int(vo["ID"])
    vo["Active"] = bool(vo.get("Active", False))
    vo["CertificateOnly"] = bool(vo.get("CertificateOnly", False))
    vo["Disable"] = bool(vo.get("Disable", False))
    if "ContactTypes" in vo:
        vo["Contacts"] = simplify_contacttypes(vo["ContactTypes"])
        del vo["ContactTypes"]
    if "ReportingGroups" in vo:
        vo["ReportingGroups"] = simplify_reportinggroups(vo["ReportingGroups"])
    if "OASIS" in vo:
        if not is_null(vo["OASIS"], "Managers"):
            vo["OASIS"]["Managers"] = simplify_oasis_managers(vo["OASIS"]["Managers"])
        if not is_null(vo["OASIS"], "OASISRepoURLs", "URL"):
            vo["OASIS"]["OASISRepoURLs"] = ensure_list(vo["OASIS"]["OASISRepoURLs"]["URL"])
        vo["OASIS"]["UseOASIS"] = bool(vo["OASIS"].get("UseOASIS", False))
    if not is_null(vo, "FieldsOfScience"):
        vo["FieldsOfScience"] = simplify_fields_of_science(vo["FieldsOfScience"])
    if not is_null(vo, "ParentVO"):
        vo["ParentVO"]["ID"] = int(vo["ParentVO"]["ID"])
    vo.pop("MemeberResources", None)  # will recreate MemeberResources [sic] from RG data

    serialized = yaml.safe_dump(vo, encoding='utf-8', default_flow_style=False)
    print(serialized.decode())
    with open("virtual-organizations/{0}.yaml".format(vo['Name']), 'w') as f:
        f.write(serialized.decode())

