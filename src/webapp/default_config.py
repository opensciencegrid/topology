GIT_SSH_KEY = None

TOPOLOGY_DATA_DIR = "/tmp/topology/topology"
TOPOLOGY_DATA_REPO = "https://github.com/opensciencegrid/topology"
TOPOLOGY_DATA_BRANCH = "master"
TOPOLOGY_CACHE_LIFETIME = 60 * 15

WEBHOOK_DATA_DIR = "/tmp/topology-webhook/topology.git"
WEBHOOK_DATA_REPO = "https://github.com/opensciencegrid/topology"

CONTACT_DATA_DIR = "/tmp/topology/contact"
CONTACT_DATA_REPO = "git@bitbucket.org:opensciencegrid/contact.git"
CONTACT_DATA_BRANCH = "master"
CONTACT_CACHE_LIFETIME = 60 * 5

CACHE_LIFETIME = 60 * 15

NO_GIT = False

INSTANCE_NAME = ""  # leave blank for production

# LIGO's StashCache setup contains a long list of DNs we must generate
# by querying their LDAP server; set this to False to skip this query.
STASHCACHE_LEGACY_AUTH = True

# import logging
# LOGLEVEL = logging.DEBUG  # flask's default is WARNING

