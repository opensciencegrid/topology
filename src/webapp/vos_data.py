import copy

from collections import OrderedDict
from logging import getLogger
from typing import Dict, List, Optional, Set, Tuple, Union

from .common import Filters, ParsedYaml, VOSUMMARY_SCHEMA_URL, is_null, expand_attr_list, order_dict, escape, \
    generate_dn_hash
from .contacts_reader import ContactsData

log = getLogger(__name__)


ANY = "ANY"
PUBLIC = "PUBLIC"
ANY_PUBLIC = "ANY_PUBLIC"
XROOTD_CACHE_SERVER = "XRootD cache server"
XROOTD_ORIGIN_SERVER = "XRootD origin server"


def log_or_raise(suppress_errors: bool, an_exception: BaseException, logmethod=log.debug):
    if suppress_errors:
        logmethod("%s %s", type(an_exception), an_exception)
    else:
        raise an_exception


class VOsData(object):
    def __init__(self, contacts_data: ContactsData, reporting_groups_data: ParsedYaml):
        self.contacts_data = contacts_data
        self.vos = {}  # type: Dict[str, ParsedYaml]
        self.reporting_groups_data = reporting_groups_data
        self.stashcache_by_vo_name = {}  # type: Dict[str, StashCache]

    def get_vo_id_to_name(self) -> Dict[str, str]:
        return {self.vos[name]["ID"]: name for name in self.vos}

    def add_vo(self, vo_name: str, vo_data: ParsedYaml):
        self.vos[vo_name] = vo_data
        stashcache_data = vo_data.get('DataFederations', {}).get('StashCache')
        if stashcache_data:
            stashcache_obj = StashCache(vo_name, stashcache_data)
            if stashcache_obj.errors:
                log.exception("Problem(s) with DataFederations/StashCache data for VO %s: %s",
                              vo_name, "\n".join(stashcache_obj.errors))
            else:
                self.stashcache_by_vo_name[vo_name] = stashcache_obj

    def get_expansion(self, authorized=False, filters: Filters = None):
        if not filters:
            filters = Filters()
        expanded_vo_list = []
        for vo_name, vo_data in sorted(self.vos.items(), key=lambda x: x[0].lower()):
            try:
                expanded_vo_data = self._expand_vo(vo_name, authorized=authorized, filters=filters)

                # Add the regex pattern from the scitokens mapfile
                if not is_null(vo_data, "Credentials", "TokenIssuers"):
                    for index, token_issuer in enumerate(vo_data["Credentials"]["TokenIssuers"]):
                        url = token_issuer.get("URL")
                        subject = token_issuer.get("Subject", "")
                        pattern = ""
                        if url:
                            if subject:
                                pattern = f'/^{escape(url)},{escape(subject)}$/'
                            else:
                                pattern = f'/^{escape(url)},/'

                        if pattern:
                            expanded_vo_data["Credentials"]["TokenIssuers"]["TokenIssuer"][index]['Pattern'] = pattern

                if expanded_vo_data:
                    expanded_vo_list.append(expanded_vo_data)

            except (KeyError, ValueError, AttributeError) as err:
                log.exception("Problem with VO data for %s: %s", vo_name, err)

        return expanded_vo_list

    def get_tree(self, authorized=False, filters: Filters = None) -> Dict:
        if not filters:
            filters = Filters()
        expanded_vo_list = []
        for vo_name in sorted(self.vos.keys(), key=lambda x: x.lower()):
            try:
                expanded_vo_data = self._expand_vo(vo_name, authorized=authorized, filters=filters)
                if expanded_vo_data:
                    if 'DataFederations' in expanded_vo_data:
                        del expanded_vo_data['DataFederations']
                    expanded_vo_list.append(expanded_vo_data)
            except (KeyError, ValueError, AttributeError) as err:
                log.exception("Problem with VO data for %s: %s", vo_name, err)

        return {"VOSummary": {
            "@xmlns:xsi": "http://www.w3.org/2001/XMLSchema-instance",
            "@xsi:schemaLocation": VOSUMMARY_SCHEMA_URL,
            "VO": expanded_vo_list}}

    def _expand_vo(self, name: str, authorized: bool, filters: Filters) -> Optional[OrderedDict]:
        # Restore ordering
        new_vo = OrderedDict.fromkeys(["ID", "Name", "LongName", "CertificateOnly", "PrimaryURL",
                                       "MembershipServicesURL", "PurposeURL", "SupportURL", "AppDescription",
                                       "Community", "FieldsOfScience", "ParentVO", "ReportingGroups", "Active",
                                       "Disable", "ContactTypes", "OASIS", "Credentials"])
        new_vo.update({
            "Disable": False,
            "Active": True,
        })
        vo = self.vos[name]
        new_vo.update(vo)

        if filters.active is not None and filters.active != new_vo["Active"]:
            return
        if filters.disable is not None and filters.disable != new_vo["Disable"]:
            return
        if filters.oasis is not None and (is_null(vo, "OASIS", "UseOASIS") or
                                          filters.oasis != vo["OASIS"]["UseOASIS"]):
            return
        if filters.vo_id and vo["ID"] not in filters.vo_id:
            return

        new_vo["Name"] = name

        if not is_null(vo, "Contacts"):
            new_vo["ContactTypes"] = self._expand_contacttypes(vo["Contacts"], authorized)
        new_vo.pop("Contacts", None)

        if not is_null(vo, "ReportingGroups"):
            new_vo["ReportingGroups"] = self._expand_reporting_groups(vo["ReportingGroups"], authorized)

        oasis = OrderedDict.fromkeys(["UseOASIS", "Managers", "OASISRepoURLs"])
        oasis["UseOASIS"] = vo.get("OASIS", {}).get("UseOASIS", False)
        if not is_null(vo, "OASIS", "Managers"):
            managers = vo["OASIS"]["Managers"]
            if isinstance(managers, dict):
                oasis["Managers"] = self._expand_oasis_legacy_managers(managers)
            else:
                oasis["Managers"] = self._expand_oasis_managers(managers)
        if not is_null(vo, "OASIS", "OASISRepoURLs"):
            oasis["OASISRepoURLs"] = {"URL": vo["OASIS"]["OASISRepoURLs"]}
        new_vo["OASIS"] = oasis

        if not is_null(vo, "FieldsOfScience"):
            new_vo["FieldsOfScience"] = self._expand_fields_of_science(vo["FieldsOfScience"])

        if not is_null(vo, "ParentVO"):
            parentvo = OrderedDict.fromkeys(["ID", "Name"])
            parentvo.update(vo["ParentVO"])
            new_vo["ParentVO"] = parentvo

        if not is_null(vo, "Credentials"):
            credentials = OrderedDict.fromkeys(["TokenIssuers"])
            if not is_null(vo, "Credentials", "TokenIssuers"):
                token_issuers = vo["Credentials"]["TokenIssuers"]
                new_token_issuers = [
                    OrderedDict([
                        ("URL", x.get("URL")),
                        ("DefaultUnixUser", x.get("DefaultUnixUser")),
                        ("Description", x.get("Description")),
                        ("Subject", x.get("Subject")),
                    ])
                    for x in token_issuers
                ]
                credentials["TokenIssuers"] = {"TokenIssuer": new_token_issuers}
            new_vo["Credentials"] = credentials

        return new_vo

    def _expand_contacttypes(self, vo_contacts: Dict, authorized: bool) -> Dict:
        new_contacttypes = []
        for type_, list_ in vo_contacts.items():
            contact_items = []
            for contact in list_:
                contact_id = contact["ID"]
                new_contact = OrderedDict([("Name", contact["Name"])])
                if self.contacts_data:
                    user = self.contacts_data.users_by_id.get(contact_id)
                    if user:
                        new_contact["CILogonID"] = user.cilogon_id
                        if authorized:
                            new_contact["Email"] = user.email
                            new_contact["Phone"] = user.phone
                            new_contact["SMSAddress"] = user.sms_address
                            dns = user.dns
                            if dns:
                                new_contact["DN"] = dns[0]
                    else:
                        log.warning("id %s not found for %s", contact_id, contact["Name"])
                contact_items.append(new_contact)
            new_contacttypes.append({"Type": type_, "Contacts": {"Contact": contact_items}})
        return {"ContactType": new_contacttypes}

    @staticmethod
    def _expand_fields_of_science(fields_of_science):
        """Turn
        {"PrimaryFields": ["P1", "P2", ...],
         "SecondaryFields": ["S1", "S2", ...]}
        into
        {"PrimaryFields": {"Field": ["P1", "P2", ...]},
         "SecondaryFields": {"Field": ["S1", "S2", ...]}}
        """
        if is_null(fields_of_science, "PrimaryFields"):
            return None
        new_fields = OrderedDict()
        new_fields["PrimaryFields"] = {"Field": fields_of_science["PrimaryFields"]}
        if not is_null(fields_of_science, "SecondaryFields"):
            new_fields["SecondaryFields"] = {"Field": fields_of_science["SecondaryFields"]}
        return new_fields

    def _expand_oasis_legacy_managers(self, managers):
        """Expand
        {"a": {"DNs": [...]}}
        into
        {"Manager": [{"Name": "a", "DNs": {"DN": [...]}}]}
        """
        new_managers = copy.deepcopy(managers)
        for name, data in managers.items():
            if not is_null(data, "DNs"):
                new_managers[name]["DNs"] = {"DN": data["DNs"]}
            else:
                new_managers[name]["DNs"] = None

            new_managers[name]["CILogonID"] = None
            if self.contacts_data:
                user = self.contacts_data.users_by_id.get(data["ID"])
                if user:
                    new_managers[name]["CILogonID"] = user.cilogon_id
        return {"Manager": expand_attr_list(new_managers, "Name", ordering=["Name", "CILogonID", "DNs"],
                                            ignore_missing=True)}

    def _expand_oasis_managers(self, managers):
        """Expand
        [{"Name", "a", "DNs": [...]}, ...]
        into
        {"Manager": [{"Name": "a", "DNs": {"DN": [...]}}, ...]}
        """
        new_managers = copy.deepcopy(managers)
        for i, data in enumerate(managers):
            if not is_null(data, "DNs"):
                new_managers[i]["DNs"] = {"DN": data["DNs"]}
            else:
                new_managers[i]["DNs"] = None
            new_managers[i]["CILogonID"] = None
            if self.contacts_data:
                user = self.contacts_data.users_by_id.get(data["ID"])
                if user:
                    new_managers[i]["CILogonID"] = user.cilogon_id

        def order_manager_dict(m):
            return order_dict(m, ordering=["Name", "CILogonID", "DNs"], ignore_missing=True)

        return {"Manager": list(map(order_manager_dict, new_managers))}

    def _expand_reporting_groups(self, reporting_groups_list: List, authorized: bool) -> Dict:
        new_reporting_groups = {}
        for name, data in self.reporting_groups_data.items():
            if name not in reporting_groups_list: continue
            new_reporting_groups[name] = {}
            newdata = new_reporting_groups[name]
            if not is_null(data, "Contacts"):
                new_contacts = []
                for contact in data["Contacts"]:
                    new_contact = OrderedDict([("Name", contact["Name"])])
                    if authorized and self.contacts_data:
                        if contact["ID"] in self.contacts_data.users_by_id:
                            extra_data = self.contacts_data.users_by_id[contact["ID"]]
                            new_contact["Email"] = extra_data.email
                            new_contact["Phone"] = extra_data.phone
                            new_contact["SMSAddress"] = extra_data.sms_address
                    new_contacts.append(new_contact)
                newdata["Contacts"] = {"Contact": new_contacts}
            else:
                newdata["Contacts"] = None
            if not is_null(data, "FQANs"):
                fqans = []
                for fqan in data["FQANs"]:
                    fqans.append(OrderedDict([("GroupName", fqan["GroupName"]), ("Role", fqan["Role"])]))
                newdata["FQANs"] = {"FQAN": fqans}
            else:
                newdata["FQANs"] = None
        new_reporting_groups = expand_attr_list(new_reporting_groups, "Name", ordering=["Name", "FQANs", "Contacts"])
        return {"ReportingGroup": new_reporting_groups}


class AuthMethod:
    is_public = False
    used_in_authfile = False
    used_in_scitokens_conf = False

    def get_authfile_id(self):
        return ""

    def get_scitokens_conf_block(self, service_name: str):
        return ""


class NullAuth(AuthMethod):
    pass


class PublicAuth(AuthMethod):
    is_public = True
    used_in_authfile = True

    def __str__(self):
        return "PUBLIC"

    def get_authfile_id(self):
        return "u *"


class DNAuth(AuthMethod):
    used_in_authfile = True

    def __init__(self, dn: str):
        self.dn = dn

    def __str__(self):
        return "DN: " + self.dn

    def get_dn_hash(self):
        return generate_dn_hash(self.dn)

    def get_authfile_id(self):
        return f"u {self.get_dn_hash()}"


class FQANAuth(AuthMethod):
    used_in_authfile = True

    def __init__(self, fqan: str):
        self.fqan = fqan

    def __str__(self):
        return "FQAN: " + self.fqan

    def get_authfile_id(self):
        return f"g {self.fqan}"


class SciTokenAuth(AuthMethod):
    used_in_scitokens_conf = True

    def __init__(self, issuer: str, base_path: str, restricted_path: Optional[str], map_subject: bool):
        self.issuer = issuer
        self.base_path = base_path
        self.restricted_path = restricted_path
        self.map_subject = map_subject

    def __str__(self):
        return f"SciToken: issuer={self.issuer} base_path={self.base_path} restricted_path={self.restricted_path} " \
                f"map_subject={self.map_subject}"

    def get_scitokens_conf_block(self, service_name: str):
        if service_name not in [XROOTD_CACHE_SERVER, XROOTD_ORIGIN_SERVER]:
            raise ValueError(f"service_name must be '{XROOTD_CACHE_SERVER}' or '{XROOTD_ORIGIN_SERVER}'")
        block = f"""\
[Issuer {self.issuer}]
issuer = {self.issuer}
base_path = {self.base_path}
"""
        if self.restricted_path:
            block += f"restricted_path = {self.restricted_path}\n"
        if service_name == XROOTD_ORIGIN_SERVER:
            block += f"map_subject = {self.map_subject}\n"

        return block


class Namespace:
    def __init__(self, path: str, vo_name: str, allowed_origins: List[str], allowed_caches: List[str],
                 authz_list: List[AuthMethod], writeback: Optional[str], dirlist: Optional[str],
                 map_subject: bool):
        self.path = path
        self.vo_name = vo_name
        self.allowed_origins = allowed_origins
        self.allowed_caches = allowed_caches
        self.authz_list = authz_list
        self.writeback = writeback
        self.dirlist = dirlist
        self.map_subject = map_subject

    def is_public(self) -> bool:
        return self.authz_list and self.authz_list[0].is_public


def parse_authz(authz: Union[str, Dict]) -> Tuple[AuthMethod, Optional[str]]:
    """Return the instance of the appropriate AuthMethod from an item in an authz list for a namespace"""
    # Note:
    # This is a string:
    # - FQAN:/foobar
    # This is a dict:
    # - FQAN: /foobar
    # Accept both.
    if isinstance(authz, dict):
        for k, v in authz.items():
            if k == "SciTokens":
                try:
                    return SciTokenAuth(
                        issuer=v["Issuer"],
                        base_path=v["Base Path"],
                        restricted_path=v.get("Restricted Path", None),
                        map_subject=v.get("Map Subject", False),
                    ), None
                except (KeyError, AttributeError):
                    return NullAuth(), f"Invalid authz list entry {authz}"
            elif k == "FQAN":
                return FQANAuth(fqan=v), None
            elif k == "DN":
                return DNAuth(dn=v), None
            else:
                return NullAuth(), f"Unknown auth type {k}"
    elif isinstance(authz, str):
        if authz.startswith("FQAN:"):
            return FQANAuth(fqan=authz[5:].strip()), None
        elif authz.startswith("DN:"):
            return DNAuth(dn=authz[3:].strip()), None
        elif authz.strip() == "PUBLIC":
            return PublicAuth(), None
        else:
            return NullAuth(), f"Unknown authz list entry {authz}"


class StashCache:
    def __init__(self, vo_name: str, yaml_data: ParsedYaml):
        self.vo_name = vo_name
        self.namespaces: OrderedDict[str, Namespace] = OrderedDict()
        self.load_yaml(yaml_data)
        self.errors: Set[str] = set()

    def load_yaml(self, yaml_data: ParsedYaml):
        if is_null(yaml_data, "Namespaces"):
            return

        # Check for old yaml data, where each Namespaces is a dict and each namespace is a plain list of authz
        if not isinstance(yaml_data["Namespaces"], list):
            return self.load_old_yaml(yaml_data)

        for idx, ns_data in enumerate(yaml_data["Namespaces"]):
            # New format; Namespaces is a list of dicts
            if "Path" not in ns_data:
                self.errors.add(f"Namespace #{idx}: No Path")
                continue
            path = ns_data["Path"]
            authz_list = self.parse_authz_list(path=path, unparsed_authz_list=ns_data.get("Authorizations", []))
            self.namespaces[path] = Namespace(
                path=path,
                vo_name=self.vo_name,
                allowed_origins=ns_data.get("AllowedOrigins", []),
                allowed_caches=ns_data.get("AllowedCaches", []),
                authz_list=authz_list,
                writeback=ns_data.get("Writeback", None),
                dirlist=ns_data.get("DirList", None),
                map_subject=ns_data.get("Map Subject", False)
            )

    def load_old_yaml(self, yaml_data: ParsedYaml):
        for path, unparsed_authz_list in yaml_data["Namespaces"].items():
            authz_list = self.parse_authz_list(path, unparsed_authz_list)
            self.namespaces[path] = Namespace(
                path=path,
                vo_name=self.vo_name,
                allowed_origins=yaml_data.get("AllowedOrigins", []),
                allowed_caches=yaml_data.get("AllowedCaches", []),
                authz_list=authz_list,
                writeback=None,
                dirlist=None,
                map_subject=False)

    def parse_authz_list(self, path: str, unparsed_authz_list: List[str]) -> List[AuthMethod]:
        authz_list = []
        for authz in unparsed_authz_list:
            parsed_authz, err = parse_authz(authz)
            if err:
                self.errors.add(f"Namespace {path}: {err}")
                continue
            print(f"Path: {path}, authz: {parsed_authz}")
            if parsed_authz.is_public:
                return [parsed_authz]
            else:
                authz_list.append(parsed_authz)
        return authz_list
