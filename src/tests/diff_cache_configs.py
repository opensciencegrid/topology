#!/usr/bin/env python3

import re
import os
import sys
import json
import collections
import urllib.request
from subprocess import Popen, PIPE

CVMFS_EXTERNAL_URL = "CVMFS_EXTERNAL_URL"

baseurl = "https://raw.githubusercontent.com/cvmfs-contrib/config-repo/master"
ligoconf = "etc/cvmfs/config.d/ligo.osgstorage.org.conf"
osgconf = "etc/cvmfs/domain.d/osgstorage.org.conf"
whitelist = "cache_config_whitelist.txt"

namespaces = "https://topology.opensciencegrid.org/stashcache/namespaces.json"


def slurp_file(path):
    return open(path, "rb").read()

def slurp_url(url):
    remote = url if "://" in url else "%s/%s" % (baseurl, url)
    return urllib.request.urlopen(remote).read()


def shell_parse_env(srctxt, env):
    # evaluate shell source text and print the value of env var
    env = env.encode()
    # only eval lines that contain the env var we are interested in
    grepped = b"\n".join( line for line in srctxt.splitlines() if env in line )
    sh_code = 'eval "$1"; echo "${!2}"'
    cmdline = ["/bin/bash", "-c", sh_code, "-", grepped, env]
    sh_eval = Popen(cmdline, stdout=PIPE).communicate()[0] or b''
    return sh_eval.decode()


def get_conf_urls(confurl):
    txt = slurp_url(confurl)
    return shell_parse_env(txt, CVMFS_EXTERNAL_URL).strip().split(";")


URLInfo = collections.namedtuple("URLInfo", ["proto", "hostport", "path"])

def split_url_components(url):
    #  "https://xrootd-local.unl.edu:1094//user/ligo/" ->
    # ("https://", "xrootd-local.unl.edu:1094", "/user/ligo")
    m = re.match(r'^(https?://)([^/]*)/?(/.*)', url)
    return URLInfo(*m.groups()) if m else URLInfo(None, None, None)


def get_conf_url_infos(confurl):
    urls = get_conf_urls(confurl)
    return list(map(split_url_components, urls))


def get_conf_url_path_map(confurl):
    urlinfos = get_conf_url_infos(confurl)
    dd = collections.defaultdict(set)
    for info in urlinfos:
        dd[info.path].add(info.hostport)
    return dd


def cache_endpoints(caches, endpoint):
    endpoints = set()
    for cache in caches:
        endpoints.add(cache[endpoint])
    return endpoints


def get_namespaces_map():
    txt = slurp_url(namespaces)
    d = json.loads(txt)
    return {
        ns['path']: {
            'auth_endpoint': cache_endpoints(ns['caches'], 'auth_endpoint'),
            'endpoint': cache_endpoints(ns['caches'], 'endpoint')
        } for ns in d['namespaces']
    }


def get_whitelisted():
    wl = slurp_file(whitelist).decode()
    return set( l for l in wl.splitlines() if not l.startswith("#") )


def do_conf_comparisons():
    nsmap = get_namespaces_map()
    osgmap = get_conf_url_path_map(osgconf)
    ligomap = get_conf_url_path_map(ligoconf)
    whitelisted = get_whitelisted()

    osg_cvmfs_caches = osgmap['/']
    osg_topology_caches = nsmap['/osgconnect/public']['endpoint']

    ligo_cvmfs_caches = ligomap['/user/ligo/']
    ligo_topology_caches = nsmap['/user/ligo']['auth_endpoint']

    print_diffs(osgconf, osg_cvmfs_caches, osg_topology_caches, whitelisted)
    print_diffs(ligoconf, ligo_cvmfs_caches, ligo_topology_caches, whitelisted)

    return (osg_cvmfs_caches == osg_topology_caches and
            ligo_cvmfs_caches == ligo_topology_caches)


def print_diffs(conf, cvmfs_caches, topology_caches, whitelisted):
    conf = os.path.basename(conf)
    if cvmfs_caches == topology_caches:
        print("%s is up to date with topology source" % conf)
        print("")
    else:
        cvmfs_missing = topology_caches - cvmfs_caches
        cvmfs_extra   = cvmfs_caches    - topology_caches - whitelisted

        if cvmfs_missing:
            print("Missing items from %s (to add)" % conf)
            print_bulletted(cvmfs_missing)
            print("")
        if cvmfs_extra:
            print("Extra items in %s (to remove)" % conf)
            print_bulletted(cvmfs_extra)
            print("")


def print_bulletted(items):
    for item in sorted(items):
        print(" - %s" % item)


def main():
    return do_conf_comparisons()


if __name__ == '__main__':
    all_match = main()
    sys.exit(0 if all_match else 1)


