import copy
from collections import defaultdict, OrderedDict
from typing import Dict, List, Optional, Set, Tuple, Union
import re
import sys
import ldap3
import asn1
import hashlib

from webapp.common import is_null, readfile
from webapp.models import GlobalData
from webapp.topology import Resource, ResourceGroup
from webapp.vos_data import VOsData

import logging


ANY = "ANY"
PUBLIC = "PUBLIC"
ANY_PUBLIC = "ANY_PUBLIC"

XROOTD_CACHE_SERVER = "XRootD cache server"
XROOTD_ORIGIN_SERVER = "XRootD origin server"

log = logging.getLogger(__name__)

__oid_map = {
   "DC": "0.9.2342.19200300.100.1.25",
   "OU": "2.5.4.11",
   "CN": "2.5.4.3",
   "O": "2.5.4.10",
   "ST": "2.5.4.8",
   "C": "2.5.4.6",
   "L": "2.5.4.7",
   "postalCode": "2.5.4.17",
   "street": "2.5.4.9",
   "emailAddress": "1.2.840.113549.1.9.1",
   }


__dn_split_re = re.compile("/([A-Za-z]+)=")


def log_or_raise(suppress_errors: bool, an_exception: BaseException, logmethod=log.debug):
    if suppress_errors:
        logmethod("%s %s", type(an_exception), an_exception)
    else:
        raise an_exception


class DataError(Exception):
    """Raised when there is a problem in the topology or VO data"""


class VODataError(DataError):
    def __init__(self, vo_name, text):
        DataError.__init__(self, f"VO {vo_name}: {text}")
        self.vo_name = vo_name


class NotRegistered(Exception):
    """Raised when the FQDN is not registered at all"""


class AuthMethod:
    def is_public(self):
        return False

    def used_in_authfile(self):
        return False

    def used_in_scitokens_conf(self):
        return False

    def authfile_id(self):
        return ""

    def scitokens_conf_block(self):
        return ""


class PublicAuth(AuthMethod):
    def __str__(self):
        return "PUBLIC"

    def is_public(self):
        return True

    def used_in_authfile(self):
        return True

    def authfile_id(self):
        return "u *"


class DNAuth(AuthMethod):
    def __init__(self, dn: str):
        self.dn = dn

    def __str__(self):
        return "DN: " + self.dn

    def used_in_authfile(self):
        return True

    def dn_hash(self):
        return _generate_dn_hash(self.dn)

    def authfile_id(self):
        return f"u {self.dn_hash()}"


class FQANAuth(AuthMethod):
    def __init__(self, fqan: str):
        self.fqan = fqan

    def __str__(self):
        return "FQAN: " + self.fqan

    def used_in_authfile(self):
        return True

    def authfile_id(self):
        return f"g {self.fqan}"


class SciTokenAuth(AuthMethod):
    def __init__(self, issuer: str, base_path: str, restricted_path: Optional[str] = None):
        self.issuer = issuer
        self.base_path = base_path
        self.restricted_path = restricted_path

    def __str__(self):
        return f"SciToken: issuer={self.issuer} base_path={self.base_path} restricted_path={self.restricted_path}"

    def used_in_scitokens_conf(self):
        return True

    def scitokens_conf_block(self):
        block = f"""\
[Issuer {self.issuer}]
issuer = {self.issuer}
base_path = {self.base_path}
"""
        if self.restricted_path:
            block += f"restricted_path = {self.restricted_path}\n"

        return block


class Namespace:
    def __init__(self, path: str, vo_name: str, origins: List[str] = None, caches: List[str] = None,
                 authz_list: List[AuthMethod] = None, writeback: Optional[str] = None, dirlist: Optional[str] = None,
                 map_subject=False):
        self.path = path
        self.vo_name = vo_name
        self.origins = origins or []
        self.caches = caches or []
        self.authz_list = authz_list or []
        self.writeback = writeback
        self.dirlist = dirlist
        self.map_subject = map_subject

    def is_public(self) -> bool:
        return self.authz_list and self.authz_list[0].is_public()


def parse_authz(authz: Union[str, Dict]) -> AuthMethod:
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
                        restricted_path=v.get("Restricted Path", None)
                    )
                except (KeyError, AttributeError):
                    raise DataError(f"Invalid authz list entry {authz}")
            elif k == "FQAN":
                return FQANAuth(fqan=v)
            elif k == "DN":
                return DNAuth(dn=v)
            else:
                raise DataError(f"Unknown auth type {k}")
    elif isinstance(authz, str):
        if authz.startswith("FQAN:"):
            return FQANAuth(fqan=authz[5:].strip())
        elif authz.startswith("DN:"):
            return DNAuth(dn=authz[3:].strip())
        elif authz.strip() == "PUBLIC":
            return PublicAuth()
        else:
            raise DataError(f"Unknown authz list entry {authz}")


# TODO EC
class StashCache:
    def __init__(self, vo_name: str, yaml_data: Dict, suppress_errors: bool = True):
        self.vo_name = vo_name
        self.namespaces: OrderedDict[str, Namespace] = OrderedDict()
        self.load_yaml(yaml_data, suppress_errors)

    def load_yaml(self, yaml_data: Dict, suppress_errors: bool):
        if is_null(yaml_data, "Namespaces"):
            return

        # Check for old yaml data, where each Namespaces is a dict and each namespace is a plain list of authz
        if not isinstance(yaml_data["Namespaces"], list):
            return self.load_old_yaml(yaml_data, suppress_errors)

        for idx, ns_data in enumerate(yaml_data["Namespaces"]):
            # New format; Namespaces is a list of dicts
            if "Path" not in ns_data:
                log_or_raise(suppress_errors, VODataError(vo_name=self.vo_name, text=f"Namespace #{idx}: No Path"))
            path = ns_data["Path"]
            authz_list = self.parse_authz_list(
                path=path,
                unparsed_authz_list=ns_data.get("Authorizations", []),
                suppress_errors=suppress_errors
            )
            self.namespaces[path] = Namespace(
                path=path,
                vo_name=self.vo_name,
                origins=ns_data.get("AllowedOrigins", []),
                caches=ns_data.get("AllowedCaches", []),
                authz_list=authz_list,
                writeback=ns_data.get("Writeback", None),
                dirlist=ns_data.get("DirList", None),
                map_subject=ns_data.get("MapSubject", False)
            )

    def load_old_yaml(self, yaml_data: Dict, suppress_errors: bool):
        origins = yaml_data.get("AllowedOrigins", [])
        caches = yaml_data.get("AllowedCaches", [])
        writeback = None
        dirlist = None
        map_subject = False
        for path, unparsed_authz_list in yaml_data["Namespaces"].items():
            authz_list = self.parse_authz_list(path, unparsed_authz_list, suppress_errors)
            # log.debug(f"Creating Namespace({path}, {self.vo_name}, {origins}, {caches}, {authz_list}, {writeback}, {dirlist}, {map_subject})")
            self.namespaces[path] = Namespace(path, self.vo_name, origins, caches, authz_list, writeback, dirlist, map_subject)

    def parse_authz_list(self, path: str, unparsed_authz_list: List[str], suppress_errors) -> List[AuthMethod]:
        authz_list = []
        for authz in unparsed_authz_list:
            try:
                parsed_authz = parse_authz(authz)
            except DataError as err:
                new_err = VODataError(vo_name=self.vo_name, text=f"Namespace {path}: {err}")
                log_or_raise(suppress_errors, new_err)
                continue
            if parsed_authz.is_public():
                return [parsed_authz]
            else:
                authz_list.append(parsed_authz)
        return authz_list


def _generate_ligo_dns(ldapurl: str, ldapuser: str, ldappass: str) -> List[str]:
    """
    Query the LIGO LDAP server for all grid DNs in the IGWN collab.

    Returns a list of DNs.
    """
    results = []
    base_branch = "ou={group},dc=ligo,dc=org"
    base_query = "(&(isMemberOf=Communities:{community})(gridX509subject=*))"
    queries = {'people': base_query.format(community="LSCVirgoLIGOGroupMembers"),
               'robot': base_query.format(community="robot:OSGRobotCert")}

    try:
        server = ldap3.Server(ldapurl, connect_timeout=10)
        conn = ldap3.Connection(server, user=ldapuser, password=ldappass, raise_exceptions=True, receive_timeout=10)
        conn.bind()
    except ldap3.core.exceptions.LDAPException:
        log.exception("Failed to connect to the LIGO LDAP")
        return results

    for group in ('people', 'robot'):
        try:
            conn.search(base_branch.format(group=group),
                        queries[group],
                        search_scope='SUBTREE',
                        attributes=['gridX509subject'])
            results += [dn for e in conn.entries for dn in e.gridX509subject]
        except ldap3.core.exceptions.LDAPException:
            log.exception("Failed to query LIGO LDAP for %s DNs", group)

    conn.unbind()

    return results


def _generate_dn_hash(dn: str) -> str:
    """
    Given a DN one-liner as commonly encoded in the grid world
    (e.g., output of `openssl x509 -in $FILE -noout -subject`), run
    the OpenSSL subject hash generation algorithm.

    This is done by calculating the SHA-1 sum of the canonical form of the
    X509 certificate's subject.  Formatting is a bit like this:

    SEQUENCE:
       SET:
         SEQUENCE:
           OID
           UTF8String

    All the UTF-8 values should be converted to lower-case and multiple
    spaces should be replaced with a single space.  That is, "Foo  Bar"
    should be substituted with "foo bar" for the canonical form.
    """
    encoder = asn1.Encoder()
    encoder.start()
    info = __dn_split_re.split(dn)[1:]
    for attr, val in zip(info[0::2], info[1::2]):
        oid = __oid_map.get(attr)
        if not oid:
            raise ValueError("OID for attribute {} is not known.".format(attr))
        encoder.enter(0x11)
        encoder.enter(0x10)
        encoder.write(oid, 0x06)
        encoder.write(val.lower().encode("utf-8"), 0x0c)
        encoder.leave()
        encoder.leave()
    output = encoder.output()
    hash_obj = hashlib.sha1()
    hash_obj.update(output)
    digest = hash_obj.digest()
    int_summary = digest[0] | digest[1] << 8 | digest[2] << 16 | digest[3] << 24
    return "%08lx.0" % int_summary


def _get_resource_by_fqdn(fqdn: str, resource_groups: List[ResourceGroup]) -> Optional[Resource]:
    """Returns the Resource that has the given FQDN; if multiple Resources
    have the same FQDN, returns the first one.

    """
    for group in resource_groups:
        for resource in group.resources:
            if fqdn.lower() == resource.fqdn.lower():
                return resource
    return None


def _resource_has_cache(resource: Resource) -> bool:
    return XROOTD_CACHE_SERVER in resource.service_names


def _resource_has_origin(resource: Resource) -> bool:
    return XROOTD_ORIGIN_SERVER in resource.service_names


def _get_resource_with_service(
        fqdn: Optional[str], service_name: str, resource_groups: List[ResourceGroup], suppress_errors: bool
) -> Optional[Resource]:
    """If given an FQDN, returns the Resource _if it has the given service.
    If given None, returns None.
    If multiple Resources have the same FQDN, checks the first one.
    If suppress_errors is False, raises an expression on the following conditions:
    - no Resource matching FQDN (NotRegistered)
    - Resource does not provide a SERVICE_NAME (DataError)
    If suppress_errors is True, returns None on the above conditions.

    """
    resource = None
    if fqdn:
        resource = _get_resource_by_fqdn(fqdn, resource_groups)
        if not resource:
            log_or_raise(suppress_errors, NotRegistered(fqdn))
            return None
        if service_name not in resource.service_names:
            log_or_raise(
                suppress_errors,
                DataError(f"{fqdn} (resource name {resource.name}) does not provide an {service_name}.")
            )
            return None
    return resource


def _get_cache_resource(fqdn: Optional[str], resource_groups: List[ResourceGroup], suppress_errors: bool) -> Optional[Resource]:
    return _get_resource_with_service(fqdn, XROOTD_CACHE_SERVER, resource_groups, suppress_errors)


def _get_origin_resource(fqdn: Optional[str], resource_groups: List[ResourceGroup], suppress_errors: bool) -> Optional[Resource]:
    return _get_resource_with_service(fqdn, XROOTD_ORIGIN_SERVER, resource_groups, suppress_errors)


def _cache_is_allowed(resource, vo_name, stashcache_data, public, suppress_errors):
    allowed_vos = resource.data.get("AllowedVOs")
    if allowed_vos is None:
        if suppress_errors:
            return False
        else:
            raise DataError("Cache server at {} (resource name {}) does not provide an AllowedVOs list.".format(resource.fqdn, resource.name))

    if ('ANY' not in allowed_vos and
            vo_name not in allowed_vos and
            (not public or 'ANY_PUBLIC' not in allowed_vos)):
        log.debug(f"\tCache {resource.fqdn} does not allow {vo_name} in its AllowedVOs list")
        return False

    # For public data, caching is one-way: we OK things as long as the
    # cache is interested in the data.
    if public:
        return True

    allowed_caches = stashcache_data.get("AllowedCaches")
    if allowed_caches is None:
        if suppress_errors:
            return False
        else:
            raise DataError("VO {} in StashCache does not provide an AllowedCaches list.".format(vo_name))

    ret = 'ANY' in allowed_caches or resource.name in allowed_caches
    if not ret:
        log.debug(f"\tVO {vo_name} does not allow cache {resource.fqdn} in its AllowedCaches list")
    return ret


def _resource_allows_namespace(resource: Optional[Resource], namespace: Optional[Namespace]) -> bool:
    if not resource:
        # Treat a missing resource as one without restrictions
        return True
    allowed_vos = resource.data.get("AllowedVOs", [])
    if ANY in allowed_vos:
        return True
    if namespace:
        if ANY_PUBLIC in allowed_vos and namespace.is_public():
            return True
        elif namespace.vo_name in allowed_vos:
            return True
    return False


def _namespace_allows_origin(namespace: Namespace, origin: Optional[Resource]) -> bool:
    return origin and origin.name in namespace.origins


def _namespace_allows_cache(namespace: Namespace, cache: Optional[Resource]) -> bool:
    if ANY in namespace.caches:
        return True
    return cache and cache.name in namespace.caches


def _get_allowed_caches_for_namespace(
        namespace: Namespace, resource_groups: List[ResourceGroup], suppress_errors=True
) -> List[Resource]:
    resources = []
    for group in resource_groups:
        for resource in group.resources:
            if not _resource_has_cache(resource):
                continue

            if not _resource_allows_namespace(resource, namespace):
                continue

            if not _namespace_allows_cache(namespace, resource):
                continue

            resources.append(resource)
    return resources


def generate_cache_authfile2(
        cache_fqdn: Optional[str], global_data: GlobalData, suppress_errors=True, public=False, legacy=True
) -> str:
    resource_groups: List[ResourceGroup] = global_data.get_topology().get_resource_group_list()
    vos_data = global_data.get_vos_data()
    cache_resource = None
    if cache_fqdn:
        cache_resource = _get_cache_resource(cache_fqdn, resource_groups, suppress_errors)
        if not cache_resource:
            return ""

    public_paths = set()
    id_to_paths = defaultdict(set)
    id_to_str = {}
    warnings = []

    ligo_authz_list: List[AuthMethod] = []
    if legacy and not public:
        ldappass = readfile(global_data.ligo_ldap_passfile, log)
        ligo_dns = _generate_ligo_dns(global_data.ligo_ldap_url, global_data.ligo_ldap_user, ldappass)
        for dn in ligo_dns:
            ligo_authz_list.append(parse_authz(f"DN:{dn}"))

    for vo_name, vo_data in vos_data.vos.items():
        stashcache_data = vo_data.get('DataFederations', {}).get('StashCache')
        if not stashcache_data:
            continue
        stashcache_obj = StashCache(vo_name, stashcache_data, suppress_errors)

        for path, namespace in stashcache_obj.namespaces.items():
            if not _namespace_allows_cache(namespace, cache_resource):
                continue
            if cache_resource and not _resource_allows_namespace(cache_resource, namespace):
                continue
            if namespace.is_public():
                public_paths.add(path)
                continue
            if public:
                continue

            # Extend authz list with LIGO DNs if applicable
            extended_authz_list = namespace.authz_list
            if legacy and path == "/user/ligo":
                extended_authz_list += ligo_authz_list

            for authz in extended_authz_list:
                if authz.used_in_authfile():
                    id_to_paths[authz.authfile_id()].add(path)
                    id_to_str[authz.authfile_id()] = str(authz)

    if not id_to_paths and not public_paths:
        if suppress_errors:
            return ""
        else:
            raise DataError("No working StashCache resource/VO combinations found")

    authfile_lines = []
    authfile_lines.extend(warnings)

    if public:
        authfile_lines.append("u * \\")
        if legacy:
            authfile_lines.append("    /user/ligo -rl \\")
        for path in sorted(public_paths):
            authfile_lines.append(f"    {path} rl \\")
        # Delete trailing ' \' from the last line
        authfile_lines[-1] = authfile_lines[-1][:-2]
    else:
        for authfile_id in id_to_paths:
            paths_acl = " ".join(f"{p} rl" for p in sorted(id_to_paths[authfile_id]))
            authfile_lines.append(f"# {id_to_str[authfile_id]}")
            authfile_lines.append(f"{authfile_id} {paths_acl}")

    authfile = "\n".join(authfile_lines) + "\n"

    return authfile


def generate_origin_authfile2(
        origin_fqdn: str, global_data: GlobalData, suppress_errors=True, public=False
) -> str:
    resource_groups: List[ResourceGroup] = global_data.get_topology().get_resource_group_list()
    vos_data = global_data.get_vos_data()
    origin_resource = None
    if origin_fqdn:
        origin_resource = _get_origin_resource(origin_fqdn, resource_groups, suppress_errors)
        if not origin_resource:
            return ""

    public_paths = set()
    id_to_paths = defaultdict(set)
    id_to_str = {}
    warnings = []

    for vo_name, vo_data in vos_data.vos.items():
        stashcache_data = vo_data.get('DataFederations', {}).get('StashCache')
        if not stashcache_data:
            continue
        stashcache_obj = StashCache(vo_name, stashcache_data, suppress_errors)

        for path, namespace in stashcache_obj.namespaces.items():
            if not _namespace_allows_origin(namespace, origin_resource):
                continue
            if not _resource_allows_namespace(origin_resource, namespace):
                continue
            if namespace.is_public():
                public_paths.add(path)
                continue
            if public:
                continue

            # The Authfile for origins should contain only caches and the origin itself, via SSL (i.e. DNs).
            # Ignore FQANs and DNs listed in the namespace's authz list.
            authz_list = []

            allowed_resources = [origin_resource]
            # Add caches
            allowed_caches = _get_allowed_caches_for_namespace(namespace, resource_groups, suppress_errors)
            if allowed_caches:
                allowed_resources.extend(allowed_caches)
            else:
                warnings.append(f"# WARNING: No working cache / namespace combinations found for {path}")

            for resource in allowed_resources:
                dn = resource.data.get("DN")
                if dn:
                    authz_list.append(DNAuth(dn))
                else:
                    warnings.append(
                        f"# WARNING: Resource {resource.name} was skipped for VO {vo_name}, namespace {path}"
                        f" because the resource does not provide a DN."
                    )
                    continue

            for authz in authz_list:
                if authz.used_in_authfile():
                    id_to_paths[authz.authfile_id()].add(path)
                    id_to_str[authz.authfile_id()] = str(authz)

    if not id_to_paths and not public_paths:
        if suppress_errors:
            return ""
        else:
            raise DataError("No working StashCache resource/VO combinations found")

    authfile_lines = []
    authfile_lines.extend(warnings)
    for authfile_id in id_to_paths:
        paths_acl = " ".join(f"{p} lr" for p in sorted(id_to_paths[authfile_id]))
        authfile_lines.append(f"# {id_to_str[authfile_id]}")
        authfile_lines.append(f"{authfile_id} {paths_acl}")

    # Public paths must be at the end
    if public_paths:
        authfile_lines.append("")
        paths_acl = " ".join(f"{p} lr" for p in sorted(public_paths))
        authfile_lines.append(f"u * {paths_acl}")

    return "\n".join(authfile_lines) + "\n"


def generate_origin_scitokens2(
        origin_fqdn: str, global_data: GlobalData, suppress_errors = True
) -> str:
    """
    Generate the SciTokens needed by a StashCache origin server, given the fqdn
    of the origin server.

    The scitokens config for a StashCache namespace is in the VO YAML and looks like:

        DataFederations:
            StashCache:
                Namespaces:
                    /store:
                        - SciTokens:
                            Issuer: https://scitokens.org/cms
                            Base Path: /
                            Restricted Path: /store

    "Restricted Path" is optional.
    `fqdn` must belong to a registered cache resource.

    You may have multiple `- SciTokens:` blocks

    Returns a file with a dummy "issuer" block if there are no `- SciTokens:` blocks.

    If suppress_errors is True, returns an empty string on various error conditions (e.g. no fqdn,
    no resource matching fqdn, resource does not contain an origin server, etc.).  Otherwise, raises
    ValueError or DataError.

    """

    resource_groups: List[ResourceGroup] = global_data.get_topology().get_resource_group_list()
    vos_data = global_data.get_vos_data()

    origin_resource = _get_origin_resource(origin_fqdn, resource_groups, suppress_errors)
    if not origin_resource:
        return ""

    template = """\
[Global]
audience = {allowed_vos_str}

{issuer_blocks_str}
"""

    allowed_vos = set()
    origin_authz_list = []

    for vo_name, vo_data in vos_data.vos.items():
        stashcache_data = vo_data.get('DataFederations', {}).get('StashCache')
        if not stashcache_data:
            continue
        stashcache_obj = StashCache(vo_name, stashcache_data, suppress_errors)

        for path, namespace in stashcache_obj.namespaces.items():
            if namespace.is_public():
                continue
            if not _namespace_allows_origin(namespace, origin_resource):
                continue
            if not _resource_allows_namespace(origin_resource, namespace):
                continue

            for authz in namespace.authz_list:
                if authz.used_in_scitokens_conf():
                    origin_authz_list.append(authz)
                    allowed_vos.add(vo_name)

    # Older plugin versions require at least one issuer block (SOFTWARE-4389)
    if not origin_authz_list:
        dummy_auth = SciTokenAuth(issuer="https://scitokens.org/nonexistent", base_path="/no-issuers-found")
        origin_authz_list.append(dummy_auth)

    issuer_blocks = [a.scitokens_conf_block() for a in origin_authz_list]
    issuer_blocks_str = "\n".join(issuer_blocks)
    allowed_vos_str = ", ".join(sorted(allowed_vos))

    return template.format(**locals()).rstrip() + "\n"


def generate_cache_scitokens2(
        cache_fqdn: str, global_data: GlobalData, suppress_errors = True
) -> str:
    """
    Generate the SciTokens needed by a StashCache cache server, given the fqdn
    of the cache server.

    The scitokens config for a StashCache namespace is in the VO YAML and looks like:

        DataFederations:
            StashCache:
                Namespaces:
                    /store:
                        - SciTokens:
                            Issuer: https://scitokens.org/cms
                            Base Path: /
                            Restricted Path: /store

    "Restricted Path" is optional.
    `fqdn` must belong to a registered cache resource.

    You may have multiple `- SciTokens:` blocks

    Returns a file with a dummy "issuer" block if there are no `- SciTokens:` blocks.

    If suppress_errors is True, returns an empty string on various error conditions (e.g. no fqdn,
    no resource matching fqdn, resource does not contain an origin server, etc.).  Otherwise, raises
    ValueError or DataError.

    """

    resource_groups: List[ResourceGroup] = global_data.get_topology().get_resource_group_list()
    vos_data = global_data.get_vos_data()

    cache_resource = _get_cache_resource(cache_fqdn, resource_groups, suppress_errors)
    if not cache_resource:
        return ""

    template = """\
[Global]
audience = {allowed_vos_str}

{issuer_blocks_str}
"""

    allowed_vos = set()
    origin_authz_list = []

    for vo_name, vo_data in vos_data.vos.items():
        stashcache_data = vo_data.get('DataFederations', {}).get('StashCache')
        if not stashcache_data:
            continue
        stashcache_obj = StashCache(vo_name, stashcache_data, suppress_errors)

        for path, namespace in stashcache_obj.namespaces.items():
            if namespace.is_public():
                continue
            if not _namespace_allows_cache(namespace, cache_resource):
                continue
            if not _resource_allows_namespace(cache_resource, namespace):
                continue

            for authz in namespace.authz_list:
                if authz.used_in_scitokens_conf():
                    origin_authz_list.append(authz)
                    allowed_vos.add(vo_name)

    # Older plugin versions require at least one issuer block (SOFTWARE-4389)
    if not origin_authz_list:
        dummy_auth = SciTokenAuth(issuer="https://scitokens.org/nonexistent", base_path="/no-issuers-found")
        origin_authz_list.append(dummy_auth)

    issuer_blocks = [a.scitokens_conf_block() for a in origin_authz_list]
    issuer_blocks_str = "\n".join(issuer_blocks)
    allowed_vos_str = ", ".join(sorted(allowed_vos))

    return template.format(**locals()).rstrip() + "\n"


def get_namespaces_info(global_data: GlobalData, suppress_errors = True) -> Dict:
    # Helper functions
    def _cache_resource_dict(r: Resource):
        endpoint = f"{r.fqdn}:8000"
        for svc in r.services:
            if svc.get("Name") == XROOTD_CACHE_SERVER:
                if not is_null(svc, "Details", "uri_override"):
                    endpoint = svc["Details"]["uri_override"]
                break
        return {"endpoint": endpoint, "resource": r.name}

    def _namespace_dict(ns: Namespace):
        nsdict = {
            "path": ns.path,
            "readhttps": not ns.is_public(),
            "usetokenonread": any(isinstance(a, SciTokenAuth) for a in ns.authz_list),
            "writebackhost": ns.writeback,
            "dirlisthost": ns.dirlist,
            "caches": [],
        }

        for cache_name, cache_resource_obj in cache_resource_objs.items():
            if _resource_allows_namespace(cache_resource_obj, ns) and _namespace_allows_cache(ns, cache_resource_obj):
                nsdict["caches"].append(cache_resource_dicts[cache_name])
        return nsdict
    # End helper functions

    resource_groups: List[ResourceGroup] = global_data.get_topology().get_resource_group_list()
    vos_data = global_data.get_vos_data()

    cache_resource_objs = {}  # type: Dict[str, Resource]
    cache_resource_dicts = {}  # type: Dict[str, Dict]

    for group in resource_groups:
        for resource in group.resources:
            if _resource_has_cache(resource):
                cache_resource_objs[resource.name] = resource
                cache_resource_dicts[resource.name] = _cache_resource_dict(resource)

    result_namespaces = []
    for vo_name, vo_data in vos_data.vos.items():
        stashcache_data = vo_data.get('DataFederations', {}).get('StashCache')
        if not stashcache_data:
            continue
        stashcache_obj = StashCache(vo_name, stashcache_data, suppress_errors)

        for namespace in stashcache_obj.namespaces.values():
            result_namespaces.append(_namespace_dict(namespace))

    return {
        "caches": list(cache_resource_dicts.values()),
        "namespaces": result_namespaces
    }
