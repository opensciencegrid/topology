Topology
========


This repository contains information for known projects, site resources, and
Virtual Organizations known to the OSG, as well as scripts for managing and
displaying this information.  The information was sourced from the old OIM site
that was hosted at oim.grid.iu.edu.


Structure of the Data
---------------------

The data is organized as files in [YAML format](https://en.wikipedia.org/wiki/YAML)
as follows:

-   `projects/` contains information about research projects that run jobs on OSG.
    Each project has its own file, named `<PROJECT>.yaml`

-   `virtual-organizations/` contains information about Virtual Organizations
    (VOs).
    Each VO has its own file, named `<VO>.yaml`.  In addition, there is a file
    containing information about "reporting groups" called
    `REPORTING_GROUPS.yaml`.

-   `topology/` contains information about the topology of the resources that OSG sites provide.
    Resources such as HTCondor-CE, GridFTP, XRootD, or Squid are collected into "resource groups." 
    Each resource group has its own file, which are further organized by facility, and then by site.
    Resource group files are named `<FACILITY>/<SITE>/<RESOURCEGROUP>.yaml`

    For example, the OSG resources in the CHTC can be found in the following file:
    `topology/University of Wisconsin/CHTC/CHTC.yaml`


Accessing the Data
------------------

Data can be accessed in two formats: the YAML files can be accessed directly
from a clone of the GitHub repository.  Alternatively, the data can be accessed
in XML format at the following URLs:

-   For projects: https://my.opensciencegrid.org/miscproject/xml
-   For VOs: https://my.opensciencegrid.org/vosummary/xml
-   For resource group topology: https://my.opensciencegrid.org/rgsummary/xml

These XML pages are compatible with the XML format once provided by
`myosg.grid.iu.edu`.


Updating the Data or Creating New Data
--------------------------------------

To update the data for your site, project, or VO, please either edit the
matching YAML file and submit a GitHub pull request.
Or, if you are not comfortable directly making those changes, send an email to <mailto:help@opensciencegrid.org> with
the changes you want made.

To create a new resource group, project, or VO, please use one of the template
files to create the file in the appropriate directory, and fill out the
information.  The comments in the template files should explain the structure
and the meaning of the data.
If you do not feel comfortable creating the new file yourself, send an email to <mailto:help@opensciencegrid.org> with
details about your resource group, project, or VO.

The template files are:

-   `template-project.yaml` for new projects; should be put in
    `projects/<PROJECT NAME>.yaml`
-   `template-virtual-organization.yaml` for new VOs; should be put in
    `virtual-organizations/<VO NAME>.yaml`
-   `template-resourcegroup.yaml` for new resource groups;
    should be put in `<FACILITY>/<SITE>/<RESOURCE GROUP NAME>.yaml`.

**Note**: File and directory names _must_ match the name of your project, VO,
facility, site, or resource group, as appropriate.  This includes case and
spaces.
