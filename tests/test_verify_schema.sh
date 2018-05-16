#!/bin/bash -xe

PYTHONPATH="$PYTHONPATH:$TRAVIS_BUILD_DIR/"
export PYTHONPATH

function verify_xml {
    # Verifies XML data from stdin against the schema
    type="$1"
    xml="$2"
    xmllint --noout --schema "$TRAVIS_BUILD_DIR/schema/$type.xsd" $xml
}

echo -e "===================================================\n"\
     "DOWNLOADING AND VERIFYING XML AGAINST THEIR SCHEMAS\n"\
     "==================================================="

for DATA_TYPE in rgdowntime miscproject rgsummary vosummary; do
    echo -e "$DATA_TYPE\n-------------------------------------"
    ORIG_XML=/tmp/$DATA_TYPE.orig.xml
    ./converters/download --out $ORIG_XML $DATA_TYPE
    # TODO write miscproject.xsd
    [ $DATA_TYPE != "miscproject" ] && verify_xml $DATA_TYPE $ORIG_XML
done

echo -e "============================================================================\n"\
     "CONVERTING DOWNLOADED XML TO YAML TO XML AND VERIFYING AGAINST THEIR SCHEMAS\n"\
     "============================================================================"

for XML_TYPE in miscproject rgsummary vosummary; do
    echo -e "-------------\n$XML_TYPE\n-------------"
    ORIG_XML=/tmp/$XML_TYPE.orig.xml
    YAML_DIR="$TRAVIS_BUILD_DIR"
    case $XML_TYPE in
        miscproject)
            YAML_DIR="$YAML_DIR/projects/"
            ./converters/project_xml_to_yaml $ORIG_XML $YAML_DIR
            python3 webapp/project_reader.py $YAML_DIR /tmp/$XML_TYPE.xml
            # TODO convert project XML
            ;;
        rgsummary)
            YAML_DIR="$YAML_DIR/topology/"
            ./converters/rg_xml_to_yaml $ORIG_XML /tmp/rgdowntime.orig.xml $YAML_DIR
            python3 webapp/rg_reader.py $YAML_DIR /tmp/$XML_TYPE.xml /tmp/rgdowntime.xml
            verify_xml $XML_TYPE /tmp/$XML_TYPE.xml
            verify_xml rgdowntime /tmp/rgdowntime.xml
            ;;
        vosummary)
            YAML_DIR="$YAML_DIR/virtual-organizations/"
            ./converters/vo_xml_to_yaml $ORIG_XML $YAML_DIR
            python3 webapp/vo_reader.py
            verify_xml $XML_TYPE 'new_vos.xml'
            ;;
        *)
            continue
            ;;
    esac
done
