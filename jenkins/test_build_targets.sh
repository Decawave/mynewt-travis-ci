#!/bin/bash -x

# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#  http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.

EXIT_CODE=0

export
# Check that the bin path is setup properly
if [[ ! $PATH == *"$JENKINS_BIN"* ]];then
    export PATH=${JENKINS_BIN}:$PATH
fi

TARGETS=$(cat ${WORKSPACE}/targets.txt)
for target in ${TARGETS}; do
    echo "Building target=$target"

    if echo $target |grep -q -e "^unittest\$";then
        echo "Skipping dummy target unittest"
        continue
    fi

    if echo $target |grep -q "cmake_generic";then
        make -f Makefile.cmake generic && make -C ./build_generic
        rc=$?
        [[ $rc -ne 0 ]] && EXIT_CODE=$rc
        continue
    fi

    if echo $target |grep -q "cmake_cortex-a73";then
        make -f Makefile.cmake cortex-a73 && make -C ./build_cortex-a73
        rc=$?
        [[ $rc -ne 0 ]] && EXIT_CODE=$rc
        continue
    fi

    # Without suppressing output, travis complains that the log is too big
    # Without output, travis terminates a job that doesn't print out anything in a few minutes
    newt build -q -l info $target

    rc=$?
    [[ $rc -ne 0 ]] && EXIT_CODE=$rc
done

exit $EXIT_CODE
