#!/usr/bin/python

import requests
import os
import glob
import yaml
import sys

try:
    from yaml import CSafeLoader as SafeLoader
except ImportError:
    from yaml import SafeLoader

baseurl   = 'https://gracc.opensciencegrid.org/q'
indexurl  = baseurl  + '/gracc.osg.summary'
searchurl = indexurl + '/_search'

_topdir = os.path.abspath(os.path.dirname(__file__) + "/../..")

def bucket2fqdn(b):
    # extract fqdn from the ProbeName in a CE bucket from ES
    return b['key'].split(':')[1]

def get_gracc_reporting_CEs():
    # query gracc for unique ProbeName's reported in the last year

    ce_query = {
        "query": {
            "bool": {
                "must": [
                    { "term": { "ResourceType": "Batch" } },
                    { "range": { "EndTime": { "gte": "now-1y" } } }
                ]
            }
        },
        "size": 0,
        "aggs": {
            "CEs" : {
                "terms": {"field" : "ProbeName", "size" : 10000}
            }
        }
    }

    res = requests.get(searchurl, json=ce_query).json()

    buckets = res['aggregations']['CEs']['buckets']

    fqdns = set(map(bucket2fqdn, buckets))

    return fqdns


def rgfilter(fn):
    return not (fn.endswith("_downtime.yaml") or fn.endswith("/SITE.yaml"))


def load_yamlfile(fn):
    with open(fn) as f:
        try:
            yml = yaml.load(f, Loader=SafeLoader)
            if yml is None:
                print("YAML file is empty or invalid: %s", fn)
            return yml
        except yaml.error.YAMLError as e:
            print("Failed to parse YAML file: %s\n%s" % (fn, e))


def get_topology_active_CEs():

    os.chdir(_topdir + "/topology")

    yamls = sorted(glob.glob("*/*/*.yaml"))
    rgfns = list(filter(rgfilter, yamls))
    rgs = list(map(load_yamlfile, rgfns))

    ce = set()
    for rg,f in zip(rgs,rgfns):
        for resource in rg['Resources']:
            if 'CE' in rg['Resources'][resource]['Services']:
                try:
                    if rg['Resources'][resource]['Active']:
                        ce.add(rg['Resources'][resource]['FQDN'])
                except KeyError:
                    ce.add(rg['Resources'][resource]['FQDN'])

    return ce


def main():
    ce_list = get_topology_active_CEs()
    ce_gracc = get_gracc_reporting_CEs()

    ce_not_registered = ce_gracc.difference(ce_list)
    ce_not_report = ce_list.difference(ce_gracc)

    if ce_not_report:
        print("\nThe registered resources with the following FQDNs have not reported in GRACC "
              "in the past year:\n{0}".format('\n'.join(ce_not_report)))

    if ce_not_registered:
        print("\nThe resources with following FQDNs have reported in GRACC during past year "
              "but have not registered:\n{0}".format('\n'.join(ce_not_registered)))


if __name__ == '__main__':
    sys.exit(main())