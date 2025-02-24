import re
import flask
import pytest
from typing import Dict, List
import urllib.parse
from pytest_mock import MockerFixture

# Rewrites the path so the app can be imported like it normally is
import os
import sys
import csv
import io

topdir = os.path.join(os.path.dirname(__file__), "..")
sys.path.append(topdir)

os.environ['TESTING'] = "True"

from app import app, global_data
from webapp.topology import Facility, Site, Resource, ResourceGroup

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
    '/miscsite/json',
    '/miscfacility/json',
    '/vosummary/xml',
    '/rgsummary/xml',
    '/rgdowntime/xml',
    '/rgdowntime/ical',
    "/stashcache/authfile",
    "/stashcache/authfile-public",
    "/stashcache/origin-authfile-public?fqdn=sc-origin.chtc.wisc.edu",
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
    "/cache/scitokens.conf",
    "/api/institutions",
    "/cache/grid-mapfile",
    "/origin/grid-mapfile",
    "/osdf/namespaces",
    "/stashcache/namespaces",
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

    def test_cache_authfile(self, client: flask.Flask, mocker: MockerFixture):
        mocker.patch("webapp.ldap_data.get_ligo_ldap_dn_list", mocker.MagicMock(return_value=["deadbeef.0"]))
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

    def test_resource_stashcache_files(self, client: flask.Flask, mocker: MockerFixture):
        """Tests that the resource table contains the same files as the singular api outputs"""

        # Disable legacy auth until it's turned back on in Resource.get_stashcache_files()
        old_legacy_auth = app.config.get("STASHCACHE_LEGACY_AUTH", None)
        app.config["STASHCACHE_LEGACY_AUTH"] = False

        def test_stashcache_file(key, endpoint, fqdn, resource_stashcache_files):

            response = client.get(f"{endpoint}?fqdn={fqdn}")

            if key in resource_stashcache_files:
                assert response.status_code == 200
                assert response.data.decode() == resource_stashcache_files[key]

            else:
                assert response.status_code != 200 or not response.data

        try:
            mocker.patch("webapp.ldap_data.get_ligo_ldap_dn_list", mocker.MagicMock(return_value=["deadbeef.0"]))

            resources = client.get('/miscresource/json').json
            resources_stashcache_files = client.get('/resources/stashcache-files').json

            # Sanity check: have a reasonable number of resources
            assert len(resources_stashcache_files) > 20

            keys_and_endpoints = [
                ("CacheAuthfilePublic", "/cache/Authfile-public"),
                ("CacheAuthfile", "/cache/Authfile"),
                ("CacheScitokens", "/cache/scitokens.conf"),
                ("OriginAuthfilePublic", "/origin/Authfile-public"),
                ("OriginAuthfile", "/origin/Authfile"),
                ("OriginScitokens", "/origin/scitokens.conf")
            ]

            for resource_name, resource_stashcache_files in resources_stashcache_files.items():
                for key, endpoint in keys_and_endpoints:
                    test_stashcache_file(key, endpoint, resources[resource_name]["FQDN"], resource_stashcache_files)

        finally:
            if old_legacy_auth is None:
                del app.config["STASHCACHE_LEGACY_AUTH"]
            else:
                app.config["STASHCACHE_LEGACY_AUTH"] = old_legacy_auth

    def test_institution_accept_type(self, client: flask.Flask):
        """Checks both formats output the same content"""

        json_institutions = client.get("/api/institutions", headers={"Accept": "application/json"}).json
        json_tuples = [tuple(map(str, x)) for x in sorted(json_institutions, key=lambda x: x[0])]

        csv_institutions = csv.reader(io.StringIO(client.get("/api/institutions").data.decode()))
        csv_tuples = [tuple(x) for x in sorted(csv_institutions, key=lambda x: x[0])]

        assert len(csv_tuples) == len(json_tuples)

        assert tuple(json_tuples) == tuple(csv_tuples)


    def test_origin_grid_mapfile(self, client: flask.Flask):
        TEST_ORIGIN = "ap20.uc.osg-htc.org"  # This origin serves protected data
        response = client.get("/origin/grid-mapfile")
        assert response.status_code == 400  # fqdn not specified

        # Compare the hashes in an origin's grid-mapfile with the hashes in the origin's Authfile

        # First get a set of the hashes in the grid-mapfile
        response = client.get(f"/origin/grid-mapfile?fqdn={TEST_ORIGIN}")
        assert response.status_code == 200
        grid_mapfile_text = response.data.decode("utf-8")
        grid_mapfile_lines = grid_mapfile_text.split("\n")
        # Have a reasonable number of mappings
        assert len(grid_mapfile_lines) > 20

        mapfile_matches = filter(None,
                                 (re.fullmatch(r'"[^"]+" ([0-9a-f]+[.]0)', line)
                                  for line in grid_mapfile_lines))
        mapfile_hashes = set(match.group(1) for match in mapfile_matches)

        # Next get a set of the user (u) hashes in the authfile
        response = client.get(f"/origin/Authfile?fqdn={TEST_ORIGIN}")
        assert response.status_code == 200
        authfile_text = response.data.decode("utf-8")
        authfile_lines = authfile_text.split("\n")
        # Have a reasonable number of caches; each one has a comment with the DN so there should be
        # twice as many lines as authorizations
        assert len(authfile_lines) > 40

        authfile_matches = filter(None,
                                  (re.match(r'u ([0-9a-f]+[.]0)', line)
                                   for line in authfile_lines))
        authfile_hashes = set(match.group(1) for match in authfile_matches)

        hashes_not_in_mapfile = authfile_hashes - mapfile_hashes
        assert not hashes_not_in_mapfile, f"Hashes in authfile but not in mapfile: {hashes_not_in_mapfile}"

        hashes_not_in_authfile = mapfile_hashes - authfile_hashes
        assert not hashes_not_in_authfile, f"Hashes in mapfile but not in authfile: {hashes_not_in_authfile}"

    def test_cache_grid_mapfile(self, client: flask.Flask):
        TEST_CACHE = "stash-cache.osg.chtc.io"  # This cache allows cert-based auth but not LIGO data
        response = client.get("/cache/grid-mapfile")
        assert response.status_code == 400  # fqdn not specified

        # Compare the hashes in a cache's grid-mapfile with the hashes in the cache's Authfile

        # First get a set of the hashes in the grid-mapfile
        response = client.get(f"/cache/grid-mapfile?fqdn={TEST_CACHE}")
        assert response.status_code == 200
        grid_mapfile_text = response.data.decode("utf-8")
        grid_mapfile_lines = grid_mapfile_text.split("\n")
        # Make sure we have some mappings (we may not have LIGO data so there's only a few)
        assert len(grid_mapfile_lines) > 1

        mapfile_matches = filter(None,
                                 (re.fullmatch(r'"[^"]+" ([0-9a-f]+[.]0)', line)
                                  for line in grid_mapfile_lines))
        mapfile_hashes = set(match.group(1) for match in mapfile_matches)

        # Next get a set of the user (u) hashes in the authfile
        response = client.get(f"/cache/Authfile?fqdn={TEST_CACHE}")
        assert response.status_code == 200
        authfile_text = response.data.decode("utf-8")
        authfile_lines = authfile_text.split("\n")
        # Make sure we have some mappings; each one has a comment with the DN so there should be
        # twice as many lines as authorizations
        assert len(authfile_lines) > 2

        authfile_matches = filter(None,
                                  (re.match(r'u ([0-9a-f]+[.]0)', line)
                                   for line in authfile_lines))
        authfile_hashes = set(match.group(1) for match in authfile_matches)

        hashes_not_in_mapfile = authfile_hashes - mapfile_hashes
        assert not hashes_not_in_mapfile, f"Hashes in authfile but not in mapfile: {hashes_not_in_mapfile}"

        hashes_not_in_authfile = mapfile_hashes - authfile_hashes
        assert not hashes_not_in_authfile, f"Hashes in mapfile but not in authfile: {hashes_not_in_authfile}"

    def test_namespaces_json(self, client):
        response = client.get('/osdf/namespaces')
        assert response.status_code == 200
        assert "namespaces" in response.json


class TestEndpointContent:
    # Pre-build some test cases based on AMNH resources
    mock_facility = Facility("test_facility_name", 12345)

    mock_site_info = {
        "AddressLine1": "Central Park West at 79th St.",
        "City": "New York",
        "Country": "United States",
        "Description": "The American Museum of Natural History is one of the world's preeminent scientific and cultural institutions.",
        "Latitude": 40.7128,
        "LongName": "American Museum of Natural History",
        "Longitude": -74.006,
        "State": "NY",
        "Zipcode": "10024-5192"
    }
    mock_site = Site("test_site_name", 1234, mock_facility, mock_site_info)

    mock_resource_group_info = {
        'Production': True,
        'SupportCenter': 'Self Supported',
        'GroupDescription': 'American Museum of Natural History Slurm cluster for the CC* proposal (NSF 19-533)',
        'GroupID': 497,
        'Resources': {
            'OSG_US_AMNH_ARES': {
                'Active': False,
                'Description': 'This is a Hosted CE for the AMNH Slurm cluster',
                'ID': 985,
                'ContactLists': {
                    'Administrative Contact': {
                        'Primary': {
                            'Name': 'Marco Mascheroni',
                            'ID': '030408ab932e143859b5f97a2d1c9e30ba2a9f0d'
                        },
                        'Secondary': {
                            'Name': 'Jeffrey Michael Dost',
                            'ID': '3a8eb6436a8b78ca50f7e93bb2a4d1f0141212ba'
                        }
                    },
                    'Security Contact': {
                        'Primary': {
                            'Name': 'Marco Mascheroni',
                            'ID': '030408ab932e143859b5f97a2d1c9e30ba2a9f0d'
                        },
                        'Secondary': {
                            'Name': 'Jeffrey Michael Dost',
                            'ID': '3a8eb6436a8b78ca50f7e93bb2a4d1f0141212ba'
                        }
                    },
                    'Site Contact': {
                        'Primary': {
                            'Name': 'Sajesh Singh',
                            'ID': '0da9ca0b7d1d58f1a91c6797e4bb29b64846f88e'
                        },
                        'Secondary': {
                            'Name': 'AMNH OSG Contact List',
                            'ID': 'e7b8d36d684570dcb0ed8ff7b723928d5a93b513'
                        }
                    }
                },
                'FQDN': 'hosted-ce22.grid.uchicago.edu',
                'Services': {
                    'CE': {
                        'Description': 'American Museum of Natural History Hosted CE'
                    }
                },
                'Tags': ['CC*']
            },
            'AMNH-ARES': {
                'Active': True,
                'Description': 'This is a Hosted CE for the AMNH Slurm cluster',
                'ID': 1074,
                'ContactLists': {
                    'Administrative Contact': {
                        'Primary': {
                            'Name': 'Marco Mascheroni',
                            'ID': '030408ab932e143859b5f97a2d1c9e30ba2a9f0d'
                        },
                        'Secondary': {
                            'Name': 'Jeffrey Michael Dost',
                            'ID': '3a8eb6436a8b78ca50f7e93bb2a4d1f0141212ba'
                        }
                    },
                    'Security Contact': {
                        'Primary': {
                            'Name': 'Marco Mascheroni',
                            'ID': '030408ab932e143859b5f97a2d1c9e30ba2a9f0d'
                        },
                        'Secondary': {
                            'Name': 'Jeffrey Michael Dost',
                            'ID': '3a8eb6436a8b78ca50f7e93bb2a4d1f0141212ba'
                        }
                    },
                    'Site Contact': {
                        'Primary': {
                            'Name': 'Sajesh Singh',
                            'ID': '0da9ca0b7d1d58f1a91c6797e4bb29b64846f88e'
                        },
                        'Secondary': {
                            'Name': 'AMNH OSG Contact List',
                            'ID': 'e7b8d36d684570dcb0ed8ff7b723928d5a93b513'
                        }
                    }
                },
                'FQDN': 'hosted-ce22.opensciencegrid.org',
                'Services': {
                    'CE': {
                        'Description': 'American Museum of Natural History Hosted CE'
                    }
                },
                'Tags': ['CC*']
            },
            'AMNH-ARES-CE1': {
                'Active': True,
                'Description': 'This is a Hosted CE for the AMNH Slurm cluster',
                'ID': 1216,
                'ContactLists': {
                    'Administrative Contact': {
                        'Primary': {
                            'Name': 'Marco Mascheroni',
                            'ID': '030408ab932e143859b5f97a2d1c9e30ba2a9f0d'
                        },
                        'Secondary': {
                            'Name': 'Jeffrey Michael Dost',
                            'ID': '3a8eb6436a8b78ca50f7e93bb2a4d1f0141212ba'
                        }
                    },
                    'Security Contact': {
                        'Primary': {
                            'Name': 'Marco Mascheroni',
                            'ID': '030408ab932e143859b5f97a2d1c9e30ba2a9f0d'
                        },
                        'Secondary': {
                            'Name': 'Jeffrey Michael Dost',
                            'ID': '3a8eb6436a8b78ca50f7e93bb2a4d1f0141212ba'
                        }
                    },
                    'Site Contact': {
                        'Primary': {
                            'Name': 'Sajesh Singh',
                            'ID': '0da9ca0b7d1d58f1a91c6797e4bb29b64846f88e'
                        },
                        'Secondary': {
                            'Name': 'AMNH OSG Contact List',
                            'ID': 'e7b8d36d684570dcb0ed8ff7b723928d5a93b513'
                        }
                    }
                },
                'FQDN': 'amnh-ares-ce1.svc.opensciencegrid.org',
                'Services': {
                    'CE': {
                        'Description': 'American Museum of Natural History Hosted CE'
                    }
                },
                'Tags': ['CC*']
            },
            'OSG_US_AMNH_HEL': {
                'Active': False,
                'Description': 'Second Hosted CE for the AMNH',
                'ID': 1052,
                'ContactLists': {
                    'Administrative Contact': {
                        'Primary': {
                            'Name': 'Marco Mascheroni',
                            'ID': '030408ab932e143859b5f97a2d1c9e30ba2a9f0d'
                        },
                        'Secondary': {
                            'Name': 'Jeffrey Michael Dost',
                            'ID': '3a8eb6436a8b78ca50f7e93bb2a4d1f0141212ba'
                        }
                    },
                    'Security Contact': {
                        'Primary': {
                            'Name': 'Marco Mascheroni',
                            'ID': '030408ab932e143859b5f97a2d1c9e30ba2a9f0d'
                        },
                        'Secondary': {
                            'Name': 'Jeffrey Michael Dost',
                            'ID': '3a8eb6436a8b78ca50f7e93bb2a4d1f0141212ba'
                        }
                    },
                    'Site Contact': {
                        'Primary': {
                            'Name': 'Sajesh Singh',
                            'ID': '0da9ca0b7d1d58f1a91c6797e4bb29b64846f88e'
                        },
                        'Secondary': {
                            'Name': 'AMNH OSG Contact List',
                            'ID': 'e7b8d36d684570dcb0ed8ff7b723928d5a93b513'
                        }
                    }
                },
                'FQDN': 'hosted-ce36.grid.uchicago.edu',
                'Services': {
                    'CE': {
                        'Description': 'American Museum of Natural History Hosted CE for HEL cluster'
                    }
                },
                'Tags': ['CC*']
            },
            'AMNH-HEL': {
                'Active': True,
                'Description': 'Second Hosted CE for the AMNH',
                'ID': 1075,
                'ContactLists': {
                    'Administrative Contact': {
                        'Primary': {
                            'Name': 'Jeffrey Peterson',
                            'ID': '3ef2e11c271234a34f154e75b28d3b4554bb8f63'
                        },
                        'Secondary': {
                            'Name': 'Jeffrey Michael Dost',
                            'ID': '3a8eb6436a8b78ca50f7e93bb2a4d1f0141212ba'
                        }
                    },
                    'Security Contact': {
                        'Primary': {
                            'Name': 'Jeffrey Peterson',
                            'ID': '3ef2e11c271234a34f154e75b28d3b4554bb8f63'
                        },
                        'Secondary': {
                            'Name': 'Jeffrey Michael Dost',
                            'ID': '3a8eb6436a8b78ca50f7e93bb2a4d1f0141212ba'
                        }
                    },
                    'Site Contact': {
                        'Primary': {
                            'Name': 'Sajesh Singh',
                            'ID': '0da9ca0b7d1d58f1a91c6797e4bb29b64846f88e'
                        },
                        'Secondary': {
                            'Name': 'AMNH OSG Contact List',
                            'ID': 'e7b8d36d684570dcb0ed8ff7b723928d5a93b513'
                        }
                    }
                },
                'FQDN': 'hosted-ce36.opensciencegrid.org',
                'Services': {
                    'CE': {
                        'Description': 'American Museum of Natural History Hosted CE for HEL cluster'
                    }
                },
                'Tags': ['CC*']
            },
            'AMNH-HEL-CE1': {
                'Active': True,
                'Description': 'Second Hosted CE for the AMNH',
                'ID': 1217,
                'ContactLists': {
                    'Administrative Contact': {
                        'Primary': {
                            'Name': 'Jeffrey Peterson',
                            'ID': '3ef2e11c271234a34f154e75b28d3b4554bb8f63'
                        },
                        'Secondary': {
                            'Name': 'Jeffrey Michael Dost',
                            'ID': '3a8eb6436a8b78ca50f7e93bb2a4d1f0141212ba'
                        }
                    },
                    'Security Contact': {
                        'Primary': {
                            'Name': 'Jeffrey Peterson',
                            'ID': '3ef2e11c271234a34f154e75b28d3b4554bb8f63'
                        },
                        'Secondary': {
                            'Name': 'Jeffrey Michael Dost',
                            'ID': '3a8eb6436a8b78ca50f7e93bb2a4d1f0141212ba'
                        }
                    },
                    'Site Contact': {
                        'Primary': {
                            'Name': 'Sajesh Singh',
                            'ID': '0da9ca0b7d1d58f1a91c6797e4bb29b64846f88e'
                        },
                        'Secondary': {
                            'Name': 'AMNH OSG Contact List',
                            'ID': 'e7b8d36d684570dcb0ed8ff7b723928d5a93b513'
                        }
                    }
                },
                'FQDN': 'amnh-hel-ce1.svc.opensciencegrid.org',
                'Services': {
                    'CE': {
                        'Description': 'American Museum of Natural History Hosted CE for HEL cluster'
                    }
                },
                'Tags': ['CC*']
            },
            'AMNH-Mendel': {
                'Active': False,
                'Description': 'Third Hosted CE for the AMNH',
                'ID': 1111,
                'ContactLists': {
                    'Administrative Contact': {
                        'Primary': {
                            'Name': 'Marco Mascheroni',
                            'ID': '030408ab932e143859b5f97a2d1c9e30ba2a9f0d'
                        },
                        'Secondary': {
                            'Name': 'Jeffrey Michael Dost',
                            'ID': '3a8eb6436a8b78ca50f7e93bb2a4d1f0141212ba'
                        }
                    },
                    'Security Contact': {
                        'Primary': {
                            'Name': 'Marco Mascheroni',
                            'ID': '030408ab932e143859b5f97a2d1c9e30ba2a9f0d'
                        },
                        'Secondary': {
                            'Name': 'Jeffrey Michael Dost',
                            'ID': '3a8eb6436a8b78ca50f7e93bb2a4d1f0141212ba'
                        }
                    },
                    'Site Contact': {
                        'Primary': {
                            'Name': 'Sajesh Singh',
                            'ID': '0da9ca0b7d1d58f1a91c6797e4bb29b64846f88e'
                        },
                        'Secondary': {
                            'Name': 'AMNH OSG Contact List',
                            'ID': 'e7b8d36d684570dcb0ed8ff7b723928d5a93b513'
                        }
                    }
                },
                'FQDN': 'hosted-ce39.opensciencegrid.org',
                'Services': {
                    'CE': {
                        'Description': 'American Museum of Natural History Hosted CE for Mendel cluster'
                    }
                },
                'Tags': ['CC*']
            },
            'AMNH-Mendel-CE1': {
                'Active': True,
                'Description': 'Third Hosted CE for the AMNH',
                'ID': 1221,
                'ContactLists': {
                    'Administrative Contact': {
                        'Primary': {
                            'Name': 'Marco Mascheroni',
                            'ID': '030408ab932e143859b5f97a2d1c9e30ba2a9f0d'
                        },
                        'Secondary': {
                            'Name': 'Jeffrey Michael Dost',
                            'ID': '3a8eb6436a8b78ca50f7e93bb2a4d1f0141212ba'
                        }
                    },
                    'Security Contact': {
                        'Primary': {
                            'Name': 'Marco Mascheroni',
                            'ID': '030408ab932e143859b5f97a2d1c9e30ba2a9f0d'
                        },
                        'Secondary': {
                            'Name': 'Jeffrey Michael Dost',
                            'ID': '3a8eb6436a8b78ca50f7e93bb2a4d1f0141212ba'
                        }
                    },
                    'Site Contact': {
                        'Primary': {
                            'Name': 'Sajesh Singh',
                            'ID': '0da9ca0b7d1d58f1a91c6797e4bb29b64846f88e'
                        },
                        'Secondary': {
                            'Name': 'AMNH OSG Contact List',
                            'ID': 'e7b8d36d684570dcb0ed8ff7b723928d5a93b513'
                        }
                    }
                },
                'FQDN': 'amnh-mendel-ce1.svc.opensciencegrid.org',
                'Services': {
                    'CE': {
                        'Description': 'American Museum of Natural History Hosted CE for Mendel cluster'
                    }
                },
                'Tags': ['CC*']
            },
            'AMNH-Huxley-AP1': {
                'Active': True,
                'Description': 'OS Pool access point',
                'ID': 1210,
                'ContactLists': {
                    'Administrative Contact': {
                        'Primary': {
                            'Name': 'Sajesh Singh',
                            'ID': '0da9ca0b7d1d58f1a91c6797e4bb29b64846f88e'
                        },
                        'Secondary': {
                            'Name': 'AMNH OSG Contact List',
                            'ID': 'e7b8d36d684570dcb0ed8ff7b723928d5a93b513'
                        }
                    },
                    'Security Contact': {
                        'Primary': {
                            'Name': 'Sajesh Singh',
                            'ID': '0da9ca0b7d1d58f1a91c6797e4bb29b64846f88e'
                        },
                        'Secondary': {
                            'Name': 'AMNH OSG Contact List',
                            'ID': 'e7b8d36d684570dcb0ed8ff7b723928d5a93b513'
                        }
                    }
                },
                'FQDN': 'huxley-osgsub-001.sdmz.amnh.org',
                'Services': {
                    'Submit Node': {
                        'Description': 'OS Pool access point'
                    }
                },
                'Tags': ['CC*', 'OSPool']
            },
            'AMNH-Mendel-AP1': {
                'Active': True,
                'Description': 'OS Pool access point',
                'ID': 1261,
                'ContactLists': {
                    'Administrative Contact': {
                        'Primary': {
                            'Name': 'Sajesh Singh',
                            'ID': '0da9ca0b7d1d58f1a91c6797e4bb29b64846f88e'
                        },
                        'Secondary': {
                            'Name': 'AMNH OSG Contact List',
                            'ID': 'e7b8d36d684570dcb0ed8ff7b723928d5a93b513'
                        }
                    },
                    'Security Contact': {
                        'Primary': {
                            'Name': 'Sajesh Singh',
                            'ID': '0da9ca0b7d1d58f1a91c6797e4bb29b64846f88e'
                        },
                        'Secondary': {
                            'Name': 'AMNH OSG Contact List',
                            'ID': 'e7b8d36d684570dcb0ed8ff7b723928d5a93b513'
                        }
                    }
                },
                'FQDN': 'mendel-osgsub-001.sdmz.amnh.org',
                'Services': {
                    'Submit Node': {
                        'Description': 'OS Pool access point'
                    }
                },
                'Tags': ['CC*', 'OSPool']
            }
        }
    }
    mock_resource_group = ResourceGroup("test_resource_group", mock_resource_group_info, mock_site, global_data.get_topology().common_data)

    mock_resource_information = {
        'Active': False,
        'Description': 'Hosted CE for FANDM-ITS',
        'ID': 1296,
        'ContactLists': {
            'Administrative Contact': {
                'Primary': {
                    'Name': 'Jeffrey Peterson',
                    'ID': '3ef2e11c271234a34f154e75b28d3b4554bb8f63'
                },
                'Secondary': {
                    'Name': 'Jeffrey Michael Dost',
                    'ID': '3a8eb6436a8b78ca50f7e93bb2a4d1f0141212ba'
                }
            },
            'Security Contact': {
                'Primary': {
                    'Name': 'Jeffrey Peterson',
                    'ID': '3ef2e11c271234a34f154e75b28d3b4554bb8f63'
                },
                'Secondary': {
                    'Name': 'Jeffrey Michael Dost',
                    'ID': '3a8eb6436a8b78ca50f7e93bb2a4d1f0141212ba'
                }
            }
        },
        'FQDN': 'fandm-its-ce1.svc.opensciencegrid.org',
        'Services': {
            'CE': {
                'Description': 'FANDM-ITS CE1 hosted CE'
            }
        },
        'Tags': ['CC*']
    }
    mock_resource = Resource("AMNH-ARES", mock_resource_information, global_data.get_topology().common_data,
                             mock_resource_group)

    mock_facility.add_site(mock_site)
    mock_site.add_resource_group(mock_resource_group)

    def test_resource_defaults(self, client: flask.Flask):
        resources = client.get('/miscresource/json').json

        # Check that it is not empty
        assert len(resources) > 0

        # Check that the resource contains the default keys
        assert set(resources.popitem()[1]).issuperset(["ID", "Name", "Active", "Disable", "Services", "Tags",
                                                        "Description", "FQDN", "FQDNAliases", "VOOwnership",
                                                        "WLCGInformation", "ContactLists", "IsCCStar"])

    def test_site_defaults(self, client: flask.Flask):
        sites = client.get('/miscsite/json').json

        # Check that it is not empty
        assert len(sites) > 0

        # Check that the site contains the appropriate keys
        assert set(sites.popitem()[1]).issuperset(["ID", "Name", "IsCCStar"])

    def test_facility_defaults(self, client: flask.Flask):
        facilities = client.get('/miscfacility/json').json

        # Check that it is not empty
        assert len(facilities) > 0

        # Check that the site contains the appropriate keys
        assert set(facilities.popitem()[1]).issuperset(["ID", "Name", "IsCCStar"])

    def test_institution_default(self, client: flask.Flask):
        institutions = client.get("/api/institutions", headers={"Accept": "application/json"}).json

        assert len(institutions) > 0

        # Check facilities exist and have the "have resources" bit flipped
        assert [i for i in institutions if i[0] == "JINR"][0][1]
        assert [i for i in institutions if i[0] == "Universidade de São Paulo - Laboratório de Computação Científica Avançada"][0][1]

        # Project Organizations exist and have "has project" bit flipped
        assert [i for i in institutions if i[0] == "Iolani School"][0][2]
        assert [i for i in institutions if i[0] == "University of California, San Diego"][0][2]

        # Both
        assert [i for i in institutions if i[0] == "Harvard University"][0][1] and [i for i in institutions if i[0] == "Harvard University"][0][2]

        # Check Project only doesn't have resource bit
        assert [i for i in institutions if i[0] == "National Research Council of Canada"][0][1] is False

        # Facility Tests
        facilities = set(global_data.get_topology().facilities.keys())

        # Check all facilities exist
        assert set(i[0] for i in institutions).issuperset(facilities)

        # Check all facilities have their facilities bit flipped
        assert all(x[1] for x in institutions if x[0] in institutions)

        # Project Tests
        projects = set(x['Organization'] for x in global_data.get_projects()['Projects']['Project'])

        # Check all projects exist
        assert set(i[0] for i in institutions).issuperset(projects)

        # Check all projects have the project bit flipped
        assert all(x[2] for x in institutions if x[0] in projects)

    def test_institution_ids(self, client: flask.Flask):
        _ = global_data.get_mappings(strict=True)
        institution_ids_list = client.get("/institution_ids").json

        assert len(institution_ids_list) > 20, "Unexpectedly few institutions: %d" % len(institution_ids_list)
        names_list = [i["name"] for i in institution_ids_list]
        names_set = set(names_list)
        duplicates = len(names_list) - len(names_set)
        assert duplicates == 0, "%d duplicate names found in institution_ids list provided by API" % duplicates

        osg_ids_list = [i["id"] for i in institution_ids_list]
        osg_ids_set = set(osg_ids_list)
        duplicates = len(osg_ids_list) - len(osg_ids_set)
        assert duplicates == 0, "%d duplicate ids found in institution_ids list provided by API" % duplicates


if __name__ == '__main__':
    pytest.main()
