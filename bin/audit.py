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
                        gfactoryDB.add(attr.get('value'))


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
        if treeDump:
            print("| " + name.text)
        try:
            topologyDB['resourceGroups'].add(name.text)
        except KeyError:
            topologyDB['resourceGroups'] = {name.text}

        for facility in child.findall('Facility'):
            facilityName = facility.find('Name')
            if treeDump:
                print("| ---- " + facilityName.text)
            try:
                topologyDB['facilities'].add(facilityName.text)
            except KeyError:
                topologyDB['facilities'] = {facilityName.text}
        for site in child.findall('Site'):
            siteName = site.find('Name')
            if treeDump:
                print("| ---- " + siteName.text)
            try:
                topologyDB['sites'].add(siteName.text)
            except KeyError:
                topologyDB['sites'] = {siteName.text}
        for resources in child.findall('Resources'):
            for resource in resources.findall('Resource'):
                resourceName = resource.find('Name')
                if treeDump:
                    print("| >>>> " + resourceName.text)
                try:
                    topologyDB['resources'].add(resourceName.text)
                except KeyError:
                    topologyDB['resources'] = {resourceName.text}


def findMatches(nonMatchNames, topologyDB):
    matches = {'resourceGroups': set(),
               'sites': set(),
               'facilities': set()
               }
    # If a name that doesn't
    for entry in nonMatchNames:
        if entry in topologyDB['resourceGroups']:
            matches.get('resourceGroups').add(entry)
        elif entry in topologyDB['sites']:
            matches.get('sites').add(entry)
        elif entry in topologyDB['facilities']:
            matches.get('facilities').add(entry)

    return matches


def run(argv):

    # This is for downloading xml files and parse, the script uses string currently
    # with open("resource_topology.xml", "wb") as file:
    #     file.write(response.content)

    topologyDB = {}
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
    gfactoryDB = set()
    for xml in gfactory:
        getGfactoryData(gfactoryDB, xml)
    # print(sorted(topologyDB['resources']))
    # print(sorted(gfactoryDB))
    nonMatchNames = gfactoryDB.difference(topologyDB['resources'])
    print(f'\nGLIDEIN_ResourceNames that does not match Topology records: \n\n',
          sorted(nonMatchNames), '\n\n')
    matches = findMatches(nonMatchNames, topologyDB)
    print(f'\nGLIDEIN_ResourceNames that match a Resource Group: \n',
          matches.get('resourceGroups'))
    print(f'\nGLIDEIN_ResourceNames that match a Site: \n', matches.get('sites'))
    print(f'\nGLIDEIN_ResourceNames that match a Facility: \n',
          matches.get('facilites'))


if __name__ == "__main__":
    run(sys.argv)
