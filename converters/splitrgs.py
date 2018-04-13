import anymarkup
import os
import shutil
import sys
import xmltodict

try:
    infile, outdir = sys.argv[1:]
except IndexError:
    print("Usage: %s <infile> <outdir>" % sys.argv[0], file=sys.stderr)
    sys.exit(2)

with open(infile, "r") as infh:
    # Use dict constructor to get rid of ordering
    parsed = xmltodict.parse(infh.read(), dict_constructor=dict)

if not os.path.exists(outdir):
    os.makedirs(outdir)
rgs = parsed["ResourceSummary"]["ResourceGroup"]
for rg in rgs:
    anymarkup.serialize_file({"ResourceGroup": rg}, os.path.join(outdir, rg["GroupName"]+".xml"), format="xml")
