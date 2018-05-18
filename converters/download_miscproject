#!/usr/bin/env python3

from subprocess import Popen, PIPE
import os
import sys
import urllib.parse
import urllib.request


params = {
    "count_active": "on",
    "count_enabled": "on",
}

query = urllib.parse.urlencode(params)

url = "https://myosg.grid.iu.edu/miscproject/xml?count_sg_1&%s" % query

with urllib.request.urlopen(url) as req:
    data = req.read().decode("utf-8")

newenv = os.environ.copy()
newenv["XMLLINT_INDENT"] = "\t"
proc = Popen("xmllint --format -", stdin=PIPE, stdout=sys.stdout, shell=True, encoding="utf-8", env=newenv)
proc.communicate(data)
