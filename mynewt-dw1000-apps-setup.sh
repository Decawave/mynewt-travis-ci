#!/bin/bash -x

cd repos/mynewt-dw1000-core
# Try to checkout the same branch as core from apps if it exists
git checkout -q ${TRAVIS_BRANCH}
echo -n "Core branch:"
git status -bs
cd -
