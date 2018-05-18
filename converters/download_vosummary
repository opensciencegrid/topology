#!/usr/bin/env python3

from subprocess import Popen, PIPE
from argparse import ArgumentParser
import http.client
import os
import sys
import urllib.parse
import urllib.request


YES, NO, ONLY = "yes", "no", "only"

params = {
    "all_vos": "on",
    "sort_key": "name",

    "summary_attrs_showcontact": "on",
    "summary_attrs_showdesc": "on",
    "summary_attrs_showfield_of_science": "on",
    #"summary_attrs_showmember_resource": "on",
    "summary_attrs_showoasis": "on",
    "summary_attrs_showparent_vo": "on",
    "summary_attrs_showreporting_group": "on",

    "oasis_value": "1",
}

parser = ArgumentParser()
parser.add_argument("--show-inactive", choices=[YES, NO, ONLY], default=YES)

args = parser.parse_args()

if args.show_inactive == ONLY:
    params["active"] = "on"
    params["active_value"] = "0"
elif args.show_inactive == NO:
    params["active"] = "on"
    params["active_value"] = "1"
elif args.show_inactive == YES:
    params.pop("active", None)
else: assert False


query = urllib.parse.urlencode(params)

url = "https://myosg.grid.iu.edu/vosummary/xml?%s" % query

# From SO:
# https://stackoverflow.com/questions/1875052/using-client-certificates-with-urllib2
class HTTPSClientAuthHandler(urllib.request.HTTPSHandler):
    def __init__(self, key, cert):
        urllib.request.HTTPSHandler.__init__(self)
        self.key = key
        self.cert = cert

    def https_open(self, req):
        # Rather than pass in a reference to a connection class, we pass in
        # a reference to a function which, for all intents and purposes,
        # will behave as a constructor
        return self.do_open(self.getConnection, req)

    def getConnection(self, host, timeout=300):
        return http.client.HTTPSConnection(host, key_file=self.key, cert_file=self.cert)

opener = urllib.request.build_opener(HTTPSClientAuthHandler('key.pem', 'cert.pem') )
response = opener.open(url)
data = response.read().decode("utf-8")

newenv = os.environ.copy()
newenv["XMLLINT_INDENT"] = "\t"
proc = Popen("xmllint --format -", stdin=PIPE, stdout=sys.stdout, shell=True, encoding="utf-8", env=newenv)
proc.communicate(data)
