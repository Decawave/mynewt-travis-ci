#!/bin/bash -x

# Manually install the apps repo to avoid circular references
git clone https://github.com/decawave/mynewt-dw1000-apps repos/mynewt-dw1000-apps
CORE_BRANCH=$(git status -bs|head -1|awk '{print $2}')
cd repos/mynewt-dw1000-apps
git checkout -q ${CORE_BRANCH}
git status -bs
cd -
