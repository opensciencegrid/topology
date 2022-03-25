#!/usr/bin/env python3


from webapp.common import safe_dict_get
from webapp.cilogon_ldap import get_cilogon_ldap_id_map
from webapp.cilogon_ldap import cilogon_id_map_to_ssh_keys
from webapp.cilogon_ldap import get_contact_cilogon_id_map


def get_oasis_manager_endpoint_info(global_data, vo, ldappass):
    """ return list of oasis manager info for endpoint with the structure:

        [ {'ContactID': ContactID, 'Name': Name, 'DNs': DNs,
           'CILogonID': CILogonID, 'sshPublicKeys': [sshPubKey, ...]}, ... ]

        with one list entry per oasis manager for the given vo, whose
        contact db info specifies a CILogonID, and whose cilogon info
        for that CILogonID contains a list of ssh public keys.

        Alternatively, if vo="*", return a dict of the form

            {vo: OASISManagers}

        where OASISManagers is a list as described above for each vo. """

    if vo != "*":
        managers = get_vo_oasis_managers(global_data, vo)
        if not managers:
            return []

    ldap_url = global_data.cilogon_ldap_url
    ldap_user = global_data.cilogon_ldap_user
    cilogon_id_map = get_cilogon_ldap_id_map(ldap_url, ldap_user, ldappass)
    ssh_keys_map = cilogon_id_map_to_ssh_keys(cilogon_id_map)
    contact_cilogon_ids = get_contact_cilogon_id_map(global_data)

    if vo == "*":
        vo_managers = get_all_oasis_managers(global_data)
        return {
            vo: get_managers_info(managers, contact_cilogon_ids, ssh_keys_map)
            for vo,managers in vo_managers.items()
        }
    else:
        return get_managers_info(managers, contact_cilogon_ids, ssh_keys_map)


def get_managers_info(managers, contact_cilogon_ids, ssh_keys_map):
    info = []
    for manager in managers:
        ContactID = safe_dict_get(manager, 'ID')
        Name = manager.get('Name')
        DNs = manager.get('DNs', [])
        if ContactID in contact_cilogon_ids:
            CILogonID = contact_cilogon_ids[ContactID].cilogon_id
            ssh_keys = ssh_keys_map.get(CILogonID, [])
            cilogon_info = {'CILogonID': CILogonID, 'sshPublicKeys': ssh_keys}
        else:
            cilogon_info = {}
        info.append(
            dict(ContactID=ContactID, Name=Name, DNs=DNs, **cilogon_info)
        )
    return info


def get_vo_oasis_managers(global_data, vo):
    """return OASIS Managers list for given vo, if any, else an empty list"""
    vos_data = global_data.get_vos_data()
    return _extract_vo_oasis_managers(vos_data.vos, vo)


def get_all_oasis_managers(global_data):
    """return dict of OASIS Managers lists for all VOs"""
    vos = global_data.get_vos_data().vos
    return { vo: _extract_vo_oasis_managers(vos, vo) for vo in vos }


def _extract_vo_oasis_managers(vos, vo):
    """ helper for get_vo_oasis_managers / get_all_oasis_managers """
    managers = safe_dict_get(vos, vo, "OASIS", "Managers", default=[])
    if not isinstance(managers, list):
        return []
    return managers


