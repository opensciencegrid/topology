#!/bin/sh

cd "$(dirname "$0")/../../"
export PYTHONPATH=src/:$PYTHONPATH
exec ./bin/osg-authfile > /dev/null 2>&1
