from collections import OrderedDict
from logging import getLogger
import hashlib
import json
import os
import re
import subprocess
import sys
from typing import Any, Dict, List, Union, AnyStr, NewType, TypeVar
from functools import wraps

log = getLogger(__name__)

import xmltodict
import yaml
try:
    from yaml import CSafeLoader as SafeLoader
except ImportError:
    log.warning("CSafeLoader not available - install libyaml-devel and reinstall PyYAML")
    from yaml import SafeLoader

MISCUSER_SCHEMA_URL = "https://topology.opensciencegrid.org/schema/miscuser.xsd"
RGSUMMARY_SCHEMA_URL = "https://topology.opensciencegrid.org/schema/rgsummary.xsd"
RGDOWNTIME_SCHEMA_URL = "https://topology.opensciencegrid.org/schema/rgdowntime.xsd"
VOSUMMARY_SCHEMA_URL = "https://topology.opensciencegrid.org/schema/vosummary.xsd"

GRIDTYPE_1 = "OSG Production Resource"
GRIDTYPE_2 = "OSG Integration Test Bed Resource"

SSH_WITH_KEY = os.path.abspath(os.path.dirname(__file__) + "/ssh_with_key.sh")

ParsedYaml = NewType("ParsedYaml", Dict[str, Any])  # a complex data structure that's a result of parsing a YAML file
PreJSON = NewType("PreJSON", Dict[str, Any])  # a complex data structure that will be converted to JSON in the webapp
T = TypeVar("T")

class InvalidArgumentsError(Exception): pass


class Filters(object):
    def __init__(self):
        self.facility_id = []
        self.facility_name = []
        self.site_id = []
        self.site_name = []
        self.support_center_id = []
        self.support_center_name = []
        self.service_id = []
        self.service_name = []
        self.grid_type = None
        self.active = None
        self.disable = None
        self.past_days = 0  # for rgdowntime
        self.voown_id = []
        self.voown_name = []
        self.rg_id = []
        self.rg_name = []
        self.service_hidden = None
        self.oasis = None  # for vosummary
        self.vo_id = []  # for vosummary
        self.vo_name = []
        self.has_wlcg = None

    @classmethod
    def from_args(cls, args, global_data):
        """Parse http request parameters into a filter object"""

        filters = cls()

        filters.active = cls.get_filter_value(args, "active")
        filters.disable = cls.get_filter_value(args, "disable")
        filters.oasis = cls.get_filter_value(args, "oasis")

        filters.populate_gridtype_filter_from_args(args)
        filters.populate_service_hidden_filter_from_args(args)
        filters.populate_past_days_from_args(args)
        filters.populate_has_wlcg_from_args(args)

        for filter_key, filter_list, description in [
            ("facility", filters.facility_id, "facility ID"),
            ("rg", filters.rg_id, "resource group ID"),
            ("service", filters.service_id, "service ID"),
            ("sc", filters.support_center_id, "support center ID"),
            ("site", filters.site_id, "site ID"),
            ("vo", filters.vo_id, "VO ID"),
            ("voown", filters.voown_id, "VO owner ID"),
        ]:
            cls.add_selector_filter_from_args(args, filter_key, filter_list, description)
            cls.add_id_filter_from_args(args, filter_key, filter_list)

        for filter_key, filter_list in [
            ("facility", filters.facility_name),
            ("rg", filters.rg_name),
            ("service", filters.service_name),
            ("sc", filters.support_center_name),
            ("site", filters.site_name),
            ("vo", filters.vo_name),
            ("voown", filters.voown_name),
        ]:
            cls.add_name_filter_from_args(args, filter_key, filter_list)

        filters.populate_voown_name(global_data.get_vos_data().get_vo_id_to_name())

        return filters

    @staticmethod
    def get_filter_value(args, filter_key):
        filter_value_key = filter_key + "_value"
        if filter_key in args:
            filter_value_str = args.get(filter_value_key, "")
            if filter_value_str == "0":
                return False
            elif filter_value_str == "1":
                return True
            else:
                raise InvalidArgumentsError("{0} must be 0 or 1".format(filter_value_key))

    @staticmethod
    def add_selector_filter_from_args(args, filter_key, filter_list, description):
        if filter_key in args:
            pat = re.compile(r"{0}_(\d+)".format(filter_key))
            arg_sel = "{0}_sel[]".format(filter_key)
            for k, v in args.items():
                if k == arg_sel:
                    try:
                        filter_list.append(int(v))
                    except ValueError:
                        raise InvalidArgumentsError("{0}={1}: must be int".format(k,v))
                elif pat.match(k):
                    m = pat.match(k)
                    filter_list.append(int(m.group(1)))
            if not filter_list:
                raise InvalidArgumentsError("at least one {0} must be specified"
                                            " via the syntax <code>{1}_<b>ID</b>=on</code>"
                                            " or <code>{1}_sel[]=<b>ID</b></code>."
                                            " (These may be specified multiple times for multiple IDs.)"\
                                            .format(description, filter_key))

    @staticmethod
    def add_name_filter_from_args(args, filter_key, filter_list):
        arg_sel = "{0}_name[]".format(filter_key)
        selected_args = args.getlist(arg_sel)
        filter_list.extend(selected_args)

    @staticmethod
    def add_id_filter_from_args(args, filter_key, filter_list):
        arg_sel = "{0}_id[]".format(filter_key)
        selected_args = args.getlist(arg_sel)
        for v in selected_args:
            try:
                filter_list.append(int(v))
            except ValueError:
                raise InvalidArgumentsError("{0}={1}: must be int".format(arg_sel, v))

    def populate_gridtype_filter_from_args(self, args):
        if "gridtype" in args:
            gridtype_1, gridtype_2 = args.get("gridtype_1", ""), args.get("gridtype_2", "")
            if gridtype_1 == "on" and gridtype_2 == "on":
                pass
            elif gridtype_1 == "on":
                self.grid_type = GRIDTYPE_1
            elif gridtype_2 == "on":
                self.grid_type = GRIDTYPE_2
            else:
                raise InvalidArgumentsError("gridtype_1 or gridtype_2 or both must be \"on\"")

    def populate_service_hidden_filter_from_args(self, args):
        if "service_hidden_value" in args:  # note no "service_hidden" args
            if args["service_hidden_value"] == "0":
                self.service_hidden = False
            elif args["service_hidden_value"] == "1":
                self.service_hidden = True
            else:
                raise InvalidArgumentsError("service_hidden_value must be 0 or 1")

    def populate_past_days_from_args(self, args):
        if "downtime_attrs_showpast" in args:
            # doesn't make sense for rgsummary but will be ignored anyway
            try:
                v = args["downtime_attrs_showpast"]
                if v == "all":
                    self.past_days = -1
                elif not v:
                    self.past_days = 0
                else:
                    self.past_days = int(args["downtime_attrs_showpast"])
            except ValueError:
                raise InvalidArgumentsError("downtime_attrs_showpast must be an integer, \"\", or \"all\"")

    def populate_has_wlcg_from_args(self, args):
        if "has_wlcg" in args:
            self.has_wlcg = True

    def populate_voown_name(self, vo_id_to_name: Dict):
        self.voown_name.extend([vo_id_to_name.get(i, "") for i in self.voown_id])


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


def ensure_list(x: Union[None, T, List[T]]) -> List[T]:
    if isinstance(x, list):
        return x
    elif x is None:
        return []
    return [x]


def simplify_attr_list(data: Union[Dict, List], namekey: str, del_name: bool = True) -> Dict:
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
        if del_name:
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


def safe_dict_get(item, *keys, default=None):
    """ traverse dict hierarchy without producing KeyErrors:
        safe_dict_get(item, key1, key2, ..., default=default)
        -> item[key1][key2][...] if defined and not None, else default
    """
    for key in keys:
        if isinstance(item, dict):
            item = item.get(key)
        else:
            return default
    return default if item is None else item


def order_dict(value: Dict, ordering: List, ignore_missing=False) -> OrderedDict:
    """
    Convert a dict to an OrderedDict with key order provided by ``ordering``.
    """
    new_value = OrderedDict()
    for elem in ordering:
        if elem in value:
            new_value[elem] = value[elem]
        elif not ignore_missing:
            new_value[elem] = None
    return new_value


def to_xml(data) -> str:
    return xmltodict.unparse(data, pretty=True, encoding="utf-8")


def to_xml_bytes(data) -> bytes:
    return to_xml(data).encode("utf-8", errors="replace")


# bytes cannot be encoded to json in python3
def bytes2str(o):
    if isinstance(o, (list, tuple)):
        return type(o)(map(bytes2str, o))
    elif isinstance(o, dict):
        return dict(map(bytes2str, o.items()))
    elif isinstance(o, bytes):
        return o.decode(errors='ignore')
    else:
        return o


def to_json(data: PreJSON) -> str:
    return json.dumps(bytes2str(data), sort_keys=True)


def to_json_bytes(data: PreJSON) -> bytes:
    return to_json(data).encode("utf-8", errors="replace")


def trim_space(s: str) -> str:
    """Remove leading and trailing whitespace but not newlines"""
    # leading and trailing whitespace causes "\n"'s in the resulting string
    ret = re.sub(r"(?m)[ \t]+$", "", s)
    ret = re.sub(r"(?m)^[ \t]+", "", ret)
    return ret


def run_git_cmd(cmd: List, dir=None, git_dir=None, ssh_key=None) -> bool:
    """
    Run git command, optionally specifying ssh key and/or git dirs

    Options:

        dir       path to git work-tree, if not current directory
        git_dir   path to git-dir, if not .git subdir of work-tree
        ssh_key   path to ssh public key identity file, if any

    For a bare git repo, specify `git_dir` but not `dir`.
    """
    if ssh_key and not os.path.exists(ssh_key):
        log.critical("ssh key not found at %s: unable to update secure repo",
                     ssh_key)
        return False
    base_cmd = ["git"]
    if dir:
        base_cmd += ["--work-tree", dir]
        if git_dir is None:
            git_dir = os.path.join(dir, ".git")
    if git_dir:
        base_cmd += ["--git-dir", git_dir]

    full_cmd = base_cmd + cmd

    env = None
    if ssh_key:
        env = dict(os.environ)
        env['GIT_SSH_KEY_FILE'] = ssh_key
        env['GIT_SSH'] = SSH_WITH_KEY

    git_result = subprocess.run(full_cmd, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
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

def git_clone_or_fetch_mirror(repo, git_dir, ssh_key=None) -> bool:
    if os.path.exists(git_dir):
        ok = run_git_cmd(["fetch", "origin"], git_dir=git_dir, ssh_key=ssh_key)
    else:
        ok = run_git_cmd(["clone", "--mirror", repo, git_dir], ssh_key=ssh_key)
        # disable mirror push
        ok = ok and run_git_cmd(["config", "--unset", "remote.origin.mirror"],
                                                              git_dir=git_dir)
    return ok


def gen_id(instr: AnyStr, digits, minimum=1, hashfn=hashlib.md5) -> int:
    instr_b = instr if isinstance(instr, bytes) else instr.encode("utf-8", "surrogateescape")
    mod = (10 ** digits) - minimum
    return minimum + (int(hashfn(instr_b).hexdigest(), 16) % mod)


def load_yaml_file(filename) -> ParsedYaml:
    """Load a yaml file (wrapper around yaml.safe_load() because it does not
    report the filename in which an error occurred.

    """
    try:
        with open(filename, encoding='utf-8', errors='surrogateescape') as stream:
            return yaml.load(stream, Loader=SafeLoader)
    except yaml.YAMLError as e:
        log.error("YAML error in %s: %s", filename, e)
        raise


def readfile(path, logger):
    """ return stripped file contents, or None on errors """
    if path:
        try:
            with open(path, mode="rb") as f:
                return f.read().strip()
        except IOError as e:
            if logger:
                logger.error("Failed to read file '%s': %s", path, e)
            return None


def escape(pattern: str) -> str:
    """Escapes regex characters that stopped being escaped in python 3.7"""

    escaped_string = re.escape(pattern)

    if sys.version_info < (3, 7):
        return escaped_string

    unescaped_characters = ['!', '"', '%', "'", ',', '/', ':', ';', '<', '=', '>', '@', "`"]
    for unescaped_character in unescaped_characters:

        escaped_string = re.sub(unescaped_character, f"\\{unescaped_character}", escaped_string)

    return escaped_string


def support_cors(f):

    @wraps(f)
    def wrapped():

        response = f()

        response.headers['Access-Control-Allow-Origin'] = '*'

        return response

    return wrapped


XROOTD_CACHE_SERVER = "XRootD cache server"
XROOTD_ORIGIN_SERVER = "XRootD origin server"
