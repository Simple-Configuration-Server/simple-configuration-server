"""
Test if the validate.py script fails if wrong data is returned by an
endpoint


Copyright 2022 Tom Brouwer

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""
from pathlib import Path
import sys
import os

# Add the docker folder to path, so the 'validate.py' main function can be
# imported
tests_path = Path(__file__).parent.absolute()
sys.path.append(
    Path(tests_path, '../docker').absolute().as_posix()
)
sys.path.append(
    Path(tests_path, '../').absolute().as_posix()
)
from validate import main  # noqa: E402

file_dir = Path(__file__).parent.absolute()
config_dir = Path(file_dir, 'data/2')


def test_validation_fails():
    """A wrong text response is defined for one of the endpoints"""
    validation_failed = False
    try:
        os.environ['SCS_CONFIG_DIR'] = config_dir.as_posix()
        main()
    except AssertionError as e:
        validation_failed = True
        message = e.args[0]

    assert 'Wrong text response' in message
    assert validation_failed
