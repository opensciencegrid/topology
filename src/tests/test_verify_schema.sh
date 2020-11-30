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
bitbucket.org ssh-rsa AAAAB3NzaC1yc2EAAAABIwAAAQEAubiN81eDcafrgMeLzaFPsw2kNvEcqTKl/VqLat/MaB33pZy0y3rJZtnqwR2qOOvbwKZYKiEO1O6VqNEBxKvJJelCq0dTXWT5pbO2gDXC6h6QDXCaHo6pOHGPUy+YBaGQRGuSusMEASYiWunYN0vCAI8QaXnWMXNMdFP3jHAJH0eDsoiGnLPBlBp4TNm6rYI74nMzgz3B9IikW4WVK+dc8KZJZWYjAuORU3jc1c/NPskD2ASinf8v3xnfXeukU0sJ5N6m5E8VLjObPEO+mN2t/FZTMZLiFqPWc/ALSqnMnnhwrNi2rbfg/rd/IpL8Le3pSBne8+seeFVBoGqzHM9yXw==
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
    git clone git@bitbucket.org:opensciencegrid/contact.git /tmp/contact
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
