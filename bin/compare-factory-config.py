#!/bin/env python3
import yaml
import sys
import os
import glob
import stat
import re  # for parsing gatekeeper
import shutil
import urllib.request
try:
    import xml.etree.cElementTree as ET
except ImportError:
    import xml.etree.ElementTree as ET

tree_dump = False  # toggle to view the tree structure of topology inputs
factory_dump = False  # toggle to view parsed factory ResourceNames


def get_topology_data(topology_DB):
    """
    insert Names under a dictionary that stores four "groupname"-{names} pairs
    Structure of the dictionary:
    {'resourceGroups': set,
     'facilities': set,
     'sites': set,
     'resources': set}

    The XML has the following hierarchy: (only showing info we need)
    | root
    | --ResourceGroup
    | ----Facility
    | ----Site
    | ----Resources
    | --------Resource

    Code below is for parsing xml files.
    topologyTree = ET.parse("resource_topology.xml")
    topologyRoot = topologyTree.getroot()
    """

    response = urllib.request.urlopen(
        "https://topology.opensciencegrid.org/rgsummary/xml?service=on&service_1=on")
    topology_page = response.read()
    topology_root = ET.fromstring(topology_page)

    for child in topology_root.findall('ResourceGroup'):
        # adding resourceGroup Name attribute to a set
        name = child.find('GroupName')
        if tree_dump:
            print("| Group       | " + name.text)
        topology_DB['resourceGroups'].add(name.text)

        for facility in child.findall('Facility'):
            facility_name = facility.find('Name')
            if tree_dump:
                print("|  |-Facility |   " + facility_name.text)
            topology_DB['facilities'].add(facility_name.text)
        for site in child.findall('Site'):
            site_name = site.find('Name')
            if tree_dump:
                print("|  |-Site     |   " + site_name.text)
            topology_DB['sites'].add(site_name.text)
        for resources in child.findall('Resources'):
            for resource in resources.findall('Resource'):
                resource_name = resource.find('Name')
                if tree_dump:
                    print("|  |-Resource |   " + resource_name.text)
                fqdn = resource.find('FQDN').text
                if tree_dump:
                    print("|    |-FQDN   |     " + fqdn)
                topology_DB['resources'].add((resource_name.text, fqdn))


def get_gfactory_data(gfactory_DB, filename):
    """
    Code below is for parsing xml URLs.
    # response = urllib.request.urlopen(xml)
    # gfactoryPage = response.read()
    # root = ET.fromstring(gfactoryPage)
    """

    if (filename.endswith('xml')):
        tree = ET.parse(filename)
        root = tree.getroot()
        # insert Names in Topology database into
        for entry in root.findall('entries/entry'):
            if entry.get('enabled') == 'True':
                # only compairing active gfactory entries
                for attr in entry.findall('attrs/attr'):
                    if attr.get('name') == 'GLIDEIN_ResourceName':
                        if factory_dump:
                            print(attr.get('value'))
                        # gfactory structure: {GLIDEIN_ResourceName: (entry name, fqdn), ...}
                        try:
                            gfactory_DB[attr.get('value')].append(
                                (entry.get('name'), re.split(':|\s', entry.get('gatekeeper'))[0]))
                        except KeyError:
                            gfactory_DB[attr.get('value')] = []
                            gfactory_DB[attr.get('value')].append(
                                (entry.get('name'), re.split(':|\s', entry.get('gatekeeper'))[0]))
                        break
    else:
        # yml files are assumed to have only active entries
        with open(filename, 'r') as stream:
            try:
                data = yaml.safe_load(stream)
            except yaml.YAMLError as error:
                print(error)
        for resource in data.values():
            for entry in resource.values():
                try:
                    for entry_name, config in entry.items():
                        resource_name = config['attrs']['GLIDEIN_ResourceName']
                        if factory_dump:
                            print(resource_name['value'])
                        try:
                            gfactory_DB[resource_name['value']].append(
                                (entry_name, 'None'))
                        except KeyError:
                            gfactory_DB[resource_name['value']] = []
                            gfactory_DB[resource_name['value']].append(
                                (entry_name, 'None'))
                except KeyError:  
                    # skip malformed entries
                    # Since there exists some entries in gfactory/autoconf that 
                    # work without the key or value we want, skip them
                    continue
                except TypeError as e:
                    # as some yml files might be incomplete, print out the filename
                    # and problematic entry so reviews can be requested
                    print('Error: ', filename, 'is not validly structured:')
                    print(f"Entry name: {entry_name}, content: {config}\n")
                except Exception as e:
                    print('Error:', e)
                    continue


def remove_readonly(func, path, _):
    """
    This function is copied from https://docs.python.org/3/library/shutil.html?highlight=shutil#rmtree-example
    On Windows systems, the rmtree function will raise a Permissionerror: [WinError 5] access denied
    This helper function clears the readonly bit and reattemps the removal
    """

    os.chmod(path, stat.S_IWRITE)
    func(path)


def find_suggestion(gatekeeper, topology_DB_resources):
    # return the corresponding resource if a gatekeeper can find a fqdn match
    for resource, fqdn in topology_DB_resources:
        if (gatekeeper == fqdn):
            return resource
    return None


def find_non_resource_matches(gfactory_DB, topology_DB, resources):
    ret = []
    # ResourceNames that does not match any resource records in TopologyDB
    # they may have match in other tags, or not in TopologyDB
    # GLIDEIN_ResourceNames that does not match resources records in TopologyDB

    nonmatch_resource_names = set(gfactory_DB.keys()).difference(
        resources)
    # Factory ResourceNames that match TopologyDB's entries other than a resource
    match_non_resource_names = nonmatch_resource_names.intersection(
        topology_DB['resourceGroups'].union(
            topology_DB['sites'], topology_DB['facilities']))

    for name in match_non_resource_names:
        for entry, gatekeeper in gfactory_DB[name]:
            # each GLIDEIN_ResourceName has a list of (entry, gatekeeper) tuples
            ret.append((entry, name, find_suggestion(
                gatekeeper, topology_DB['resources'])))
    return ret


def find_non_topology_matches(gfactory_DB, topology_DB, resources):
    ret = []
    # The GLIDEIN_ResourceNames that does not match any record in TopologyDB
    nonmatch_all_names = set(gfactory_DB.keys()).difference(
        resources.union(topology_DB['sites'], topology_DB['facilities'], topology_DB['resourceGroups']))

    for name in nonmatch_all_names:
        for entry, gatekeeper in gfactory_DB[name]:
            # each GLIDEIN_ResourceName has a list of (entry, gatekeeper) tuples
            ret.append((entry, name, find_suggestion(
                gatekeeper, topology_DB['resources'])))
    return ret


def run(argv):
    # dictionary that adds GLIDEIN_ResourceNames under corresponding tags
    topology_DB = {'resources': set(),  # set of (name, fqdn) tuples
                   'sites': set(),
                   'facilities': set(),
                   'resourceGroups': set()}
    get_topology_data(topology_DB)
    # cloning user input osg-gfactory repository to a temporary directory
    if len(argv) != 2:
        print('Error: Invalid number of arguments\nUsage: compare-factory-config.py <GIT_REPO>')
        exit(2)
    temp_dir = argv[1]

    gfactory = []
    gfactory.extend(glob.glob(os.path.abspath(temp_dir) + '/*.xml')
                    + (glob.glob(os.path.abspath(temp_dir) + '/OSG_autoconf/*.yml')))
    # dictionary that stores (GLIDEIN_ResourceNames: (entry name, suggestion)) pairs
    gfactory_DB = {}
    if factory_dump:
        print(f'\nAll the GLIDEIN_ResourceNames in factory: \n')
    for xml in gfactory:
        get_gfactory_data(gfactory_DB, xml)

    # finding results
    # extract resources from tuples
    resources = set([x[0] for x in topology_DB['resources']])
    # compairing gfactory with Topology resources
    match_nonresource_entries = find_non_resource_matches(
        gfactory_DB, topology_DB, resources)
    # Entry names corresponding to GLIDEIN_ResourceNames above
    nonmatch_all_entries = find_non_topology_matches(
        gfactory_DB, topology_DB, resources)

    # output formatted results
    print(f'\nOutput format: <corresponding factory entry name>,<GLIDEIN_ResourceName>,<suggestion for a resource match>\n')
    print(f'\nFactory entries that match a Topology entity other than a resource: \n')
    for x in match_nonresource_entries:
        print(f'{x[0]},{x[1]},{x[2]}')
    print(f'\nFactory entries that do not match any entity in Topology: \n')
    for x in nonmatch_all_entries:
        print(f'{x[0]},{x[1]},{x[2]}')
    print()  # creates an empty line gap between last record and new cmd line

    shutil.rmtree(temp_dir, onerror=remove_readonly)  # file cleanup

    if match_nonresource_entries:  # exit non-zero on mismatch (match_nonresource_entries is not empty)
        exit(1)


if __name__ == "__main__":
    run(sys.argv)
