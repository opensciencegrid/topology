#!/usr/bin/env python3
from argparse import ArgumentParser

import logging
import os
import sys
import yaml
from typing import Dict, List

if __name__ == "__main__" and __package__ is None:
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from webapp.exceptions import DataError
from webapp.common import load_yaml_file


log = logging.getLogger(__name__)


class Mappings:
    def __init__(self, nsfscience: Dict, project_institution: Dict, institution_ids: List):
        self.nsfscience = nsfscience
        self.project_institution = project_institution
        self.institution_ids = institution_ids


def get_nsfscience(indir: str, strict: bool) -> Dict:
    nsfscience = {}
    try:
        nsfscience = load_yaml_file(os.path.join(indir, "nsfscience.yaml"))
    except yaml.YAMLError:
        if strict:
            raise
        else:
            # load_yaml_file() already logs the specific error
            log.error("skipping (non-strict mode)")
    return nsfscience


def get_project_institution(indir: str, strict: bool) -> Dict:
    project_institution = {}
    try:
        project_institution = load_yaml_file(os.path.join(indir, "project_institution.yaml"))
    except yaml.YAMLError:
        if strict:
            raise
        else:
            # load_yaml_file() already logs the specific error
            log.error("skipping (non-strict mode)")
    return project_institution


def validate_institution_ids(institution_ids: List) -> List[str]:
    """Validate the institution/id mapping loaded by get_institution_ids():
    ensure required attributes are present and nonempty, and there are no duplicates.
    """
    errors = []
    institution_names_set = set()
    institution_osg_ids_set = set()
    for ii in institution_ids:
        name = ii.get("name", None)
        osg_id = ii.get("osg_id", None)
        if not name:
            errors.append("Missing 'name' in entry %r" % ii)
            continue
        if not osg_id:
            errors.append("Missing 'osg_id' in entry %r" % ii)
            continue
        if name in institution_names_set:
            errors.append("Duplicate 'name' %s in entry %r" % (name, ii))
            continue
        if osg_id in institution_osg_ids_set:
            errors.append("Duplicate 'osg_id' %s in entry %r" % (osg_id, ii))
            continue
        institution_names_set.add(name)
        institution_osg_ids_set.add(osg_id)
    return errors


def get_institution_ids(indir: str, strict: bool) -> List:
    institution_ids = []
    try:
        institution_ids = load_yaml_file(os.path.join(indir, "institution_ids.yaml"))
    except yaml.YAMLError:
        if strict:
            raise
        else:
            # load_yaml_file() already logs the specific error
            log.error("skipping (non-strict mode)")

    errors = validate_institution_ids(institution_ids)
    if errors:
        message = "Errors found with institution/id mappings:\n%s" % "\n".join(errors)
        if strict:
            raise DataError(message)
        else:
            log.error(message)
            log.error("skipping bad mappings (non-strict mode)")

    return institution_ids


def get_mappings(indir="../mappings", strict=False):
    mappings = Mappings(nsfscience=get_nsfscience(indir, strict),
                        project_institution=get_project_institution(indir, strict),
                        institution_ids=get_institution_ids(indir, strict))
    return mappings
