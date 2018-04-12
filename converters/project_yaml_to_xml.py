import os

import anymarkup



def get_projects_xml():
    """
    Returns the serailized xml (as a string)
    """

    to_output = {"Projects":{"Project": []}}
    projects = []

    for file in os.listdir("projects"):
        project = anymarkup.parse_file("projects/{0}".format(file))
        # For some reason, it parses the yaml file as a list of dictionaries
        # Convert to a big dictionary, so it can output proper xml
        new_project = {}
        for attr in project:
            new_project.update(attr)
        projects.append(new_project)


    to_output["Projects"]["Project"] = projects


    return anymarkup.serialize(to_output, 'xml')


if __name__ == "__main__":
    # We are running as the main script

    with open('new_projects.xml', 'w') as xml_file:
        xml_file.write(get_projects_xml())

