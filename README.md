Topology [![Build Status](https://travis-ci.org/opensciencegrid/topology.svg?branch=master)](https://travis-ci.org/opensciencegrid/topology)
========

This repository contains the registry of OSG projects, site resources, and Virtual Organizations, as well as
scripts for managing and displaying this information.

**For registration instructions, please see [this document](https://opensciencegrid.org/docs/common/registration).**

The information was sourced from the former OIM site that was hosted at `oim.grid.iu.edu`.
This README contains the following sections:

- [Structure of the Registry](#structure-of-the-registry)
- [Viewing the Registry](#accessing-the-data)
- [Getting Help](#getting-help)


Structure of the Registry
-------------------------

The data is organized as files in [YAML format](https://en.wikipedia.org/wiki/YAML)
as follows:

-   `projects/` contains information about research projects that run jobs on OSG.
    Each project has its own file, named `<PROJECT>.yaml`

-   `virtual-organizations/` contains information about Virtual Organizations
    (VOs).
    Each VO has its own file, named `<VO>.yaml`.
    Additionally, there is a `REPORTING_GROUPS.yaml` file that contains information about WLCG metric reporting groups
    for each VO.

-   `topology/` contains information about the topology of the resources that OSG sites provide.
    Resources such as HTCondor-CE, GridFTP, XRootD, or Squid are collected into "resource groups." 
    Each resource group has its own file, which are further organized by facility, and then by site.
    Resource group files are named `<FACILITY>/<SITE>/<RESOURCEGROUP>.yaml`

    For example, the OSG resources in the Center for High Throughput Computing can be found in the following file:
    `topology/University of Wisconsin/CHTC/CHTC.yaml`


Viewing the Registry
--------------------

Registry data can be accessed in two formats: the YAML files can be accessed directly through the GitHub interface or
from a clone of the GitHub repository.
Alternatively, the registry data can be accessed in XML format at the following URLs:

| The following data... | Can be accessed in XML format via URL...         |
|-----------------------|--------------------------------------------------|
| Project               | <https://my.opensciencegrid.org/miscproject/xml> |
| Resource Downtime     | <https://my.opensciencegrid.org/rgdowntime/xml>  |
| Resource Topology     | <https://my.opensciencegrid.org/rgsummary/xml>   |
| Virtual Organization  | <https://my.opensciencegrid.org/vosummary/xml>   |

These XML pages are compatible with the XML format once provided by `myosg.grid.iu.edu`.

### XML page arguments

Some of the XML pages listed above accept arguments for filtering queries.
These are compatible with the arguments once used by `myosg.grid.iu.edu`.

#### For the Resource Topology (rgsummary) and Resource Downtime (rgdowntime) pages

Boolean filters:

| The following argument(s)... | Will have the effect of...                         |
|------------------------------|----------------------------------------------------|
| `active=on&active_value=0`   | showing only inactive resources                    |
| `active=on&active_value=1`   | showing only active resources                      |
| `disable=on&disable_value=0` | showing only disabled resources                    |
| `disable=on&disable_value=1` | showing only enabled resources                     |
| `gridtype=on&gridtype_1=on`  | showing only production resources                  |
| `gridtype=on&gridtype_2=on`  | showing only non-production (ITB) resources        |
| `service_hidden_value=0`     | showing only non-hidden services \*                |
| `service_hidden_value=1`     | showing only hidden services \*                    |
| `has_wlcg=on`                | showing only resources with WLCG information \*\*  |

\* Note lack of `service_hidden=on` argument<br>
\*\* There is no way to show only resources without WLCG information; `has_wlcg=off` doesn't work


ID-based filters:

These select by a numeric ID on facilities, sites, support centers, resource groups, and services, and VOs.
Multiple IDs may be specified for an attribute, in which case resources that match any of the IDs listed will be shown.
There are two equivalent formats for the arguments:
- `<ATTRIB>_<ID1>=on&<ATTRIB>_<ID2>=on&<ATTRIB>_<ID3>=on`
- `<ATTRIB>_sel[]=<ID1>&<ATTRIB>_sel[]=<ID2>&<ATTRIB>_sel[]=<ID3>`

| The following attributes (`<ATTRIB>`)... | Will filter by (`<ID>`)...             |
|-----------------------------|-------------------------------|
| `facility`                  | Facility ID                   |
| `site`                      | Site ID                       |
| `rg`                        | ResourceGroup GroupID         |
| `service`                   | Service ID                    |
| `sc`                        | SupportCenter ID              |
| `voown`                     | VO Ownership (rgsummary only) |

For example, either of the two following sets of arguments will show resources that are in ANL (10089), Fermilab (10009), or UW-Madison (10011):
- `facility_10089=on&facility_10009=on&facility_10011=on`
- `facility_sel[]=10089&facility_sel[]=10009&facility_sel[]=10011`

If multiple filters are specified, only resources that match all filters will be shown.

Finally, you may restrict how much _past_ downtime is shown in the Resource Downtime XML with:
- `downtime_attrs_showpast=all`: show all past downtime
- `downtime_attrs_showpast=<DAYS>`: show downtime that ended no earlier than `<DAYS>` days ago.
  For example `downtime_attrs_showpast=7` shows downtime that ended within the past 168 hours (7 days \* 24 hours per day).
- `downtime_attrs_showpast=0`: show no past downtime; this is the default if not specified

#### For the Virtual Organization (vosummary) page

Boolean filters:

| The following argument(s)... | Will have the effect of...             |
|------------------------------|----------------------------------------|
| `active=on&active_value=0`   | showing only inactive VOs              |
| `active=on&active_value=1`   | showing only active VOs                |
| `disable=on&disable_value=0` | showing only disabled VOs              |
| `disable=on&disable_value=1` | showing only enabled VOs               |
| `oasis=on&oasis_value=0`     | showing only VOs that do not use OASIS |
| `oasis=on&oasis_value=1`     | showing only VOs that use OASIS        |

ID-based filter:

This selects based on a numeric ID on VOs.
Multiple IDs may be specified, in which case VOs that match any of the IDs listed will be shown.
There are two equivalent formats for the arguments:
- `vo_<ID1>=on&vo_<ID2>=on&vo_<ID3>=on`
- `vo_sel[]=<ID1>&vo_sel[]=<ID2>&vo_sel[]=<ID3>`

For example, either of the following will match GLOW (13), HCC (67), and IceCube (38):
- `vo_13=on&vo_67=on&vo_38=on`
- `vo_sel[]=13&vo_sel[]=67&vo_sel[]=38`



Getting Help
------------

If you have any questions or encounter any issues with the registry, please open a ticket through the system appropriate
for the VO(s) that you support:

| If you primarily support... | Submit new tickets to...                         |
|-----------------------------|--------------------------------------------------|
| LHC VOs                     | [GGUS](https://ggus.eu)                          |
| Anyone else                 | [Helpdesk](https://support.opensciencegrid.org) |

Or email us at help@opensciencegrid.org.
