import os

import anymarkup



def get_vos_xml():
    """
    Returns the serailized xml (as a string)
    """

    to_output = {"VOSummary":{"VO": []}}
    vos = []

    for file in os.listdir("virtual-organizations"):
        vo = anymarkup.parse_file("virtual-organizations/{0}".format(file))
        vos.append(vo)


    to_output["VOSummary"]["VO"] = vos

    return anymarkup.serialize(to_output, 'xml').decode()


if __name__ == "__main__":
    # We are running as the main script

    with open('new_vos.xml', 'w') as xml_file:
        xml_file.write(get_vos_xml())

