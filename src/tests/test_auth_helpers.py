"""
Unit tests for API key loading and GlobalData API key caching behavior.
"""
import pytest
import warnings
from unittest.mock import MagicMock, patch
import yaml

import os
import sys

topdir = os.path.join(str(os.path.dirname(__file__)), "..")
sys.path.insert(0, topdir)

os.environ.setdefault('TESTING', 'True')

# Third-party deprecation from python-dateutil under Python 3.12;
# we do not control that dependency's internal datetime usage in these tests.
warnings.filterwarnings(
    "ignore",
    message=r"datetime\.datetime\.utcfromtimestamp\(\) is deprecated.*",
    category=DeprecationWarning,
    module=r"dateutil\.tz\.tz",
)

from webapp.common import token_to_apikeyhash
from webapp.contacts_reader import ContactsData, get_api_keys_data
from webapp.models import GlobalData, CachedData


# ---------------------------------------------------------------------------
# Minimal YAML-dict helpers
# ---------------------------------------------------------------------------


def _make_user_yaml(full_name="Test User", email="test@example.com"):
    """Return a minimal user YAML dict."""
    data = {
        "FullName": full_name,
        "ContactInformation": {
            "PrimaryEmail": email,
        },
    }
    return data


def _make_contacts_data_by_id(raw):
    """Build a ContactsData from a mapping of contact_id -> yaml_data."""
    return ContactsData(raw)


def _write_api_keys_file(tmp_path, data):
    path = tmp_path / "api-keys.yaml"
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    return str(path)


def _testtoken(suffix: str = "0"):
    """
    Return a token in the correct format with the given suffix.
    The suffix must be 0-12 lowercase hex digits.
    """
    return "tk-aaaaaaaa-bbbb-cccc-dddd-%s" % suffix.zfill(12)


# ---------------------------------------------------------------------------
# contacts_reader.get_api_keys_data() tests
# ---------------------------------------------------------------------------

class TestGetApiKeysData:

    def test_returns_hash_to_name_mapping(self, tmp_path):
        hash_a = token_to_apikeyhash(_testtoken("a"))
        hash_b = token_to_apikeyhash(_testtoken("b"))
        contacts = _make_contacts_data_by_id(
            {
                "id-a": _make_user_yaml(full_name="User A"),
                "id-b": _make_user_yaml(full_name="User B"),
            }
        )
        api_keys_file = _write_api_keys_file(
            tmp_path,
            {
                "id-a": {"FullName": "User A", "APIKeyHash": hash_a},
                "id-b": {"FullName": "User B", "APIKeyHash": hash_b},
            },
        )
        result = get_api_keys_data(api_keys_file, contacts)
        assert result == {hash_a: "User A", hash_b: "User B"}

    def test_returns_empty_dict_when_path_is_empty(self):
        contacts = _make_contacts_data_by_id({"id-a": _make_user_yaml(full_name="User A")})
        assert get_api_keys_data("", contacts) == {}

    def test_skips_entries_with_invalid_api_key_hash(self, tmp_path, caplog):
        import logging

        contacts = _make_contacts_data_by_id(
            {"id-a": _make_user_yaml(full_name="User A")}
        )
        api_keys_file = _write_api_keys_file(
            tmp_path,
            {"id-a": {"FullName": "User A", "APIKeyHash": "sha256:xyz"}},
        )
        with caplog.at_level(logging.WARNING, logger="webapp.contacts_reader"):
            result = get_api_keys_data(api_keys_file, contacts)
        assert result == {}
        assert "invalid APIKeyHash" in caplog.text

    def test_skips_entries_with_unknown_contact_id(self, tmp_path, caplog):
        import logging

        contacts = _make_contacts_data_by_id(
            {"id-a": _make_user_yaml(full_name="User A")}
        )
        api_keys_file = _write_api_keys_file(
            tmp_path,
            {"id-missing": {"FullName": "User A", "APIKeyHash": token_to_apikeyhash(_testtoken())}},
        )
        with caplog.at_level(logging.WARNING, logger="webapp.contacts_reader"):
            result = get_api_keys_data(api_keys_file, contacts)
        assert result == {}
        assert "does not match any contact" in caplog.text

    def test_skips_entries_with_fullname_mismatch(self, tmp_path, caplog):
        import logging

        contacts = _make_contacts_data_by_id(
            {"id-a": _make_user_yaml(full_name="User A")}
        )
        api_keys_file = _write_api_keys_file(
            tmp_path,
            {"id-a": {"FullName": "Different Name", "APIKeyHash": token_to_apikeyhash(_testtoken())}},
        )
        with caplog.at_level(logging.WARNING, logger="webapp.contacts_reader"):
            result = get_api_keys_data(api_keys_file, contacts)
        assert result == {}
        assert "FullName mismatch" in caplog.text

    def test_invalid_top_level_type_returns_empty_dict(self, tmp_path, caplog):
        import logging

        contacts = _make_contacts_data_by_id(
            {"id-a": _make_user_yaml(full_name="User A")}
        )
        path = tmp_path / "api-keys.yaml"
        path.write_text(yaml.safe_dump([{"id-a": {"FullName": "User A"}}]), encoding="utf-8")

        with caplog.at_level(logging.WARNING, logger="webapp.contacts_reader"):
            result = get_api_keys_data(str(path), contacts)

        assert result == {}
        assert "must be a YAML mapping" in caplog.text


# ---------------------------------------------------------------------------
# GlobalData.get_api_keys() tests
#
# We build a minimal GlobalData with CONTACT_DATA_DIR=None so it won't try
# to read any files, then override internal state and mocks as needed.
# ---------------------------------------------------------------------------

def _make_global_data():
    """Return a GlobalData instance configured for in-memory testing."""
    return GlobalData(config={"TOPOLOGY_DATA_DIR": ".", "CONTACT_DATA_DIR": None, "API_KEYS_FILE": ""})


class TestGlobalDataGetApiKeys:

    def test_returns_a_dict(self, tmp_path):
        """get_api_keys() returns a dict of hash->owner when hashes exist in API_KEY_FILE."""
        gd = _make_global_data()
        token_hash = token_to_apikeyhash(_testtoken())
        contacts = _make_contacts_data_by_id({"id-1": _make_user_yaml(full_name="User 1")})
        gd.api_keys_file = _write_api_keys_file(
            tmp_path,
            {"id-1": {"FullName": "User 1", "APIKeyHash": token_hash}},
        )
        gd.get_contact_db_data = MagicMock(return_value=contacts)
        result = gd.get_api_keys()
        assert isinstance(result, dict)
        assert result == {token_hash: "User 1"}

    def test_calls_get_contact_db_data_when_cache_stale_and_stores_result(self, tmp_path):
        """get_api_keys() fetches contacts.yaml data when cache is stale and caches the mapping."""
        gd = _make_global_data()
        gd.api_key_set = CachedData()
        token_hash = token_to_apikeyhash(_testtoken("0"))
        contacts = _make_contacts_data_by_id({"id-1": _make_user_yaml(full_name="Cached User")})
        gd.api_keys_file = _write_api_keys_file(
            tmp_path,
            {"id-1": {"FullName": "Cached User", "APIKeyHash": token_hash}},
        )
        gd.get_contact_db_data = MagicMock(return_value=contacts)

        result = gd.get_api_keys()

        gd.get_contact_db_data.assert_called_once()
        assert result is not None
        assert result[token_hash] == "Cached User"
        result2 = gd.get_api_keys()
        gd.get_contact_db_data.assert_called_once()
        assert result2 == result

    def test_calls_try_again_on_get_api_keys_exception_and_returns_cached(self, tmp_path):
        """When API key loading raises, try_again() is called and previous data is returned."""
        gd = _make_global_data()
        gd.api_key_set = CachedData()
        gd.api_key_set.update({token_to_apikeyhash(_testtoken("3")): "Old User"})
        gd.api_key_set.force_update = True
        gd.api_keys_file = _write_api_keys_file(
            tmp_path,
            {"id-1": {"FullName": "User 1", "APIKeyHash": token_to_apikeyhash(_testtoken("1"))}},
        )

        gd.get_contact_db_data = MagicMock(return_value=_make_contacts_data_by_id({"id-1": _make_user_yaml(full_name="User 1")}))

        with patch("webapp.models.contacts_reader.get_api_keys_data", side_effect=RuntimeError("boom")):
            with patch.object(gd.api_key_set, 'try_again', wraps=gd.api_key_set.try_again) as mock_try_again:
                result = gd.get_api_keys()
                mock_try_again.assert_called_once()

        assert result == {token_to_apikeyhash(_testtoken("3")): "Old User"}

    def test_returns_empty_dict_when_contact_db_data_is_none_on_first_load(self, tmp_path):
        """get_api_keys() returns {} when contact-db data is unavailable on first load."""
        gd = _make_global_data()
        gd.api_key_set = CachedData()
        gd.api_keys_file = _write_api_keys_file(
            tmp_path,
            {"id-1": {"FullName": "User 1", "APIKeyHash": token_to_apikeyhash(_testtoken("1"))}},
        )
        gd.get_contact_db_data = MagicMock(return_value=None)

        result = gd.get_api_keys()

        assert result == {}

    def test_returns_empty_dict_when_api_keys_file_unset(self):
        """get_api_keys() returns an empty mapping when API_KEYS_FILE is unset."""
        gd = _make_global_data()
        gd.api_key_set = CachedData()
        gd.api_keys_file = ""
        gd.get_contact_db_data = MagicMock(return_value=None)

        result = gd.get_api_keys()

        assert result == {}
