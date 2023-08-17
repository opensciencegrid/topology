#!/bin/bash
set -e

cd "$(dirname "$0")/../../topology"

allowed='[A-Za-z0-9_ -]+'

sitenames_with_invalid_chars () {
  printf '%s\0' */*/SITE.yaml | tr '\0\n' '\n?' |
      cut -d/ -f2 | egrep "$@" -vx "$allowed"
}

if sitenames_with_invalid_chars -q; then
  echo "ERROR: Site names with invalid chars found:"
  echo
  sitenames_with_invalid_chars | sed 's/^/ - /'
  echo
  echo "ERROR: Site names must match pattern: '^$allowed$'"
  exit 1
else
  echo A-OK
fi

