#!/usr/bin/env python3
"""
This script creates an API key that clients can use to access contact
information in Topology pages.
"""

import argparse
import hashlib
import os
import pathlib
import re
import sys
import urllib.request
import uuid
import xml.etree.ElementTree as ET

USERS_ENDPOINT = "https://topology.opensciencegrid.org/miscuser/xml"
VALID_API_KEY_RE = re.compile(
    r"^tk-[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
)


class NoMatch(Exception):
    pass


def get_user_info(fullname=None, id_=None, endpoint=USERS_ENDPOINT) -> tuple[str, str]:
    """
    Get the miscuser XML from Topology, look up a user by ID or FullName,
    and return a tuple containing the (FullName, ID) from Topology, or raise
    NoMatch if no record is found.

    The XML is retrieved from the URL at `endpoint` and looks something like this:
    <Users>
        <User>
            <FullName>Name Of Person</FullName>
            <ID>(either an OSG ID or a hash)</ID>
        </User>
    </Users>

    If neither fullname nor id_ are specified, ValueError will be raised.
    If both fullname and id_ are specified, looks up the record by ID and
    makes sure the FullName matches, raising a NoMatch exception if it
    does not.
    """
    if not fullname and not id_:
        raise ValueError("Either fullname or id_ must be provided")

    # Fetch the XML from the endpoint
    with urllib.request.urlopen(endpoint) as response:
        xml_data = response.read()

    # Parse the XML
    root = ET.fromstring(xml_data)

    # Search through users for a match
    for user in root.findall('User'):
        user_fullname = user.findtext('FullName', '').strip()
        user_id = user.findtext('ID', '').strip()

        if id_ and fullname:
            # Both specified: match by ID and verify FullName matches
            if user_id == id_:
                if user_fullname == fullname:
                    return (user_fullname, user_id)
                else:
                    raise NoMatch(
                        f"ID {id_} found but FullName does not match. Expected {fullname}, got {user_fullname}"
                    )
        elif id_:
            # Match by ID only
            if user_id == id_:
                return (user_fullname, user_id)
        elif fullname:
            # Match by FullName only
            if user_fullname == fullname:
                return (user_fullname, user_id)

    # No match found
    if id_ and fullname:
        raise NoMatch(f"No user found with ID {id_} and FullName {fullname}")
    elif id_:
        raise NoMatch(f"No user found with ID {id_}")
    else:
        raise NoMatch(f"No user found with FullName {fullname}")


def get_arguments():
    """
    Parses command-line arguments for generating or retrieving an API key.
    """
    parser = argparse.ArgumentParser(
        description=__doc__
    )
    parser.add_argument(
        "--outfile", default="", help="write the raw API key to this file"
    )
    parser.add_argument(
        "--keyfile",
        default="",
        help="read the API key from this file instead of generating a new one",
    )
    parser.add_argument(
        "--name", dest="fullname", default="", help="look up the contact by FullName"
    )
    parser.add_argument(
        "--id", dest="id_", metavar="ID", default="", help="look up the contact by ID"
    )
    args = parser.parse_args()
    return args


def read_api_key_from_file(keyfile: str) -> str:
    """
    Reads an API key from a specified file and validates its format.

    The function reads the contents of the given file, removes any leading or
    trailing whitespace, and validates the API key against a predefined format.
    If the file cannot be read, is empty, or the API key format is invalid,
    an error is raised.

    Args:
        keyfile (str): Path to the file containing the API key.

    Raises:
        ValueError: If the file cannot be read, is empty, or contains an invalid API key.

    Returns:
        str: The validated API key.
    """
    path = pathlib.Path(keyfile)
    try:
        key_string = path.read_text().strip()
    except OSError as exc:
        raise ValueError(f"Could not read API key file {keyfile}: {exc}") from exc

    if not key_string:
        raise ValueError(f"API key file {keyfile} is empty")

    if not VALID_API_KEY_RE.fullmatch(key_string):
        raise ValueError(f"API key file {keyfile} does not contain a valid API key")

    return key_string


def get_api_key(keyfile: str = "") -> str:
    """
    Make or read the API key
    """
    if keyfile:
        api_key = read_api_key_from_file(keyfile)
    else:
        api_key = "tk-" + str(uuid.uuid4())
        assert VALID_API_KEY_RE.fullmatch(api_key)
    return api_key


def make_key_hash(api_key: str) -> str:
    """
    Create a sha256 sum of the key that can be added to the apikeys file
    """
    hash_b = hashlib.sha256(api_key.encode())
    api_key_hash = f"sha256:{hash_b.hexdigest()}"
    return api_key_hash


def print_keys_file_block(api_key_hash: str, fullname: str, id_: str):
    """
    Print the text to include in the API_KEYS_FILE; if we have the FullName
    and ID, print the whole block; otherwise, just the APIKeyHash.
    """
    if fullname and id_:
        print(f"{id_}:")
        print(f"  FullName: {fullname}")
        print(f"  APIKeyHash: {api_key_hash}")
    else:
        print(f"APIKeyHash: {api_key_hash}")


def main() -> int:
    args = get_arguments()

    if args.fullname or args.id_:
        try:
            fullname, id_ = get_user_info(fullname=args.fullname, id_=args.id_)
        except NoMatch as err:
            print(str(err), file=sys.stderr)
            return 1
    else:
        fullname, id_ = "", ""

    try:
        api_key = get_api_key(keyfile=args.keyfile)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    api_key_hash = make_key_hash(api_key)
    print_keys_file_block(api_key_hash, fullname, id_)

    # Either write the key to a file and print the file name to console,
    # or print the key itself to console.
    # The message is written to stderr so we can redirect stdout to
    # save the API_KEYS_FILE block to a file.
    if args.outfile:
        outfile = pathlib.Path(args.outfile)
        old_umask = os.umask(0o077)
        outfile.write_text(api_key)
        os.umask(old_umask)
        print(f"\nKey written to {args.outfile}", file=sys.stderr)
    elif not args.keyfile:
        # We didn't load the key from a file, so print the generated one.
        print("\nGenerated API Key: %r" % api_key, file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
