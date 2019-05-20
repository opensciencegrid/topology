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

try:
    from yaml import CSafeLoader as SafeLoader
except ImportError:
    from yaml import SafeLoader

import xml.etree.ElementTree as et


def usage():
    print("Usage: %s BASE_SHA HEAD_SHA[:MERGE_COMMIT_SHA] [GitHubUser]"
                   % os.path.basename(__file__))
    sys.exit(1)

def parseargs(args):
    insist(len(args) in (2,3))

    GH_USER = None
    MERGE_COMMIT_SHA = None
    BASE_SHA, HEAD_SHA = args[:2]
    if ':' in HEAD_SHA:
        HEAD_SHA, MERGE_COMMIT_SHA = HEAD_SHA.split(':',2)
        insist(looks_like_sha(MERGE_COMMIT_SHA))
    insist(looks_like_sha(BASE_SHA))
    insist(looks_like_sha(HEAD_SHA))

    if len(args) == 3:
        GH_USER = args[2]

    return BASE_SHA, HEAD_SHA, MERGE_COMMIT_SHA, GH_USER

def get_base_head_shas(BASE_SHA, HEAD_SHA, MERGE_SHA, errors):
    base = BASE_SHA
    head = HEAD_SHA
    up_to_date = commit_is_merged(base, head)
    if not up_to_date:
        errors += ["PR head %s is out-of-date: %s is not merged" % (head, base)]
        if MERGE_SHA and commit_is_merged(base, MERGE_SHA) \
                     and commit_is_merged(head, MERGE_SHA):
            print("Using merge commit %s to list changes instead of "
                  "out-of-date PR head %s" % (MERGE_SHA, HEAD_SHA))
            head = MERGE_SHA
        else:
            merge_base = get_merge_base(base, head)
            if merge_base:
                print("Falling back to merge-base %s to list changes instead "
                      "of unmerged PR base %s" % (merge_base, BASE_SHA))
                base = merge_base
            else:
                print("PR base and head commit histories are unrelated")
    return base, head, up_to_date

def main(args):
    BASE_SHA, HEAD_SHA, MERGE_SHA, GH_USER = parseargs(args)

    errors = []

    base, head, up_to_date = get_base_head_shas(BASE_SHA, HEAD_SHA,
                                                MERGE_SHA, errors)
    modified = get_modified_files(base, head)
    DTs = []
    for fname in modified:
        if looks_like_downtime(fname):
            DTs += [fname]
        else:
            errors += ["File '%s' is not a downtime file." % fname.decode()]

    if len(modified) == 0:
        errors += ["Will not automerge PR without any file changes."]

    if GH_USER is not None:
        contact = get_gh_contact(GH_USER)
        if contact is None:
            errors += ["No contact found for GitHub user '%s'" % GH_USER]
    else:
        contact = None

    for fname in DTs:
        dtdict_base = get_downtime_dict_at_version(base, fname)
        dtdict_new  = get_downtime_dict_at_version(head, fname)

        if dtdict_base is None or dtdict_new is None:
            errors += ["File '%s' failed to parse as YAML" % fname.decode()]
            continue

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

    if any( re.match(br'^projects/.*\.yaml', fname) for fname in modified ):
        orgs_base  = get_organizations_at_version(base)
        orgs_new   = get_organizations_at_version(head)
        orgs_added = orgs_new - orgs_base
        for org in sorted(orgs_added):
            errors += ["New Organization '%s' requires OSG approval" % org]
    else:
        orgs_added = None

    print_errors(errors)
    return ( RC.ALL_CHECKS_PASS   if len(errors) == 0
        else RC.OUT_OF_DATE_ONLY  if len(errors) == 1 and not up_to_date
        else RC.ORGS_ADDED        if orgs_added
        else RC.DT_MOD_ERRORS     if len(DTs) > 0
        else RC.CONTACT_ERROR     if contact is None
        else RC.NON_DT_ERRORS )

class RC:
    ALL_CHECKS_PASS  = 0  # all checks pass (only DT files modified)
    OUT_OF_DATE_ONLY = 1  # all checks pass except out of date
    DT_MOD_ERRORS    = 2  # DT file(s) modified, not all checks pass
    CONTACT_ERROR    = 3  # no DT files modified, contact error
    ORGS_ADDED       = 4  # explicitly reject new organizations
    NON_DT_ERRORS    = 5  # no DT files modified, other errors; not reported

# only comment on errors if DT files modified or contact unknown
reportable_errors = set([RC.OUT_OF_DATE_ONLY, RC.DT_MOD_ERRORS,
                         RC.CONTACT_ERROR, RC.ORGS_ADDED])

rejectable_errors = set([RC.ORGS_ADDED])


def insist(cond):
    if not cond:
        usage()

def looks_like_sha(arg):
    return re.search(r'^[0-9a-f]{40}$', arg)  # is not None

def looks_like_downtime(fname):
    return re.search(br'^topology/[^/]+/[^/]+/[^/]+_downtime.yaml$', fname)

def zsplit(txt):
    items = txt.split(b'\0')
    if items[-1:] == [b'']:
        items[-1:] = []
    return items

def get_modified_files(sha_a, sha_b):
    args = ['git', 'diff', '-z', '--name-only', sha_a, sha_b]
    ret, out = runcmd(args)
    if ret:
        sys.exit(1)
    return zsplit(out)

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

def list_dir_at_version(sha, path):
    treeish = b'%s:%s' % (sha.encode(), path)
    args = ['git', 'ls-tree', '-z', '--name-only', treeish]
    ret, out = runcmd(args, stderr=_devnull)
    return zsplit(out)

def get_organizations_at_version(sha):
    projects = [ parse_yaml_at_version(sha, "projects/" + fname, {})
                 for fname in list_dir_at_version(sha, "projects")
                 if re.search(br'.\.yaml$', fname) ]
    return set( p.get("Organization") for p in projects )

def commit_is_merged(sha_a, sha_b):
    args = ['git', 'merge-base', '--is-ancestor', sha_a, sha_b]
    ret, out = runcmd(args, stderr=_devnull)
    return ret == 0

def get_merge_base(sha_a, sha_b):
    args = ['git', 'merge-base', sha_a, sha_b]
    ret, out = runcmd(args, stderr=_devnull)
    return out.strip() if ret == 0 else None

def parse_yaml_at_version(sha, fname, default):
    txt = get_file_at_version(sha, fname)
    if not txt:
        return default
    try:
        return yaml.load(txt, Loader=SafeLoader)
    except yaml.error.YAMLError:
        return None

def get_downtime_dict_at_version(sha, fname):
    dtlist = parse_yaml_at_version(sha, fname, [])
    if dtlist is not None:
        return dict( (dt["ID"], dt) for dt in dtlist )

def get_rg_resources_at_version(sha, fname):
    rg = parse_yaml_at_version(sha, fname, {})
    if rg is not None:
        return rg.get("Resources", {}) if rg else {}

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
    if resources is None:
        return ["File '%s' failed to parse as YAML" % rg_fname.decode()]
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
    sys.exit(main(sys.argv[1:]))

