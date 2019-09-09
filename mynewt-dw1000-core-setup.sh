#!/bin/bash -x

# Manually install the apps repo to avoid circular references
git clone https://github.com/decawave/mynewt-dw1000-apps repos/mynewt-dw1000-apps
cd repos/mynewt-dw1000-apps
# Try to checkout the same branch as core from apps if it exists
git checkout -q ${TRAVIS_BRANCH}
echo -n "Apps branch:"
git status -bs
cd -
