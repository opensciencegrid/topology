import flask
import pytest
from pytest_mock import MockerFixture

# Rewrites the path so the app can be imported like it normally is
import os
import sys
topdir = os.path.join(os.path.dirname(__file__), "..")
sys.path.append(topdir)

from app import app, global_data
import stashcache

@pytest.fixture
def client():
    with app.test_client() as client:
        yield client


class TestStashcache:

    def test_allowedVO_includes_ANY_for_ligo_inclusion(self, client: flask.Flask, mocker: MockerFixture):
        spy = mocker.spy(global_data, "get_ligo_dn_list")

        stashcache.generate_cache_authfile(global_data, "osg-sunnyvale-stashcache.t2.ucsd.edu")

        assert spy.call_count == 1

    def test_allowedVO_includes_LIGO_for_ligo_inclusion(self, client: flask.Flask, mocker: MockerFixture):
        spy = mocker.spy(global_data, "get_ligo_dn_list")

        stashcache.generate_cache_authfile(global_data, "stashcache.gwave.ics.psu.edu")

        assert spy.call_count == 1

    def test_allowedVO_excludes_LIGO_and_ANY_for_ligo_inclusion(self, client: flask.Flask, mocker: MockerFixture):
        spy = mocker.spy(global_data, "get_ligo_dn_list")

        stashcache.generate_cache_authfile(global_data, "rds-cache.sdsc.edu")

        assert spy.call_count == 0

    def test_None_fdqn_isnt_error(self, client: flask.Flask):
        stashcache.generate_cache_authfile(global_data, None)


if __name__ == '__main__':
    pytest.main()
