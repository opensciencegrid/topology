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
    for downtime in dt_yaml:
        if downtime['ResourceName'] not in rg_yaml['Resources']:
            errors += ["Resource '%s' not found in resource group file %s" %
                       (downtime['ResourceName'], rg_fname)]
        try:
            dt_start = topology.Downtime.parsetime(downtime['StartTime'])
            dt_end   = topology.Downtime.parsetime(downtime['EndTime'])

            if dt_start >= dt_end:
                errors += [
                    "Downtime start does not precede end in %s: %s -> %s" %
                    (dt_fname, downtime['StartTime'], downtime['EndTime'])]

        except ValueError as e:
            errors += ["Invalid date in %s: %s" % (dt_fname, e)]

        for service in downtime['Services']:
            if service not in services:
                errors += ["Unknown service '%s' in %s" % (service, dt_fname)]

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
        print("%d errors encountered:" % len(downtime_filenames))
        for e in errors:
            print(e, file=sys.stderr)
        return 1
    else:
        print("A-OK.")
        return 0

if __name__ == '__main__':
    sys.exit(main())

