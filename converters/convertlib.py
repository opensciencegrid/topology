from collections import OrderedDict
from typing import Dict, List, Union

import anymarkup

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


def to_xml(data):
    return anymarkup.serialize(data, "xml").decode("utf-8")


def to_xml_file(data, outfile):
    return anymarkup.serialize_file(data, outfile, "xml")
