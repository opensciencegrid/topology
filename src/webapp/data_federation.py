import urllib
import urllib.parse
from collections import OrderedDict
from typing import Optional, List, Dict, Tuple, Union, Set

from .common import XROOTD_CACHE_SERVER, XROOTD_ORIGIN_SERVER, ParsedYaml, is_null
try:
    from .x509 import generate_dn_hash
except ImportError:  # if asn1 is unavailable
    generate_dn_hash = None


class AuthMethod:
    is_public = False
    used_in_authfile = False
    used_in_scitokens_conf = False
    used_in_grid_mapfile = False

    def get_authfile_id(self):
        return ""

    def get_scitokens_conf_block(self, service_name: str):
        return ""

    def get_grid_mapfile_line(self):
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
    used_in_grid_mapfile = True

    def __init__(self, dn: str):
        self.dn = dn

    def __str__(self):
        return "DN: " + self.dn

    def get_dn_hash(self):
        return generate_dn_hash(self.dn)

    def get_authfile_id(self):
        return f"u {self.get_dn_hash()}"

    def get_grid_mapfile_line(self):
        return f'"{self.dn}" {self.get_dn_hash()}'


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
        block = (f"[Issuer {self.issuer}]\n"
                 f"issuer = {self.issuer}\n"
                 f"base_path = {self.base_path}\n")
        if self.restricted_path:
            block += f"restricted_path = {self.restricted_path}\n"
        if service_name == XROOTD_ORIGIN_SERVER:
            block += f"map_subject = {self.map_subject}\n"

        return block


# TODO Use a dataclass (https://docs.python.org/3.9/library/dataclasses.html)
# once we can ditch Python 3.6; the webapp no longer supports 3.6 but some of
# the scripts (e.g. osg-scitokens-config) do.
class CredentialGeneration:
    """Class for storing the info of a CredentialGeneration block for a namespace.
    This is served up by the /osdf/namespaces endpoint.
    See https://opensciencegrid.atlassian.net/browse/SOFTWARE-5381 for details.

    """
    STRATEGY_VAULT = "Vault"
    STRATEGY_OAUTH2 = "OAuth2"
    STRATEGIES = [STRATEGY_OAUTH2, STRATEGY_VAULT]
    def __init__(self, strategy: str, issuer: str, max_scope_depth: Optional[int], vault_server: Optional[str], base_path: Optional[str], vault_issuer: Optional[str]):
        self.strategy = strategy
        self.issuer = issuer
        self.max_scope_depth = max_scope_depth
        self.vault_server = vault_server
        self.base_path = base_path
        self.vault_issuer = vault_issuer

    def __repr__(self):
        return self.__class__.__name__ + ("(strategy=%r, issuer=%r, base_path=%r, max_scope_depth=%r, vault_server=%r, vault_issuer=%r)" % (
            self.strategy, self.issuer, self.base_path, self.max_scope_depth, self.vault_server, self.vault_issuer
        ))

    def validate(self) -> Set[str]:
        """Return a set of error strings in the data."""
        errors = set()
        errprefix = "CredentialGeneration:"

        # Validate Strategy
        if self.strategy not in self.STRATEGIES:
            errors.add(f"{errprefix} invalid Strategy {self.strategy}")

        # Validate Issuer
        if not self.issuer:
            errors.add(f"{errprefix} Issuer not specified")
        elif not isinstance(self.issuer, str):
            errors.add(f"{errprefix} invalid Issuer {self.issuer}")
        else:
            parsed_issuer = urllib.parse.urlparse(self.issuer)
            if not parsed_issuer.netloc or parsed_issuer.scheme != "https":
                errors.add(f"{errprefix} Issuer not a valid URL {self.issuer}")

        # Validate BasePath
        if self.base_path and not isinstance(self.base_path, str):
            errors.add(f"{errprefix} invalid BasePath {self.base_path}")

        # Validate MaxScopeDepth
        if self.max_scope_depth:
            try:
                int(self.max_scope_depth)
            except TypeError:
                errors.add(f"{errprefix} invalid MaxScopeDepth (not an integer) {self.max_scope_depth}")
            else:
                if self.max_scope_depth < 0:
                    errors.add(f"{errprefix} negative MaxScopeDepth {self.max_scope_depth}")

        # Validate VaultServer
        if self.vault_server:
            if self.strategy != self.STRATEGY_VAULT:
                errors.add(f"{errprefix} VaultServer specified for a {self.strategy} strategy")
        else:
            if self.strategy == self.STRATEGY_VAULT:
                errors.add(f"{errprefix} VaultServer not specified for a {self.strategy} strategy")

        # Validate VaultIssuer
        if self.vault_issuer and self.strategy != self.STRATEGY_VAULT:
            errors.add(f"{errprefix} VaultIssuer specified for a {self.strategy} strategy")

        return errors


class Namespace:
    def __init__(
        self,
        path: str,
        vo_name: str,
        allowed_origins: List[str],
        allowed_caches: List[str],
        authz_list: List[AuthMethod],
        writeback: Optional[str],
        dirlist: Optional[str],
        credential_generation: Optional[CredentialGeneration],
    ):
        self.path = path
        self.vo_name = vo_name
        self.allowed_origins = allowed_origins
        self.allowed_caches = allowed_caches
        self.authz_list = authz_list
        self.writeback = writeback
        self.dirlist = dirlist
        self.credential_generation = credential_generation

    def is_public(self) -> bool:
        return self.authz_list and self.authz_list[0].is_public


def _parse_authz_scitokens(attributes: Dict, authz: Dict) -> Tuple[AuthMethod, Optional[str]]:
    """Parse a SciTokens dict in an authz list for a namespace.  On success, return a SciTokenAuth instance and None;
    on failure, return a NullAuth instance and a string indicating the error.
    """
    errors = ""
    issuer = attributes.get("Issuer")
    if not issuer:
        errors += "'Issuer' missing or empty; "
    base_path = attributes.get("BasePath", attributes.get("Base Path"))
    if not base_path:
        errors += "'BasePath' missing or empty; "
    restricted_path = attributes.get("RestrictedPath", attributes.get("Restricted Path", None))
    if restricted_path and not isinstance(restricted_path, str):
        errors += "'RestrictedPath' not a string; "
    map_subject = attributes.get("MapSubject", attributes.get("Map Subject", False))
    if not isinstance(map_subject, bool):
        errors += "'MapSubject' not a boolean; "
    if errors:
        errors = errors[:-2]  # chop off last '; '
        return NullAuth(), f"Invalid SciTokens auth {authz}: {errors}"
    return SciTokenAuth(
        issuer=issuer,
        base_path=base_path,
        restricted_path=restricted_path,
        map_subject=map_subject
    ), None


def _parse_authz_dict(authz: Dict) -> Tuple[AuthMethod, Optional[str]]:
    """Return the instance of the appropriate AuthMethod from a single item of dict type in an authz list.
    An authz list item can be a dict for FQAN, DN, or SciTokens.

    We are expecting only one element in this dict: the key indicates the authorization type,
    and the value is the contents.

    On success, return the appropriate AuthMethod and None; on failure, return a NullAuth and a string describing the error.
    """

    for auth_type, attributes in authz.items():
        if auth_type == "SciTokens":
            if not isinstance(attributes, dict) or not attributes:
                return NullAuth(), f"Invalid SciTokens auth {authz}: no attributes"
            return _parse_authz_scitokens(attributes=attributes, authz=authz)
        elif auth_type == "FQAN":
            if not attributes:
                return NullAuth(), f"Invalid FQAN auth {authz}: FQAN missing or empty"
            return FQANAuth(fqan=attributes), None
        elif auth_type == "DN":
            if generate_dn_hash is None:
                return NullAuth(), f"'asn1' library unavailable; cannot handle DN auth {authz}"
            if not attributes:
                return NullAuth(), f"Invalid DN auth {authz}: DN missing or empty"
            return DNAuth(dn=attributes), None
        else:
            return NullAuth(), f"Unknown auth type {auth_type} in {authz}"


def _parse_authz_str(authz: str) -> Tuple[AuthMethod, Optional[str]]:
    """Return the instance of the appropriate AuthMethod from a single item of string type in an authz list.
    An authz list item can be a string for FQAN and DN auth only, or PUBLIC.

    On success, return the appropriate AuthMethod and None; on failure, return a NullAuth and a string describing the error.
    """
    if authz.startswith("FQAN:"):
        fqan = authz[5:].strip()
        if not fqan:
            return NullAuth(), f"Invalid FQAN auth {authz}: FQAN missing or empty"
        return FQANAuth(fqan=fqan), None
    elif authz.startswith("DN:"):
        if generate_dn_hash is None:
            return NullAuth(), f"'asn1' library unavailable; cannot handle DN auth {authz}"
        dn = authz[3:].strip()
        if not dn:
            return NullAuth(), f"Invalid DN auth {authz}: DN missing or empty"
        return DNAuth(dn=dn), None
    elif authz.strip() == "PUBLIC":
        return PublicAuth(), None
    else:
        return NullAuth(), f"Unknown authz list entry {authz}"


def parse_authz(authz: Union[str, Dict]) -> Tuple[AuthMethod, Optional[str]]:
    """Return the instance of the appropriate AuthMethod from a single item in an authz list for a namespace.

    An authz list item can be a string (for FQAN or DN auth) or dict (FQAN, DN, or SciTokens auth).
    Return a tuple with the AuthMethod and an optional error string; if there is an error, the auth method is a NullAuth
    and the error string contains a description of the error.  If there is no error, the error string is None.
    """
    # YAML note:
    # This is a string:
    # - FQAN:/foobar
    # This is a dict:
    # - FQAN: /foobar
    # Accept both.
    if isinstance(authz, dict):
        return _parse_authz_dict(authz)
    elif isinstance(authz, str):
        return _parse_authz_str(authz)
    else:
        return NullAuth(), f"Unknown authz list entry {authz}"


class StashCache:
    def __init__(self, vo_name: str, yaml_data: ParsedYaml):
        self.vo_name = vo_name
        self.namespaces: OrderedDict[str, Namespace] = OrderedDict()
        self.errors: Set[str] = set()
        self.load_yaml(yaml_data)

    def load_yaml(self, yaml_data: ParsedYaml):
        if is_null(yaml_data, "Namespaces"):
            return

        # Handle both old format and new format for Namespaces
        if isinstance(yaml_data["Namespaces"], list):
            return self.load_new_yaml(yaml_data)
        else:
            return self.load_old_yaml(yaml_data)

    def load_new_yaml(self, yaml_data: ParsedYaml):
        """Load new format Namespaces info:

        Namespaces is a list of dicts; AllowedOrigins and AllowedCaches are elements of each dict.
        """
        for idx, ns_data in enumerate(yaml_data["Namespaces"]):
            if "Path" not in ns_data:
                self.errors.add(f"Namespace #{idx}: No Path")
                continue

            path = ns_data["Path"]
            if path in self.namespaces:
                orig_vo_name = self.namespaces[path].vo_name
                self.errors.add(f"Namespace #{idx}: Redefining {path}; original was defined in {orig_vo_name}")
                continue

            authz_list = self.parse_authz_list(path=path, unparsed_authz_list=ns_data.get("Authorizations", []))

            credential_generation = None
            if "CredentialGeneration" in ns_data:
                cg = ns_data["CredentialGeneration"]
                credential_generation = CredentialGeneration(
                    strategy=cg.get("Strategy", ""),
                    issuer=cg.get("Issuer", ""),
                    max_scope_depth=cg.get("MaxScopeDepth", None),
                    vault_server=cg.get("VaultServer", None),
                    base_path=cg.get("BasePath", None),
                    vault_issuer=cg.get("VaultIssuer", None),
                )
                cg_errors = credential_generation.validate()
                if cg_errors:
                    self.errors += {f"Namespace {path}: {e}" for e in cg_errors}
                    continue

            self.namespaces[path] = Namespace(
                path=path,
                vo_name=self.vo_name,
                allowed_origins=ns_data.get("AllowedOrigins", []),
                allowed_caches=ns_data.get("AllowedCaches", []),
                authz_list=authz_list,
                writeback=ns_data.get("Writeback", None),
                dirlist=ns_data.get("DirList", None),
                credential_generation=credential_generation,
            )

    def load_old_yaml(self, yaml_data: ParsedYaml):
        """Load old format Namespaces/AllowedOrigins/AllowedCaches info:

        Namespaces is a dict, and there are also AllowedOrigins and AllowedCaches lists at the same level.
        """
        for path, unparsed_authz_list in yaml_data["Namespaces"].items():
            authz_list = self.parse_authz_list(path, unparsed_authz_list)
            if path in self.namespaces:
                orig_vo_name = self.namespaces[path].vo_name
                self.errors.add(f"Redefining {path}; original was defined in {orig_vo_name}")
                continue
            self.namespaces[path] = Namespace(
                path=path,
                vo_name=self.vo_name,
                allowed_origins=yaml_data.get("AllowedOrigins", []),
                allowed_caches=yaml_data.get("AllowedCaches", []),
                authz_list=authz_list,
                writeback=None,
                dirlist=None,
                credential_generation=None,
            )

    def parse_authz_list(self, path: str, unparsed_authz_list: List[Union[str, Dict]]) -> List[AuthMethod]:
        authz_list = []
        for authz in unparsed_authz_list:
            parsed_authz, err = parse_authz(authz)
            if err:
                self.errors.add(f"Namespace {path}: {err}")
                continue
            if parsed_authz.is_public:
                return [parsed_authz]
            else:
                authz_list.append(parsed_authz)
        return authz_list
