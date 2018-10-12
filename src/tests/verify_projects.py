#!/usr/bin/env python

from __future__ import print_function

import glob
import yaml
import sys
import os
import re

_topdir = os.path.abspath(os.path.dirname(__file__) + "/../..")

def load_yaml_file(fname, errors):
    try:
        yml = yaml.safe_load(open(fname))
        if yml is None:
            errors.append("YAML file is empty or invalid: %s", fname)
        return yml
    except yaml.error.YAMLError as e:
        errors.append("Failed to parse YAML file: %s\n%s" % (fname, e))

def validate_project_file(fname):
    errors = []
    project = load_yaml_file(fname, errors)

    if errors:
        return errors

    name = re.search(r'([^/]+)\.yaml$', fname).group(1)
    if project["Name"] != name:
        err = "Project '%s' does not match filename '%s'" \
                        % (project["Name"], fname)
        errors.append(err)

    return errors

def main():
    os.chdir(_topdir + "/projects")

    project_filenames = sorted(glob.glob("*.yaml"))

    errors = []
    for fname in project_filenames:
        errors += validate_project_file(fname)

    print("%d project files processed." % len(project_filenames))
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

