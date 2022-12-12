# Copyright 2022 The envd Authors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import glob
import os
import subprocess
from typing import List, Literal
import argparse
import logging

logging.basicConfig(
    level=logging.INFO, format="[%(asctime)s-%(levelname)s]: %(message)s"
)

TEST_NAME_SYMBOL = "It"
DYNAMIC_NODE_SYMBOL = "undefined"

EXTRACT_GLOB_PATH = "e2e/**/*.go"
EXCLUDE_GLOB_PATH = "e2e/*/docs/*.go"

# Build inject parameters
ROOT = "github.com/tensorchord/envd"
VERSION = (
    subprocess.check_output(
        "git describe --match 'v[0-9]*' --always --tags --abbrev=0",
        shell=True,
    )
    .decode()
    .strip()
    .rstrip()
)
BUILD_DATE = (
    subprocess.check_output(
        "date -u +'%Y-%m-%dT%H:%M:%SZ'",
        shell=True,
    )
    .decode()
    .strip()
    .rstrip()
)
GIT_COMMIT = (
    subprocess.check_output(
        "git rev-parse HEAD",
        shell=True,
    )
    .decode()
    .strip()
    .rstrip()
)
GIT_TREE_STATE = (
    subprocess.check_output(
        "git rev-parse HEAD",
        shell=True,
    )
    .decode()
    .strip()
    .rstrip()
)
GIT_TAG = (
    subprocess.check_output(
        "git describe --tags --abbrev=0",
        shell=True,
    )
    .decode()
    .strip()
    .rstrip()
)


def extract_files() -> List[str]:
    """extract file list from e2e test path, exclude `suite_test.go` and docs test

    Return:
        files (List[str]): test files
    """
    test_files = list(
        set(glob.glob(EXTRACT_GLOB_PATH, recursive=True))
        - set(glob.glob(EXCLUDE_GLOB_PATH, recursive=True))
    )
    # filter out suite_test.go and e2e_helper.go for avoid duplicate
    test_files = [file for file in test_files if not file.endswith("suite_test.go")]
    test_files = [file for file in test_files if not file.endswith("e2e_helper.go")]
    return test_files


def run_test(
    files: List[str],
    ci_index: int,
    ci_total: int,
    mode: Literal["safe", "import"],
):
    """run tests focus on part of them decide by job or ci id

    Args:
        files (List[str]): test files to be select from
        ci_index (int): job or ci id
        ci_total (int): job or ci number of total
    """
    logging.info(
        f"ldflag argument:\n\
        VERSION: {VERSION}\n\
        BUILD_DATE: {BUILD_DATE}\n\
        GIT_COMMIT: {GIT_COMMIT}\n\
        GIT_TREE_STATE: {GIT_TREE_STATE}\n\
        GIT_TAG: {GIT_TAG}"
    )
    desc_run = [files[i] for i in range(len(files)) if i % ci_total == ci_index]
    logging.info(f"run {len(desc_run)} test files: {desc_run}")

    desc_regex = "".join([f'--focus-file "{decs}" ' for decs in desc_run])
    cmd = f'ginkgo run -r --ldflags "-s -w -X {ROOT}/pkg/version.version={VERSION} \
            -X {ROOT}/pkg/version.buildDate={BUILD_DATE} \
            -X {ROOT}/pkg/version.gitCommit={GIT_COMMIT} \
            -X {ROOT}/pkg/version.gitTreeState={GIT_TREE_STATE} \
            -X {ROOT}/pkg/version.gitTag={GIT_TAG} \
            -X {ROOT}/pkg/version.developmentFlag=true \
            -X {ROOT}/pkg/version.ghaBuildMode={mode}" \
            --cover --covermode atomic --coverprofile e2e-{ci_index}-coverage.out \
            --coverpkg {ROOT}/pkg/... {desc_regex} -v --timeout 15m --race ./e2e/...'

    proc_env = os.environ.copy()
    proc_env["GIT_LATEST_TAG"] = GIT_TAG
    proc_env["ENVD_ANALYTICS"] = "false"
    proc = subprocess.run(cmd, capture_output=False, shell=True, env=proc_env)

    if proc.returncode != 0:
        raise RuntimeError(f"ginkgo test failed: return code {proc.returncode}")


def main():
    parser = argparse.ArgumentParser(
        description="Github Action Test load-balance runner for Envd"
    )
    parser.add_argument("ci_index", help="index of job to run, range [0, ci_total-1]")
    parser.add_argument("ci_total", help="number of jobs")
    parser.add_argument(
        "--export-cache",
        required=False,
        action="store_true",
        help="running mode, something for export/import cache, empty for only import cache",
    )
    args = parser.parse_args()

    ci_index: int = int(args.ci_index)
    ci_total: int = int(args.ci_total)
    mode: Literal["safe", "import"] = "safe" if args.export_cache else "import"
    if ci_index >= ci_total or ci_index < 0 or ci_total <= 0:
        raise RuntimeError(
            f"bad argument ci_index {ci_index} and ci_total {ci_total}, should be 0 <= ci_index < ci_total"
        )
    test_files = extract_files()
    test_files = sorted(test_files)
    average_workload = len(test_files) / ci_total
    logging.info(f"extracted {len(test_files)} test files, see: {test_files}")
    logging.info(f"average tests carried per job: {average_workload}")

    if average_workload > 2:
        logging.info(
            "average tests carried per job[{average_workload}] > 2, "
            "as maximum time of estimated test case may be 300s, "
            "we recommend to increase ci_total to make total time less than 10min"
        )
    run_test(test_files, ci_index, ci_total, mode)


if __name__ == "__main__":
    main()
