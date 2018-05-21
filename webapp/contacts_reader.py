from argparse import ArgumentParser, FileType
from collections import OrderedDict
import hashlib
import sys
from typing import Dict

import anymarkup

from webapp.common import MaybeOrderedDict, to_xml, MISCUSER_SCHEMA_URL


class User(object):
    def __init__(self, name, yaml_data):
        self.name = name
        self.yaml_data = yaml_data

    def get_tree(self, authorized=False, filters=None) -> MaybeOrderedDict:
        tree = OrderedDict()
        tree["FullName"] = self.name
        tree["PhotoURL"] = self.yaml_data.get("PhotoURL", None)
        tree["GravatarURL"] = self._get_gravatar_url(
            self.yaml_data["ContactInformation"]["PrimaryEmail"])
        tree["Profile"] = self.yaml_data.get("Profile", None)
        if authorized:
            tree["ContactInformation"] = self._expand_contact_info()
        return tree

    @property
    def email(self):
        return self.yaml_data["ContactInformation"]["PrimaryEmail"]

    @property
    def phone(self):
        return self.yaml_data["ContactInformation"].get("PrimaryPhone", None)

    @property
    def sms_address(self):
        return self.yaml_data["ContactInformation"].get("SMSAddress", None)

    @staticmethod
    def _get_gravatar_url(email):
        return "http://www.gravatar.com/avatar/{0}".format(
            hashlib.md5(email.strip().lower().encode()).hexdigest()
        )

    def _expand_contact_info(self):
        contact_info = OrderedDict()
        for key in ["PrimaryEmail", "SecondaryEmail", "PrimaryPhone",
                    "SecondaryPhone", "IM"]:
            contact_info[key] = self.yaml_data["ContactInformation"].get(key, None)
        dns = self.yaml_data["ContactInformation"].get("DNs", None)
        contact_info["DN"] = ",".join(dns) if dns else None
        contact_info["ContactPreference"] = \
            self.yaml_data["ContactInformation"].get("ContactPreference",
                               self.yaml_data.get("Profile", None))
        return contact_info


class ContactsData(object):
    def __init__(self, yaml_data):
        self.yaml_data = yaml_data
        self.users_by_id = {}
        for user_name, user_data in self.yaml_data.items():
            id_ = user_data["ID"]
            self.users_by_id[id_] = User(user_name, user_data)

    def get_tree(self, authorized=False, filters=None) -> Dict:
        user_list = []
        for id_ in sorted(self.users_by_id.keys(),
                          key=lambda x: self.users_by_id[x].name.lower()):
            user = self.users_by_id[id_]
            assert isinstance(user, User)
            user_tree = user.get_tree(authorized, filters)
            if user_tree:
                user_list.append(user_tree)
        return {"Users":
                {"@xmlns:xsi": "http://www.w3.org/2001/XMLSchema-instance",
                 "@xsi:schemaLocation": MISCUSER_SCHEMA_URL,
                 "User": user_list}}


def get_contacts_data(infile) -> ContactsData:
    return ContactsData(anymarkup.parse_file(infile))


def main(argv):
    parser = ArgumentParser()
    parser.add_argument("infile", help="input file for contacts data")
    parser.add_argument("outfile", nargs='?', type=FileType('w'), default=sys.stdout, help="output file for miscuser")
    args = parser.parse_args(argv[1:])
    args.outfile.write(to_xml(get_contacts_data(args.infile).get_tree(authorized=True)))

if __name__ == '__main__':
    sys.exit(main(sys.argv))
