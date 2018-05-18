#!/usr/bin/env python3
from argparse import ArgumentParser
from subprocess import Popen, PIPE
import os
import sys
import urllib.parse
import urllib.request

# TODO Add the filtering arguments from download_rgsummary.py

params = {
    "all_resources": "on",
}


parser = ArgumentParser()
parser.add_argument("--past-days", default="7", help="Number of days of past downtime, '', or 'all'")
args = parser.parse_args()

params["downtime_attrs_showpast"] = args.past_days

query = urllib.parse.urlencode(params)

url = "https://myosg.grid.iu.edu/rgdowntime/xml?%s" % query

with urllib.request.urlopen(url) as req:
    data = req.read().decode("utf-8")

newenv = os.environ.copy()
newenv["XMLLINT_INDENT"] = "\t"
proc = Popen("xmllint --format -", stdin=PIPE, stdout=sys.stdout, shell=True, encoding="utf-8", env=newenv)
proc.communicate(data)
