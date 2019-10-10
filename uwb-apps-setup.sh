#!/bin/bash -x

cd repos/decawave-uwb-core
# Try to checkout the same branch as core from apps if it exists
git checkout -q ${TRAVIS_BRANCH}
echo -n "Core branch:"
git status -bs
cd -
echo -n "Apps branch:"
git status -bs
