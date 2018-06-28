#!/usr/bin/env python

from __future__ import print_function

import glob
import yaml
import sys
import os
import re

import xml.etree.ElementTree as et

_topdir = os.path.abspath(os.path.dirname(__file__) + "/../..")
sys.path.append(_topdir + "/src")

from webapp import topology

xml_fname = sys.argv[1]
xml_txt = open(xml_fname).read()
xml = et.fromstring(xml_txt)

check_count = 0
errors = []

def validate_time(t):
    global check_count
    try:
        topology.Downtime.parsetime(t)
    except ValueError:
        errors.append(t)
    check_count += 1

for dttype in ("PastDowntimes", "CurrentDowntimes", "FutureDowntimes"):
    for dt in xml.find(dttype).findall('Downtime'):
        validate_time(dt.find('StartTime').text)
        validate_time(dt.find('EndTime').text)

print("%d times checked" % check_count)
if errors:
    print("%d time format errors" % len(errors))
    for e in errors:
        print("Invalid time format: '%s'" % e, file=sys.stderr)
    sys.exit(1)
else:
    print("A-OK")
    sys.exit(0)

