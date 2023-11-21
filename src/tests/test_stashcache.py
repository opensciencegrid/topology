from configparser import ConfigParser
import copy
import flask
import pytest
import re
from pytest_mock import MockerFixture
import time
from typing import List, Dict
import urllib, urllib.parse

# Rewrites the path so the app can be imported like it normally is
import os
import sys

topdir = os.path.join(os.path.dirname(__file__), "..")
sys.path.append(topdir)

os.environ['TESTING'] = "True"

from app import app, global_data
from webapp import models, topology, vos_data
from webapp.common import load_yaml_file
from webapp.data_federation import CredentialGeneration
import stashcache

HOST_PORT_RE = re.compile(r"[a-zA-Z0-9.-]{3,63}:[0-9]{2,5}")
PROTOCOL_HOST_PORT_RE = re.compile(r"[a-z]+://" + HOST_PORT_RE.pattern)

GRID_MAPPING_REGEX = re.compile(r'^"(/[^"]*CN=[^"]+")\s+([0-9a-f]{8}[.]0)$')
# ^^ the DN starts with a slash and will at least have a CN in it.
EMPTY_LINE_REGEX = re.compile(r'^\s*(#|$)')  # Empty or comment-only lines
I2_TEST_CACHE = "osg-sunnyvale-stashcache.nrp.internet2.edu"
# ^^ one of the Internet2 caches; these serve both public and LIGO data
# fake origins in our test data:
TEST_ITB_HELM_ORIGIN = "helm-origin.osgdev.test.io"
TEST_SC_ORIGIN = "sc-origin.test.wisc.edu"


# Some DNs I can use for testing and the hashes they map to.
# All of these were generated with osg-ca-generator on alma8
#   openssl x509 -in /etc/grid-security/hostcert.pem -noout -subject -nameopt compat
# I got the hashes from a previous run of the test.
MOCK_DNS_AND_HASHES = {
    "/DC=org/DC=opensciencegrid/C=US/O=OSG Software/OU=Services/CN=testhost1": "f7d78bab.0",
    "/DC=org/DC=opensciencegrid/C=US/O=OSG Software/OU=Services/CN=testhost2": "941f0a37.0",
    "/DC=org/DC=opensciencegrid/C=US/O=OSG Software/OU=Services/CN=testhost3": "77934f6c.0",
    "/DC=org/DC=opensciencegrid/C=US/O=OSG Software/OU=Services/CN=testhost4": "def5b9bc.0",
    "/DC=org/DC=opensciencegrid/C=US/O=OSG Software/OU=Services/CN=testhost5": "83a7951b.0",
}

MOCK_DN_LIST = list(MOCK_DNS_AND_HASHES.keys())


@pytest.fixture
def test_global_data() -> models.GlobalData:
    """Get a copy of the global data with some entries created for testing"""
    new_global_data = copy.deepcopy(global_data)

    # Start with a fully populated set of topology data
    topo = new_global_data.get_topology()
    assert isinstance(topo, topology.Topology), "Unable to get Topology data"

    # Add our testing RG
    testrg = load_yaml_file(topdir + "/tests/data/testrg.yaml")
    topo.add_rg("University of Wisconsin", "CHTC", "testrg", testrg)

    # Put it back into global_data2 and make sure it doesn't get overwritten by future calls
    new_global_data.topology.data = topo
    new_global_data.topology.next_update = time.time() + 999999

    # Start with a fully populated set of VO data
    vos = new_global_data.get_vos_data()
    assert isinstance(vos, vos_data.VOsData), "Unable to get VO data"

    # Load our testing VO
    testvo = load_yaml_file(topdir + "/tests/data/testvo.yaml")
    vos.add_vo("testvo", testvo)

    # Put it back into global_data2 and make sure it doesn't get overwritten by future calls
    new_global_data.vos_data.data = vos
    new_global_data.vos_data.next_update = time.time() + 999999

    return new_global_data


@pytest.fixture
def client():
    with app.test_client() as client:
        yield client


class TestStashcache:

    def test_allowedVO_includes_ANY_for_ligo_inclusion(self, client: flask.Flask, mocker: MockerFixture):
        spy = mocker.spy(global_data, "get_ligo_dn_list")

        stashcache.generate_cache_authfile(global_data, "osg-sunnyvale-stashcache.nrp.internet2.edu")

        assert spy.call_count == 5

    def test_allowedVO_includes_LIGO_for_ligo_inclusion(self, client: flask.Flask, mocker: MockerFixture):
        spy = mocker.spy(global_data, "get_ligo_dn_list")

        stashcache.generate_cache_authfile(global_data, "stashcache.gwave.ics.psu.edu")

        assert spy.call_count == 5

    def test_allowedVO_excludes_LIGO_and_ANY_for_ligo_inclusion(self, client: flask.Flask, mocker: MockerFixture):
        spy = mocker.spy(global_data, "get_ligo_dn_list")

        stashcache.generate_cache_authfile(global_data, "rds-cache.sdsc.edu")

        assert spy.call_count == 0

    def test_scitokens_issuer_sections(self, test_global_data):
        origin_scitokens_conf = stashcache.generate_origin_scitokens(
            test_global_data, TEST_ITB_HELM_ORIGIN)
        assert origin_scitokens_conf.strip(), "Generated scitokens.conf empty"

        cp = ConfigParser()
        cp.read_string(origin_scitokens_conf, "origin_scitokens.conf")

        try:
            assert "Global" in cp, "Missing Global section"
            assert "Issuer https://test.wisc.edu" in cp, \
                "Issuer missing"
            assert "Issuer https://test.wisc.edu/issuer2" in cp, \
                "Issuer 2 missing"
            assert "base_path" in cp["Issuer https://test.wisc.edu/issuer2"], \
                "Issuer 2 base_path missing"
            assert cp["Issuer https://test.wisc.edu/issuer2"]["base_path"] == "/testvo/issuer2test", \
                "Issuer 2 has wrong base path"
        except AssertionError:
            print(f"Generated origin scitokens.conf text:\n{origin_scitokens_conf}\n", file=sys.stderr)
            raise

    def test_scitokens_issuer_public_read_auth_write_namespaces_info(self, test_global_data):
        namespaces_json = stashcache.get_namespaces_info(test_global_data)
        namespaces = namespaces_json["namespaces"]
        testvo_PUBLIC_namespace_list = [
            ns for ns in namespaces if ns.get("path") == "/testvo/PUBLIC"
        ]
        assert testvo_PUBLIC_namespace_list, "/testvo/PUBLIC namespace not found"
        ns = testvo_PUBLIC_namespace_list[0]
        assert ns["usetokenonread"] is False, \
            "usetokenonread is wrong for public namespace"
        assert ns["readhttps"] is False, \
            "readhttps is wrong for public namespace"
        assert ns["writebackhost"] == f"https://{TEST_SC_ORIGIN}:1095", \
            "writebackhost is wrong for namespace with auth write"

    def test_scitokens_issuer_public_read_auth_write_scitokens_conf(self, test_global_data):
        origin_scitokens_conf = stashcache.generate_origin_scitokens(
            test_global_data, TEST_SC_ORIGIN)
        assert origin_scitokens_conf.strip(), "Generated scitokens.conf empty"

        cp = ConfigParser()
        cp.read_string(origin_scitokens_conf, "origin_scitokens.conf")
        try:
            assert "Global" in cp, "Missing Global section"
            assert "Issuer https://test.wisc.edu" in cp, \
                "Expected issuer missing"
            assert "base_path" in cp["Issuer https://test.wisc.edu"], \
                "'Issuer https://test.wisc.edu' section missing expected attribute"
            assert cp["Issuer https://test.wisc.edu"]["base_path"] == "/testvo", \
                "'Issuer https://test.wisc.edu' section has wrong base path"
        except AssertionError:
            print(f"Generated origin scitokens.conf text:\n{origin_scitokens_conf}\n", file=sys.stderr)
            raise

    def test_None_fdqn_isnt_error(self, client: flask.Flask):
        stashcache.generate_cache_authfile(global_data, None)

    def test_origin_grid_mapfile_nohost(self, client: flask.Flask):
        text = stashcache.generate_origin_grid_mapfile(global_data, "", suppress_errors=False)
        for line in text.split("\n"):
            assert EMPTY_LINE_REGEX.match(line), f'Unexpected text "{line}".\nFull text:\n{text}\n'

    def test_origin_grid_mapfile_with_host(self, client: flask.Flask):
        text = stashcache.generate_origin_grid_mapfile(global_data, "origin-auth2001.chtc.wisc.edu",
                                                       suppress_errors=False)
        num_mappings = 0
        for line in text.split("\n"):
            if EMPTY_LINE_REGEX.match(line):
                continue
            elif GRID_MAPPING_REGEX.match(line):
                num_mappings += 1
            else:
                assert False, f'Unexpected text "{line}".\nFull text:\n{text}\n'
        assert num_mappings > 5, f"Too few mappings found.\nFull text:\n{text}\n"

    def test_cache_grid_mapfile_nohost(self, client: flask.Flask):
        text = stashcache.generate_cache_grid_mapfile(global_data, "", legacy=False, suppress_errors=False)

        for line in text.split("\n"):
            if EMPTY_LINE_REGEX.match(line):
                continue
            mm = GRID_MAPPING_REGEX.match(line)
            if mm:
                dn = mm.group(1)
                if "CN=Brian Paul Bockelman" in dn or "CN=Matyas Selmeci A148276" in dn or "CN=Judith Lorraine Stephen" in dn:
                    # HACK: these three have their FQANs explicitly allowed in some namespaces so it's OK
                    # for them to show up in grid-mapfiles even without an FQDN
                    continue
                else:
                    assert False, f'Unexpected text "{line}".\nFull text:\n{text}\n'
            else:
                assert False, f'Unexpected text "{line}".\nFull text:\n{text}\n'

    def test_cache_grid_mapfile_i2_cache(self, client: flask.Flask, mocker: MockerFixture):
        mocker.patch.object(global_data, "get_ligo_dn_list", return_value=MOCK_DN_LIST, autospec=True)
        text = stashcache.generate_cache_grid_mapfile(global_data,
                                                      I2_TEST_CACHE,
                                                      legacy=True,
                                                      suppress_errors=False)
        num_mappings = 0
        for line in text.split("\n"):
            if EMPTY_LINE_REGEX.match(line):
                continue
            elif GRID_MAPPING_REGEX.match(line):
                num_mappings += 1
            else:
                assert False, f'Unexpected text "{line}".\nFull text:\n{text}\n'
        assert num_mappings > 5, f"Too few mappings found.\nFull text:\n{text}\n"


class TestNamespaces:
    @pytest.fixture
    def namespaces_json(self, test_global_data) -> Dict:
        return stashcache.get_namespaces_info(test_global_data)

    @pytest.fixture
    def namespaces(self, namespaces_json) -> List[Dict]:
        assert "namespaces" in namespaces_json
        return namespaces_json["namespaces"]

    @staticmethod
    def validate_cache_schema(cc):
        assert HOST_PORT_RE.match(cc["auth_endpoint"])
        assert HOST_PORT_RE.match(cc["endpoint"])
        assert cc["resource"] and isinstance(cc["resource"], str)

    @staticmethod
    def validate_namespace_schema(ns):
        assert isinstance(ns["caches"], list)  # we do have a case where it's empty
        assert ns["path"].startswith("/")  # implies str
        assert isinstance(ns["readhttps"], bool)
        assert isinstance(ns["usetokenonread"], bool)
        assert ns["dirlisthost"] is None or PROTOCOL_HOST_PORT_RE.match(ns["dirlisthost"])
        assert ns["writebackhost"] is None or PROTOCOL_HOST_PORT_RE.match(ns["writebackhost"])
        credgen = ns["credential_generation"]
        if credgen is not None:
            assert isinstance(credgen["max_scope_depth"], int) and credgen["max_scope_depth"] > -1
            assert credgen["strategy"] in CredentialGeneration.STRATEGIES
            assert credgen["issuer"]
            parsed_issuer = urllib.parse.urlparse(credgen["issuer"])
            assert parsed_issuer.netloc and parsed_issuer.scheme == "https"
            if credgen["vault_server"]:
                assert isinstance(credgen["vault_server"], str)
            if credgen["vault_issuer"]:
                assert isinstance(credgen["vault_issuer"], str)
            if credgen["base_path"]:
                assert isinstance(credgen["base_path"], str)

    def test_caches(self, namespaces_json):
        assert "caches" in namespaces_json
        caches = namespaces_json["caches"]
        # Have a reasonable number of caches
        assert len(caches) > 20
        for cache in caches:
            self.validate_cache_schema(cache)

    def test_namespaces(self, namespaces):
        # Have a reasonable number of namespaces
        assert len(namespaces) > 15

        found_credgen = False
        for namespace in namespaces:
            if namespace["credential_generation"] is not None:
                found_credgen = True
            self.validate_namespace_schema(namespace)
            if namespace["caches"]:
                for cache in namespace["caches"]:
                    self.validate_cache_schema(cache)
        assert found_credgen, "At least one namespace with credential_generation"

    @staticmethod
    def validate_scitokens_block(sci):
        assert sci["issuer"]
        assert isinstance(sci["issuer"], str)
        assert "://" in sci["issuer"]
        assert isinstance(sci["basepath"], list)
        assert sci["basepath"]  # must have at least 1
        for bp in sci["basepath"]:
            assert bp.startswith("/")  # implies str
            assert "," not in bp
        assert isinstance(sci["restrictedpath"], list)
        for rp in sci["restrictedpath"]:  # may be empty
            assert rp.startswith("/")  # implies str
            assert "," not in rp

    def test_issuers_in_namespaces(self, namespaces):
        for namespace in namespaces:
            assert isinstance(namespace["scitokens"], list)
            for scitokens_block in namespace["scitokens"]:
                self.validate_scitokens_block(scitokens_block)


if __name__ == '__main__':
    pytest.main()
