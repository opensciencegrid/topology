import xmltodict
import yaml

from typing import Dict, List, Union

with open('vos.xml', 'r') as vo_xml_file:
    # Use dict_constructore = dict so we don't get ordered dicts, we don't really care about ordering
    parsed = xmltodict.parse(vo_xml_file.read(), dict_constructor=dict)

def simplify_contactlists(node):
    """
    Recursively scan through the data structure, looking for the key "Contact",
    and deduplicate the list.
    """
    if isinstance(node, dict):
        if 'Contact' in node:
            # De-dupe!!!
            if isinstance(node['Contact'], list):
                # From https://stackoverflow.com/questions/7090758/python-remove-duplicate-dictionaries-from-a-list
                # Convert each item in the list to a tuple.  Then do a 'set' on that, then convert back to dict.
                node['Contact'] = [dict(tupleized) for tupleized in set(tuple(item.items()) for item in node['Contact'])]
        elif 'ContactID' in node:
            del node['ContactID']
        else:
            for key in node:
                simplify_contactlists(node[key])
    elif isinstance(node, list):
        for item in node:
            simplify_contactlists(item)


# Multiline string to look nice'er
def str_presenter(dumper, data):
    if len(data.splitlines()) > 1:  # check for multiline string
        return dumper.represent_scalar('tag:yaml.org,2002:str', data, style='|')
    return dumper.represent_scalar('tag:yaml.org,2002:str', data)

yaml.add_representer(str, str_presenter)


for vo in parsed['VOSummary']['VO']:
    simplify_contactlists(vo)
    print("Would Create file: {0}.yaml".format(vo['Name']))
    serialized = yaml.safe_dump(vo, encoding='utf-8', default_flow_style=False)
    print(serialized.decode())
    with open("virtual-organizations/{0}.yaml".format(vo['Name']), 'w') as f:
        f.write(serialized.decode())

