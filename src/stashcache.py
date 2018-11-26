
from collections import defaultdict
import re
import ldap
import asn1
import hashlib

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

def _generate_ligo_dns():
    """
    Query the LIGO LDAP server for all grid DNs in the LVC collab.

    Returns a list of DNs.
    """
    ldap_obj = ldap.initialize("ldap://ldap.ligo.org")
    query = "(&(isMemberOf=Communities:LSCVirgoLIGOGroupMembers)(gridX509subject=*))"
    results = ldap_obj.search_s("ou=people,dc=ligo,dc=org", ldap.SCOPE_ONELEVEL,
                                query, ["gridX509subject"])
    all_dns = []
    for result in results:
        user_dns = result[1].get('gridX509subject', [])
        for dn in user_dns:
            if dn.startswith(b"/"):
                all_dns.append(dn.replace(b"\n", b" ").decode("utf-8"))

    return all_dns


def _generate_dn_hash(dn: str):
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


def generate_authfile(vo_data):
    """
    Generate the Xrootd authfile needed by a StashCache cache server.
    """
    authfile = ""
    id_to_dir = defaultdict(list)
    for vo_name, vo_data in vo_data.vos.items():
        stashcache_data = vo_data.get('DataFederations', {}).get('StashCache')
        if not stashcache_data:
            continue

        for dirname, authz_list in stashcache_data.get("Authorizations", {}).items():
            for authz in authz_list:
                if authz.startswith("FQAN:"):
                    id_to_dir["g {}".format(authz[5:])].append(dirname)
                elif authz.startswith("DN:"):
                    hash = _generate_dn_hash(authz[3:])
                    id_to_dir["u {}".format(hash)].append(dirname)

    for dn in _generate_ligo_dns():
        hash = _generate_dn_hash(dn)
        id_to_dir["u {}".format(hash)].append("/user/ligo")

    for id, dir_list in id_to_dir.items():
        if dir_list:
            authfile += "{} {}\n".format(id,
                " ".join([i + " rl" for i in dir_list]))

    return authfile


def generate_public_authfile(vo_data):
    """
    Generate the Xrootd authfile needed for public caches
    """
    authfile = "u * /user/ligo -rl \\\n"
    id_to_dir = defaultdict(list)

    public_dirs = [] 
    for vo_name, vo_data in vo_data.vos.items():
        stashcache_data = vo_data.get('DataFederations', {}).get('StashCache')
        if not stashcache_data:
            continue

        for dirname, authz_list in stashcache_data.get("Authorizations", {}).items():
            for authz in authz_list:
                if authz == "PUBLIC":
                    public_dirs.append(dirname)

    for dirname in public_dirs:
        authfile += "    {} rl \\\n".format(dirname)

    return authfile[:-2]
