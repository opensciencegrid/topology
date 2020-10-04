#!/bin/env python3

# from gfactoryXmlToDB import *
from collections import defaultdict
import yaml
import git
import tempfile
import sys
import os
import stat
import shutil
import urllib.request
try:
    import xml.etree.cElementTree as ET
except ImportError:
    import xml.etree.ElementTree as ET

treeDump = False  # toggle to view the tree structure of both inputs


def getTopologyData(topologyDB):
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
    topologyPage = response.read()
    topologyRoot = ET.fromstring(topologyPage)

    for child in topologyRoot.findall('ResourceGroup'):
        # adding resourceGroup Name attribute to a set
        name = child.find('GroupName')
        if treeDump:
            print("| " + name.text)
        topologyDB['resourceGroups'].add(name.text)

        for facility in child.findall('Facility'):
            facilityName = facility.find('Name')
            if treeDump:
                print("| ---- " + facilityName.text)
            topologyDB['facilities'].add(facilityName.text)
        for site in child.findall('Site'):
            siteName = site.find('Name')
            if treeDump:
                print("| ---- " + siteName.text)
            topologyDB['sites'].add(siteName.text)
        for resources in child.findall('Resources'):
            for resource in resources.findall('Resource'):
                resourceName = resource.find('Name')
                if treeDump:
                    print("| >>>> " + resourceName.text)
                topologyDB['resources'].add(resourceName.text)


def getGfactoryData(gfactoryDB, xml):
    """
    Code below is for parsing xml URLs.
    # response = urllib.request.urlopen(xml)
    # gfactoryPage = response.read()
    # root = ET.fromstring(gfactoryPage)
    """

    tree = ET.parse(xml)
    root = tree.getroot()
    # insert Names in Topology database into
    for entry in root.findall('entries/entry'):
        for attr in entry.findall('attrs/attr'):
            if attr.get('name') == 'GLIDEIN_ResourceName':
                if treeDump:
                    print(attr.get('value'))
                # gfactory structure: {GLIDEIN_ResourceName: entry name, ...}
                gfactoryDB[attr.get('value')] = entry.get('name')


def findMatches(nonMatchNames, topologyDB, gfactoryDB):
    # nonmatch names that are in the rest three groups of topologyDB should be added
    matchedEntries = [gfactoryDB[x] for x in nonMatchNames.intersection
                      (topologyDB['resourceGroups'].union(topologyDB['sites'], topologyDB['facilities']))]
    return matchedEntries


def remove_readonly(func, path, _):
    # This function is copied from https://docs.python.org/3/library/shutil.html?highlight=shutil#rmtree-example
    # On Windows systems, the rmtree function will raise a Permissionerror: [WinError 5] access denied
    # This helper function clears the readonly bit and reattemps the removal
    os.chmod(path, stat.S_IWRITE)
    func(path)


def run(argv):

    # dictionary that adds GLIDEIN_ResourceNames under corresponding tags
    topologyDB = {'resources': set(),
                  'sites': set(),
                  'facilities': set(),
                  'resourceGroups': set()}
    getTopologyData(topologyDB)
    # cloning gfactory repository to a temporary directory
    tempDir = tempfile.mkdtemp()
    git.Repo.clone_from(
        'https://github.com/opensciencegrid/osg-gfactory',
        to_path=tempDir
    )
    # TODO: replace gfactory with testFactory after getting correct info about yml files
    gfactory = []
    for filename in os.listdir(os.path.abspath(tempDir)):
        # TODO: also add yml files
        if filename.endswith('.xml'):
            gfactory.append(os.path.join(tempDir, filename))
    """
    Hardcoded xml sources
    gfactory = [
        'https://raw.githubusercontent.com/opensciencegrid/osg-gfactory/master/10-cms-cern_osg.xml',
        'https://raw.githubusercontent.com/opensciencegrid/osg-gfactory/master/10-cmsonly-cern_fnal.xml',
        'https://raw.githubusercontent.com/opensciencegrid/osg-gfactory/master/10-cmsopp-cern_osg.xml',
        'https://raw.githubusercontent.com/opensciencegrid/osg-gfactory/master/10-cmst1-all.xml',
        'https://raw.githubusercontent.com/opensciencegrid/osg-gfactory/master/10-cmst1-uscmst2-all.xml',
        'https://raw.githubusercontent.com/opensciencegrid/osg-gfactory/master/10-covid19-osg.xml',
        'https://raw.githubusercontent.com/opensciencegrid/osg-gfactory/master/10-cream.xml',
        'https://raw.githubusercontent.com/opensciencegrid/osg-gfactory/master/10-fermi-fnal_osg.xml',
        'https://raw.githubusercontent.com/opensciencegrid/osg-gfactory/master/10-noncms-osg.xml',
        'https://raw.githubusercontent.com/opensciencegrid/osg-gfactory/master/10-testonly-itb.xml',
        'https://raw.githubusercontent.com/opensciencegrid/osg-gfactory/master/20-local-itb.xml',
        'https://raw.githubusercontent.com/opensciencegrid/osg-gfactory/master/30-local-cern.xml',
        'https://raw.githubusercontent.com/opensciencegrid/osg-gfactory/master/30-local-fnal.xml'
    ] """
    # dictionary that stores (GLIDEIN_ResourceNames: entry name) pairs
    gfactoryDB = {}
    for xml in gfactory:
        getGfactoryData(gfactoryDB, xml)

    # comparing gfactory with Topology resources
    # GLIDEIN_ResourceNames that does not match resources records in TopologyDB
    nonMatchNames = set(gfactoryDB.keys()).difference(
        topologyDB['resources'])

    # corresponding entry names of those nonmatches
    nonMatchEntries = [gfactoryDB[x] for x in nonMatchNames]
    print(f'\nEntries that does not have a record in Topology resources: \n\n',
          sorted(nonMatchEntries), '\n')

    # The nonmatching GLIDEIN_ResourceNames that has a record in TopologyDB
    matchedEntries = findMatches(nonMatchNames, topologyDB, gfactoryDB)
    print(f'\nEntries that does not have a record in Topology resources tag but have records in Topology database: \n\n',
          sorted(matchedEntries), '\n')

    shutil.rmtree(tempDir, onerror=remove_readonly)  # file cleanup


if __name__ == "__main__":
    run(sys.argv)
