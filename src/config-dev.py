# config file for local development
#
# Uses the local topology checkout to source the data from.
# Copy this to "config.py" to configure the webapp when doing local development.


import os

# The parent directory of this file, i.e. the current checkout:
TOPOLOGY_DATA_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# If you use this checkout for TOPOLOGY_DATA_DIR, be sure to set NO_GIT=True,
# otherwise your changes will get blown away!
NO_GIT = True


# If you have access to contact DB, point this to a checkout of it.
CONTACT_DATA_DIR = None

# Load topology data every 60 seconds:
TOPOLOGY_CACHE_LIFETIME = 60
# Load contact data every 6 seconds:
CONTACT_CACHE_LIFETIME = 6

INSTANCE_NAME = "local test"  # leave blank for production

# Set this to False to skip querying LIGO's LDAP servers when generating
# StashCache information.
STASHCACHE_LEGACY_AUTH = True

# import logging
# LOGLEVEL = logging.DEBUG  # flask's default is WARNING

# Be authorized.  Does nothing if you don't have any contacts data.
AUTH = True
