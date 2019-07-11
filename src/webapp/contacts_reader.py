#!/usr/bin/env python3
from argparse import ArgumentParser, FileType
from collections import OrderedDict
import hashlib
from logging import getLogger
import os
import sys
from typing import Dict, Optional

# thanks stackoverflow
if __name__ == "__main__" and __package__ is None:
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from webapp.common import to_xml, MISCUSER_SCHEMA_URL, load_yaml_file


log = getLogger(__name__)


class User(object):
    def __init__(self, id_, yaml_data):
        self.id = id_
        self.yaml_data = yaml_data

    def get_tree(self, authorized=False, filters=None) -> Optional[OrderedDict]:
        tree = OrderedDict()
        tree["FullName"] = self.yaml_data["FullName"]
        tree["ID"] = self.id
        tree["PhotoURL"] = self.yaml_data.get("PhotoURL", None)
        tree["GravatarURL"] = self._get_gravatar_url(
            self.yaml_data["ContactInformation"]["PrimaryEmail"])
        tree["Profile"] = self.yaml_data.get("Profile", None)
        tree["GitHub"] = self.yaml_data.get("GitHub", None)
        if self.yaml_data.get("Flags"):
            tree["Flags"] = {"Flag": self.yaml_data["Flags"]}
        if authorized:
            tree["ContactInformation"] = self._expand_contact_info()
        return tree

    @property
    def name(self):
        return self.yaml_data["FullName"]

    @property
    def email(self):
        return self.yaml_data["ContactInformation"]["PrimaryEmail"]

    @property
    def phone(self):
        return self.yaml_data["ContactInformation"].get("PrimaryPhone", None)

    @property
    def sms_address(self):
        return self.yaml_data["ContactInformation"].get("SMSAddress", None)

    @property
    def dns(self):
        dns = self.yaml_data["ContactInformation"].get("DNs", None)
        return dns

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
        for user_id, user_data in self.yaml_data.items():
            self.users_by_id[user_id] = User(user_id, user_data)

    def get_dns(self):
        """
        Get the DNs for all of the users (useful for auth)
        """
        dns = []
        for id, user in self.users_by_id.items():
            if not user.dns:
                continue
            for dn in user.dns:
                dns.append(dn)
        return dns

    def get_tree(self, authorized=False, filters=None) -> Dict:
        user_list = []
        for id_ in sorted(self.users_by_id.keys(),
                          key=lambda x: self.users_by_id[x].name.lower()):
            user = self.users_by_id[id_]
            assert isinstance(user, User)
            try:
                user_tree = user.get_tree(authorized, filters)
            except (AttributeError, KeyError, ValueError) as err:
                log.exception("Error adding user with id %s: %r", id_, err)
                continue
            if user_tree:
                user_list.append(user_tree)
        return {"Users":
                {"@xmlns:xsi": "http://www.w3.org/2001/XMLSchema-instance",
                 "@xsi:schemaLocation": MISCUSER_SCHEMA_URL,
                 "User": user_list}}


def get_contacts_data(infile) -> ContactsData:
    if infile:
        return ContactsData(load_yaml_file(infile))
    else:
        return ContactsData({})


def main(argv):
    parser = ArgumentParser()
    parser.add_argument("infile", help="input file for contacts data")
    parser.add_argument("outfile", nargs='?', default=None, help="output file for miscuser")
    args = parser.parse_args(argv[1:])
    xml = to_xml(get_contacts_data(args.infile).get_tree(authorized=True))
    if args.outfile:
        with open(args.outfile, "w") as fh:
            fh.write(xml)
    else:
        print(xml)


if __name__ == '__main__':
    sys.exit(main(sys.argv))
