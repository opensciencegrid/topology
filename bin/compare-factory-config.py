#!/bin/env python3
import yaml
import git
import tempfile
import sys
import os
import glob
import stat
import shutil
import urllib.request
try:
    import xml.etree.cElementTree as ET
except ImportError:
    import xml.etree.ElementTree as ET

tree_dump = False  # toggle to view the tree structure of both inputs


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
        "https://topology.opensciencegrid.org/rgsummary/xml?gridtype=on&gridtype_1=on&active=on&active_value=1&service=on&service_1=on")
    topology_page = response.read()
    topology_root = ET.fromstring(topology_page)

    for child in topology_root.findall('ResourceGroup'):
        # adding resourceGroup Name attribute to a set
        name = child.find('GroupName')
        if tree_dump:
            print("| " + name.text)
        topology_DB['resourceGroups'].add(name.text)

        for facility in child.findall('Facility'):
            facility_name = facility.find('Name')
            if tree_dump:
                print("| ---- " + facility_name.text)
            topology_DB['facilities'].add(facility_name.text)
        for site in child.findall('Site'):
            site_name = site.find('Name')
            if tree_dump:
                print("| ---- " + site_name.text)
            topology_DB['sites'].add(site_name.text)
        for resources in child.findall('Resources'):
            for resource in resources.findall('Resource'):
                resource_name = resource.find('Name')
                if tree_dump:
                    print("| >>>> " + resource_name.text)
                topology_DB['resources'].add(resource_name.text)


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
                # print('Not able --', entry.get('name'))
                for attr in entry.findall('attrs/attr'):
                    if attr.get('name') == 'GLIDEIN_ResourceName':
                        if tree_dump:
                            print(attr.get('value'))
                        # gfactory structure: {GLIDEIN_ResourceName: entry name, ...}
                        # print(entry.get('name'), 'is',entry.get('enabled'))
                        gfactory_DB[attr.get('value')] = entry.get('name')
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
                        if tree_dump:
                            print(resource_name)
                        gfactory_DB[resource_name] = entry_name
                except:  # skip malformed entries
                    continue


def remove_readonly(func, path, _):
    """
    This function is copied from https://docs.python.org/3/library/shutil.html?highlight=shutil#rmtree-example
    On Windows systems, the rmtree function will raise a Permissionerror: [WinError 5] access denied
    This helper function clears the readonly bit and reattemps the removal
    """

    os.chmod(path, stat.S_IWRITE)
    func(path)


def run(argv):

    # dictionary that adds GLIDEIN_ResourceNames under corresponding tags
    topology_DB = {'resources': set(),
                   'sites': set(),
                   'facilities': set(),
                   'resourceGroups': set()}
    get_topology_data(topology_DB)
    # cloning gfactory repository to a temporary directory
    temp_dir = tempfile.mkdtemp()
    git.Repo.clone_from(
        'https://github.com/opensciencegrid/osg-gfactory',
        to_path=temp_dir
    )
    gfactory = []
    gfactory.extend(glob.glob(os.path.abspath(temp_dir) + '/*.xml')
                    + (glob.glob(os.path.abspath(temp_dir) + '/OSG_autoconf/*.yml')))
    # dictionary that stores (GLIDEIN_ResourceNames: entry name) pairs
    gfactory_DB = {}
    for xml in gfactory:
        get_gfactory_data(gfactory_DB, xml)

    # compairing gfactory with Topology resources
    # GLIDEIN_ResourceNames that does not match resources records in TopologyDB
    nonmatch_resource_names = set(gfactory_DB.keys()).difference(
        topology_DB['resources'])
    # The GLIDEIN_ResourceNames that match record other than resources in TopologyDB
    match_nonresource_entries = [(gfactory_DB[x], x) for x in nonmatch_resource_names.intersection
                                 (topology_DB['resourceGroups'].union(topology_DB['sites'], topology_DB['facilities']))]

    # The GLIDEIN_ResourceNames that does not match any record in TopologyDB
    nonmatch_all_names = set(gfactory_DB.keys()).difference(
        topology_DB['resources'].union(topology_DB['sites'], topology_DB['facilities'], topology_DB['resourceGroups']))
    # Entry names corresponding to GLIDEIN_ResourceNames above
    nonmatch_all_entries = [gfactory_DB[x] for x in nonmatch_all_names]

    print(f'\nFactory entries that match a Topology entity other than a resource: \n')
    for x in match_nonresource_entries:
        print(f'- {x[0]}: {x[1]}')
    print(f'\nFactory entries that do not match any entity in Topology: \n')
    for x in sorted(nonmatch_all_entries):
        print(f'- {x}')
    print()  # creates an empty line gap between last record and new cmd line

    shutil.rmtree(temp_dir, onerror=remove_readonly)  # file cleanup


if __name__ == "__main__":
    run(sys.argv)
