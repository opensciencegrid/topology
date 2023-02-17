#!/usr/bin/env python3

import time
import sys
import os

import xml.etree.ElementTree as et

_topdir = os.path.abspath(os.path.dirname(__file__) + "/../..")
sys.path.append(_topdir + "/src")

from webapp import topology

check_count = 0
errors = []

_timefmt = "%b %d, %Y %H:%M %p %Z"
def validate_time(t):
    global check_count
    try:
        time.strptime(t, _timefmt)
    except ValueError:
        errors.append(t)
    check_count += 1

def validate_xml(xml_fname):
    xml_txt = open(xml_fname).read()
    xml = et.fromstring(xml_txt)

    for dttype in ("PastDowntimes", "CurrentDowntimes", "FutureDowntimes"):
        for dt in xml.find(dttype).findall('Downtime'):
            validate_time(dt.find('StartTime').text)
            validate_time(dt.find('EndTime').text)

    print("%d time(s) checked" % check_count)
    if errors:
        print("%d time format error(s)" % len(errors))
        for e in errors:
            print("ERROR: Invalid time format: '%s'" % e, file=sys.stderr)
        return 1
    else:
        print("A-OK")
        return 0

def main():
    return validate_xml(sys.argv[1])

if __name__ == '__main__':
    sys.exit(main())

