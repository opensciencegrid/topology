#!/bin/env python3

# from gfactoryXmlToDB import *
from collections import defaultdict
import yaml
import requests
import sys
import urllib.request
try:
    import xml.etree.cElementTree as ET
except ImportError:
    import xml.etree.ElementTree as ET


treeDump = False  # toggle to view the tree structure of both inputs


def getGfactoryData(gfactoryDB, xml):
    response = urllib.request.urlopen(xml)
    gfactoryPage = response.read()
    root = ET.fromstring(gfactoryPage)

    # insert Names in Topology database into
    for entries in root.findall('entries'):
        for entry in entries.findall('entry'):
            for attrs in entry.findall('attrs'):
                for attr in attrs.findall('attr'):
                    if attr.get('name') == 'GLIDEIN_ResourceName':
                        if treeDump:
                            print(attr.get('value'))
                        # gfactoryDB.add(attr.get('value'))
                        # elements in gfactoryDB is key-value pairs
                        # key: GLIDEIN_ResourceName, value: entry name
                        gfactoryDB[attr.get('value')] = entry.get('name')


def getTopologyData(topologyDB):
    # insert Names under a dictionary that stores four "groupname"-{names} pairs
    # Structure of the dictionary:
    # {'resourceGroups': {},
    #  'facilities': {},
    #  'sites': {},
    #  'resources': {}}
    #
    # The XML has the following hierarchy: (only showing info we need)
    # | root
    # | --ResourceGroup
    # | ----Facility
    # | ----Site
    # | ----Resources
    # | --------Resource
    response = urllib.request.urlopen(
        "https://my.opensciencegrid.org/rgsummary/xml")
    topologyPage = response.read()
    topologyRoot = ET.fromstring(topologyPage)

    # -- file version of parsing. Currently this script read from string
    # topologyTree = ET.parse("resource_topology.xml")
    # topologyRoot = topologyTree.getroot()

    for child in topologyRoot.findall('ResourceGroup'):
        # adding resourceGroup Name attribute to a set
        name = child.find('GroupName')
        if treeDump: print("| " + name.text)
        topologyDB['resourceGroups'].add(name.text)

        for facility in child.findall('Facility'):
            facilityName = facility.find('Name')
            if treeDump: print("| ---- " + facilityName.text)
            topologyDB['facilities'].add(facilityName.text)
        for site in child.findall('Site'):
            siteName = site.find('Name')
            if treeDump: print("| ---- " + siteName.text)
            topologyDB['sites'].add(siteName.text)
        for resources in child.findall('Resources'):
            for resource in resources.findall('Resource'):
                resourceName = resource.find('Name')
                if treeDump: print("| >>>> " + resourceName.text)
                topologyDB['resources'].add(resourceName.text)

def findMatches(nonMatchNames, topologyDB, gfactoryDB):
    # TODO: change the matches set to a name-name pairs set
    matches = {'resourceGroups': set(),
               'sites': set(),
               'facilities': set()
               }
    # nonmatch names that are in the rest three groups of topologyDB should be added
    matchedEntries = [gfactoryDB[x] for x in nonMatchNames.intersection
                      (topologyDB['resourceGroups'].union(topologyDB['sites'], topologyDB['facilities']))]
    # If a name that doesn't
    # for entry in nonMatchNames:
    #     if entry in topologyDB['resourceGroups']:
    #         matches.get('resourceGroups').add(entry)
    #     elif entry in topologyDB['sites']:
    #         matches.get('sites').add(entry)
    #     elif entry in topologyDB['facilities']:
    #         matches.get('facilities').add(entry)

    return matchedEntries


def run(argv):

    # This is for downloading xml files and parse, the script uses string currently
    # with open("resource_topology.xml", "wb") as file:
    #     file.write(response.content)

    topologyDB = {'resources': set(),
                  'sites': set(),
                  'facilities': set(),
                  'resourceGroups': set()}
    getTopologyData(topologyDB)
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
    ]
    # dictionary that stores (GLIDEIN_ResourceNames: entry name) pairs
    gfactoryDB = {}
    for xml in gfactory:
        getGfactoryData(gfactoryDB, xml)
    # print(sorted(topologyDB['resources']))
    # print(sorted(gfactoryDB))

    # GLIDEIN_ResourceNames that does not match resources records in TopologyDB
    nonMatchNames = set(gfactoryDB.keys()).difference(topologyDB['resources'])
    # corresponding entry names of those nonmatches
    nonMatchEntries = [gfactoryDB[x] for x in nonMatchNames]
    print(f'\nEntries that does not have a record in Topology resources: \n\n',
          sorted(nonMatchEntries), '\n\n')
    matchedEntries = findMatches(nonMatchNames, topologyDB, gfactoryDB)
    # print(f'\nGLIDEIN_ResourceNames that match a Resource Group: \n',
    #       matchedEntries.get('resourceGroups'))
    # print(f'\nGLIDEIN_ResourceNames that match a Site: \n', matchedEntries.get('sites'))
    # print(f'\nGLIDEIN_ResourceNames that match a Facility: \n',
    #       matchedEntries.get('facilites'))
    print(f'\nEntries that does not have a record in Topology resources tag but have records in Topology database: \n', sorted(matchedEntries))

if __name__ == "__main__":
    run(sys.argv)
