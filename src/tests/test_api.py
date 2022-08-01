import re
import flask
import pytest

# Rewrites the path so the app can be imported like it normally is
import os
import sys
topdir = os.path.join(os.path.dirname(__file__), "..")
sys.path.append(topdir)

from app import app

HOST_PORT_RE = re.compile(r"[a-zA-Z0-9.-]{3,63}:[0-9]{2,5}")
PROTOCOL_HOST_PORT_RE = re.compile(r"[a-z+]://" + HOST_PORT_RE.pattern)

INVALID_USER = dict(
    username="invalid",
    password="user"
)

TEST_ENDPOINTS = [
    '/',
    '/map/iframe',
    '/miscuser/xml',
    '/nsfscience/csv',
    '/organizations',
    '/resources',
    "/collaborations/osg-scitokens-mapfile.conf",
    '/contacts',
    '/miscproject/xml',
    '/miscproject/json',
    '/miscresource/json',
    '/vosummary/xml',
    '/rgsummary/xml',
    '/rgdowntime/xml',
    '/rgdowntime/ical',
    "/stashcache/authfile",
    "/stashcache/authfile-public",
    "/stashcache/origin-authfile-public?fqdn=sc-origin2000.chtc.wisc.edu",
    "/stashcache/origin-authfile",
    "/stashcache/scitokens",
    "/oasis-managers/json",
    "/generate_downtime",
    "/generate_resource_group_downtime",
    "/cache/Authfile-public",
    "/cache/Authfile",
    "/origin/Authfile",
    "/origin/Authfile-public",
    "/origin/scitokens.conf",
    "/cache/scitokens.conf"
]


@pytest.fixture
def client():
    with app.test_client() as client:
        yield client


class TestAPI:

    def test_sanity(self, client: flask.Flask):
        response = client.get('/')
        assert response.status_code == 200

    @pytest.mark.parametrize('endpoint', TEST_ENDPOINTS)
    def test_endpoint_existence(self, endpoint, client: flask.Flask):
        response = client.get(endpoint)
        assert response.status_code != 404

    def test_cache_authfile(self, client: flask.Flask):
        resources = client.get('/miscresource/json').json
        for resource in resources.values():

            resource_fqdn = resource["FQDN"]
            previous_endpoint = client.get(f"/stashcache/authfile?cache_fqdn={resource_fqdn}")
            current_endpoint = client.get(f"/cache/Authfile?fqdn={resource_fqdn}")

            assert previous_endpoint.status_code == current_endpoint.status_code
            assert previous_endpoint.data == current_endpoint.data

    def test_cache_authfile_public(self, client: flask.Flask):
        resources = client.get('/miscresource/json').json
        for resource in resources.values():

            resource_fqdn = resource["FQDN"]
            current_endpoint = client.get(f"/cache/Authfile-public?fqdn={resource_fqdn}")
            previous_endpoint = client.get(f"/stashcache/authfile-public?cache_fqdn={resource_fqdn}")

            assert previous_endpoint.status_code == current_endpoint.status_code
            assert previous_endpoint.data == current_endpoint.data

    def test_origin_authfile(self, client: flask.Flask):
        resources = client.get('/miscresource/json').json
        for resource in resources.values():

            resource_fqdn = resource["FQDN"]
            current_endpoint = client.get(f"/origin/Authfile?fqdn={resource_fqdn}")
            previous_endpoint = client.get(f"/stashcache/origin-authfile?fqdn={resource_fqdn}")

            assert previous_endpoint.status_code == current_endpoint.status_code
            assert previous_endpoint.data == current_endpoint.data

    def test_origin_authfile_public(self, client: flask.Flask):
        resources = client.get('/miscresource/json').json
        for resource in resources.values():

            resource_fqdn = resource["FQDN"]
            current_endpoint = client.get(f"/origin/Authfile-public?fqdn={resource_fqdn}")
            previous_endpoint = client.get(f"/stashcache/origin-authfile-public?fqdn={resource_fqdn}")

            assert previous_endpoint.status_code == current_endpoint.status_code
            assert previous_endpoint.data == current_endpoint.data

    def test_cache_scitokens(self, client: flask.Flask):
        resources = client.get('/miscresource/json').json
        for resource in resources.values():

            resource_fqdn = resource["FQDN"]
            previous_endpoint = client.get(f"/stashcache/scitokens?cache_fqdn={resource_fqdn}")
            current_endpoint = client.get(f"/cache/scitokens.conf?fqdn={resource_fqdn}")

            assert previous_endpoint.status_code == current_endpoint.status_code
            assert previous_endpoint.data == current_endpoint.data

    def test_origin_scitokens(self, client: flask.Flask):
        resources = client.get('/miscresource/json').json
        for resource in resources.values():

            resource_fqdn = resource["FQDN"]
            previous_endpoint = client.get(f"/stashcache/scitokens?origin_fqdn={resource_fqdn}")
            current_endpoint = client.get(f"/origin/scitokens.conf?fqdn={resource_fqdn}")

            assert previous_endpoint.status_code == current_endpoint.status_code
            assert previous_endpoint.data == current_endpoint.data

    def test_resource_stashcache_files(self, client: flask.Flask):
        """Tests that the resource table contains the same files as the singular api outputs"""

        def test_stashcache_file(key, endpoint, fqdn, resource_stashcache_files):

            response = client.get(f"{endpoint}?fqdn={fqdn}")

            if key in resource_stashcache_files:
                assert response.status_code == 200
                assert response.data.decode() == resource_stashcache_files[key]

            else:
                assert response.status_code != 200 or not response.data

        resources = client.get('/miscresource/json').json
        resources_stashcache_files = client.get('/resources/stashcache-files').json

        # Sanity check: have a reasonable number of resources
        assert len(resources_stashcache_files) > 20

        keys_and_endpoints = [
            ("CacheAuthfilePublic",  "/cache/Authfile-public"),
            ("CacheAuthfile",        "/cache/Authfile"),
            ("CacheScitokens",       "/cache/scitokens.conf"),
            ("OriginAuthfilePublic", "/origin/Authfile-public"),
            ("OriginAuthfile",       "/origin/Authfile"),
            ("OriginScitokens",      "/origin/scitokens.conf")
        ]

        for resource_name, resource_stashcache_files in resources_stashcache_files.items():
            for key, endpoint in keys_and_endpoints:
                test_stashcache_file(key, endpoint, resources[resource_name]["FQDN"], resource_stashcache_files)

    def test_stashcache_namespaces(self, client: flask.Flask):
        def validate_cache_schema(cc):
            assert HOST_PORT_RE.match(cc["auth_endpoint"])
            assert HOST_PORT_RE.match(cc["endpoint"])
            assert HOST_PORT_RE.match(cc["resource"])

        def validate_namespace_schema(ns):
            assert isinstance(ns["caches"], list)  # we do have a case where it's empty
            assert ns["path"].startswith("/")  # implies str
            assert isinstance(ns["readhttps"], bool)
            assert isinstance(ns["usetokenonread"], bool)
            assert ns["dirlisthost"] is None or PROTOCOL_HOST_PORT_RE.match(ns["dirlisthost"])
            assert ns["writebackhost"] is None or PROTOCOL_HOST_PORT_RE.match(ns["dirlisthost"])

        response = client.get('/stashcache/namespaces')
        assert response.status_code == 200
        namespaces_json = response.json

        assert "caches" in namespaces_json
        caches = namespaces_json["caches"]
        # Have a reasonable number of caches
        assert len(caches) > 20
        for cache in caches:
            validate_cache_schema(cache)

        assert "namespaces" in namespaces_json
        namespaces = namespaces_json["namespaces"]
        # Have a reasonable number of namespaces
        assert len(namespaces) > 15

        for namespace in namespaces:
            validate_namespace_schema(namespace)
            if namespace["caches"]:
                validate_cache_schema(namespace["caches"][0])


if __name__ == '__main__':
    pytest.main()
