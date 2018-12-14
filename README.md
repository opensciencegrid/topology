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
    Additionally, each VO has a file that contains information about WLCG metric reporting groups called
    `REPORTING_GROUPS.yaml`.

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


Getting Help
------------

If you have any questions or encounter any issues with the registry, please open a ticket through the system appropriate
for the VO(s) that you support:

| If you primarily support... | Submit new tickets to...                         |
|-----------------------------|--------------------------------------------------|
| LHC VOs                     | [GGUS](https://ggus.eu)                          |
| Anyone else                 | [Freshdesk](https://support.opensciencegrid.org) |

Or email us at help@opensciencegrid.org.
