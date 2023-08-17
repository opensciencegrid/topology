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
          BasePath: /chtc
          RestrictedPath: /PROTECTED/matyas,/PROTECTED/bbockelm
          MapSubject: True

  (for backwards compat, `Base Path`, `Restricted Path`, and `Map Subject` are also accepted)

  This results in an issuer block that looks like

      [Issuer https://chtc.cs.wisc.edu]
      issuer = https://chtc.cs.wisc.edu
      base_path = /chtc
      restricted_path = /PROTECTED/matyas,/PROTECTED/bbockelm
      map_subject = true

  See [the XrdSciTokens readme](https://github.com/xrootd/xrootd/tree/master/src/XrdSciTokens#readme) for a reference of what these mean.
 
  `RestrictedPath` is optional (and rarely set); it is omitted if not specified. 
  `MapSubject` is optional and defaults to `false` if not specified.
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
Writeback: https://<HOST>:<PORT>
```
Writeback is the HTTPS URL of the XRootD service (a stash-origin-auth, usually on 1095) that can be used for _writing_ files to.
Writeback is optional.

```yaml
DirList: https://<HOST>:<PORT>
```
DirList is the HTTPS URL of an XRootD service that can be used to get a directory listing.
DirList is optional.

```yaml
CredentialGeneration:
  Strategy: "Vault" or "OAuth2"
  Issuer: "<ISSUER URL>"
  BasePath: "<PATH>"
  MaxScopeDepth: <INTEGER>
  VaultServer: "<HOST>:<PORT>"
  VaultIssuer: "<ISSUER STRING>"
```
CredentialGeneration is an optional block of information about how clients can obtain credentials for the namespace.
If specified:
- Strategy must be `OAuth2` or `Vault`, depending on whether OAuth2 or a Hashicorp Vault server is being used
- Issuer is a token issuer URL
- *BasePath* (optional): If using the `OAuth2` strategy - and the base path of the issuer does not match the
  namespace path - set the base path so the correct scope prefix can be requested by the client
- MaxScopeDepth (optional) is the maximum number of path components a token's scope field may have;
  note that scopes are relative to the BasePath.
  If missing, assumed to be 0, i.e. the scope is always `/`.
- VaultServer is the endpoint for the Hashicorp Vault server used with the Vault strategy 
- *VaultIssuer* (optional): If using the `Vault` strategy, this sets the issuer name (opaque string, not
  a URL) to be used with the vault server.

### Contents of a cache or origin in resource data

A cache is a resource containing an `XRootD cache server` service.
An origin is a resource containing an `XRootD origin server` service.

The FQDN of the resource is the primary key when looking up auth info for a cache/origin.

A cache/origin should have the DN of their XRootD cert in the DN field.
A DN is *required* for a cache.
A DN is recommended for an origin.

A cache/origin must have an AllowedVOs attribute.
AllowedVOs is a list containing either
- One or more names of VOs whose namespaces the cache/origin will allow access to
- "ANY" meaning the cache/origin will serve data for any namespace
- "ANY_PUBLIC" meaning the cache/origin will serve data for any namespace that has "PUBLIC" in its Authorizations list

The namespaces must also list the cache/origin's resource name in its AllowedCaches/AllowedOrigins list.


#### Cache endpoints

The `/stashcache/namespaces` Topology endpoint contains the `<HOST>:<PORT>`
of the authenticated (`xrootd@stash-cache-auth`) and public (`xrootd@stash-cache`) services.
The default value for `<HOST>` is the resource's FQDN.
The default values for `<PORT>` are 8000 for the public service and 8443 for the authenticated service.
To override these, add a `Details/endpoint_override` and `Details/auth_endpoint_override` field to the `XRootD cache server` service.
For example:

```yaml
Resources:
  Stashcache-Chicago:
    ...
    Services:
      XRootD cache server:
        Description: Internet2 Chicago Cache
        Details:
          endpoint_override:      osg-chicago-stashcache.nrp.internet2.edu:8443
          auth_endpoint_override: osg-chicago-stashcache.nrp.internet2.edu:8444
    ...
```

### Supporting a Namespace

A namespace is public if it contains "PUBLIC" in its Authorizations list.

An origin supports a public namespace if:
- The namespace contains the origin resource name in its AllowedOrigins list, and
- The origin resource contains "ANY", "ANY_PUBLIC", or the namespace's VO in its AllowedVOs list

A cache supports a public namespace if:
- The namespace contains the cache resource name or "ANY" in its AllowedCaches list, and
- The cache resource contains "ANY", "ANY_PUBLIC", or the namespace's VO in its AllowedVOs list

A namespace is protected if it does not contain "PUBLIC" in its Authorizations list.

An origin supports a protected namespace if:
- The namespace contains the origin resource name in its AllowedOrigins list, and
- The origin resource contains "ANY" or the namespace's VO in its AllowedVOs list

A cache supports a protected namespace if:
- The namespace contains the cache resource name or "ANY" in its AllowedCaches list, and
- The cache resource contains "ANY" or the namespace's VO in its AllowedVOs list


### Origin public Authfile generation

The Authfile for a public origin is served at `/origin/Authfile-public?fqdn=<ORIGIN FQDN>`.

The public Authfile is basically a giant `u *` list:
- Allow read access to the path of each namespace supported by the origin (`rl` permissions) 

### Origin authenticated Authfile generation

The Authfile for an authenticated origin is served at `/origin/Authfile?fqdn=<ORIGIN FQDN>`.

If the origin resource specifies a DN, add a `u <DN HASH> <PATH1> rl <PATH2> rl ...` ACL for every path supported by the origin.

For every cache resource, add a `u <DN HASH> <PATH1> rl <PATH2> rl ...` ACL for every namespace supported both by that cache and the origin.

### Cache public Authfile generation

The Authfile for a public cache is served at `/cache/Authfile-public?fqdn=<CACHE FQDN>`.

The public Authfile is basically a giant `u *` list:
- Explicitly deny read access to `/user/ligo` (with `-rl` permissions)
- Allow read access to the path of each namespace supported by the cache (`rl` permissions) 

### Cache authenticated Authfile generation

The Authfile for an authenticated cache is served at `/cache/Authfile?fqdn=<CACHE FQDN>`.

- Add a `u <DN HASH> <PATH1> rl <PATH2> rl ...` for every DN listed in the Authorizations list of every namespace supported by the cache.
- Add a `g <FQAN> <PATH1> rl <PATH2> rl ...` for every FQAN listed in the Authorizations list of every namespace supported by the cache.

In addition, if the cache supports the `/user/ligo` namespace and the webapp can access LIGO's LDAP server:

- Add a `u <DN HASH> /user/ligo rl` for every DN obtained from the LIGO's LDAP server.


### Origin xrootd-scitokens config generation

The scitokens config file for xrootd-scitokens for an origin is served at `/origin/scitokens.conf?fqdn=<ORIGIN FQDN>`.

- Add an issuer block for every namespace supported by the origin that has a SciTokens entry in its Authorizations list.
  
- Add a `[Global]` section setting the audience to a list of supported VOs with issuer blocks.

The end result looks like this:
```ini
[Global]
audience = OSG

[Issuer https://osg-htc.org/ospool]
issuer = https://osg-htc.org/ospool
base_path = /ospool/PROTECTED
map_subject = True
```

### Cache xrootd-scitokens config generation

The scitokens config file for xrootd-scitokens for a cache is served at `/cache/scitokens.conf?fqdn=<CACHE FQDN>`.

- Add an issuer block for every namespace supported by the cache that has a SciTokens entry in its Authorizations list.
  
- Add a `[Global]` section setting the audience to a list of supported VOs with issuer blocks.

The end result looks like this:
```ini
[Global]
audience = IceCube, HCC, GLOW, OSG

[Issuer https://scitokens.org/icecube]
issuer = https://scitokens.org/icecube
base_path = /icecube


[Issuer https://scitokens.org/hcc]
issuer = https://scitokens.org/hcc
base_path = /hcc


[Issuer https://chtc.cs.wisc.edu]
issuer = https://chtc.cs.wisc.edu
base_path = /chtc


[Issuer https://osg-htc.org/ospool]
issuer = https://osg-htc.org/ospool
base_path = /ospool/PROTECTED
```


### Namespaces JSON generation

The JSON file containing cache and namespace information for stashcp is served at `/stashcache/namespaces`.

The JSON contains an attribute `caches` that is a list of caches.
Each cache in the list contains the following attributes:
- `endpoint`: The `<HOST>:<PORT>` of the public (`xrootd@stash-cache`) service
- `auth_endpoint`: The `<HOST>:<PORT>` of the authenticated (`xrootd@stash-cache-auth`) service
- `resource`: The resource name of the cache.

The JSON also contains an attribute `namespaces` that is a list of namespaces with the following attributes:
- `path` is the path of the namespace
- `dirlisthost` is the `<HOST>:<PORT>` of the `DirList` attribute in the namespace YAML, or `null` if missing
- `writebackhost` is the `<HOST>:<PORT>` of the `Writeback` attribute in the namespace YAML, or `null` if missing
- `readhttps` is `false` if the namespace is public and `true` if the namespace is not public
- `usetokenonread` is `true` if the namespace has a SciTokens entry in its Authorizations list and `false` otherwise
- `caches` is a list of caches that support the namespace;
  each cache in the list contains the `endpoint`, `auth_endpoint`, and `resource` attributes as in the `caches` list above
- `credential_generation` is information about how to generate credentials that can access the namespace.
  If not null, it has:
  - `strategy`: either `OAuth2` or `Vault`
  - `issuer`: the token issuer for the credentials
  - `base_path`: the base_path to use for calculation of scopes.  Only set if it is different from the namespace path; otherwise, null
  - `max_scope_depth`: integer; the max number of levels you can get a credential to be scoped for;
    "0" means that the scope will always be `/`.
    Note that scopes are usually relative to the namespace path.
  - `vault_server`: the Vault server for the `Vault` strategy or null
  - `vault_issuer`: the Vault issuer for the `Vault` strategy (or null).

The final result looks like
```json
{
  "caches": [
    {
      "auth_endpoint": "osg-gftp.pace.gatech.edu:8443",
      "endpoint": "osg-gftp.pace.gatech.edu:8000",
      "resource": "Georgia_Tech_PACE_GridFTP"
    },
    {
      "auth_endpoint": "osg-gftp2.pace.gatech.edu:8443",
      "endpoint": "osg-gftp2.pace.gatech.edu:8000",
      "resource": "Georgia_Tech_PACE_GridFTP2"
    }
  ],
  "namespaces": [
    {
      "caches": [
        {
          "auth_endpoint": "rds-cache.sdsc.edu:8443",
          "endpoint": "rds-cache.sdsc.edu:8000",
          "resource": "RDS_AUTH_OSDF_CACHE"
        }
      ],
      "credential_generation": null,
      "dirlisthost": null,
      "path": "/xenon/PROTECTED",
      "readhttps": true,
      "usetokenonread": false,
      "writebackhost": null
    },
    {
      "caches": [
        (a whole bunch)
      ],
      "credential_generation": {
        "issuer": "https://osg-htc.org/ospool",
        "max_scope_depth": 4,
        "strategy": "OAuth2"
      },
      "dirlisthost": "https://origin-auth2001.chtc.wisc.edu:1095",
      "path": "/ospool/PROTECTED",
      "readhttps": true,
      "usetokenonread": true,
      "writebackhost": "https://origin-auth2001.chtc.wisc.edu:1095"
    }
  ]
}
```
