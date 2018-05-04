#!/usr/bin/env python3

from subprocess import Popen, PIPE
import os
import sys
import urllib.parse
import urllib.request


params = {
    "all_resources": "on",

    "downtime_attrs_showpast": "7",  # number of days or "all"
}

query = urllib.parse.urlencode(params)

url = "https://myosg.grid.iu.edu/rgdowntime/xml?%s" % query

with urllib.request.urlopen(url) as req:
    data = req.read().decode("utf-8")

newenv = os.environ.copy()
newenv["XMLLINT_INDENT"] = "\t"
proc = Popen("xmllint --format -", stdin=PIPE, stdout=sys.stdout, shell=True, encoding="utf-8", env=newenv)
proc.communicate(data)
