#!/bin/zsh

test_topology=http://localhost:5000
prod_topology=https://topology.opensciencegrid.org

cache_args=(
    ""
    "?fqdn=sc-cache.chtc.wisc.edu"
    "?fqdn=stash-cache.osg.chtc.io"
    "?fqdn=dummy.example.net"
    "?fqdn=osg.kans.nrp.internet2.edu"
)

cache_endpoints=(
    "cache/Authfile"
    "cache/Authfile-public"
    "cache/scitokens.conf"
)

origin_args=(
    ""
    "?fqdn=sc-origin.chtc.wisc.edu"
    "?fqdn=sc-origin2000.chtc.wisc.edu"
    "?fqdn=origin.ligo.caltech.edu"
    "?fqdn=hcc-stashcache-origin.unl.edu"
)

origin_endpoints=(
    "origin/Authfile"
    "origin/Authfile-public"
    "origin/scitokens.conf"
)

oldfile=/tmp/stashcachetest-prod.txt
newfile=/tmp/stashcachetest-test.txt
truncate -s0 $oldfile
truncate -s0 $newfile
for endpoint in "${cache_endpoints[@]}"
do
    for arg in "${cache_args[@]}"
    do
        url=$endpoint$arg
        printf "%s\n\n\n" "$url" >> $oldfile
        printf "%s\n\n\n" "$url" >> $newfile
        curl -L "$prod_topology/$url" | sort >> $oldfile
        curl -L "$test_topology/$url" | sort >> $newfile
    done
done

printf "\n\n\n\n" >> $oldfile
printf "\n\n\n\n" >> $newfile

for endpoint in "${origin_endpoints[@]}"
do
    for arg in "${origin_args[@]}"
    do
        url=$endpoint$arg
        printf "%s\n\n\n" "$url" >> $oldfile
        printf "%s\n\n\n" "$url" >> $newfile
        curl -L "$prod_topology/$url" | sort >> $oldfile
        curl -L "$test_topology/$url" | sort >> $newfile
    done
done

diff -u $oldfile $newfile
