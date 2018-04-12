import os

import anymarkup



def get_vos_xml():
    """
    Returns the serailized xml (as a string)
    """

    to_output = {"VOSummary":{"VO": []}}
    projects = []

    for file in os.listdir("virtual-organiztions"):
        vo = anymarkup.parse_file("virtual-organizations/{0}".format(file))
        projects.append(vo)


    to_output["VOSummary"]["VO"] = vo

    return anymarkup.serialize(to_output, 'xml').decode()


if __name__ == "__main__":
    # We are running as the main script

    with open('new_vos.xml', 'w') as xml_file:
        xml_file.write(get_vos_xml())

