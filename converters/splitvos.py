#!/usr/bin/env python3
"""Split a VOSummary XML file into a directory of XML files of the
individual <VO>s.
"""
import anymarkup
import os
import shutil
import sys
import xmltodict

try:
    infile, outdir = sys.argv[1:]
except IndexError:
    print("Usage: %s <infile> <outdir>" % sys.argv[0], file=sys.stderr)
    sys.exit(2)

with open(infile, "r") as infh:
    # Use dict constructor to get rid of ordering
    parsed = xmltodict.parse(infh.read(), dict_constructor=dict)

if not os.path.exists(outdir):
    os.makedirs(outdir)
vos = parsed["VOSummary"]["VO"]
for vo in vos:
    anymarkup.serialize_file({"VO": vo}, os.path.join(outdir, vo["Name"]+".xml"), format="xml")
