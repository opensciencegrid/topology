import xmltodict
import yaml
import anymarkup
import sys

if len(sys.argv) >= 2:
    with open(sys.argv[1], "r") as rg_xml_file:
        # Use dict constructor to get rid of ordering
        parsed = xmltodict.parse(rg_xml_file.read(), dict_constructor=dict)
else:
    parsed = xmltodict.parse(sys.stdin.read(), dict_constructor=dict)

if len(sys.argv) >= 3:
    anymarkup.serialize_file(parsed, sys.argv[2], format="xml")
else:
    print(anymarkup.serialize(parsed, format="xml").decode("utf-8", errors="ignore"))

# # Multiline string to look nice'er
# def str_presenter(dumper, data):
#     if len(data.splitlines()) > 1:  # check for multiline string
#         return dumper.represent_scalar('tag:yaml.org,2002:str', data, style='|')
#     return dumper.represent_scalar('tag:yaml.org,2002:str', data)
#
# yaml.add_representer(str, str_presenter)
#
#
# for vo in parsed['VOSummary']['VO']:
#     print("Would Create file: {0}.yaml".format(vo['Name']))
#     serialized = yaml.safe_dump(vo, encoding='utf-8', default_flow_style=False)
#     print(serialized.decode())
#     with open("virtual-organizations/{0}.yaml".format(vo['Name']), 'w') as f:
#         f.write(serialized.decode())
#
