Sources
=======

Conversion scripts
------------------

Scripts inside the `converters` directory are used for the initial conversion
of XML data (obtained from myosg.grid.iu.edu) into directory trees of YAML
files.

### updateall ###

Usage:

    updateall

Download current XML from MyOSG and convert to YAML directory trees.

### download ###

Usage:

    download [--auth --key KEY.PEM --cert CERT.PEM] [--out OUTPUT.XML] <data> [<options>]

Download current XML from MyOSG.  If you pass `--auth`, authenticated access with an x509 cert will be used.

`<data>` is the data file to download, one of:

- `miscproject`: project data
- `rgdowntime`: downtime data
- `rgsummary`: topology data
- `vosummary`: VO data

Run `download <data> -h` to see the various filtering options.

### project_xml_to_yaml ###

Usage:

    project_xml_to_yaml <input XML> <output directory>

Convert an XML projects file into a YAML directory tree.


### resourcegroup_xml_to_yaml ###

Usage:

    resourcegroup_xml_to_yaml <input XML> <downtime XML> <output directory>

Convert an XML resource group summary file into a YAML resource topology tree,
with downtime info.


### vo_xml_to_yaml ###

Usage:

    vo_xml_to_yaml <input XML> <output directory>

Convert an XML VOs file into a YAML directory tree.

