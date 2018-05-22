from argparse import ArgumentParser

import os

import anymarkup



def get_projects(indir="projects"):
    to_output = {"Projects":{"Project": []}}
    projects = []

    for file in os.listdir(indir):
        project = anymarkup.parse_file(os.path.join(indir, file))
        projects.append(project)

    to_output["Projects"]["Project"] = projects

    return to_output


def get_projects_xml():
    """Returns the serialized XML as a string"""
    return anymarkup.serialize(get_projects(), 'xml').decode()


if __name__ == "__main__":
    # We are running as the main script
    parser = ArgumentParser()
    parser.add_argument("indir", help="input dir for projects data")
    parser.add_argument("outfile", nargs='?', default=None, help="output file for vosummary")
    args = parser.parse_args()

    xml = get_projects_xml()
    if args.outfile:
        with open(args.outfile, "w") as fh:
            fh.write(xml)
    else:
        print(xml)
