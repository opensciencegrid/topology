#!/bin/bash -e

# Use the Travis build dir if specified, otherwise assume that the
# repo is unpacked in the current working dir
REPO_ROOT_DIR=${TRAVIS_BUILD_DIR:-.}

PYTHONPATH="$PYTHONPATH:$REPO_ROOT_DIR/src"
export PYTHONPATH

function verify_xml {
    # Verifies XML data against the schema
    xml="$1"
    type="$2"
    echo "Validating $type XML schema..."
    xmllint --noout --schema "$REPO_ROOT_DIR/src/schema/$type.xsd" $xml
}

if [[ $TRAVIS_PULL_REQUEST == "false" || $GH_EVENT == 'push' ]] &&
   [[ $GITHUB_REPOSITORY == 'opensciencegrid/topology' ]]; then
    # Ensure that the .ssh dir exists
    mkdir ~/.ssh
    chmod 0700 ~/.ssh
    touch ~/.ssh/known_hosts
    chmod 0600 ~/.ssh/known_hosts
    cat >> ~/.ssh/known_hosts <<EOF
github.com ssh-rsa AAAAB3NzaC1yc2EAAAABIwAAAQEAq2A7hRGmdnm9tUDbO9IDSwBK6TbQa+PXYPCPy6rbTrTtw7PHkccKrpp0yVhp5HdEIcKr6pLlVDBfOLX9QUsyCOV0wzfjIJNlGEYsdlLJizHhbn2mUjvSAHQqZETYP81eFzLQNnPHt4EVVUh7VfDESU84KezmD5QlWpXLmvU31/yMf+Se8xhHTvKSCZIFImWwoG6mbUoWf9nzpIoaSjB+weqqUUmpaaasXVal72J+UX2B+2RPW3RcT0eOzQgqlJL3RKrTJvdsjE3JEAvGq3lGHSZXy28G3skua2SmVi/w4yCE6gbODqnTWlg7+wC604ydGXA8VJiS5ap43JXiUFFAaQ==
EOF

    touch contacts
    chmod 600 contacts

    if [[ $GH_EVENT == 'push' ]]; then
        echo "$CONTACT_DB_KEY" > contacts
    else
        openssl aes-256-cbc \
                -K $encrypted_457175ef53a3_key \
                -iv $encrypted_457175ef53a3_iv \
                -in src/tests/contacts.enc \
                -out contacts \
                -d
    fi

    eval `ssh-agent -s`
    ssh-add contacts
    git clone git@github.com:opensciencegrid/contact.git /tmp/contact
    CONTACT_YAML=/tmp/contact/contacts.yaml
fi

for DATA_TYPE in miscproject vosummary rgsummary; do
    CONVERTED_XML=/tmp/$DATA_TYPE.xml

    case $DATA_TYPE in
        miscproject)
            YAML_DIR="$REPO_ROOT_DIR/projects"
            READER=src/webapp/project_reader.py
            READER_ARGS="$YAML_DIR $CONVERTED_XML"
            ;;
        rgsummary)
            YAML_DIR="$REPO_ROOT_DIR/topology"
            READER=src/webapp/rg_reader.py
            READER_ARGS="$YAML_DIR $CONVERTED_XML /tmp/rgdowntime.xml"
            ;;
        vosummary)
            YAML_DIR="$REPO_ROOT_DIR/virtual-organizations"
            READER=src/webapp/vo_reader.py
            READER_ARGS="$YAML_DIR $CONVERTED_XML"
            ;;
    esac

    # Resource group and VO readers should use the contact info if we have
    # access to the SSH keys for the contacts repo
    if [[ $DATA_TYPE == 'vosummary' ]] || [[ $DATA_TYPE == 'rgsummary' ]]; then
        if [[ $TRAVIS_PULL_REQUEST == "false" || $GH_EVENT == 'push' ]] &&
           [[ $GITHUB_REPOSITORY == 'opensciencegrid/topology' ]]; then
            READER_ARGS="--contacts $CONTACT_YAML $READER_ARGS"
        fi
    fi

    python3 $READER $READER_ARGS
    verify_xml $CONVERTED_XML $DATA_TYPE
    
    [[ $DATA_TYPE == 'rgsummary' ]] && verify_xml /tmp/rgdowntime.xml rgdowntime
done

echo
echo "Validating timestamps in rgdowntime.xml ..."
./src/tests/verify_xml_downtimes.py /tmp/rgdowntime.xml

# Exit 0 if we get to the end
exit 0
