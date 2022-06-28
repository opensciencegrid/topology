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

Projects data only lists execute resources by resource group but we need to know the possible CEs the job will run on so I add those as well.


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


## StashCache schema

The data for the various Stash/OSDF endpoints is split between resource and VO data.
VO YAML files have an optional DataFederation dict which contains information for how the VO's data fits into data federations.
The only supported data federation is StashCache.
The DataFederation dict is not included in any of the XMLs.

```yaml
DataFederation:
  StashCache:
    Namespaces:
      - <NAMESPACE 1>
      - <NAMESPACE 2>
      ...
      - <NAMESPACE n>
```

### Contents of a namespace in VO data

Each `<NAMESPACE>` is a dict, containing the following attributes:

```yaml
Path: <string>
```
Path (required) is the directory in the Stash/OSDF global namespace that this Namespace definition refers to.

```yaml
Authorizations:
  - PUBLIC
```
This denotes a public namespace, which does not require authentication for read access.
Public namespaces are served by public cache/origin xrootd instances.

Alternatively:
```yaml
Authorizations:
  - <DN/FQAN/SCITOKENS AUTH 1>
  ...
  - <DN/FQAN/SCITOKENS AUTH n>
```
These denote an authenticated namespace, which requires authentication for read access.
Authenticated namespaces are served by stash-cache-auth or stash-origin-auth xrootd instances.
There are three kinds of authorization types:

- DN authorization looks like

      - DN: /DC=org/DC=cilogon/C=US/O=University of Wisconsin-Madison/CN=Matyas Selmeci A148276

  it will result in a `u <HASH> ...` ID in Authfiles, where <HASH> is the X.509 hash of the DN.

  (For backwards compat, the space after the `:` can be omitted.)


- FQAN authorization looks like

      - FQAN: /glow

  it will result in a `g /glow ...` ID in Authfiles.

  (For backwards compat, the space after the `:` can be omitted.)


- SciToken authorization looks like

      - SciTokens:
          Issuer: https://chtc.cs.wisc.edu
          Base Path: /chtc
          Restricted Path: /PROTECTED/matyas,/PROTECTED/bbockelm
          Map Subject: True

  This results in an issuer block that looks like

      [Issuer https://chtc.cs.wisc.edu]
      issuer = https://chtc.cs.wisc.edu
      base_path = /chtc
      restricted_path = /PROTECTED/matyas,/PROTECTED/bbockelm
      map_subject = true

  See [the XrdSciTokens readme](https://github.com/xrootd/xrootd/tree/master/src/XrdSciTokens#readme) for a reference of what these mean.
 
  `Restricted Path` is optional (and rarely set); it is omitted if not specified. 
  `Map Subject` is optional and defaults to `false` if not specified.
  It is only used in scitokens.cfg for the origin.

```yaml
AllowedOrigins:
  - ORIGIN_RESOURCE1
  ...
  - ORIGIN_RESOURCEn
```
AllowedOrigins is a list of resource names of origins that will serve data for this namespace.
The origins must also list the namespace's VO, "ANY", or "ANY_PUBLIC" (public data only) in their AllowedVOs list in order to serve this VO's data.

```yaml
AllowedCaches:
  - ANY
```
or
```yaml
AllowedCaches:
  - CACHE_RESOURCE1
  ...
  - CACHE_RESOURCEn
```
AllowedCaches is a list of resource names of caches that will serve data for this namespace.
"ANY" will allow any cache to serve this namespace's data.
The caches must also list the namespace's VO, "ANY", or "ANY_PUBLIC" (public data only) in their AllowedVOs list in order to serve this VO's data.

```yaml
Writeback: <HOST>:<PORT>
```
Writeback is the hostname and port of the XRootD service (a stash-origin-auth, usually on 1095) that can be used for _writing_ files to.
Writeback is optional.

```yaml
DirList: <HOST>:<PORT>
```
DirList is the hostname and port of an XRootD service that can be used to get a directory listing.
DirList is optional.


### Contents of a cache in resource data
