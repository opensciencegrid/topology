Developer Documentation
=======================

Useful Definitions
------------------

| Field   | Definition                                                                                                                                           |
|---------|------------------------------------------------------------------------------------------------------------------------------------------------------|
| Active  | If set to `false`, the service is not up.  A resource should be marked as inactive instead of being deleted if it has recent (< 1 yr) GRACC records. |
| Disable | This is a leftover from the import process and will be removed soon.  Delete Resources and ResourceGroups instead of marking them disabled.          |

XML consumers
-------------

- AGIS (ATLAS)
- CERN
  - Queries for [Squid FQDNs](http://svnweb.cern.ch/world/wsvn/wlcgsquidmon/trunk/scripts/grid-services/get_squids.py)
- GGUS (WLCG)
  - [ALICE](https://topology.opensciencegrid.org/rgsummary/xml?gridtype=on&gridtype_1=on&voown=on&voown_sel%5B%5D=58&active=on&active_value=1)
  - [ATLAS](https://topology.opensciencegrid.org/rgsummary/xml?gridtype=on&gridtype_1=on&voown=on&voown_35=on&active=on&active_value=1)
  - [BELLE](https://topology.opensciencegrid.org/rgsummary/xml?gridtype=on&gridtype_1=on&voown=on&voown_sel%5B%5D=69&active=on&active_value=1)
  - [CMS](https://topology.opensciencegrid.org/rgsummary/xml?gridtype=on&gridtype_1=on&voown=on&voown_3=on&active=on&active_value=1&disable_value=1)
- GRACC (OSG)
  - [Projects](https://github.com/opensciencegrid/gracc-request/blob/83f3fab52b108b872009430773ce8f1a9fcbe659/config/gracc-request.toml#L42)
  - [Topology](https://github.com/opensciencegrid/gracc-request/blob/83f3fab52b108b872009430773ce8f1a9fcbe659/config/gracc-request.toml#L41)
  - [VOs](https://github.com/opensciencegrid/gracc-request/blob/83f3fab52b108b872009430773ce8f1a9fcbe659/config/gracc-request.toml#L40)
- OASIS (OSG)
  - Both the stratum-0 (oasis.opensciencegrid.org) and stratum-1 (oasis-replica.opensciencegrid.org) query the XML data
    for `OASISRepoURLs`
  - `oasis-login` queries for the list of OASIS managers as well as the `UseOASIS` field using the following:

        https://topology.opensciencegrid.org/vosummary/xml?summary_attrs_showoasis=on&oasis=on&oasis_value=1

- [Perfsonar ETF](https://topology.opensciencegrid.org/rgsummary/xml?summary_attrs_showservice=on&summary_attrs_showfqdn=on&gip_status_attrs_showtestresults=on&downtime_attrs_showpast=&account_type=cumulative_hours&ce_account_type=gip_vo&se_account_type=vo_transfer_volume&bdiitree_type=total_jobs&bdii_object=service&bdii_server=is-osg&start_type=7daysago&start_date=11%2F17%2F2014&end_type=now&all_resources=on&facility_sel%5B%5D=10009&gridtype=on&gridtype_1=on&active=on&active_value=1&disable_value=0) (OSG)
- SAM (WLCG)
- SiteDB (CMS), soon to be CRIC


## Topology cacher

The topology cacher (`topology_cacher.py`) is a script, designed to be run from cron, that downloads topology XML information,
saves it locally, and combines some of the information into JSON files.

It queries the `/rgsummary/xml` and `/miscproject/xml` endpoints (as-is, no arguments).

In addition to saving the XML files, it creates two JSON files:

- `project_resource_allocations.json` is for looking up resource allocations for projects.
- `resource_info_lookups.json` contains dicts for easier lookups of common queries, such as "resource name by FQDN."

### project_resource_allocations.json

This conversion is done by `TopologyData.get_project_resource_allocations()` which converts XML from miscproject.xml like
```xml
<Projects>
    <Project>
        <Name>MyProject</Name>
        <ResourceAllocations>
            <ResourceAllocation>
            <Type>Other</Type>
            <SubmitResources>
                <SubmitResource>Submit1</SubmitResource>
                <SubmitResource>Submit2</SubmitResource>
            </SubmitResources>
            <ExecuteResourceGroups>
                <ExecuteResourceGroup>
                    <GroupName>ExampleNetCEs</GroupName>
                    <LocalAllocationID>ID1</LocalAllocationID>
                </ExecuteResourceGroup>
            </ExecuteResourceGroups>
            </ResourceAllocation>
        </ResourceAllocations>
    </Project>
</Projects>
```
into a Python dict like
```python
{
    "MyProject": [
        {
            "type": "Other",
            "submit_resources": [
                { "group_name": "ExampleNetSubmits", "name": "Submit1", "fqdn": "submit1.example.net" },
                { "group_name": "ExampleNetSubmits", "name": "Submit2", "fqdn": "submit2.example.net" }
            ],
            "execute_resource_groups": [
                {
                    "group_name": "ExampleNetCEs",
                    "local_allocation_id": "ID1",
                    "ces": [
                        { "name": "CE1", "fqdn": "ce1.example.net" },
                        { "name": "CE2", "fqdn": "ce2.example.net" }
                    ]
                }
            ]
        }
    ]
}
```
Resource names, Resource Group names, CEs, and FQDN info are all taken fron rgsummary.xml.


```json
{
  "ACE_LIAID": [],
  "CHTC-Staff": [ {
      "execute_resource_groups": [ {
          "ces": [ {
              "fqdn": "itb-slurm-ce.osgdev.chtc.io",
              "name": "CHTC-ITB-SLURM-CE"
            }
          ],
          "group_name": "CHTC-ITB",
          "local_allocation_id": "glow"
        }
      ],
      "submit_resources": [ {
          "fqdn": "submittest0000.chtc.wisc.edu",
          "group_name": "CHTC-ITB",
          "name": "CHTC-ITB-submittest0000"
        }
      ],
      "type": "Other"
    }
  ]
}
```

Projects data only lists execute resources by resource group but we need to know the possible CEs the job will run on so I add those ad well.


### resource_info_lookups.json example

```json
{
  "resource_lists_by_group": {
    "AGLT2": [
      {
        "fqdn": "squid.aglt2.org",
        "group_name": "AGLT2",
        "name": "AGLT2-squid",
        "service_ids": [
          "138"
        ],
        "tags": []
      },
      {
        "fqdn": "sl-um-es3.slateci.io",
        "group_name": "AGLT2",
        "name": "AGLT2-squid-2",
        "service_ids": [
          "138"
        ],
        "tags": []
      }
    ],
    "AMNH": [
      {
        "fqdn": "hosted-ce22.opensciencegrid.org",
        "group_name": "AMNH",
        "name": "AMNH-ARES",
        "service_ids": [
          "1"
        ],
        "tags": [
          "CC*"
        ]
      }
    ]
  },
  "resources_by_fqdn": {
    "249cc.yeg.rac.sh": {
      "fqdn": "249cc.yeg.rac.sh",
      "group_name": "CyberaEdmonton",
      "name": "CYBERA_EDMONTON",
      "service_ids": [
        "1"
      ],
      "tags": []
    },
    "40.119.41.40": {
      "fqdn": "40.119.41.40",
      "group_name": "UCSDT2",
      "name": "UCSDT2-Cloud-3-squid",
      "service_ids": [
        "138"
      ],
      "tags": []
    }
  },
  "resources_by_name": {
    "AGLT2-squid": {
      "fqdn": "squid.aglt2.org",
      "group_name": "AGLT2",
      "name": "AGLT2-squid",
      "service_ids": [
        "138"
      ],
      "tags": []
    },
    "AGLT2-squid-2": {
      "fqdn": "sl-um-es3.slateci.io",
      "group_name": "AGLT2",
      "name": "AGLT2-squid-2",
      "service_ids": [
        "138"
      ],
      "tags": []
    }
  }
}
```
service_ids are numeric -- see `services.yaml` in the Topology data for the corresponding names.

