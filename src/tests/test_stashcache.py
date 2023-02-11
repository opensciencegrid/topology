import flask
import pytest
import re
from pytest_mock import MockerFixture

# Rewrites the path so the app can be imported like it normally is
import os
import sys

topdir = os.path.join(os.path.dirname(__file__), "..")
sys.path.append(topdir)

from app import app, global_data
import stashcache

GRID_MAPPING_REGEX = re.compile(r'^"(/[^"]*CN=[^"]+")\s+([0-9a-f]{8}[.]0)$')
# ^^ the DN starts with a slash and will at least have a CN in it.
EMPTY_LINE_REGEX = re.compile(r'^\s*(#|$)')  # Empty or comment-only lines
I2_TEST_CACHE = "osg-sunnyvale-stashcache.t2.ucsd.edu"
# ^^ one of the Internet2 caches; these serve both public and LIGO data


# Some DNs I can use for testing and the hashes they map to.
# All of these were generated with osg-ca-generator on alma8 and printed with
#   openssl x509 -in /etc/grid-security/hostcert.pem -noout -subject -subject_hash_old -nameopt compat
# (trailing ".0" added by hand)
MOCK_DNS_AND_HASHES = {
    "/DC=org/DC=opensciencegrid/C=US/O=OSG Software/OU=Services/CN=testhost1": "d460d8b7.0",
    "/DC=org/DC=opensciencegrid/C=US/O=OSG Software/OU=Services/CN=testhost2": "23c91cd1.0",
    "/DC=org/DC=opensciencegrid/C=US/O=OSG Software/OU=Services/CN=testhost3": "fd626fa1.0",
    "/DC=org/DC=opensciencegrid/C=US/O=OSG Software/OU=Services/CN=testhost4": "cc84ae86.0",
    "/DC=org/DC=opensciencegrid/C=US/O=OSG Software/OU=Services/CN=testhost5": "8967f473.0",
}

MOCK_DN_LIST = list(MOCK_DNS_AND_HASHES.keys())


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

    def test_origin_grid_mapfile(self, client: flask.Flask):
        nohost_text = stashcache.generate_origin_grid_mapfile(global_data, "", suppress_errors=False)
        for line in nohost_text.split("\n"):
            assert EMPTY_LINE_REGEX.match(line)

        test_origin_text = stashcache.generate_origin_grid_mapfile(global_data, "origin-auth2001.chtc.wisc.edu",
                                                                   suppress_errors=False)
        num_mappings = 0
        for line in test_origin_text.split("\n"):
            if EMPTY_LINE_REGEX.match(line):
                continue
            elif GRID_MAPPING_REGEX.match(line):
                num_mappings += 1
            else:
                assert False, 'Unexpected text "%s".\nFull text:\n%s' % (line, test_origin_text)
        assert num_mappings > 5, "Too few mappings found.\nFull text:\n%s" % test_origin_text

    def test_cache_authfile(self, client: flask.Flask, mocker: MockerFixture):
        m = mocker.patch.object(global_data, "get_ligo_dn_list", spec={"return_value": MOCK_DN_LIST})
        text = stashcache.generate_cache_authfile(
            global_data,
            I2_TEST_CACHE,
            legacy=True,
            suppress_errors=False,
        )

        assert False, f"Cache authfile dump:\n{text}"

    def test_cache_grid_mapfile(self, client: flask.Flask, mocker: MockerFixture):
        nohost_text = stashcache.generate_cache_grid_mapfile(global_data, "", legacy=False, suppress_errors=False)
        for line in nohost_text.split("\n"):
            if EMPTY_LINE_REGEX.match(line):
                continue
            mm = GRID_MAPPING_REGEX.match(line)
            if mm:
                dn = mm.group(1)
                if "CN=Brian Paul Bockelman" in dn or "CN=Matyas Selmeci A148276" in dn:
                    # HACK: these two have their FQANs explicitly allowed in some namespaces so it's OK
                    # for them to show up in grid-mapfiles even without an FQDN
                    continue
                else:
                    assert False, 'Unexpected text "%s".\nFull text:\n%s' % (line, nohost_text)
            else:
                assert False, 'Unexpected text "%s".\nFull text:\n%s' % (line, nohost_text)

        m = mocker.patch.object(global_data, "get_ligo_dn_list", spec={"return_value": MOCK_DN_LIST})
        test_cache_text = stashcache.generate_cache_grid_mapfile(global_data,
                                                                 I2_TEST_CACHE,
                                                                 legacy=True,
                                                                 suppress_errors=False)
        num_mappings = 0
        for line in test_cache_text.split("\n"):
            if EMPTY_LINE_REGEX.match(line):
                continue
            elif GRID_MAPPING_REGEX.match(line):
                num_mappings += 1
            else:
                assert False, 'Unexpected text "%s".\nFull text:\n%s' % (line, test_cache_text)
        assert num_mappings > 5, "Too few mappings found.\nFull text:\n%s" % test_cache_text


if __name__ == '__main__':
    pytest.main()
