import anymarkup
import os

topdir = "/tmp/topology"
SCHEMA_LOCATION = b"https://my.opensciencegrid.org/schema/rgsummary.xsd"

paths = []
for root, dirs, files in os.walk(topdir):
    for f in files:
        if f.endswith(".yml"):
            paths.append(os.path.join(root, f))

resourcegroups = []
# assumption: resourcegroups are unique between sites
for p in sorted(paths):
    rg = anymarkup.parse_file(p)
    resourcegroups.append(rg)

# This sort key _almost_ matches the ordering the original XML file came in
# but fails with punctuation.
resourcegroups.sort(key=lambda rg:rg["GroupName"].lower())

serialized = anymarkup.serialize({"ResourceSummary": {"ResourceGroup": resourcegroups}}, "xml")
serialized = \
    serialized.replace(
        b"<ResourceSummary>",
        b"<ResourceSummary xmlns:xsi=\"http://www.w3.org/2001/XMLSchema-instance\" xsi:schemaLocation=\"%s\">"
        % SCHEMA_LOCATION)
with open("rgsummary.xml", "wb") as outfile:
    outfile.write(serialized)
