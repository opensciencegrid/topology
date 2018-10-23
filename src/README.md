Developer Documentation
=======================

Useful Definitions
------------------

| Field   | Definition                                                                                                                                           |
|---------|------------------------------------------------------------------------------------------------------------------------------------------------------|
| Active  | If set to `false`, the service is not up.  A resource should be marked as inactive instead of being deleted if it has recent (< 1 yr) GRACC records. |
| Disable | A value of `true` is the same as deletion. Legacy field for resources and resource groups.                                                           |

XML consumers
-------------

- AGIS (ATLAS)
- GGUS (WLCG)
- GRACC (OSG)
  - [Projects](https://github.com/opensciencegrid/gracc-request/blob/83f3fab52b108b872009430773ce8f1a9fcbe659/config/gracc-request.toml#L42)
  - [Topology](https://github.com/opensciencegrid/gracc-request/blob/83f3fab52b108b872009430773ce8f1a9fcbe659/config/gracc-request.toml#L41)
  - [VOs](https://github.com/opensciencegrid/gracc-request/blob/83f3fab52b108b872009430773ce8f1a9fcbe659/config/gracc-request.toml#L40)
- OASIS (OSG)
  - Both the stratum-0 (oasis.opensciencegrid.org) and stratum-1 (oasis-replica.opensciencegrid.org) query the XML data
    for `OASISRepoURLs`
- [Perfsonar ETF](https://my.opensciencegrid.org/rgsummary/xml?summary_attrs_showservice=on&summary_attrs_showfqdn=on&gip_status_attrs_showtestresults=on&downtime_attrs_showpast=&account_type=cumulative_hours&ce_account_type=gip_vo&se_account_type=vo_transfer_volume&bdiitree_type=total_jobs&bdii_object=service&bdii_server=is-osg&start_type=7daysago&start_date=11%2F17%2F2014&end_type=now&all_resources=on&facility_sel%5B%5D=10009&gridtype=on&gridtype_1=on&active=on&active_value=1&disable_value=0) (OSG)
- SAM (WLCG)
- SiteDB (CMS), soon to be CRIC
