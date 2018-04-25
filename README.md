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
    Each VO has its own file, named `<VO>.yaml`

-   `topology/` contains information about the topology of the resources that
    OSG sites provide.  Resources are collected into "resource groups."  Each
    resource group has its own file, which are further organized by facility,
    and then by site.  Resource group files are named
    `<FACILITY>/<SITE>/<RESOURCEGROUP>.yaml`


Accessing the Data
------------------

Data can be accessed in two formats: the YAML files can be accessed directly
from a clone of the GitHub repository.  Alternatively, the data can be accessed
in XML format at the following URLs:

-   **TODO** for projects
-   **TODO** for VOs
-   **TODO** for topology of resource groups

These XML pages are compatible with the XML format once provided by
`myosg.grid.iu.edu`.


Updating the Data or Creating New Data
--------------------------------------

To update the data for your site, project, or VO, please either edit the
matching YAML file and submit a GitHub pull request.  Or, if you are not
comfortable directly making those changes, send email to **TODO**
with the changes you want made.

To create a new resource group, project, or VO, please use one of the template
files to create the file in the appropriate directory, and fill out the
information.  The comments in the template files should explain the structure
and the meaning of the data.  If anything is confusing or you do not feel
comfortable creating the new file yourself, send email to **TODO** with details
about your resource group, project, or VO.

The template files are:

-   `template-project.yaml` for new projects; should be put in
    `projects/<PROJECT NAME>.yaml`
-   `template-vo.yaml` for new VOs; should be put in
    `virtual-organizations/<VO NAME>.yaml`
-   `template-resourcegroup.yaml` for new resource groups;
    should be put in `<FACILITY>/<SITE>/<RESOURCE GROUP NAME>.yaml`.

**Note**: File and directory names _must_ match the name of your project, VO,
facility, site, or resource group, as appropriate.  This includes case and
spaces.


The Scripts
-----------

### Conversion scripts

Scripts inside the `converters` directory are used for two things:
-   the initial conversion of XML data (obtained from myosg.grid.iu.edu)
    into directory trees of YAML files
-   the conversion of the YAML files back into XML so that scripts that
    use the XML interface to MyOSG continue to work with minimal
    modifications


#### download_rgsummary.py

Usage:

    download_rgsummary.py [options] > rgsummary.xml

Options:

    --show-inactive=YES|NO|ONLY     Show inactive resource groups [default: YES]
    --show-itb=YES|NO|ONLY          Show ITB resource groups [default: YES]
    --show-disabled-resource=YES|NO|ONLY    Show resource groups with disabled resources [default: YES]

Download the current XML of the resource groups from MyOSG.


#### project_xml_to_yaml.py

Usage:

    project_xml_to_yaml.py

Convert an XML projects file named `projects.xml` into a YAML directory tree
in `./projects`.


#### project_yaml_to_xml.py

Usage:

    project_yaml_to_xml.py

Convert a YAML projects directory tree named `projects` into an XML file named
`new_projects.xml`.


#### resourcegroup_xml_to_yaml.py

Usage:

    resourcegroup_xml_to_yaml.py <input XML> <output directory>

Convert an XML resource group summary file into a YAML resource topology tree.


#### resourcegroup_yaml_to_xml.py

Usage:

    resourcegroup_yaml_to_xml.py <input directory> [<output XML>]

Convert a YAML resource topology directory tree into XML.  If the output file
is not specified, the contents are printed to standard output.


#### vo_xml_to_yaml.py

Usage:

    vo_xml_to_yaml.py

Convert an XML VOs file named `vos.xml` into a YAML directory tree
in `./virtual-organizations`.


#### vo_yaml_to_xml.py

Usage:

    vo_yaml_to_xml.py

Convert a YAML VOs directory tree named `virtual-organizations` into an XML
file named `new_vos.xml`.


