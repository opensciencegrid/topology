# config file for CI testing development


import os

# The parent directory of this file, i.e. the current checkout:
TOPOLOGY_DATA_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# If you use this checkout for TOPOLOGY_DATA_DIR, be sure to set NO_GIT=True,
# otherwise your changes will get blown away!
NO_GIT = True

# test_verify_schema.sh might have checked this out
if os.path.exists("/tmp/contact/contacts.yaml"):
    CONTACT_DATA_DIR = "/tmp/contact"
else:
    CONTACT_DATA_DIR = None

TOPOLOGY_CACHE_LIFETIME = 999
CONTACT_CACHE_LIFETIME = 999

INSTANCE_NAME = "CI testing"

# Set this to False to skip querying LIGO's LDAP servers when generating
# StashCache information.
STASHCACHE_LEGACY_AUTH = False

import logging
LOGLEVEL = logging.DEBUG  # flask's default is WARNING

# Be authorized.  Does nothing if you don't have any contacts data.
AUTH = True
