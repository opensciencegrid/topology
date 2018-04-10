import anymarkup
import os
import shutil


# Example URL: https://myosg.grid.iu.edu/rgsummary/xml?summary_attrs_showhierarchy=on&summary_attrs_showwlcg=on&summary_attrs_showservice=on&summary_attrs_showfqdn=on&summary_attrs_showvoownership=on&summary_attrs_showcontact=on&gip_status_attrs_showtestresults=on&downtime_attrs_showpast=&account_type=cumulative_hours&ce_account_type=gip_vo&se_account_type=vo_transfer_volume&bdiitree_type=total_jobs&bdii_object=service&bdii_server=is-osg&all_resources=on&facility_sel%5B%5D=10009&gridtype=on&gridtype_1=on&active=on&active_value=1&disable_value=1
# Layout in that URL is
# <ResourceGroup>
#   <Facility>
#   <Site>
#   <Resources>
#     <Resource>
#     ...

# Layout we want is
# facility/
#   site/
#     site.yml
#     resourcegroup1.yml
#     ...
# (where "facility", "site", and "resourcegroup1" but _not_ "site.yml" are
# named after the facility, site, and resource group (sanitized).


def to_file_name(name):
    """Replaces characters in ``name`` that shouldn't be used for file or
    dir names.

    """
    filename = ""
    for char in name:
        if char in '/:.\\':
            filename += "_"
        else:
            filename += char
    return filename


parsed = anymarkup.parse_file('../examples/rgsummary1.xml')['ResourceSummary']

topology = {}

for rg in parsed['ResourceGroup']:
    sanfacility = to_file_name(rg['Facility']['Name'])
    if sanfacility not in topology:
        topology[sanfacility] = {}
    sansite = to_file_name(rg['Site']['Name'])
    if sansite not in topology[sanfacility]:
        topology[sanfacility][sansite] = {}
    sanrg = to_file_name(rg['GroupName']) + ".yml"
    topology[sanfacility][sansite][sanrg] = rg

topdir = "/tmp/topology"
if os.path.isdir(topdir):
    shutil.rmtree(topdir)
os.makedirs(topdir)
for fkey, fval in topology.items():
    facilitydir = os.path.join(topdir, fkey)
    for skey, sval in fval.items():
        sitedir = os.path.join(facilitydir, skey)
        os.makedirs(sitedir)
        for rgkey, rgval in sval.items():
            serialized = anymarkup.serialize(rgval, "yaml").decode()
            serialized = serialized.replace("!!omap", "").strip()
            with open(os.path.join(sitedir, rgkey), "w") as f:
                f.write(serialized)
print("take a look in", topdir)
# for project in parsed['Projects']['Project']:
#     print("Would Create file: %s.yaml" % (project['Name']))
#     serialized = anymarkup.serialize(project, "yaml")
#     serialized = serialized.replace("!!omap", "").strip()
#     with open("projects/{0}.yaml".format(project['Name']), 'w') as f:
#         f.write(serialized)
#     #print(project)


