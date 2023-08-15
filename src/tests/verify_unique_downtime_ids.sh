#!/bin/bash

cd "$(dirname "$0")/../../topology"

dupes=$( grep -h '^ *ID:' */*/*_downtime.yaml | awk '{print $2}' | sort |
         uniq -c | awk '$1 > 1 {print $2}' )

if [[ $dupes ]]; then
  for d in $dupes; do
    echo "ERROR: Found duplicate downtime ID: $d in:"
    grep -n "^ *ID: *$d *$" */*/*_downtime.yaml | sed "s/^/- /"
  done
  exit 1
else
  echo A-OK
fi
