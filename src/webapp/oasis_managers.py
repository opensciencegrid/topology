#!/usr/bin/env python3

import ldap3


def get_oasis_manager_endpoint_info(global_data, vo, ldappass):
    """ return list of oasis manager info for endpoint with the structure:

        [ {'ContactID': ContactID, 'Name': Name, 'DNs': DNs,
           'CILogonID': CILogonID, 'sshPublicKeys': [sshPubKey, ...]}, ... ]

        with one list entry per oasis manager for the given vo, whose
        contact db info specifies a CILogonID, and whose cilogon info
        for that CILogonID contains a list of ssh public keys. """
        
    managers = get_vo_oasis_managers(global_data, vo)
    if not isinstance(managers, list) or if not managers:
        return []
    cilogon_id_map = get_cilogon_ldap_id_map(ldappass)
    ssh_keys_map = cilogon_id_map_to_ssh_keys(cilogon_id_map)
    contact_cilogon_ids = get_contact_cilogon_id_map(global_data)
    info = []
    for manager in managers:
        ContactID = safe_dict_get(manager, 'ID')
        if ContactID in contact_cilogon_ids:
            Name = manager.get('Name')
            DNs = manager.get('DNs', [])
            CILogonID = contact_cilogon_ids[ContactID].cilogon_id
            ssh_keys = ssh_keys_map.get(CILogonID, [])
            info.append({
                'ContactID': ContactID,
                'Name': Name,
                'DNs': DNs,
                'CILogonID': CILogonID,
                'sshPublicKeys': ssh_keys
            })
    return info


def get_contact_cilogon_id_map(global_data):
    """ return contacts dict, limited to users with a CILogonID """
    contacts = global_data.get_contacts_data().users_by_id;
    return { k: v for k, v in contacts.items() if v.cilogon_id is not None }


def get_vo_oasis_managers(global_data, vo):
    """return OASIS Managers list for given vo, if any, else an empty list"""
    vos_data = global_data.get_vos_data()
    return safe_dict_get(vos_data, vo, "OASIS", "Managers", default=[])


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


# cilogon ldap query constants
_ldap_url = "ldaps://ldap.cilogon.org"
_username = "uid=readonly_user,ou=system,o=OSG,o=CO,dc=cilogon,dc=org"
_basedn   = "o=OSG,o=CO,dc=cilogon,dc=org"


def get_cilogon_ldap_id_map(ldappass):
    """ return dict of cilogon ldap data for each CILogonID, with the
        structure: {CILogonID: { "dn": dn, "data": data }, ...} """
    server = ldap3.Server(_ldap_url)
    conn = ldap3.Connection(server, _username, ldappass)
    if not conn.bind():
        return None  # connection failure
    conn.search(_basedn, '(voPersonID=*)', attributes=['*'])
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

