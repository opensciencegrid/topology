#!/usr/bin/env python3

# COManage REST API functions


# This module is not currently used, as it proved TOO SLOW to query for
# identifiers in serial, and we found a cool workaround to make a limited
# number of interesting identifiers available to ldap queries.
# Nonetheless, we are keeping this code around in case we need to use the
# COManage REST API in the future from topology.
#
# https://opensciencegrid.atlassian.net/browse/SOFTWARE-5313


import os
import re
import sys
import json
import getopt
import collections
import urllib.error
import urllib.request


ENDPOINT = "https://registry.cilogon.org/registry/"
OSG_CO_ID = 7

GET    = "GET"
PUT    = "PUT"
POST   = "POST"
DELETE = "DELETE"


class Options:
    endpoint  = ENDPOINT
    osg_co_id = OSG_CO_ID
    authstr   = None


options = Options()


def setup_auth(user, passwd):
    options.authstr = mkauthstr(user, passwd)


def _make_bytes(s):
    return s if isinstance(s, bytes) else s.encode()


def mkauthstr(user, passwd):
    from base64 import encodebytes
    user = _make_bytes(user)
    passwd = _make_bytes(passwd)
    raw_authstr = b'%s:%s' % (user, passwd)
    return encodebytes(raw_authstr).decode().replace('\n', '')


def mkrequest(target, **kw):
    return mkrequest2(GET, target, **kw)


def mkrequest2(method, target, **kw):
    return mkrequest3(method, target, data=None, **kw)


def mkrequest3(method, target, data, **kw):
    url = os.path.join(options.endpoint, target)
    if kw:
        url += "?" + "&".join( "{}={}".format(k,v) for k,v in kw.items() )
    req = urllib.request.Request(url, json.dumps(data).encode("utf-8"))
    req.add_header("Authorization", "Basic %s" % options.authstr)
    req.add_header("Content-Type", "application/json")
    req.get_method = lambda: method
    return req


def call_api(target, **kw):
    return call_api2(GET, target, **kw)


def call_api2(method, target, **kw):
    return call_api3(method, target, data=None, **kw)


def call_api3(method, target, data, **kw):
    req = mkrequest3(method, target, data, **kw)
    resp = urllib.request.urlopen(req)
    payload = resp.read()
    return json.loads(payload) if payload else None


# primary api calls


def get_osg_co_groups():
    return call_api("co_groups.json", coid=options.osg_co_id)


def get_co_group_identifiers(gid):
    return call_api("identifiers.json", cogroupid=gid)


def get_co_group_members(gid):
    return call_api("co_group_members.json", cogroupid=gid)


def get_co_person_identifiers(pid):
    return call_api("identifiers.json", copersonid=pid)


def get_co_group(gid):
    grouplist = get_datalist("CoGroups", call_api("co_groups/%s.json" % gid))
    if not grouplist:
        raise RuntimeError("No such CO Group Id: %s" % gid)
    return grouplist[0]


def get_datalist(listname, data):
    return data[listname] if data else []


# specific queries


def get_osgid_github_map():
    osg_co_groups = get_datalist('CoGroups', get_osg_co_groups())

    gids = [ g["Id"] for g in osg_co_groups ]

    cgms = [ get_datalist('CoGroupMembers', get_co_group_members(gid))
             for gid in gids ]

    pids = set( x['Person']['Id'] for cgm in cgms for x in cgm )
    pidids = { pid: get_datalist('Identifiers', get_co_person_identifiers(pid))
               for pid in pids }

    a = collections.defaultdict(dict)
    for pid in pidids:
        for identifier in pidids[pid]:
            a[pid][identifier["Type"]] = identifier["Identifier"]

    return { a[pid]["osgid"]: a[pid]["GitHub"]
             for pid in a if "osgid" in a[pid] and "GitHub" in a[pid] }


def merge_github_info(yaml_data, osg_github_map):
    """ merge {OSGID: GitHub} map into yaml_data contacts, in-place """
    for id_, contact in yaml_data.items():
        if id_ in osg_github_map:
            contact["GitHub"] = osg_github_map[id_]
        elif contact.get("CILogonID") in osg_github_map:
            contact["GitHub"] = osg_github_map[contact["CILogonID"]]

