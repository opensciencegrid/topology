import xmltodict
import yaml

with open('projects.xml', 'r') as project_xml_file:
    # Use dict_constructore = dict so we don't get ordered dicts, we don't really care about ordering
    parsed = xmltodict.parse(project_xml_file.read(), dict_constructor=dict)



# Multiline string to look nice'er
def str_presenter(dumper, data):
    if len(data.splitlines()) > 1:  # check for multiline string
        return dumper.represent_scalar('tag:yaml.org,2002:str', data, style='|')
    return dumper.represent_scalar('tag:yaml.org,2002:str', data)

yaml.add_representer(str, str_presenter)


for project in parsed['Projects']['Project']:
    print("Would Create file: {0}.yaml".format(project['Name']))
    serialized = yaml.safe_dump(project, encoding='utf-8', default_flow_style=False)
    print(serialized.decode())
    with open("projects/{0}.yaml".format(project['Name']), 'w') as f:
        f.write(serialized.decode())
