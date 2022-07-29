#!/bin/zsh

test_topology=http://localhost:9000
prod_topology=https://topology.opensciencegrid.org

cache_args=(
    ""
    "?fqdn=sc-cache.chtc.wisc.edu"
    "?fqdn=stash-cache.osg.chtc.io"
    "?fqdn=dummy.example.net"
    "?fqdn=osg-kansas-city-stashcache.nrp.internet2.edu"
    "?fqdn=stashcache.gwave.ics.psu.edu"
)

cache_endpoints=(
    "cache/Authfile"
    "cache/Authfile-public"
    "cache/scitokens.conf"
)

origin_args=(
    ""
    "?fqdn=sc-origin2000.chtc.wisc.edu"
    "?fqdn=origin-auth2000.chtc.wisc.edu"
    "?fqdn=origin-auth2001.chtc.wisc.edu"
    "?fqdn=origin.ligo.caltech.edu"
    "?fqdn=hcc-stashcache-origin.unl.edu"
    "?fqdn=osdftest.t2.ucsd.edu"
)

origin_endpoints=(
    "origin/Authfile"
    "origin/Authfile-public"
    "origin/scitokens.conf"
)

function url_to_result_path {
    echo "$@" | tr -c A-Za-z0-9 _
}

progdir=$(dirname "$0")
rm -rf   "$progdir/testresults"
mkdir -p "$progdir/testresults"

for endpoint in "${cache_endpoints[@]}"
do
    if [[ $endpoint = *scitokens.conf ]]; then
      maybe_sort="cat"
    else
      maybe_sort="sort"
    fi
    for arg in "${cache_args[@]}"
    do
        url=$endpoint$arg
        oldfile=$progdir/testresults/$(url_to_result_path "$url").old
        newfile=$progdir/testresults/$(url_to_result_path "$url").new
        curl -L "$prod_topology/$url" | grep -v "^# /" | $maybe_sort > $oldfile
        curl -L "$test_topology/$url" | grep -v "^# DN: " | grep -v "^# FQAN: " | $maybe_sort > $newfile
    done
done

for endpoint in "${origin_endpoints[@]}"
do
    if [[ $endpoint = *scitokens.conf ]]; then
      maybe_sort="cat"
    else
      maybe_sort="sort"
    fi
    for arg in "${origin_args[@]}"
    do
        url=$endpoint$arg
        oldfile=$progdir/testresults/$(url_to_result_path "$url").old
        newfile=$progdir/testresults/$(url_to_result_path "$url").new
        curl -L "$prod_topology/$url" | grep -v "^# /" | $maybe_sort > $oldfile
        curl -L "$test_topology/$url" | grep -v "^# DN: " | grep -v "^# FQAN: " | $maybe_sort > $newfile
    done
done

#diff -U 7 $oldfile $newfile
