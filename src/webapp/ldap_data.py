import logging
from typing import List

import ldap3

log = logging.getLogger(__name__)


CILOGON_LDAP_TIMEOUT = 10
LIGO_LDAP_TIMEOUT = 10


def get_contact_cilogon_id_map(global_data):
    """ return contacts dict, limited to users with a CILogonID """
    contacts = global_data.get_contacts_data().users_by_id
    return { k: v for k, v in contacts.items() if v.cilogon_id is not None }


# cilogon ldap query constants
#_ldap_url = "ldaps://ldap.cilogon.org"
#_username = "uid=readonly_user,ou=system,o=OSG,o=CO,dc=cilogon,dc=org"
_cilogon_basedn   = "o=OSG,o=CO,dc=cilogon,dc=org"


def get_cilogon_ldap_id_map(ldap_url, ldap_user, ldap_pass):
    """ return dict of cilogon ldap data for each CILogonID, with the
        structure: {CILogonID: { "dn": dn, "data": data }, ...} """
    server = ldap3.Server(ldap_url, connect_timeout=CILOGON_LDAP_TIMEOUT)
    conn = ldap3.Connection(server, ldap_user, ldap_pass, receive_timeout=CILOGON_LDAP_TIMEOUT)
    if not conn.bind():
        return None  # connection failure
    conn.search(_cilogon_basedn, '(voPersonID=*)', attributes=['*'])
    result_data = [ (e.entry_dn, e.entry_attributes_as_dict)
                    for e in conn.entries ]
    conn.unbind()
    return {
        voPersonID: { "dn": dn, "data": data }
        for dn, data in result_data
        if "voPersonID" in data
        for voPersonID  in data["voPersonID"]
    }


def cilogon_id_map_to_ssh_keys(m):
    """ convert id map (as returned by get_cilogon_ldap_id_map) to a dict with
        structure: {CILogonID: [sshPublicKey, ...], ...} for each id that has
        ssh public keys defined """
    return {
        k: v['data']['sshPublicKey']
        for k, v in m.items()
        if 'sshPublicKey' in v['data']
    }


def _entry2cinfo(entry):
    ci = {}
    emails = entry['data'].get('mail')
    if emails:
        ci['PrimaryEmail'] = emails[0].lower()
        if len(emails) >= 2:
            ci['SecondaryEmail'] = emails[1].lower()
    else:
        return None
    return ci


def cilogon_id_map_to_yaml_data(m):
    data = {}
    for id_, entry in m.items():
        cinfo = _entry2cinfo(entry)
        if cinfo:
            data[id_] = {'CILogonID'          : id_,
                         'FullName'           : entry['data']['cn'][0],
                         'ContactInformation' : cinfo}

            github = entry['data'].get('voPersonExternalID')
            if github:
                data[id_]['GitHub'] = github[0]

    return data


def get_osgid_lookup(yaml_data):
    osgid_lookup = {}
    for contact in yaml_data.values():
        if 'CILogonID' in contact:
            osgid_lookup[contact['CILogonID']] = contact
    return osgid_lookup


def get_email_lookup(yaml_data):
    email_lookup = {}
    for contact in yaml_data.values():
        ci = contact.get('ContactInformation')
        if not ci:
            continue
        for Email in ('PrimaryEmail', 'SecondaryEmail'):
            if Email in ci:
                email_lookup[ci[Email].lower()] = contact
    return email_lookup


def get_sup_contact(contact, osgid_lookup, email_lookup):
    id_ = contact.get('CILogonID')
    if id_ in osgid_lookup:
        return osgid_lookup[id_]
    ci = contact.get('ContactInformation')
    if not ci:
        return None
    for Email in ('PrimaryEmail', 'SecondaryEmail'):
        if Email in ci:
            addr = ci[Email]
            if addr in email_lookup:
                return email_lookup[addr]
    return None


def supplement_contact_info(contact, sup_contact):
    for k in sup_contact:
        if k not in contact:
            contact[k] = sup_contact[k]
        elif isinstance(contact[k], dict) and isinstance(sup_contact[k], dict):
            for k2 in set(sup_contact[k]) - set(contact[k]):
                contact[k][k2] = sup_contact[k][k2]


def merge_yaml_data(yaml_data_main, yaml_data_secondary):
    # main is comanage (cilogon), secondary is contact db
    yd = dict(yaml_data_main)
    osgid_lookup = get_osgid_lookup(yaml_data_secondary)
    email_lookup = get_email_lookup(yaml_data_secondary)

    for contact in yd.values():
        sup_contact = get_sup_contact(contact, osgid_lookup, email_lookup)
        if sup_contact:
            supplement_contact_info(contact, sup_contact)

    for id_, contact in yaml_data_secondary.items():
        if id_ not in yd:
            yd[id_] = contact

    return yd


def get_ligo_ldap_dn_list(ldap_url: str, ldap_user: str, ldap_pass: str) -> List[str]:
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
        server = ldap3.Server(ldap_url, connect_timeout=LIGO_LDAP_TIMEOUT)
        conn = ldap3.Connection(server, user=ldap_user, password=ldap_pass, raise_exceptions=True,
                                receive_timeout=LIGO_LDAP_TIMEOUT)
        conn.bind()
    except ldap3.core.exceptions.LDAPException:
        log.exception("Failed to connect to the LIGO LDAP")
        return results

    try:
        for group in ('people', 'robot'):
            try:
                conn.search(base_branch.format(group=group),
                            queries[group],
                            search_scope='SUBTREE',
                            attributes=['gridX509subject'])
                results.extend(dn for e in conn.entries for dn in e.gridX509subject)
            except ldap3.core.exceptions.LDAPException:
                log.exception("Failed to query LIGO LDAP for %s DNs", group)
    finally:
        conn.unbind()

    return results
