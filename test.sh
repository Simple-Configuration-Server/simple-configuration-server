#!/bin/bash
set -e

# Validate python version consistency in repository
# Dockerfile and CI/CD
PYTHON_VERSION=3.10

DOCKERFILE_CONTENTS=$(cat Dockerfile)
CICDFILE_CONTENTS=$(cat ./.github/workflows/main.yml)
INSTALL_CONTENTS=$(cat install.sh)
DEV_INSTALL_CONTENTS=$(cat install.dev.sh)

if [[ $DOCKERFILE_CONTENTS != *"FROM python:$PYTHON_VERSION "* ]]; then
  echo "ERROR: Dockerfile python version inconsistent with test.sh!"
  exit 1
fi

if [[ $CICDFILE_CONTENTS != *"image: python:$PYTHON_VERSION"* ]]; then
  echo "ERROR: GitLab workflow python version inconsistent with test.sh!"
  exit 1
fi

if [[ $INSTALL_CONTENTS != *"python$PYTHON_VERSION "* ]]; then
  echo "ERROR: install.sh python version inconsistent with test.sh!"
  exit 1
fi

if [[ $DEV_INSTALL_CONTENTS != *"python$PYTHON_VERSION "* ]]; then
  echo "ERROR: install.dev.sh python version inconsistent with test.sh!"
  exit 1
fi

echo "Python version consistency check: PASSED"
echo " "

# Tests are run this way, so each file is seperately tested. We cannot re-use
# loaded modules accross tests, because the modules use global variables
find ./tests -iname "test_*.py" -print0 | xargs -0 -n1 pytest