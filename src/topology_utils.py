"""
Various helper utilities necessary for clients of the topology
service.
"""

from __future__ import print_function

import os
import sys
import urllib
import fnmatch
try:
    import urlparse
except ImportError:
    import urllib.parse as urlparse

import xml.etree.ElementTree as ET

import requests

def get_auth_session(args):
    """
    Return a requests session ready for an XML query.
    """
    euid = os.geteuid()
    if euid == 0:
        cert = '/etc/grid-security/hostcert.pem'
        key = '/etc/grid-security/hostkey.pem'
    else:
        cert = '/tmp/x509up_u%d' % euid
        key = '/tmp/x509up_u%d' % euid

    cert = os.environ.get('X509_USER_PROXY', cert)
    key = os.environ.get('X509_USER_PROXY', key)

    if args.cert:
        cert = args.cert
    if args.key:
        key = args.key

    session = requests.Session()

    if os.path.exists(cert):
        session.cert = cert
    if os.path.exists(key):
        session.cert = (cert, key)

    return session


def update_url_hostname(url, args):
    """
    Given a URL and an argument object, update the URL's hostname
    according to args.host and return the newly-formed URL.
    """
    if not args.host:
        return url
    url_list = list(urlparse.urlsplit(url))
    url_list[1] = args.host
    return urlparse.urlunsplit(url_list)


def get_contact_list_info(contact_list):
    """
    Get contact list info out of contact list

    In rgsummary, this looks like:
        <ContactLists>
            <ContactList>
                <ContactType>Administrative Contact</ContactType>
                <Contacts>
                    <Contact>
                        <Name>Matyas Selmeci</Name>
                        ...
                    </Contact>
                </Contacts>
            </ContactList>
            ...
        </ContactLists>

    and the arg `contact_list` is the contents of a single <ContactList>

    If vosummary, this looks like:
        <ContactTypes>
            <ContactType>
                <Type>Miscellaneous Contact</Type>
                <Contacts>
                    <Contact>
                        <Name>...</Name>
                        ...
                    </Contact>
                    ...
                </Contacts>
            </ContactType>
            ...
        </ContactTypes>

    and the arg `contact_list` is the contents of <ContactTypes>


    Returns: a list of dicts that each look like:
    { 'ContactType': 'Administrative Contact',
      'Name': 'Matyas Selmeci',
      'Email': '...',
      ...
    }
    """
    contact_list_info = []
    for contact in contact_list:
        if contact.tag == 'ContactType' or contact.tag == 'Type':
            contact_list_type = contact.text.lower()
        if contact.tag == 'Contacts':
            for con in contact:
                contact_info = { 'ContactType' : contact_list_type }
                for contact_contents in con:
                    contact_info[contact_contents.tag] = contact_contents.text
                contact_list_info.append(contact_info)

    return contact_list_info


def get_vo_map(args, session=None):
    """
    Generate a dictionary mapping from the VO name (key) to the
    VO ID (value).
    """
    old_no_proxy = os.environ.pop('no_proxy', None)
    os.environ['no_proxy'] = '.opensciencegrid.org'

    url = update_url_hostname("https://my.opensciencegrid.org/vosummary"
                              "/xml?all_vos=on&active_value=1", args)
    if session is None:
        with get_auth_session(args) as session:
            response = session.get(url)
    else:
        response = session.get(url)

    if old_no_proxy is not None:
        os.environ['no_proxy'] = old_no_proxy
    else:
        del os.environ['no_proxy']

    if response.status_code != requests.codes.ok:
        raise Exception("MyOSG request failed (status %d): %s" % \
              (response.status_code, response.text[:2048]))

    root = ET.fromstring(response.content)
    if root.tag != 'VOSummary':
        raise Exception("MyOSG returned invalid XML with root tag %s" % root.tag)
    vo_map = {}
    for child_vo in root:
        if child_vo.tag != "VO":
            raise Exception("MyOSG returned a non-VO  (%s) inside VO summary." % \
                            root.tag)
        vo_info = {}
        for child_info in child_vo:
            vo_info[child_info.tag] = child_info.text
        if 'ID' in vo_info and 'Name' in vo_info:
            vo_map[vo_info['Name'].lower()] = vo_info['ID']

    return vo_map


SERVICE_IDS = {'ce': 1,
               'srmv2': 3,
               'gridftp': 5,
               'xrootd': 142,
               'perfsonar-bandwidth': 130,
               'perfsonar-latency': 130,
               'gums': 101,
              }
def mangle_url(url, args, session=None):
    """
    Given a MyOSG URL, switch to using the hostname specified in the
    arguments
    """
    if not args.host:
        return url
    url_list = list(urlparse.urlsplit(url))
    url_list[1] = args.host

    qs_dict = urlparse.parse_qs(url_list[3])
    qs_list = urlparse.parse_qsl(url_list[3])

    if getattr(args, 'provides_service', None):
        if 'service' not in qs_dict:
            qs_list.append(("service", "on"))
        for service in args.provides_service.split(","):
            service = service.strip().lower()
            service_id = SERVICE_IDS.get(service)
            if not service_id:
                raise Exception("Requested service %s not known; known service"
                                " names: %s" % (service, ", ".join(SERVICE_IDS)))
            qs_list.append(("service_sel[]", str(service_id)))

    if getattr(args, 'owner_vo', None):
        vo_map = get_vo_map(args, session)
        if 'voown' not in qs_dict:
            qs_list.append(("voown", "on"))
        for vo in args.owner_vo.split(","):
            vo = vo.strip().lower()
            vo_id = vo_map.get(vo)
            if not vo_id:
                raise Exception("Requested owner VO %s not known; known VOs: %s" \
                    % (vo, ", ".join(vo_map)))
            qs_list.append(("voown_sel[]", str(vo_id)))

    url_list[3] = urllib.urlencode(qs_list, doseq=True)

    return urlparse.urlunsplit(url_list)


def get_contacts(args, urltype, roottype):
    """
    Get one type of contacts for OSG.
    """
    old_no_proxy = os.environ.pop('no_proxy', None)
    os.environ['no_proxy'] = '.opensciencegrid.org'

    base_url = "https://my.opensciencegrid.org/" + urltype + "summary/xml?" \
               "&active=on&active_value=1&disable=on&disable_value=0"
    with get_auth_session(args) as session:
        url = mangle_url(base_url, args, session)
        #print(url)
        response = session.get(url)

    if old_no_proxy is not None:
        os.environ['no_proxy'] = old_no_proxy
    else:
        del os.environ['no_proxy']

    if response.status_code != requests.codes.ok:
        print("MyOSG request failed (status %d): %s" % \
              (response.status_code, response.text[:2048]), file=sys.stderr)
        return None

    root = ET.fromstring(response.content)
    if root.tag != roottype + 'Summary':
        print("MyOSG returned invalid XML with root tag %s" % root.tag,
              file=sys.stderr)
        return None

    return root


def get_vo_contacts(args):
    """
    Get resource contacts for OSG.  Return results.
    """
    root = get_contacts(args, 'vo', 'VO')
    if root is None:
        return 1

    results = {}
    for child_vo in root:
        if child_vo.tag != "VO":
            print("MyOSG returned a non-VO (%s) inside summary." % \
                  root.tag, file=sys.stderr)
            return 1
        name = None
        contact_list_info = []
        for item in child_vo:
            if item.tag == 'Name':
                name = item.text
            if item.tag == "ContactTypes":
                for contact_type in item:
                    contact_list_info.extend( \
                        get_contact_list_info(contact_type))

        if name and contact_list_info:
            results[name] = contact_list_info

    return results


def get_resource_contacts_by_name_and_fqdn(args):
    """
    Get resource contacts for OSG.  Return results.

    Returns two dictionaries, one keyed on the resource name and one keyed on
    the resource FQDN.
    """
    root = get_contacts(args, 'rg', 'Resource')
    if root is None:
        return {}, {}

    results_by_name = {}
    results_by_fqdn = {}
    for child_rg in root:
        if child_rg.tag != "ResourceGroup":
            print("MyOSG returned a non-resource group (%s) inside summary." % \
                  root.tag, file=sys.stderr)
            return {}, {}
        for child_res in child_rg:
            if child_res.tag != "Resources":
                continue
            for resource in child_res:
                resource_name = None
                resource_fqdn = None
                contact_list_info = []
                for resource_tag in resource:
                    if resource_tag.tag == 'Name':
                        resource_name = resource_tag.text
                    if resource_tag.tag == 'FQDN':
                        resource_fqdn = resource_tag.text
                    if resource_tag.tag == 'ContactLists':
                        for contact_list in resource_tag:
                            if contact_list.tag == 'ContactList':
                                contact_list_info.extend( \
                                    get_contact_list_info(contact_list))

                if contact_list_info:
                    if resource_name:
                        results_by_name[resource_name] = contact_list_info
                    if resource_fqdn:
                        results_by_fqdn[resource_fqdn] = contact_list_info

    return results_by_name, results_by_fqdn


def get_resource_contacts(args):
    return get_resource_contacts_by_name_and_fqdn(args)[0]


def get_resource_contacts_by_fqdn(args):
    return get_resource_contacts_by_name_and_fqdn(args)[1]


def filter_contacts(args, results):
    """
    Given a set of result contacts, filter them according to given arguments
    """
    results = dict(results)  # make a copy so we don't modify the original

    if getattr(args, 'name_filter', None):
        # filter out undesired names
        for name in results.keys():
            if not fnmatch.fnmatch(name, args.name_filter) and \
                    args.name_filter not in name:
                del results[name]
    elif getattr(args, 'fqdn_filter', None):
        # filter out undesired FQDNs
        for fqdn in results.keys():
            if not fnmatch.fnmatch(fqdn, args.fqdn_filter) and \
                    args.fqdn_filter not in fqdn:
                del results[fqdn]

    if args.contact_type != 'all':
        # filter out undesired contact types
        for name in results.keys():
            contact_list = []
            for contact in results[name]:
                contact_type = contact['ContactType']
                if contact_type.startswith(args.contact_type):
                    contact_list.append(contact)
            if contact_list == []:
                del results[name]
            else:
                results[name] = contact_list

    return results
