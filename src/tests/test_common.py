import re
import flask
from flask import testing
import pytest
from pytest_mock import MockerFixture

# Rewrites the path so the app can be imported like it normally is
import os
import sys

topdir = os.path.join(os.path.dirname(__file__), "..")
sys.path.append(topdir)

from app import app, global_data
from webapp.common import Filters, InvalidArgumentsError, GRIDTYPE_1, GRIDTYPE_2


@pytest.fixture
def client() -> testing.FlaskClient:
    with app.test_client() as client:
        yield client


class TestFilterFromArgs:

    @staticmethod
    def get_request_args(client, url):
        request_context = client.application.test_request_context(url)
        return request_context.request.args

    def test_empty_args(self, client: testing.FlaskClient):
        """Check that no args results in an empty filter"""

        args = self.get_request_args(client, "/test")
        arg_informed_filters = Filters.from_args(args, global_data)

        default_filter = Filters()

        # Iterate the class attributes and confirm the are the same in both
        for k in Filters().__dict__.keys():
            assert getattr(default_filter, k) == getattr(arg_informed_filters, k)

    def test_get_filter_value_sets_value(self, client: testing.FlaskClient):
        """Check we can set values using the get_filter_value method"""

        args = self.get_request_args(client, "/test?active=0&active_value=0")
        arg_informed_filters = Filters.from_args(args, global_data)

        assert arg_informed_filters.active is not None

    def test_get_filter_value_correctly_sets_value(self, client: testing.FlaskClient):
        """Check we can set values using the get_filter_value method"""

        args = self.get_request_args(client, "/test?active=0&active_value=0")
        arg_informed_filters = Filters.from_args(args, global_data)

        assert arg_informed_filters.active is False

    def test_get_filter_value_correctly_sets_value_multi(self, client: testing.FlaskClient):
        """Check we can set values using the get_filter_value method"""

        args = self.get_request_args(client, "/test?"
                                             "active=0&active_value=1"
                                             "&disable=0&disable_value=1"
                                             "&oasis=0&oasis_value=0")
        arg_informed_filters = Filters.from_args(args, global_data)

        assert arg_informed_filters.active is True
        assert arg_informed_filters.disable is True
        assert arg_informed_filters.oasis is False

    def test_populate_service_hidden_filter_from_args(self, client: testing.FlaskClient):
        args = self.get_request_args(client, "/test?"
                                             "service_hidden_value=1")
        arg_informed_filters = Filters.from_args(args, global_data)

        assert arg_informed_filters.service_hidden is True

    def test_populate_service_hidden_filter_from_args_invalid(self, client: testing.FlaskClient):
        args = self.get_request_args(client, "/test?"
                                             "service_hidden_value=test")

        with pytest.raises(InvalidArgumentsError) as e_info:
            Filters.from_args(args, global_data)

    def test_populate_gridtype_filter_from_args_single(self, client: testing.FlaskClient):
        args = self.get_request_args(client, "/test?"
                                             "gridtype=on&"
                                             "gridtype_1=on")
        arg_informed_filters = Filters.from_args(args, global_data)

        assert arg_informed_filters.grid_type == GRIDTYPE_1

    def test_populate_gridtype_filter_from_args_double(self, client: testing.FlaskClient):
        args = self.get_request_args(client, "/test?"
                                             "gridtype=on&"
                                             "gridtype_1=on&"
                                             "gridtype_2=on")
        arg_informed_filters = Filters.from_args(args, global_data)

        assert arg_informed_filters.grid_type is None

    def test_populate_gridtype_filter_from_args_error(self, client: testing.FlaskClient):
        args = self.get_request_args(client, "/test?"
                                             "gridtype=on&")

        with pytest.raises(InvalidArgumentsError) as e_info:
            Filters.from_args(args, global_data)

    def test_populate_past_days_from_args_all(self, client: testing.FlaskClient):
        args = self.get_request_args(client, "/test?"
                                             "downtime_attrs_showpast=all")
        arg_informed_filters = Filters.from_args(args, global_data)

        assert arg_informed_filters.past_days is -1

    def test_populate_past_days_from_args_none(self, client: testing.FlaskClient):
        args = self.get_request_args(client, "/test?"
                                             "downtime_attrs_showpast")
        arg_informed_filters = Filters.from_args(args, global_data)

        assert arg_informed_filters.past_days is 0

    def test_populate_past_days_from_args_int(self, client: testing.FlaskClient):
        args = self.get_request_args(client, "/test?"
                                             "downtime_attrs_showpast=56")
        arg_informed_filters = Filters.from_args(args, global_data)

        assert arg_informed_filters.past_days is 56

    def test_populate_past_days_from_args_error(self, client: testing.FlaskClient):
        args = self.get_request_args(client, "/test?"
                                             "downtime_attrs_showpast=test")

        with pytest.raises(InvalidArgumentsError) as e_info:
            Filters.from_args(args, global_data)

    def test_populate_has_wlcg_from_args(self, client: testing.FlaskClient):
        args = self.get_request_args(client, "/test?has_wlcg")
        arg_informed_filters = Filters.from_args(args, global_data)

        assert arg_informed_filters.has_wlcg is True

    def test_add_selector_filter_from_args(self, client: testing.FlaskClient):
        args = self.get_request_args(client, "/test?"
                                             "facility&"
                                             "facility_sel[]=70&"
                                             "facility_311")
        arg_informed_filters = Filters.from_args(args, global_data)

        assert set(arg_informed_filters.facility_id) == set([70, 311])

    def test_add_selector_filter_from_args_multi(self, client: testing.FlaskClient):
        args = self.get_request_args(client, "/test?"
                                             "rg&"
                                             "rg_sel[]=32&"
                                             "rg_123&"
                                             "vo&"
                                             "vo_sel[]=21&"
                                             "vo_45")
        arg_informed_filters = Filters.from_args(args, global_data)

        assert set(arg_informed_filters.rg_id) == set([32, 123])
        assert set(arg_informed_filters.vo_id) == set([21, 45])

    def test_add_selector_filter_from_args_int_error(self, client: testing.FlaskClient):
        args = self.get_request_args(client, "/test?"
                                             "rg&"
                                             "rg_sel[]=test")

        with pytest.raises(InvalidArgumentsError) as e_info:
            Filters.from_args(args, global_data)

    def test_add_selector_filter_from_args_no_input_error(self, client: testing.FlaskClient):
        args = self.get_request_args(client, "/test?"
                                             "rg&")

        with pytest.raises(InvalidArgumentsError) as e_info:
            Filters.from_args(args, global_data)

    def test_add_id_filter_from_args(self, client: testing.FlaskClient):
        args = self.get_request_args(client, "/test?"
                                             "site_id[]=90&"
                                             "site_id[]=33&"
                                             "service_id[]=21&"
                                             "voown_id[]=4&")
        arg_informed_filters = Filters.from_args(args, global_data)

        assert set(arg_informed_filters.site_id) == set([90, 33])
        assert set(arg_informed_filters.service_id) == set([21])
        assert set(arg_informed_filters.voown_id) == set([4])

    def test_add_id_filter_from_args_int_error(self, client: testing.FlaskClient):
        args = self.get_request_args(client, "/test?"
                                             "site_id[]=temp")

        with pytest.raises(InvalidArgumentsError) as e_info:
            Filters.from_args(args, global_data)

    def test_joint_selector_and_id_from_args(self, client: testing.FlaskClient):
        args = self.get_request_args(client, "/test?"
                                             "site_id[]=90&"
                                             "site_id[]=33&"
                                             "service_id[]=21&"
                                             "rg&"
                                             "rg_sel[]=32&"
                                             "rg_123&"
                                             "site&"
                                             "site_sel[]=21&"
                                             "site_45")
        arg_informed_filters = Filters.from_args(args, global_data)

        assert set(arg_informed_filters.site_id) == set([90, 33, 21, 45])
        assert set(arg_informed_filters.rg_id) == set([32, 123])
        assert set(arg_informed_filters.service_id) == set([21])

    def test_add_name_filter_from_args(self, client: testing.FlaskClient):
        args = self.get_request_args(client, "/test?"
                                             "site_name[]=test0&"
                                             "site_name[]=test1")
        arg_informed_filters = Filters.from_args(args, global_data)

        assert set(arg_informed_filters.site_name) == set(["test0", "test1"])

    def test_add_name_filter_from_args_multi(self, client: testing.FlaskClient):
        args = self.get_request_args(client, "/test?"
                                             "site_name[]=test0&"
                                             "rg_name[]=test32&"
                                             "sc_name[]=test1")
        arg_informed_filters = Filters.from_args(args, global_data)

        assert set(arg_informed_filters.site_name) == set(["test0"])
        assert set(arg_informed_filters.rg_name) == set(["test32"])
        assert set(arg_informed_filters.support_center_name) == set(["test1"])

    def test_joint_voown_name_and_id(self, client: testing.FlaskClient):
        args = self.get_request_args(client, "/test?"
                                             "voown_id[]=133&"
                                             "voown_name[]=ANL&"
                                             "voown&"
                                             "voown_69&"
                                             "voown_sel[]=1")
        arg_informed_filters = Filters.from_args(args, global_data)

        assert set(arg_informed_filters.voown_name) == set(["ACCRE", "ANL", "Belle", "CDF"])

    def test_all(self, client: testing.FlaskClient):
        args = self.get_request_args(client, "/test?"
                                             "site_name[]=test0&"
                                             "rg_id[]=32&"
                                             "voown_name[]=test1&"
                                             "downtime_attrs_showpast=56&"
                                             "gridtype=on&"
                                             "gridtype_1=on&"
                                             "gridtype_2=on&"
                                             "service_hidden_value=1&"
                                             "has_wlcg")

        arg_informed_filters = Filters.from_args(args, global_data)

        assert set(arg_informed_filters.site_name) == set(["test0"])
        assert set(arg_informed_filters.rg_id) == set([32])
        assert set(arg_informed_filters.voown_name) == set(["test1"])
        assert arg_informed_filters.past_days is 56
        assert arg_informed_filters.grid_type is None
        assert arg_informed_filters.service_hidden is True
        assert arg_informed_filters.has_wlcg is True
