#!/usr/bin/env python3
from argparse import ArgumentParser
import logging
import os
import pprint
import sys

import yaml

# thanks stackoverflow
if __name__ == "__main__" and __package__ is None:
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from webapp.common import load_yaml_file, to_xml
from webapp.contacts_reader import get_contacts_data
from webapp.vos_data import VOsData


log = logging.getLogger(__name__)


def get_vos_data(indir, contacts_data, strict=False) -> VOsData:
    reporting_groups_data = load_yaml_file(os.path.join(indir, "REPORTING_GROUPS.yaml"))
    vos_data = VOsData(contacts_data=contacts_data, reporting_groups_data=reporting_groups_data)
    for file in os.listdir(indir):
        if file == "REPORTING_GROUPS.yaml": continue
        if not file.endswith(".yaml"): continue
        name = file[:-5]
        data = None
        try:
            data = load_yaml_file(os.path.join(indir, file))
            vos_data.add_vo(name, data)
        except yaml.YAMLError:
            if strict:
                raise
            else:
                # load_yaml_file() already logs the specific error
                log.error("skipping (non-strict mode)")
                continue
        except Exception as e:
            log.error("%r adding VO %s", e, name)
            log.error("Data:\n%s", pprint.pformat(data))
            if strict:
                raise
            log.exception("Skipping (non-strict mode); exception info follows")
            continue

    return vos_data


def main(argv):
    parser = ArgumentParser()
    parser.add_argument("indir", help="input dir for virtual-organizations data")
    parser.add_argument("outfile", nargs='?', default=None, help="output file for vosummary")
    parser.add_argument("--contacts", help="contacts yaml file")
    parser.add_argument("--nostrict", action='store_false', dest='strict', help="Skip files with parse errors (instead of exiting)")
    args = parser.parse_args(argv[1:])

    contacts_data = None
    if args.contacts:
        contacts_data = get_contacts_data(args.contacts)
    xml = to_xml(
        get_vos_data(args.indir, contacts_data=contacts_data, strict=args.strict).get_tree(authorized=True))
    if args.outfile:
        with open(args.outfile, "w") as fh:
            fh.write(xml)
    else:
        print(xml)

if __name__ == '__main__':
    logging.basicConfig()
    sys.exit(main(sys.argv))
