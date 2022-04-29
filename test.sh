#!/bin/bash

# Tests are run this way, so each file is seperately tested. We cannot re-use
# loaded modules accross tests, because the modules use global variables
find ./tests -iname "test_*.py" -print0 | xargs -0 -n1 pytest
