#!/usr/bin/env python

import collections
import glob
import yaml
import sys
import os
import validators

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

def verify_vo(vos, yamls):
    errors = collections.defaultdict(list)
    vo_id = collections.defaultdict(list)
    parent_vo = dict()

    for vo, filename in zip(vos, yamls):
        if filename == 'REPORTING_GROUPS.yaml':
            continue
        try:
            vo_id[int(vo['ID'])].append(filename)
        except (KeyError, ValueError):
            errors['No int ID'].append(filename)
        if 'ParentVO' in vo:
            try:
                name = vo['ParentVO']['Name'] + ".yaml"
                id = int(vo['ParentVO']['ID'])
                parent_vo[name] = id
            except (KeyError, ValueError):
                errors['PV name or id'].append(filename)
        if 'PrimaryURL' in vo and not validators.url(vo['PrimaryURL']):
            errors['invalid URL'].append(filename)
        elif 'PurposeURL' in vo and not validators.url(vo['PurposeURL']):
            errors['invalid URL'].append(filename)
        elif 'SupportURL' in vo and not validators.url(vo['SupportURL']):
            errors['invalid URL'].append(filename)

    for names in vo_id.values():
        if len(names) > 1:
            errors['shareID'].append(names)

    for name, id in parent_vo.items():
        if id not in vo_id or name not in vo_id[id]:
            errors['PV name and ID not match'].append(name)

    return errors

def main():

    os.chdir(_topdir + '/virtual-organizations')

    yamls = glob.glob("*.yaml")
    vos = list(map(load_yamlfile, yamls))

    errors = verify_vo(vos, yamls)

    if errors:
        print("%d errors encountered:" % len(errors))
        if 'No int ID' in errors:
            print("\nThe following VO does not have an int ID:\n{0}"
                  .format('\n'.join(vo for vo in errors['No int ID'])))
        if 'PV name or id' in errors:
            print("\nThe following VOs have ParentVO without int ID or name:\n{0}"
                  .format('\n'.join(vo for vo in errors['PV name or id'])))
        if 'PV name and ID not match' in errors:
            print("\nThe name or ID of ParentVO in following VOs do not match existing VOs:\n{0}"
                  .format('\n'.join(vo for vo in errors['PV name and ID not match'])))
        if 'invalid URL' in errors:
            print("\nThe following VOs have invalid PrimaryURL, PurposeURL or SupportURL:\n{0}"
                  .format('\n'.join(vo for vo in errors['invalid URL'])))
        if 'shareID' in errors:
            print("\nThe following groups of VOs share the same ID:")
            for group in errors['shareID']:
                print(group)

if __name__ == '__main__':
    sys.exit(main())