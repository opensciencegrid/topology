
from collections import defaultdict
from typing import Dict, List, Optional
import re
import sys
import ldap3
import asn1
import hashlib

from webapp.common import readfile
from webapp.models import GlobalData
from webapp.topology import Resource, ResourceGroup
from webapp.vos_data import VOsData

import logging

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

_ligo_ldap_branch = "ou=people,dc=ligo,dc=org"

class DataError(Exception):
    """Raised when there is a problem in the topology or VO data"""

class NotRegistered(Exception):
    """Raised when the FQDN is not registered at all"""


def _generate_ligo_dns(ldapurl: str, ldapuser: str, ldappass: str) -> List[str]:
    """
    Query the LIGO LDAP server for all grid DNs in the IGWN collab.

    Returns a list of DNs.
    """
    query = "(&(isMemberOf=Communities:LSCVirgoLIGOGroupMembers)(gridX509subject=*))"
    try:
        server = ldap3.Server(ldapurl, connect_timeout=10)
        conn = ldap3.Connection(server, user=ldapuser, password=ldappass, raise_exceptions=True, receive_timeout=10)
        conn.bind()
    except ldap3.core.exceptions.LDAPException:
        log.exception("Failed to connect to the LIGO LDAP")
        return []

    try:
        conn.search(_ligo_ldap_branch,
                    query,
                    search_scope='LEVEL',
                    attributes=['gridX509subject'])
        results = [dn for e in conn.entries for dn in e.gridX509subject]
    except ldap3.core.exceptions.LDAPException:
        log.exception("Failed to query the LIGO LDAP")
    finally:
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


def _get_resource_by_fqdn(fqdn: str, resource_groups: List[ResourceGroup]) -> Resource:
    """Returns the Resource that has the given FQDN; if multiple Resources
    have the same FQDN, returns the first one.

    """
    for group in resource_groups:
        for resource in group.resources:
            if fqdn.lower() == resource.fqdn.lower():
                return resource


def _get_cache_resource(fqdn: Optional[str], resource_groups: List[ResourceGroup], suppress_errors: bool) -> Optional[Resource]:
    """If given an FQDN, returns the Resource _if it has an "XRootD cache server" service_.
    If given None, returns None.
    If multiple Resources have the same FQDN, checks the first one.
    If suppress_errors is False, raises an expression on the following conditions:
    - no Resource matching FQDN (NotRegistered)
    - Resource does not provide an XRootD cache server (DataError)
    If suppress_errors is True, returns None on the above conditions.

    """
    resource = None
    if fqdn:
        resource = _get_resource_by_fqdn(fqdn, resource_groups)
        if not resource:
            if suppress_errors:
                return None
            else:
                raise NotRegistered(fqdn)
        if "XRootD cache server" not in resource.service_names:
            if suppress_errors:
                return None
            else:
                raise DataError("{} (resource name {}) does not provide an XRootD cache server.".format(fqdn, resource.name))
    return resource


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


def generate_cache_authfile(global_data: GlobalData,
                            fqdn=None,
                            legacy=True,
                            suppress_errors=True) -> str:
    """
    Generate the Xrootd authfile needed by a StashCache cache server.
    """
    authfile = ""
    id_to_dir = defaultdict(set)

    resource_groups = global_data.get_topology().get_resource_group_list()
    resource = _get_cache_resource(fqdn, resource_groups, suppress_errors)
    if fqdn and not resource:
        return ""

    vo_data = global_data.get_vos_data()
    for vo_name, vo_details in vo_data.vos.items():
        stashcache_data = vo_details.get('DataFederations', {}).get('StashCache')
        if not stashcache_data:
            continue

        namespaces = stashcache_data.get("Namespaces")
        if not namespaces:
            if suppress_errors:
                continue
            else:
                raise DataError("VO {} in StashCache does not provide a Namespaces list.".format(vo_name))

        needs_authz = False
        for namespace, authz_list in namespaces.items():
            if not authz_list:
                if suppress_errors:
                    continue
                else:
                    raise DataError("Namespace {} (VO {}) does not provide any authorizations.".format(namespace, vo_name))
            if authz_list != ["PUBLIC"]:
                needs_authz = True
                break
        if not needs_authz:
            continue

        if resource and not _cache_is_allowed(resource, vo_name, stashcache_data, False, suppress_errors):
            continue

        for namespace, authz_list in namespaces.items():
            for authz in authz_list:
                if not isinstance(authz, str):
                    continue
                if authz.startswith("FQAN:"):
                    id_to_dir["g {}".format(authz[5:])].add(namespace)
                elif authz.startswith("DN:"):
                    hash = _generate_dn_hash(authz[3:])
                    id_to_dir["u {}".format(hash)].add(namespace)

    if legacy:
        ldappass = readfile(global_data.ligo_ldap_passfile, log)
        for dn in _generate_ligo_dns(global_data.ligo_ldap_url, global_data.ligo_ldap_user, ldappass):
            hash = _generate_dn_hash(dn)
            id_to_dir["u {}".format(hash)].add("/user/ligo")

    for id, dir_list in id_to_dir.items():
        if dir_list:
            authfile += "{} {}\n".format(id,
                " ".join([i + " rl" for i in sorted(dir_list)]))

    return authfile


def generate_public_cache_authfile(vo_data: VOsData, resource_groups: List[ResourceGroup], fqdn=None, legacy=True, suppress_errors=True) -> str:
    """
    Generate the Xrootd authfile needed for public caches
    """
    if legacy:
        authfile = "u * /user/ligo -rl \\\n"
    else:
        authfile = "u * \\\n"

    resource = _get_cache_resource(fqdn, resource_groups, suppress_errors)
    if fqdn and not resource:
        return ""

    public_dirs = set()
    vo_data = global_data.get_vos_data()
    for vo_name, vo_details in vo_data.vos.items():
        stashcache_data = vo_details.get('DataFederations', {}).get('StashCache')
        if not stashcache_data:
            continue
        if resource and not _cache_is_allowed(resource, vo_name, stashcache_data, True, suppress_errors):
            continue

        for dirname, authz_list in stashcache_data.get("Namespaces", {}).items():
            if "PUBLIC" in authz_list:
                public_dirs.add(dirname)

    for dirname in sorted(public_dirs):
        authfile += "    {} rl \\\n".format(dirname)

    if authfile.endswith("\\\n"):
        authfile = authfile[:-2] + "\n"

    return authfile


def generate_cache_scitokens(vo_data: VOsData, resource_groups: List[ResourceGroup], fqdn: str, suppress_errors=True) -> str:
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

    If suppress_errors is True, returns an empty string on various error conditions (e.g. no fqdn,
    no resource matching fqdn, resource does not contain a cache server, etc.).  Otherwise, raises
    ValueError or DataError.

    """
    template = """\
[Global]
audience = {allowed_vos_str}

{issuer_blocks_str}
"""

    if not fqdn:
        if suppress_errors:
            return ""
        else:
            raise ValueError("fqdn: empty")

    resource = _get_cache_resource(fqdn, resource_groups, suppress_errors)
    if not resource:
        return ""

    log.debug(f"Generating stashcache cache config for {fqdn}")
    allowed_vos = []
    issuer_blocks = []
    for vo_name, vo_data in vo_data.vos.items():
        stashcache_data = vo_data.get('DataFederations', {}).get('StashCache')
        if not stashcache_data:
            continue

        namespaces = stashcache_data.get("Namespaces", {})
        if not namespaces:
            continue

        log.debug(f"Namespaces found for {vo_name}")
        needs_authz = False
        for authz_list in namespaces.values():
            for authz in authz_list:
                if authz != "PUBLIC":
                    needs_authz = True
                    break
        if not needs_authz:
            log.debug(f"\tAuth not needed for {vo_name}")
            continue

        if not _cache_is_allowed(resource, vo_name, stashcache_data,
                                 public=False, suppress_errors=suppress_errors):
            continue

        for dirname, authz_list in namespaces.items():
            for authz in authz_list:
                if not isinstance(authz, dict) or not isinstance(authz.get("SciTokens"), dict):
                    log.debug(f"\tNo SciTokens info for {dirname} in {vo_name}")
                    continue
                issuer_blocks.append(_get_scitokens_issuer_block(vo_name, authz['SciTokens'],
                                                                 dirname, suppress_errors))
                allowed_vos.append(vo_name)

    issuer_blocks_str = "\n".join(issuer_blocks)
    allowed_vos_str = ", ".join(allowed_vos)

    return template.format(**locals()).rstrip() + "\n"


def _get_scitokens_issuer_block(vo_name: str, scitokens: Dict, dirname: str, suppress_errors: bool) -> str:
    template = """\
[Issuer {dirname}]
issuer = {issuer}
base_path = {base_path}
{restricted_path_line}
"""
    issuer_block = ""
    if not scitokens.get("Issuer"):
        if suppress_errors:
            return ""
        raise DataError("'Issuer' missing from the SciTokens config for {}.".format(vo_name))
    issuer = scitokens["Issuer"]
    if not scitokens.get("Base Path"):
        if suppress_errors:
            return ""
        raise DataError("'Base Path' missing from the SciTokens config for {}.".format(vo_name))
    base_path = scitokens["Base Path"]

    if scitokens.get("Restricted Path"):
        restricted_path_line = "restricted_path = {}\n".format(scitokens['Restricted Path'])
    else:
        restricted_path_line = ""

    return template.format(**locals())


def _origin_is_allowed(origin_hostname, vo_name, stashcache_data, resource_groups, suppress_errors=True):
    origin_resource = _get_resource_by_fqdn(origin_hostname, resource_groups)
    if not origin_resource:
        if suppress_errors:
            return False
        else:
            raise NotRegistered(origin_hostname)
    if 'XRootD origin server' not in origin_resource.service_names:
        if suppress_errors:
            return False
        else:
            raise DataError("{} (resource name {}) does not provide an XRootD origin server.".format(origin_hostname, origin_resource.name))
    allowed_vos = origin_resource.data.get("AllowedVOs")
    if allowed_vos is None:
        if suppress_errors:
            return False
        else:
            raise DataError("Origin server at {} (resource name {}) does not provide an AllowedVOs list.".format(origin_hostname, origin_resource.name))

    if 'ANY' not in allowed_vos and vo_name not in allowed_vos:
        return False

    allowed_origins = stashcache_data.get("AllowedOrigins")
    if allowed_origins is None:
        if suppress_errors:
            return False
        else:
            raise DataError("VO {} in StashCache does not provide an AllowedOrigins list.".format(vo_name))

    return origin_resource.name in allowed_origins


def _get_allowed_caches(vo_name, stashcache_data, resource_groups, suppress_errors=True) -> List[Resource]:
    allowed_caches = stashcache_data.get("AllowedCaches")
    if allowed_caches is None:
        if suppress_errors:
            return []
        else:
            raise DataError("VO {} in StashCache does not provide an AllowedCaches list.".format(vo_name))

    resources = []
    for group in resource_groups:
        for resource in group.resources:
            # First, does this provide a cache service?
            if 'XRootD cache server' not in resource.service_names:
                continue

            # Next, does it allow this VO?  Unlike the StashCache origin case requiring the origin to list AllowedVOs,
            # we do not consider the lack of AllowedVOs an error as the cache doesn't
            # explicitly record *which* data federation it is participating in (might not be SC!).
            allowed_vos = resource.data.get("AllowedVOs", [])
            if 'ANY' not in allowed_vos and (vo_name != "ANY_PUBLIC" and vo_name not in allowed_vos):
                continue
            if 'ANY' not in allowed_caches and resource.name not in allowed_caches:
                continue
            resources.append(resource)
    return resources


def generate_origin_authfile(origin_hostname, vo_data, resource_groups, suppress_errors=True, public_only=False):
    public_namespaces = set()
    id_to_namespaces = defaultdict(set)
    id_to_dn = {}
    warnings = []
    for vo_name, vo_data in vo_data.vos.items():
        stashcache_data = vo_data.get('DataFederations', {}).get('StashCache')
        if not stashcache_data:
            continue

        if not _origin_is_allowed(origin_hostname, vo_name, stashcache_data, resource_groups, suppress_errors=suppress_errors):
            continue

        namespaces = stashcache_data.get("Namespaces")
        if not namespaces:
            if suppress_errors:
                continue
            else:
                raise DataError("VO {} in StashCache does not provide a Namespaces list.".format(vo_name))

        for namespace, authz_list in namespaces.items():
            if not authz_list:
                if suppress_errors:
                    continue
                else:
                    raise DataError("Namespace {} (VO {}) does not provide any authorizations.".format(namespace, vo_name))

            if authz_list == ["PUBLIC"]:
                public_namespaces.add(namespace)
                continue

            if public_only:
                continue

            allowed_caches = stashcache_data.get("AllowedCaches")
            if allowed_caches is None:
                if suppress_errors:
                    continue
                else:
                    raise DataError("VO {} in StashCache does not provide an AllowedCaches list.".format(vo_name))

            allowed_resources = _get_allowed_caches(vo_name, stashcache_data, resource_groups, suppress_errors=suppress_errors)
            origin_resource = _get_resource_by_fqdn(origin_hostname, resource_groups)
            allowed_resources.append(origin_resource)

            for resource in allowed_resources:
                dn = resource.data.get("DN")
                if not dn:
                    warnings.append("# WARNING: Resource {} was skipped for VO {}"
                                    " because the resource does not provide a DN.\n".format(resource.name, vo_name))
                    continue
                dn_hash = _generate_dn_hash(dn)
                id_to_namespaces[dn_hash].add(namespace)
                id_to_dn[dn_hash] = dn

    if not id_to_namespaces and not public_namespaces:
        if suppress_errors:
            return ""
        else:
            raise DataError("No working StashCache resource/VO combinations found")

    results = ""
    if warnings:
        results += "".join(warnings) + "\n"
    for id, namespaces in id_to_namespaces.items():
        dn = id_to_dn[id]
        results += "# {}\nu {} {}\n".format(dn, id, " ".join("{} lr".format(i) for i in sorted(namespaces)))
    if public_namespaces:
        results += "\nu * {}\n".format(" ".join("{} lr".format(i) for i in sorted(public_namespaces)))
    return results


def generate_origin_scitokens(vo_data: VOsData, resource_groups: List[ResourceGroup], fqdn: str, suppress_errors=True) -> str:
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

    template = """\
[Global]
audience = {allowed_vos_str}

{issuer_blocks_str}
"""
    allowed_vos = []
    issuer_blocks = []
    for vo_name, vo_data in vo_data.vos.items():
        stashcache_data = vo_data.get('DataFederations', {}).get('StashCache')
        if not stashcache_data:
            continue

        if not _origin_is_allowed(fqdn, vo_name, stashcache_data, resource_groups, suppress_errors=suppress_errors):
            continue

        namespaces = stashcache_data.get("Namespaces")
        if not namespaces:
            if suppress_errors:
                continue
            else:
                raise DataError("VO {} in StashCache does not provide a Namespaces list.".format(vo_name))

        for dirname, authz_list in namespaces.items():
            if not authz_list:
                if suppress_errors:
                    continue
                else:
                    raise DataError("Namespace {} (VO {}) does not provide any authorizations.".format(dirname, vo_name))

            for authz in authz_list:
                if not isinstance(authz, dict) or not isinstance(authz.get("SciTokens"), dict):
                    continue
                issuer_blocks.append(_get_scitokens_issuer_block(vo_name, authz['SciTokens'],
                                                                 dirname, suppress_errors))
                allowed_vos.append(vo_name)

    # Older plugin versions require at least one issuer block (SOFTWARE-4389)
    if not issuer_blocks:
        issuer_blocks.append(
            _get_scitokens_issuer_block(vo_name="nonexistent",
                                        scitokens={"Issuer": "https://scitokens.org/nonexistent",
                                                   "Base Path": "/no-issuers-found"},
                                        dirname="/no-issuers-found",
                                        suppress_errors=suppress_errors))
    issuer_blocks_str = "\n".join(issuer_blocks)
    allowed_vos_str = ", ".join(allowed_vos)

    return template.format(**locals()).rstrip() + "\n"
