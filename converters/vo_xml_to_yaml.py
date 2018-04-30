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


for vo in parsed['VOSummary']['VO']:
    newvo = vo
    if "ContactTypes" in newvo:
        newvo["Contacts"] = simplify_contacttypes(newvo["ContactTypes"])
        del newvo["ContactTypes"]

    # pprint.pprint(newvo)

    print("Would Create file: {0}.yaml".format(newvo['Name']))
    serialized = yaml.safe_dump(vo, encoding='utf-8', default_flow_style=False)
    print(serialized.decode())
    with open("virtual-organizations/{0}.yaml".format(newvo['Name']), 'w') as f:
        f.write(serialized.decode())

