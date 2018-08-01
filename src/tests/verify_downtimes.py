#!/usr/bin/env python

from __future__ import print_function

import glob
import yaml
import sys
import os
import re

_topdir = os.path.abspath(os.path.dirname(__file__) + "/../..")
sys.path.append(_topdir + "/src")

from webapp import topology

def validate_downtime_file(dt_fname):
    #print("processing %s ..." % dt_fname)
    rg_fname = re.sub(r'_downtime.yaml$', '.yaml', dt_fname)
    if not os.path.exists(rg_fname):
        return ["Resource Group file missing: " + rg_fname]
    dt_yaml = yaml.safe_load(open(dt_fname))
    rg_yaml = yaml.safe_load(open(rg_fname))

    errors = []
    if dt_yaml is None:
        errors.append("Downtime file is empty or invalid: %s" % dt_fname)
    if rg_yaml is None:
        errors.append("Resource Group file is empty or invalid: %s" % rg_fname)
    if errors:
        return errors

    for downtime in dt_yaml:
        def add_err(msg):
            err = "%s:\n" % dt_fname
            if 'ID' in downtime:
                err += "  ID: %d\n" % downtime['ID']
            err += "  ResourceName: %s\n" % downtime['ResourceName']
            err += "  %s" % msg
            errors.append(err)

        if downtime['ResourceName'] not in rg_yaml['Resources']:
            add_err("Resource '%s' not found in resource group file" %
                    downtime['ResourceName'])
        try:
            dt_start = topology.Downtime.parsetime(downtime['StartTime'])
            dt_end   = topology.Downtime.parsetime(downtime['EndTime'])

            if dt_start >= dt_end:
                add_err("StartTime does not precede EndTime: '%s' -> '%s'" %
                        (downtime['StartTime'], downtime['EndTime']))

        except ValueError as e:
            add_err("Invalid date: '%s'" % e)

        for service in downtime['Services']:
            if service not in services:
                add_err("Unknown service: '%s'" % service)

    return errors


def main():
    global services
    os.chdir(_topdir + "/topology")

    downtime_filenames = sorted(glob.glob("*/*/*_downtime.yaml"))

    services = yaml.load(open("services.yaml"))

    errors = []
    for dt_fname in downtime_filenames:
        errors += validate_downtime_file(dt_fname)

    print("%d downtime files processed." % len(downtime_filenames))
    if errors:
        print("%d errors encountered:" % len(errors))
        for e in errors:
            print(e, file=sys.stderr)
        return 1
    else:
        print("A-OK.")
        return 0

if __name__ == '__main__':
    sys.exit(main())

