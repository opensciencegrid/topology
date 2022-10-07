#!/usr/bin/env python3

# COManage REST API functions

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


def mkauthstr(user, passwd):
    from base64 import encodebytes
    raw_authstr = '%s:%s' % (user, passwd)
    return encodebytes(raw_authstr.encode()).decode().replace('\n', '')


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
    grouplist = call_api("co_groups/%s.json" % gid) | get_datalist("CoGroups")
    if not grouplist:
        raise RuntimeError("No such CO Group Id: %s" % gid)
    return grouplist[0]


# @rorable
# def foo(x): ...
# x | foo -> foo(x)
class rorable:
    def __init__(self, f): self.f = f
    def __call__(self, *a, **kw): return self.f(*a, **kw)
    def __ror__ (self, x): return self.f(x)


def get_datalist(listname):
    def get(data):
        return data[listname] if data else []
    return rorable(get)


