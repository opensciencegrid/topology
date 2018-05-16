Sources
=======

Conversion scripts
------------------

Scripts inside the `converters` directory are used for two things:
-   the initial conversion of XML data (obtained from myosg.grid.iu.edu)
    into directory trees of YAML files
-   the conversion of the YAML files back into XML so that scripts that
    use the XML interface to MyOSG continue to work with minimal
    modifications


### download_projects.py ###

Usage:

    download_projects.py > projects.xml

Download the current XML of projects from MyOSG.


#### download_rgsummary.py

Usage:

    download_rgsummary.py [options] > rgsummary.xml

Options:

    --show-inactive=YES|NO|ONLY     Show inactive resources [default: YES]
    --show-itb=YES|NO|ONLY          Show ITB resource groups [default: YES]
    --show-disabled-resource=YES|NO|ONLY    Show disabled resources [default: YES]

Download the current XML of the resource groups from MyOSG.


### download_vosummary.py ###

Usage:

    download_vosummary.py [options] > vos.xml

Options:

    --show-inactive=YES|NO|ONLY     Show inactive VOs [default: YES]

Download the current XML of the VO data from MyOSG.


### project_xml_to_yaml.py ###

Usage:

    project_xml_to_yaml.py

Convert an XML projects file named `projects.xml` into a YAML directory tree
in `./projects`.


### project_yaml_to_xml.py ###

Usage:

    project_yaml_to_xml.py

Convert a YAML projects directory tree named `projects` into an XML file named
`new_projects.xml`.


### resourcegroup_xml_to_yaml.py ###

Usage:

    resourcegroup_xml_to_yaml.py <input XML> <output directory>

Convert an XML resource group summary file into a YAML resource topology tree.


### resourcegroup_yaml_to_xml.py ###

Usage:

    resourcegroup_yaml_to_xml.py <input directory> [<output XML>]

Convert a YAML resource topology directory tree into XML.  If the output file
is not specified, the contents are printed to standard output.


### vo_xml_to_yaml.py ###

Usage:

    vo_xml_to_yaml.py

Convert an XML VOs file named `vos.xml` into a YAML directory tree
in `./virtual-organizations`.


### vo_yaml_to_xml.py ###

Usage:

    vo_yaml_to_xml.py

Convert a YAML VOs directory tree named `virtual-organizations` into an XML
file named `new_vos.xml`.


