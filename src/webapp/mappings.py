#!/usr/bin/env python3
from argparse import ArgumentParser

import logging
import os
import sys
import yaml
from typing import Dict

if __name__ == "__main__" and __package__ is None:
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from webapp.common import load_yaml_file


log = logging.getLogger(__name__)


class Mappings:
    def __init__(self, nsfscience: Dict):
        self.nsfscience = nsfscience


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


def get_mappings(indir="../mappings", strict=False):
    mappings = Mappings(nsfscience=get_nsfscience(indir, strict))
    return mappings
