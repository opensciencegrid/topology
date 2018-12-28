#!/bin/sh

cd "$(dirname "$0")/../../"
export PYTHONPATH=src/:$PYTHONPATH
set -e
set -x
./bin/osg-origin-authfile hcc-anvil-175-55.unl.edu
