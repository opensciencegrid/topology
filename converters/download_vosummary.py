#!/usr/bin/env python3

from subprocess import Popen, PIPE
from argparse import ArgumentParser
import os
import sys
import urllib.parse
import urllib.request


YES, NO, ONLY = "yes", "no", "only"

# summary_attrs_showfield_of_science=on&all_vos=on&active=on&active_value=1&oasis_value=1&sort_key=name
params = {
    "all_vos": "on",
    "sort_key": "name",

    "summary_attrs_showcontact": "on",
    "summary_attrs_showdesc": "on",
    "summary_attrs_showfield_of_science": "on",
    "summary_attrs_showmember_resource": "on",
    "summary_attrs_showoasis": "on",
    "summary_attrs_showparent_vo": "on",
    "summary_attrs_showreporting_group": "on",

    "oasis_value": "1",
}

parser = ArgumentParser()
parser.add_argument("--show-inactive", choices=[YES, NO, ONLY], default=YES)

args = parser.parse_args()

if args.show_inactive == ONLY:
    params["active"] = "on"
    params["active_value"] = "0"
elif args.show_inactive == NO:
    params["active"] = "on"
    params["active_value"] = "1"
elif args.show_inactive == YES:
    params.pop("active", None)
else: assert False


query = urllib.parse.urlencode(params)

url = "https://myosg.grid.iu.edu/vosummary/xml?%s" % query

with urllib.request.urlopen(url) as req:
    data = req.read().decode("utf-8")

newenv = os.environ.copy()
newenv["XMLLINT_INDENT"] = "\t"
proc = Popen("xmllint --format -", stdin=PIPE, stdout=sys.stdout, shell=True, encoding="utf-8", env=newenv)
proc.communicate(data)
