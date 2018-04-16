#!/usr/bin/env python3

from subprocess import Popen, PIPE
from argparse import ArgumentParser
import os
import sys
import urllib.parse
import urllib.request


YES, NO, ONLY = "yes", "no", "only"


params = {
    "all_resources": "on",

    "summary_attrs_showservice": "1",
    # "summary_attrs_showrsvstatus": "1",  # <- should not be updated manually
    # "summary_attrs_showgipstatus": "1",  # <- gip is dead
    # "summary_attrs_showvomembership": "1",  # <- shows "SupportedVOs" field, usually blank & superseded by CE collector
    "summary_attrs_showvoownership": "1",
    "summary_attrs_showwlcg": "1",
    # "summary_attrs_showenv": "1",  # <- this one is never filled out
    "summary_attrs_showcontact": "1",
    "summary_attrs_showfqdn": "1",
    "summary_attrs_showhierarchy": "1",

    # "summary_attrs_showticket": "1",  # <- shows open GOC tickets
}

parser = ArgumentParser()
parser.add_argument("--show-inactive", choices=[YES, NO, ONLY], default=NO)
parser.add_argument("--show-itb", choices=[YES, NO, ONLY], default=NO)
parser.add_argument("--show-disabled-resource", choices=[YES, NO, ONLY], default=YES)
# can't filter on disabled _ResourceGroup_, but can show/hide RG's if they have _any_ Resources enabled/disabled

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

if args.show_itb == ONLY:
    params["gridtype"] = "on"
    params["gridtype_2"] = "on"
elif args.show_itb == NO:
    params["gridtype"] = "on"
    params["gridtype_1"] = "on"
elif args.show_itb == YES:
    params.pop("gridtype", None)
else: assert False

if args.show_disabled_resource == ONLY:
    params["disable"] = "on"
    params["disable_value"] = "1"
elif args.show_disabled_resource == NO:
    params["disable"] = "on"
    params["disable_value"] = "0"
elif args.show_disabled_resource == YES:
    params.pop("disable", None)
else: assert False


query = urllib.parse.urlencode(params)

url = "https://myosg.grid.iu.edu/rgsummary/xml?%s" % query

with urllib.request.urlopen(url) as req:
    data = req.read().decode("utf-8")

newenv = os.environ.copy()
#newenv["XMLLINT_INDENT"] = "\t"
proc = Popen("xmllint --format -", stdin=PIPE, stdout=sys.stdout, shell=True, encoding="utf-8", env=newenv)
proc.communicate(data)
