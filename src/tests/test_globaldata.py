import flask
import pytest
from pytest_mock import MockerFixture
import time
import math

# Rewrites the path so the app can be imported like it normally is
import os
import sys
topdir = os.path.join(os.path.dirname(__file__), "..")
sys.path.append(topdir)

import app
from webapp import rg_reader

class TestGlobalData:

    def test_cache_updater(self, mocker: MockerFixture):
        """
        Tests that calls to get topology data do not break the data cache

        Does this by spying on two functions:

        app.global_data.get_topology to track calls to get the topology data
        rg_reader.get_topology to track cache breaks

        The goal of this test is to make sure that all calls to app.global_data.get_topology
        do not result in a call to rg_reader.get_topology. In terms of our goal this shows
        that users will not be able to break the cache with their calls to get_topology.
        """

        spy_get_topology = mocker.spy(app.global_data, "get_topology")
        spy_cache_bust = mocker.spy(rg_reader, "get_topology")

        time.sleep(1)
        assert spy_get_topology.call_count == spy_cache_bust.call_count

        app.global_data.get_topology()

        # Here you will notice I allow the cache to break
        assert spy_get_topology.call_count - 1 == spy_cache_bust.call_count or \
               spy_get_topology.call_count == spy_cache_bust.call_count

        time.sleep(30)
        assert spy_get_topology.call_count - 1 == spy_cache_bust.call_count or \
               spy_get_topology.call_count == spy_cache_bust.call_count

        app.global_data.get_topology()
        assert spy_get_topology.call_count - 2 == spy_cache_bust.call_count or \
               spy_get_topology.call_count - 1 == spy_cache_bust.call_count

        for i in range(1, 21):

            time.sleep(60)
            app.global_data.get_topology()
            assert spy_get_topology.call_count - (2 + i) == spy_cache_bust.call_count or \
                   spy_get_topology.call_count - (1 + i) == spy_cache_bust.call_count
