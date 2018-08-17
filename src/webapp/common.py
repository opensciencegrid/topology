from collections import OrderedDict
from logging import getLogger
import hashlib
import os
import re
import shlex
import subprocess
import sys
from typing import Dict, List, Union, AnyStr

import xmltodict

MaybeOrderedDict = Union[None, OrderedDict]

MISCUSER_SCHEMA_URL = "https://my.opensciencegrid.org/schema/miscuser.xsd"
RGSUMMARY_SCHEMA_URL = "https://my.opensciencegrid.org/schema/rgsummary.xsd"
RGDOWNTIME_SCHEMA_URL = "https://my.opensciencegrid.org/schema/rgdowntime.xsd"
VOSUMMARY_SCHEMA_URL = "https://my.opensciencegrid.org/schema/vosummary.xsd"


log = getLogger(__name__)


class Filters(object):
    def __init__(self):
        self.facility_id = []
        self.site_id = []
        self.support_center_id = []
        self.service_id = []
        self.grid_type = None
        self.active = None
        self.disable = None
        self.past_days = 0  # for rgdowntime
        self.voown_id = []
        self.voown_name = []
        self.rg_id = []
        self.service_hidden = None
        self.oasis = None  # for vosummary
        self.vo_id = []  # for vosummary
        self.has_wlcg = None

    def populate_voown_name(self, vo_id_to_name: Dict):
        self.voown_name = [vo_id_to_name.get(i, "") for i in self.voown_id]


def is_null(x, *keys) -> bool:
    for key in keys:
        if not key: continue
        if not isinstance(x, dict) or key not in x:
            return True
        else:
            # actually want to check x[key]
            x = x[key]
    return (x is None or x == "null"
            or (isinstance(x, (list, dict)) and len(x) < 1)
            or x in ["(Information not available)",
                     "no applicable service exists",
                     "(No resource group description)",
                     "(No resource description)",
                     ])


def ensure_list(x) -> List:
    if isinstance(x, list):
        return x
    elif x is None:
        return []
    return [x]


def simplify_attr_list(data: Union[Dict, List], namekey: str) -> Dict:
    """
    Simplify
        [{namekey: "name1", "attr1": "val1", ...},
         {namekey: "name2", "attr1": "val1", ...}]}
    or, if there's only one,
        {namekey: "name1", "attr1": "val1", ...}
    to
      {"name1": {"attr1": "val1", ...},
       "name2": {"attr1": "val1", ...}}
    """
    new_data = {}
    for d in ensure_list(data):
        new_d = dict(d)
        if is_null(new_d, namekey):
            continue
        name = new_d[namekey]
        del new_d[namekey]
        new_data[name] = new_d
    return new_data


def expand_attr_list_single(data: Dict, namekey:str, valuekey: str, name_first=True) -> List[OrderedDict]:
    """
    Expand
        {"name1": "val1",
         "name2": "val2"}
    to
        [{namekey: "name1", valuekey: "val1"},
         {namekey: "name2", valuekey: "val2"}]
    (except using an OrderedDict)
    """
    newdata = []
    for name, value in data.items():
        if name_first:
            newdata.append(OrderedDict([(namekey, name), (valuekey, value)]))
        else:
            newdata.append(OrderedDict([(valuekey, value), (namekey, name)]))
    return newdata


def expand_attr_list(data: Dict, namekey: str, ordering: Union[List, None]=None, ignore_missing=False) -> List[OrderedDict]:
    """
    Expand
        {"name1": {"attr1": "val1", ...},
         "name2": {"attr1": "val1", ...}}
    to
        [{namekey: "name1", "attr1": "val1", ...},
         {namekey: "name2", "attr1": "val1", ...}]}
    (except using an OrderedDict)
    If ``ordering`` is not None, the keys are used in the order provided by ``ordering``.
    """
    newdata = []
    for name, value in data.items():
        new_value = OrderedDict()
        if ordering:
            for elem in ordering:
                if elem == namekey:
                    new_value[elem] = name
                elif elem in value:
                    new_value[elem] = value[elem]
                elif not ignore_missing:
                    new_value[elem] = None
        else:
            new_value[namekey] = name
            new_value.update(value)
        newdata.append(new_value)
    return newdata


def to_xml(data) -> str:
    return xmltodict.unparse(data, pretty=True, encoding="utf-8")


def to_xml_bytes(data) -> bytes:
    return to_xml(data).encode("utf-8", errors="replace")


def trim_space(s: str) -> str:
    """Remove leading and trailing whitespace but not newlines"""
    # leading and trailing whitespace causes "\n"'s in the resulting string
    ret = re.sub(r"(?m)[ \t]+$", "", s)
    ret = re.sub(r"(?m)^[ \t]+", "", ret)
    return ret


def run_git_cmd(cmd: List, dir=None, ssh_key=None) -> bool:
    if ssh_key and not os.path.exists(ssh_key):
        log.critical("ssh key not found at %s: unable to update secure repo",
                     ssh_key)
        return False
    if dir:
        base_cmd = ["git", "--git-dir", os.path.join(dir, ".git"), "--work-tree", dir]
    else:
        base_cmd = ["git"]

    if ssh_key:
        shell = True
        # From SO: https://stackoverflow.com/questions/4565700/specify-private-ssh-key-to-use-when-executing-shell-command
        full_cmd = "ssh-agent bash -c " + \
                   shlex.quote("ssh-add {0}; {1}".format(shlex.quote(ssh_key),
                               " ".join([shlex.quote(s) for s in (base_cmd + cmd)])))
    else:
        shell = False
        full_cmd = base_cmd + cmd

    git_result = subprocess.run(full_cmd, shell=shell, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                encoding="utf-8")
    if git_result.returncode != 0:
        out = git_result.stdout
        log.warning("Git failed:\nCommand was {0}\nOutput was:\n{1}".format(full_cmd, git_result.stdout))
        return False

    return True


def git_clone_or_pull(repo, dir, branch, ssh_key=None) -> bool:
    if os.path.exists(os.path.join(dir, ".git")):
        _ = run_git_cmd(["clean", "-df"], dir=dir)
        ok = run_git_cmd(["fetch", "origin"], dir=dir, ssh_key=ssh_key)
        ok = ok and run_git_cmd(["reset", "--hard", "origin/{0}".format(branch)], dir=dir)
    else:
        ok = run_git_cmd(["clone", repo, dir], ssh_key=ssh_key)
        ok = ok and run_git_cmd(["checkout", branch], dir=dir)
    return ok


def gen_id(instr: AnyStr, digits, minimum=1, hashfn=hashlib.md5) -> int:
    instr_b = instr if isinstance(instr, bytes) else instr.encode("utf-8", "surrogateescape")
    mod = (10 ** digits) - minimum
    return minimum + (int(hashfn(instr_b).hexdigest(), 16) % mod)
