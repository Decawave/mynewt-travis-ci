#!/bin/bash -x

# Manually install the apps repo to avoid circular references
if [ ! -d repos/decawave-uwb-apps ];then
    git clone git@github.com:decawave/uwb-apps.git repos/decawave-uwb-apps
else
    cd repos/decawave-uwb-apps
    git fetch
fi

cd repos/decawave-uwb-apps
# Try to checkout the same branch as core from apps if it exists
git checkout -q ${BRANCH_NAME}
echo -n "Apps branch:"
git status -bs
cd -
# Apply Patches
cd ${WORKSPACE}/repos/apache-mynewt-core
git checkout -- ./
git apply ../../patches/apache-mynewt-core/mynewt_1_7_0*.patch
cd ${WORKSPACE}
