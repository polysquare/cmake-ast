#!/bin/bash
# /ci/install-cmake-from-repo
#
# Helper script to install cmake from a repository
# line passed on the commandline.
#
# See LICENCE.md for Copyright information
echo "$@" >> /etc/apt/sources.list
apt-get update -y --force-yes -qq
apt-get remove cmake -y --force-yes -qq
apt-get install cmake -y --force-yes -qq
