#!/usr/bin/env python3

from subprocess import Popen, PIPE
from argparse import ArgumentParser
import os
import sys
import urllib.parse
import urllib.request
import http.client


YES, NO, ONLY = "yes", "no", "only"


params = {
    "all_resources": "on",

    "summary_attrs_showservice": "1",
    # "summary_attrs_showrsvstatus": "1",  # <- rsv is dead
    # "summary_attrs_showgipstatus": "1",  # <- gip is dead
    # "summary_attrs_showvomembership": "1",  # <- shows "SupportedVOs" field, reported by rsv (which is dead)
    "summary_attrs_showvoownership": "1",
    "summary_attrs_showwlcg": "1",
    # "summary_attrs_showenv": "1",  # <- this one is never filled out
    "summary_attrs_showcontact": "1",
    "summary_attrs_showfqdn": "1",
    "summary_attrs_showhierarchy": "1",  # <- shows facility & site info
    "summary_attrs_showdesc": "1",  # <- shows description

    # "summary_attrs_showticket": "1",  # <- shows open GOC tickets
}

parser = ArgumentParser()
parser.add_argument("--show-inactive-resources", choices=[YES, NO, ONLY], default=YES)  # original GRACC URL used NO
parser.add_argument("--show-itb", choices=[YES, NO, ONLY], default=YES)  # original GRACC URL used NO
parser.add_argument("--show-disabled-resources", choices=[YES, NO, ONLY], default=YES)
parser.add_argument("--facility", action="append", type=int, help="facility id(s) to show", default=[])
parser.add_argument("--rg", action="append", type=int, help="resource group id(s) to show", default=[])
parser.add_argument("--service", action="append", type=int, help="service id(s) to show", default=[])
parser.add_argument("--site", action="append", type=int, help="site id(s) to show", default=[])
parser.add_argument("--sc", action="append", type=int, help="support center id(s) to show", default=[])
parser.add_argument("--voown", action="append", type=int, help="vo owner id(s) to show", default=[])
parser.add_argument("--wlcg", action="store_true", help="WLCG resources only")

args = parser.parse_args()

if args.show_inactive_resources == ONLY:
    params["active"] = "on"
    params["active_value"] = "0"
elif args.show_inactive_resources == NO:
    params["active"] = "on"
    params["active_value"] = "1"
elif args.show_inactive_resources == YES:
    params.pop("active", None)
else: assert False

if args.show_itb == ONLY:
    params["gridtype"] = "on"
    params["gridtype_2"] = "on"
elif args.show_itb == NO:
    params["gridtype"] = "on"
    params["gridtype_1"] = "on"
elif args.show_itb == YES:
    params.pop("gridtype", None)
else: assert False

if args.show_disabled_resources == ONLY:
    params["disable"] = "on"
    params["disable_value"] = "1"
elif args.show_disabled_resources == NO:
    params["disable"] = "on"
    params["disable_value"] = "0"
elif args.show_disabled_resources == YES:
    params.pop("disable", None)
else: assert False

if args.wlcg:
    params["has_wlcg"] = "on"

filter_params = []

for id_list, main_param, sel_param, pop_all_resources in [
    (args.facility, "facility", "facility_sel[]", True),
    (args.rg, "rg", "rg_sel[]", True),
    (args.sc, "sc", "sc_sel[]", True),
    (args.service, "service", "service_sel[]", False),
    (args.site, "site", "site_sel[]", True),
    (args.voown, "voown", "voown_sel[]", False),
    ]:

    if id_list:
        if pop_all_resources:
            params.pop("all_resources", None)
        params[main_param] = "on"
        filter_params.extend([(sel_param, str(id_)) for id_ in id_list])

params_list = list(params.items()) + filter_params
query = urllib.parse.urlencode(params_list, doseq=True)

url = "https://myosg.grid.iu.edu/rgsummary/xml?%s" % query

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
