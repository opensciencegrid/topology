#!/usr/bin/env python

import collections
import subprocess
import yaml
import sys
import os
import re

try:
    from urllib.request import urlopen
except ImportError:
    from urllib2 import urlopen

import xml.etree.ElementTree as et


def usage():
    print("Usage: %s BASE_SHA MERGE_COMMIT_SHA [GitHubUser]"
                   % os.path.basename(__file__))
    sys.exit(1)

def main(args):
    insist(len(args) in (2,3))
    insist(looks_like_sha(args[0]))
    insist(looks_like_sha(args[1]))

    BASE_SHA, MERGE_COMMIT_SHA = args[:2]
    modified = get_modified_files(BASE_SHA, MERGE_COMMIT_SHA)
    errors = []
    if not commit_is_merged(BASE_SHA, MERGE_COMMIT_SHA):
        errors += ["Commit %s is not merged into %s" %
                   (BASE_SHA, MERGE_COMMIT_SHA)]
    DTs = []
    for fname in modified:
        if looks_like_downtime(fname):
            DTs += [fname]
        else:
            errors += ["File '%s' is not a downtime file." % fname.decode()]

    if len(args) == 3:
        contact = get_gh_contact(args[2])
        if contact is None:
            errors += ["No contact found for GitHub user '%s'" % args[2]]
    else:
        contact = None

    for fname in DTs:
        dtdict_base = get_downtime_dict_at_version(BASE_SHA, fname)
        dtdict_new  = get_downtime_dict_at_version(MERGE_COMMIT_SHA, fname)
        dtminus, dtplus = diff_dtdict(dtdict_base, dtdict_new)
        for dt in dtminus:
            print("Old Downtime %d modified for resource '%s'" %
                  (dt["ID"], dt["ResourceName"]))
        for dt in dtplus:
            print("New Downtime %d modified for resource '%s'" %
                  (dt["ID"], dt["ResourceName"]))

        resources_affected = set( dt["ResourceName"] for dt in dtminus ) \
                           | set( dt["ResourceName"] for dt in dtplus  )

        if resources_affected and contact:
            rg_fname = re.sub(br'_downtime.yaml$', b'.yaml', fname)
            errors += check_resource_contacts(BASE_SHA, rg_fname,
                                              resources_affected, contact)

    print_errors(errors)
    sys.exit(len(errors) > 0)

def insist(cond):
    if not cond:
        usage()

def looks_like_sha(arg):
    return re.search(r'^[0-9a-f]{40}$', arg)  # is not None

def looks_like_downtime(fname):
    return re.search(br'^topology/[^/]+/[^/]+/[^/]+_downtime.yaml$', fname)

def get_modified_files(sha_a, sha_b):
    args = ['git', 'diff', '-z', '--name-only', sha_a, sha_b]
    ret, out = runcmd(args)
    if ret:
        sys.exit(1)
    return out.rstrip(b'\0').split(b'\0')

def runcmd(cmdline, **popen_kw):
    from subprocess import Popen, PIPE
    p = Popen(cmdline, stdout=PIPE, **popen_kw)
    out, err = p.communicate()
    return p.returncode, out

def print_errors(errors):
    if errors:
        print("Commit is not eligible for auto-merge:")
        for e in errors:
            print(" - %s" % e)
    else:
        print("Commit is eligible for auto-merge.")

_devnull = open("/dev/null", "w")
def get_file_at_version(sha, fname):
    args = ['git', 'show', b'%s:%s' % (sha.encode(), fname)]
    ret, out = runcmd(args, stderr=_devnull)
    return out

def commit_is_merged(sha_a, sha_b):
    args = ['git', 'merge-base', '--is-ancestor', sha_a, sha_b]
    ret, out = runcmd(args, stderr=_devnull)
    return ret == 0

def get_downtime_dict_at_version(sha, fname):
    txt = get_file_at_version(sha, fname)
    dtlist = yaml.safe_load(txt) if txt else []
    return dict( (dt["ID"], dt) for dt in dtlist )

def get_rg_resources_at_version(sha, fname):
    txt = get_file_at_version(sha, fname)
    rg = yaml.safe_load(txt)
    return rg["Resources"]

def resource_contact_ids(res):
    clists = res["ContactLists"]
    return set( contact["ID"] for ctype in clists.values()
                              for contact in ctype.values() )

def diff_dtdict(dtdict_a, dtdict_b):
    def dt_changed(ID):
        return dtdict_a[ID] != dtdict_b[ID]
    dtids_a = set(dtdict_a)
    dtids_b = set(dtdict_b)
    dtids_mod = set(filter(dt_changed, dtids_a & dtids_b))
    dt_a = [ dtdict_a[ID] for ID in (dtids_a - dtids_b) | dtids_mod ]
    dt_b = [ dtdict_b[ID] for ID in (dtids_b - dtids_a) | dtids_mod ]

    return dt_a, dt_b

def check_resource_contacts(sha, rg_fname, resources_affected, contact):
    resources = get_rg_resources_at_version(sha, rg_fname)
    return [ "%s not associated with resource '%s'" % (contact, res)
             for res in resources_affected if res in resources
             if contact.ID not in resource_contact_ids(resources[res]) ]

_contact_fields = ['ID', 'FullName', 'GitHub']
Contact = collections.namedtuple('Contact', _contact_fields)

def u2contact(u):
    return Contact(*[ u.find(field).text for field in _contact_fields ])

_contacts_url = 'https://topology.opensciencegrid.org/miscuser/xml'
def get_contacts():
    txt = urlopen(_contacts_url).read()
    xmltree = et.fromstring(txt)
    users = xmltree.findall('User')
    return list(map(u2contact, users))

def get_gh_contact(ghuser):
    contact_list = get_contacts()
    gh_contacts = [ c for c in contact_list if c.GitHub == ghuser ]
    return gh_contacts[0] if len(gh_contacts) == 1 else None

if __name__ == '__main__':
    main(sys.argv[1:])

