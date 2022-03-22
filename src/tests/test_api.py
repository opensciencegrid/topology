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
    "/cache-authfile",
    "/cache-authfile-public",
    "/scitokens-cache",
    "/scitokens-origin",
    "/stashcache/authfile",
    "/stashcache/authfile-public",
    "/stashcache/origin-authfile-public?fqdn=sc-origin2000.chtc.wisc.edu",
    "/stashcache/origin-authfile",
    "/stashcache/scitokens",
    "/oasis-managers/json",
    "/generate_downtime",
    "/generate_resource_group_downtime"
]


@pytest.fixture
def client():
    with app.test_client() as client:
        yield client


class TestLogin:

    def test_sanity(self, client: flask.Flask):
        response = client.get('/')
        assert response.status_code == 200

    @pytest.mark.parametrize('endpoint', TEST_ENDPOINTS)
    def test_endpoint_existence(self, endpoint, client: flask.Flask):
        response = client.get(endpoint)
        assert response.status_code != 404

    def test_cache_authfile_equals_authfile(self, client: flask.Flask):
        cache_authfile = client.get('/cache-authfile')
        authfile = client.get("/stashcache/authfile")
        assert cache_authfile.data == authfile.data

    def test_cache_authfile_public_equals_authfile_public(self, client: flask.Flask):
        cache_authfile_public = client.get('/cache-authfile-public')
        authfile_public = client.get("/stashcache/authfile-public")
        assert cache_authfile_public.data == authfile_public.data

    def test_scitokens_cache_equals_origin_authfile_public(self, client: flask.Flask):
        scitokens_cache = client.get('/scitokens-cache')
        origin_authfile_public = client.get("/stashcache/origin-authfile-public")
        assert scitokens_cache.data == origin_authfile_public.data

    def test_scitokens_origin_equals_origin_authfile(self, client: flask.Flask):
        scitokens_origin = client.get('/scitokens-origin')
        origin_authfile = client.get("/stashcache/origin-authfile")
        assert scitokens_origin.data == origin_authfile.data

if __name__ == '__main__':
    pytest.main()
