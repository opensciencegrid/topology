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
    def __init__(self, nsfscience: Dict, project_institution: Dict, institution_ids: List, field_of_science: Dict):
        self.nsfscience = nsfscience
        self.project_institution = project_institution
        self.institution_ids = institution_ids
        self.field_of_science = field_of_science


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


def get_field_of_science(indir: str, strict: bool) -> Dict:
    field_of_science = {}
    try:
        field_of_science = load_yaml_file(os.path.join(indir, "field_of_science.yaml"))
    except yaml.YAMLError:
        if strict:
            raise
        else:
            # load_yaml_file() already logs the specific error
            log.error("skipping (non-strict mode)")
    return field_of_science


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
    institution_name_fields_set = set()
    institution_id_fields_set = set()
    for ii in institution_ids:
        name = ii.get("name", None)
        id_ = ii.get("id", None)
        if not name:
            errors.append("Missing 'name' in entry %r" % ii)
            continue
        if not id_:
            errors.append("Missing 'id' in entry %r" % ii)
            continue
        if name in institution_name_fields_set:
            errors.append("Duplicate 'name' %s in entry %r" % (name, ii))
            continue
        if id_ in institution_id_fields_set:
            errors.append("Duplicate 'id' %s in entry %r" % (id_, ii))
            continue
        institution_name_fields_set.add(name)
        institution_id_fields_set.add(id_)
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
                        institution_ids=get_institution_ids(indir, strict),
                        field_of_science=get_field_of_science(indir, strict))
    return mappings
