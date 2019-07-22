#!/usr/bin/env python

import os
import glob
import sys
import yaml
import collections

try:
    from yaml import CSafeLoader as SafeLoader
except ImportError:
    from yaml import SafeLoader

_topdir = os.path.abspath(os.path.dirname(__file__) + "/../..")

def load_yamlfile(fn):
    with open(fn) as f:
        try:
            yml = yaml.load(f, Loader=SafeLoader)
            if yml is None:
                print("YAML file is empty or invalid: %s", fn)
            return yml
        except yaml.error.YAMLError as e:
            print("Failed to parse YAML file: %s\n%s" % (fn, e))

def verify_projects(projects, yamls):
    errors = collections.defaultdict(list)
    proj_id = collections.defaultdict(list)

    for project, name in zip(projects, yamls):
        if 'Sponsor' in project and 'CampusGrid' in project['Sponsor']:
            if 'Name' not in project['Sponsor']['CampusGrid']:
                errors['CampusGrid without name'].append(name)
            if 'ID' not in project['Sponsor']['CampusGrid']:
                errors['CampusGrid without ID'].append(name)
            else:
                try:
                    int(project['Sponsor']['CampusGrid']['ID'])
                except ValueError:
                    errors['CampusGrid ID not int'].append(name)
        if 'ID' not in project:
            errors['No ID'].append(name)
        else:
            try:
                proj_id[int(project['ID'])].append(name)
            except ValueError:
                errors['ID Not int'].append(name)

    for group in proj_id.values():
        if len(group) > 1:
            errors['Same ID'].append(group)

    return errors

def main():
    os.chdir(_topdir + '/projects')

    yamls = glob.glob("*.yaml")
    projects = list(map(load_yamlfile, yamls))

    errors = verify_projects(projects, yamls)

    if errors:
        print("%d errors encountered:" % len(errors))
        if 'CampusGrid without name' in errors:
            print('\nThe following projects have CampusGrid without name:\n{0}'
                  .format('\n'.join(proj for proj in errors['CampusGrid without name'])))
        if 'CampusGrid without ID' in errors:
            print('\nThe following projects have CampusGrid without ID:\n{0}'
                  .format('\n'.join(proj for proj in errors['CampusGrid without ID'])))
        if 'CampusGrid ID not int' in errors:
            print('\nThe following projects have CampusGrid without int ID:\n{0}'
                  .format('\n'.join(proj for proj in errors['CampusGrid ID not int'])))
        if 'No ID' in errors:
            print('\nThe following projects do not have ID:\n{0}'
                  .format('\n'.join(proj for proj in errors['No ID'])))
        if 'ID Not int' in errors:
            print('\nThe ID of following projects is not int ID:\n{0}'
                  .format('\n'.join(proj for proj in errors['ID Not int'])))
        if 'Same ID' in errors:
            print('\nThe following groups of projects have the same ID:')
            for projs in errors['Same ID']:
                print(projs)
        if 'CG same ID' in errors:
            print('\nThe following groups of projects have CampusGrid sharing the same ID:')
            for projs in errors['CG same ID']:
                print(projs)
        return 1
    else:
        print("A-OK.")
        return 0
    
if __name__ == '__main__':
    sys.exit(main())
