import logging
import os
import sys
import warnings
from typing import Generator

import pytest
from flask.testing import FlaskClient
from pytest_mock import MockerFixture

# Rewrites the path so the app can be imported like it normally is

topdir = os.path.join(str(os.path.dirname(__file__)), "..")
sys.path.append(topdir)

os.environ["TESTING"] = "True"

# Third-party deprecation from python-dateutil under Python 3.12;
# we do not control that dependency's internal datetime usage in these tests.
warnings.filterwarnings(
    "ignore",
    message=r"datetime\.datetime\.utcfromtimestamp\(\) is deprecated.*",
    category=DeprecationWarning,
    module=r"dateutil\.tz\.tz",
)

from app import app, global_data
from webapp.common import API_KEY_RE, token_to_apikeyhash
from webapp.contacts_reader import ContactsData

_TESTCONTACT_YAML = os.path.join(str(os.path.dirname(__file__)), "data", "testcontact.yaml")


def _testtoken(suffix: str = "0"):
    """
    Return a token in the correct format with the given suffix.
    The suffix must be 0-12 lowercase hex digits.
    """
    return "tk-aaaaaaaa-bbbb-cccc-dddd-%s" % suffix.zfill(12)


TEST_TOKEN = _testtoken("1")
UNKNOWN_TOKEN = _testtoken("0")

assert API_KEY_RE.fullmatch(TEST_TOKEN), "TEST_TOKEN %r does not match pattern" % TEST_TOKEN
assert API_KEY_RE.fullmatch(UNKNOWN_TOKEN), "UNKNOWN_TOKEN %r does not match pattern" % UNKNOWN_TOKEN

_TEST_DN = "/DC=org/DC=opensciencegrid/O=Open Science Grid/OU=Services/CN=test-host.example.com"


@pytest.fixture
def client() -> Generator[FlaskClient, None, None]:
    with app.test_client() as client:
        yield client


class TestApiKeyAuth:
    """Tests for the Bearer-token auth path in _get_authorized()."""

    @pytest.fixture
    def mock_api_keys(self, mocker: MockerFixture):
        """Patch get_api_keys to return {hash: owner} and disable the CI AUTH bypass."""
        from webapp.common import load_yaml_file

        contacts_data = ContactsData(load_yaml_file(_TESTCONTACT_YAML))
        mocker.patch.object(
            global_data,
            "get_api_keys",
            return_value={token_to_apikeyhash(TEST_TOKEN): "Alex Jordan Morgan"},
        )
        mocker.patch.object(global_data, "get_contacts_data", return_value=contacts_data)
        mocker.patch("app.default_authorized", False)

    @staticmethod
    def dn_auth_environ(dn: str) -> dict:
        """Return an environ_base dict that injects a GRST DN credential."""
        return {"GRST_CRED_AURI_0": "dn:" + dn}

    # ------------------------------------------------------------------
    # _get_authorized() parser tests (black-box via /miscuser/xml)
    # ------------------------------------------------------------------

    def test_valid_bearer_token_authorizes(
        self, client: FlaskClient, mocker: MockerFixture, mock_api_keys
    ):
        """A correct Bearer token causes the route to behave as authorized."""
        response = client.get(
            "/miscuser/xml", headers={"Authorization": f"Bearer {TEST_TOKEN}"}
        )
        assert response.status_code == 200
        assert b"<ContactInformation>" in response.data

    def test_empty_bearer_token_returns_401(
        self, client: FlaskClient, mocker: MockerFixture, mock_api_keys
    ):
        """Empty token -> 401."""
        headers = {"Authorization": "Bearer "}
        response = client.get("/miscuser/xml", headers=headers)
        assert response.status_code == 401
        assert b"<ContactInformation>" not in response.data

    def test_invalid_non_empty_bearer_returns_401(
        self, client: FlaskClient, mocker: MockerFixture, mock_api_keys
    ):
        response = client.get(
            "/miscuser/xml", headers={"Authorization": f"Bearer {UNKNOWN_TOKEN}"}
        )
        assert response.status_code == 401
        assert b"<ContactInformation>" not in response.data

    def test_query_param_token_does_not_authorize(
        self, client: FlaskClient, mocker: MockerFixture, mock_api_keys
    ):
        """Token in the query string (not the Authorization header) does not grant access."""
        response = client.get(f"/miscuser/xml?token={TEST_TOKEN}")
        assert response.status_code == 200
        assert b"<ContactInformation>" not in response.data

    def test_valid_dn_with_bad_bearer_is_unauthorized(
        self, client: FlaskClient, mocker: MockerFixture, mock_api_keys
    ):
        """An invalid non-empty Bearer token fails auth and does not fall back to DN."""
        mocker.patch.object(global_data, "get_dns", return_value={_TEST_DN})
        response = client.get(
            "/miscuser/xml",
            headers={"Authorization": f"Bearer {UNKNOWN_TOKEN}"},
            environ_base=self.dn_auth_environ(_TEST_DN),
        )
        assert response.status_code == 401
        assert b"<ContactInformation>" not in response.data

    def test_no_bearer_with_valid_dn_falls_back_to_dn_auth(
        self, client: FlaskClient, mocker: MockerFixture, mock_api_keys
    ):
        """No Bearer token should allow DN fallback to authorize."""
        mocker.patch.object(global_data, "get_dns", return_value={_TEST_DN})
        response = client.get(
            "/miscuser/xml",
            environ_base=self.dn_auth_environ(_TEST_DN),
        )
        assert response.status_code == 200
        assert b"<ContactInformation>" in response.data

    def test_none_api_keys_with_valid_header_is_401(
        self, client: FlaskClient, mocker: MockerFixture
    ):
        """When get_api_keys() returns None, a valid-looking Bearer token is rejected with 401."""
        mocker.patch.object(global_data, "get_api_keys", return_value=None)
        mocker.patch("app.default_authorized", False)
        response = client.get(
            "/miscuser/xml", headers={"Authorization": f"Bearer {TEST_TOKEN}"}
        )
        assert response.status_code == 401
        assert b"<ContactInformation>" not in response.data

    # ------------------------------------------------------------------
    # Route deny-path (no auth headers, default_authorized=False)
    # ------------------------------------------------------------------

    def test_miscuser_xml_deny_omits_contact_information(
        self, client: FlaskClient, mocker: MockerFixture
    ):
        mocker.patch("app.default_authorized", False)
        mocker.patch.object(global_data, "get_api_keys", return_value=set())
        response = client.get("/miscuser/xml")
        assert response.status_code == 200
        assert b"<ContactInformation>" not in response.data
        assert "private" in response.headers.get("Cache-Control", "")

    def test_contacts_deny_omits_email_and_phone(
        self, client: FlaskClient, mocker: MockerFixture
    ):
        mocker.patch("app.default_authorized", False)
        mocker.patch.object(global_data, "get_api_keys", return_value=set())
        response = client.get("/contacts")
        assert response.status_code == 200
        assert b"PrimaryEmail" not in response.data
        assert "private" in response.headers.get("Cache-Control", "")

    def test_oasis_managers_deny_returns_403(
        self, client: FlaskClient, mocker: MockerFixture
    ):
        mocker.patch("app.default_authorized", False)
        mocker.patch.object(global_data, "get_api_keys", return_value=set())
        response = client.get("/oasis-managers/json?vo=CMS")
        assert response.status_code == 403
        assert "private" in response.headers.get("Cache-Control", "")

    def test_vosummary_xml_deny_omits_email(
        self, client: FlaskClient, mocker: MockerFixture
    ):
        mocker.patch("app.default_authorized", False)
        mocker.patch.object(global_data, "get_api_keys", return_value=set())
        response = client.get("/vosummary/xml")
        assert response.status_code == 200
        assert b"<Email>" not in response.data

    # ------------------------------------------------------------------
    # Route allow-path equivalence: DN auth == Bearer token auth
    # ------------------------------------------------------------------

    def test_miscuser_xml_dn_and_bearer_expose_same_fields(
        self, client: FlaskClient, mocker: MockerFixture, mock_api_keys
    ):
        mocker.patch.object(global_data, "get_dns", return_value={_TEST_DN})
        resp_dn = client.get(
            "/miscuser/xml", environ_base=self.dn_auth_environ(_TEST_DN)
        )
        resp_bearer = client.get(
            "/miscuser/xml", headers={"Authorization": f"Bearer {TEST_TOKEN}"}
        )
        dn_has_ci = b"<ContactInformation>" in resp_dn.data
        bearer_has_ci = b"<ContactInformation>" in resp_bearer.data
        assert dn_has_ci == bearer_has_ci

    def test_contacts_dn_and_bearer_expose_same_fields(
        self, client: FlaskClient, mocker: MockerFixture, mock_api_keys
    ):
        mocker.patch.object(global_data, "get_dns", return_value={_TEST_DN})
        resp_dn = client.get("/contacts", environ_base=self.dn_auth_environ(_TEST_DN))
        resp_bearer = client.get(
            "/contacts", headers={"Authorization": f"Bearer {TEST_TOKEN}"}
        )
        dn_has_email = b"PrimaryEmail" in resp_dn.data
        bearer_has_email = b"PrimaryEmail" in resp_bearer.data
        assert dn_has_email == bearer_has_email

    def test_oasis_managers_dn_and_bearer_both_200(
        self, client: FlaskClient, mocker: MockerFixture, mock_api_keys
    ):
        mocker.patch.object(global_data, "get_dns", return_value={_TEST_DN})
        mocker.patch("app.get_oasis_manager_endpoint_info", return_value=[])
        mocker.patch("app.cilogon_pass", b"dummy")
        resp_dn = client.get(
            "/oasis-managers/json?vo=CMS", environ_base=self.dn_auth_environ(_TEST_DN)
        )
        resp_bearer = client.get(
            "/oasis-managers/json?vo=CMS",
            headers={"Authorization": f"Bearer {TEST_TOKEN}"},
        )
        assert resp_dn.status_code == 200
        assert resp_bearer.status_code == 200

    def test_vosummary_xml_dn_and_bearer_expose_same_fields(
        self, client: FlaskClient, mocker: MockerFixture, mock_api_keys
    ):
        mocker.patch.object(global_data, "get_dns", return_value={_TEST_DN})
        resp_dn = client.get(
            "/vosummary/xml", environ_base=self.dn_auth_environ(_TEST_DN)
        )
        resp_bearer = client.get(
            "/vosummary/xml", headers={"Authorization": f"Bearer {TEST_TOKEN}"}
        )
        dn_has_email = b"<Email>" in resp_dn.data
        bearer_has_email = b"<Email>" in resp_bearer.data
        assert dn_has_email == bearer_has_email

    # ------------------------------------------------------------------
    # Log redaction tests
    # ------------------------------------------------------------------

    def test_successful_bearer_logs_hash_prefix_and_owner(
        self, client: FlaskClient, mocker: MockerFixture, mock_api_keys, caplog
    ):
        """Successful auth logs a hash prefix and the owner name but not the raw token."""
        _ = mocker, mock_api_keys
        token_hash = token_to_apikeyhash(TEST_TOKEN)
        with caplog.at_level(logging.INFO, logger="app"):
            client.get(
                "/miscuser/xml", headers={"Authorization": f"Bearer {TEST_TOKEN}"}
            )
        assert token_hash[7:15] in caplog.text
        assert "Alex Jordan Morgan" in caplog.text
        assert TEST_TOKEN not in caplog.text

    def test_rejected_bearer_logs_hash_prefix_only(
        self, client: FlaskClient, mocker: MockerFixture, mock_api_keys, caplog
    ):
        """Rejected auth logs a hash prefix but not the raw token."""
        _ = mocker, mock_api_keys
        token_hash = token_to_apikeyhash(UNKNOWN_TOKEN)
        with caplog.at_level(logging.DEBUG, logger="app"):
            client.get(
                "/miscuser/xml", headers={"Authorization": f"Bearer {UNKNOWN_TOKEN}"}
            )
        assert token_hash[7:15] in caplog.text
        assert UNKNOWN_TOKEN not in caplog.text


if __name__ == "__main__":
    pytest.main()
