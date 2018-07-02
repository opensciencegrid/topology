Topology
========


This repository contains the registry of OSG projects, site resources, and Virtual Organizations, as well as
scripts for managing and displaying this information.
The information was sourced from the former OIM site that was hosted at `oim.grid.iu.edu`.
This README contains the following sections:

- [Structure of the Registry](#structure-of-the-registry)
- [How to Register](#how-to-register)
- [How to Register Downtime](#how-to-register-downtime)
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


How to Register
---------------

The formatting of the YAML files for the different types of registration data are described in the following template
files:

| The following data... | Is defined by template file...       | And should be copied to location, relative to the Git root directory... |
|-----------------------|--------------------------------------|-------------------------------------------------------------------------|
| Project               | `template-project.yaml`              | `projects/<PROJECT NAME>.yaml`                                          |
| Resource Downtime     | `template-downtime.yaml`             | `topology/<FACILITY>/<SITE>/<RESOURCE GROUP NAME>_downtime.yaml`        |
| Resource Topology     | `template-resourcegroup.yaml`        | `topology/<FACILITY>/<SITE>/<RESOURCE GROUP NAME>.yaml`                 |
| Virtual Organization  | `template-virtual-organization.yaml` | `virtual-organizations/<VO NAME>.yaml`                                  |

The comments in the template files explain the structure and the meaning of the data.

**Note**: File and directory names _must_ match the name of your project, VO,
facility, site, or resource group, as appropriate.  This includes case and
spaces.

### New registrations ###

To create a new resource group, project, or VO, please create the YAML file according to the table above, and use the
corresponding template file to fill in the appropriate information.
If you do not feel comfortable creating the new file yourself, send an email to <help@opensciencegrid.org> with
details about your resource group, project, or VO.

### Updating existing registrations ###

To update the data for your site resources, project, or VO, make and submit your changes using one of the following
methods:

- [Modify the corresponding YAML file](https://help.github.com/articles/editing-files-in-your-repository/) and submit
  your changes as a GitHub pull request.
- Send an email to <help@opensciencegrid.org> requesting your desired changes.

For definitions for the various fields, consult the corresponding template file for the type of data you are updating.


### How to Register Downtime ###

The file that contains downtime information about resources you own is named 
`topology/<FACILITY>/<SITE>/<RESOURCE GROUP NAME>_downtime.yaml`.
To find out what resource group a host is in, you can grep for the FQDN of the host.

To add new downtime, add the contents of `template-downtime.yaml` to the end of the downtime file in the path above,
and follow the instructions in the comments to fill out the necessary fields.
Then, submit your changes as a GitHub pull request.

**Note:** Make sure there is no additional indentation in the YAML data you add;
the first line (with the `-`) must be completely unindented.

Alternatively, send an email to <help@opensciencegrid.org> requesting your desired changes.



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

If you have any questions or encounter any issues with the registry, please contact open a ticket at
https://support.opensciencegrid.org or email us at help@opensciencegrid.org.
