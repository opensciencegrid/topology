import anymarkup
import os
from typing import List, Dict

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


def get_max_ids(resourcegroups: List[Dict]) -> Dict[int]:
    """Get the highest IDs for group, facility, site, and resource in all of the ResourceGroup data."""
    max_ids = dict(group=-1, facility=-1, site=-1, resource=-1)
    for rg in resourcegroups:
        group_id = int(rg["GroupID"])
        facility_id = int(rg["Facility"]["ID"])
        site_id = int(rg["Site"]["ID"])
        max_ids["group"] = max(max_ids["group"], group_id)
        max_ids["facility"] = max(max_ids["facility"], facility_id)
        max_ids["site"] = max(max_ids["site"], site_id)

        resource = rg["Resources"]["Resource"]
        if isinstance(resource, dict):
            # There's only one of these
            resource_id = int(resource["ID"])
            max_ids["resource"] = max(max_ids["resource"], resource_id)
        else:
            # More than one: this is a list
            for res in resource:
                resource_id = int(res["ID"])
                max_ids["resource"] = max(max_ids["resource"], resource_id)

    return max_ids


serialized = anymarkup.serialize({"ResourceSummary": {"ResourceGroup": resourcegroups}}, "xml")
serialized = \
    serialized.replace(
        b"<ResourceSummary>",
        b"<ResourceSummary xmlns:xsi=\"http://www.w3.org/2001/XMLSchema-instance\" xsi:schemaLocation=\"%s\">"
        % SCHEMA_LOCATION)
with open("rgsummary.xml", "wb") as outfile:
    outfile.write(serialized)
print(get_max_ids(resourcegroups))
