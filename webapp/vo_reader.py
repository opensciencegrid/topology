from argparse import ArgumentParser, FileType
import os
import pprint
import sys

import anymarkup

from webapp.vos_data import VOsData
from webapp.common import to_xml


def get_vos_data(indir="virtual-organizations", contacts_data=None) -> VOsData:
    reporting_groups_data = anymarkup.parse_file(os.path.join(indir, "REPORTING_GROUPS.yaml"))
    vos_data = VOsData(contacts_data=contacts_data, reporting_groups_data=reporting_groups_data)
    for file in os.listdir(indir):
        if file == "REPORTING_GROUPS.yaml": continue
        if not file.endswith(".yaml"): continue
        name = file[:-5]
        data = anymarkup.parse_file(os.path.join(indir, file))
        try:
            vos_data.add_vo(name, data)
        except Exception:
            pprint.pprint(name, data)
            raise
    return vos_data


def main(argv):
    parser = ArgumentParser()
    parser.add_argument("indir", help="input dir for virtual-organizations data")
    parser.add_argument("outfile", nargs='?', type=FileType('w'), default=sys.stdout, help="output file for vosummary")
    parser.add_argument("--contacts", help="contacts yaml file")
    args = parser.parse_args(argv[1:])

    contacts_data = None
    if args.contacts:
        contacts_data = anymarkup.parse_file(args.contacts)
    args.outfile.write(to_xml(get_vos_data(args.indir, contacts_data=contacts_data).get_tree(authorized=True)))

if __name__ == '__main__':
    sys.exit(main(sys.argv))
