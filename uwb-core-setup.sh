#!/bin/bash -x

# Manually install the apps repo to avoid circular references
git clone https://github.com/Decawave/uwb-apps repos/decawave-uwb-apps
cd repos/decawave-uwb-apps
# Try to checkout the same branch as core from apps if it exists
git checkout -q ${TRAVIS_BRANCH}
echo -n "Apps branch:"
git status -bs
cd -

# Try to checkout the same branch as core from drivers too
if (( "${TRAVIS_BRANCH}" != "master" ));then
    if [ -d repos/decawave-uwb-dw1000 ];then
        cd repos/decawave-uwb-dw1000
        git checkout -q ${TRAVIS_BRANCH}
        cd -
    fi

    if [ -d repos/decawave-uwb-dw3000-c0 ];then
        cd repos/decawave-uwb-dw3000-c0
        git checkout -q ${TRAVIS_BRANCH}
        cd -
    fi
fi

# Apply relevant patches to mynewt core
cd repos/apache-mynewt-core
MYNEWT_CORE_VERSION=$(git status |head -1|sed -e "s/HEAD detached at //"  -e "s/_tag//")
find ../../patches/apache-mynewt-core/ -name "${MYNEWT_CORE_VERSION}*" | while read name;do
    git apply $name;
done
cd -
