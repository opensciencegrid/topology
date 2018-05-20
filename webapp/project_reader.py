import os

import anymarkup



def get_projects():
    to_output = {"Projects":{"Project": []}}
    projects = []

    for file in os.listdir("projects"):
        project = anymarkup.parse_file("projects/{0}".format(file))
        projects.append(project)


    to_output["Projects"]["Project"] = projects

    return to_output


def get_projects_xml():
    """Returns the serialized XML as a string"""
    return anymarkup.serialize(get_projects(), 'xml').decode()


if __name__ == "__main__":
    # We are running as the main script

    with open('new_projects.xml', 'w') as xml_file:
        xml_file.write(get_projects_xml())

