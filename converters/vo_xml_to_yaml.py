import pprint
import xmltodict
import yaml

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
    return new_managers


for vo in parsed['VOSummary']['VO']:
    newvo = vo
    if "ContactTypes" in newvo:
        newvo["Contacts"] = simplify_contacttypes(newvo["ContactTypes"])
        del newvo["ContactTypes"]
    if "ReportingGroups" in newvo:
        newvo["ReportingGroups"] = simplify_reportinggroups(newvo["ReportingGroups"])
    if "OASIS" in vo and not is_null(vo["OASIS"], "Managers"):
        vo["OASIS"]["Managers"] = simplify_oasis_managers(vo["OASIS"]["Managers"])

    serialized = yaml.safe_dump(vo, encoding='utf-8', default_flow_style=False)
    print(serialized.decode())
    with open("virtual-organizations/{0}.yaml".format(newvo['Name']), 'w') as f:
        f.write(serialized.decode())

