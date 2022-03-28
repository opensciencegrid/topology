import flask
import pytest

# Rewrites the path so the app can be imported like it normally is
import os
import sys
topdir = os.path.join(os.path.dirname(__file__), "..")
sys.path.append(topdir)

from app import app

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
            previous_endpoint = client.get(f"/cache/Authfile?fqdn={resource_fqdn}")
            current_endpoint = client.get(f"/stashcache/authfile?cache_fqdn={resource_fqdn}")

            assert previous_endpoint.status_code == current_endpoint.status_code
            assert previous_endpoint.data == current_endpoint.data

    def test_cache_authfile_public(self, client: flask.Flask):
        resources = client.get('/miscresource/json').json
        for resource in resources.values():

            resource_fqdn = resource["FQDN"]
            previous_endpoint = client.get(f"/cache/Authfile-public?fqdn={resource_fqdn}")
            current_endpoint = client.get(f"/stashcache/authfile-public?cache_fqdn={resource_fqdn}")

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

if __name__ == '__main__':
    pytest.main()
