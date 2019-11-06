#!/bin/bash -x

cd repos/decawave-uwb-core
# Try to checkout the same branch as core from apps if it exists
git checkout -q ${BRANCH_NAME}
echo -n "Core branch:"
git status -bs
cd -
# Apply Patches
cd repos/apache-mynewt-core
git checkout -- ./
git apply ../decawave-uwb-core/patches/apache-mynewt-core/mynewt_1_7_0*.patch
cd -
