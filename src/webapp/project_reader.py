from argparse import ArgumentParser
from collections import OrderedDict

import os

import anymarkup



def get_projects(indir="../projects"):
    to_output = {"Projects":{"Project": []}}
    projects = []

    for file in os.listdir(indir):
        project = OrderedDict.fromkeys(["ID", "Name", "Description", "PIName", "Organization", "Department",
                                        "FieldOfScience", "Sponsor"])
        project.update(anymarkup.parse_file(os.path.join(indir, file)))
        projects.append(project)

    to_output["Projects"]["Project"] = projects

    return to_output


def get_projects_xml(indir="../projects"):
    """Returns the serialized XML as a string"""
    return anymarkup.serialize(get_projects(indir), 'xml').decode()


if __name__ == "__main__":
    # We are running as the main script
    parser = ArgumentParser()
    parser.add_argument("indir", help="input dir for projects data")
    parser.add_argument("outfile", nargs='?', default=None, help="output file for vosummary")
    args = parser.parse_args()

    xml = get_projects_xml(args.indir)
    if args.outfile:
        with open(args.outfile, "w") as fh:
            fh.write(xml)
    else:
        print(xml)
