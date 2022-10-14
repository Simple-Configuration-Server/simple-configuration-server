# Simple Configuration Server (SCS)
A Server for hosting configuration files and variables that's designed to
be simple do deploy and use. With SCS, you can host directories with
configuration files and variables directly over HTTP(S), like any other
file-server. Unlike simple file-servers however, SCS offers the following:

* **Jinja2 Templates**: In addition to hosting simple files, templates allow
  you to dynamically render configuration files/variables. Thereby adding the
  ability to define variables used accross multiple endpoints centrally, and
  reference them in multiple configuration file templates.
* **Seperation of Secrets**: Using the `!scs-secret` YAML-tag you can reference
  secrets stored in a seperate location. In combination with the templating
  system you can completely seperate your configuration from secrets. This
  allows you to securely _version-control your configuration using Git_.
* **POST requests with template variables**: Clients can send one or more
  template variables via POST requests, to include server-specific configuration
  parameters in returned configuration files, such as paths to specific
  directories on machines.
* **Simple User Authentication**: The built-in user authentication system
  uses a simple file-based configuration, but allows fine-grained control over
  the urls users can access, and the IP-addresses/subnets they can access them
  from.
* **Extendability**: The SCS core functionality can be further extended at
  runtime, by configuring any of the following in the configuration file:
    1. A custom Flask blueprint for authentication, to replace the
       default SCS user authentication system mentioned above
    2. Additional YAML tag constructors, with functions you can use to
       extend the YAML language used in scs-env files.
    3. Additional Flask blueprints that can pre- or post-process the requests
       and responses of the server.
    4. Additional Jinja2 template extensions, allowing you to use custom
       functions and tags inside your configuration file templates.

Please find the the full documentation, including usage examples, on the
[Simple Configuration Server Website](https://simple-configuration-server.github.io/).

This project is developed in the [Python programming language](https://www.python.org/about/)
using the [Flask Framework](https://flask.palletsprojects.com/), and
makes extensive use of Flask's default [Jinja templating engine](https://jinja.palletsprojects.com/).
[PyYAML](https://pyyaml.org/) is used for loading and saving YAML files,
and [Fast JSON schema](https://horejsek.github.io/python-fastjsonschema/) is
used to validate loaded files using JSON schemas. The Docker image uses the
[Cheroot HTTP Server](https://cheroot.cherrypy.dev/en/latest/).

## Development
This section describes how you can contribute to the development of core
SCS features. For instructions on developing extensions for SCS, please refer
to the [extensions documentation](https://simple-configuration-server.github.io/extensions).

_Note: For the process and checklist of contributing changes to this
repository, please see [CONTRIBUTING.md](CONTRIBUTING.md). If you find any
security issues, please use the process described in [SECURITY.md](SECURITY.md)
to report them._

### Setup
To work on the core SCS code, you'll need:

* A unix operating system (Windows should also work, but not using these steps)
* Python 3.10 installed (Test using `python3.10 --version`)

After creating a fork and cloning the repository locally:
1. Open a terminal in the root directory of this repository
2. Enable the githooks: `./enable_githooks.sh`. This ensures tests are run on
   commit
3. Run `./install.dev.sh` to install the Python virtual environment for
   development
4. Activate the environment: `source .env/bin/activate`
5. You should now be able to run the development server, e.g. using one of the
   test configurations:
    ```bash
    export SCS_CONFIG_DIR=$(pwd)/tests/data/1
    mkdir -p /var/log/scs
    export SCS_LOG_DIR=/var/log/scs
    export FLASK_APP=scs
    export FLASK_ENV=development
    flask run
    ```
### Code Structure
The SCS code is structured as a Python package inside the 'scs' directory of
this repository. The main entrypoint for the server is the scs.create_app()
function, which is a factory function for the Flask App. The SCS code is
divided over the following modules:
* [auth.py](scs/auth.py) contains the Flask blueprint for the built-in
  Authentication/Authorization system.
* [configs.py](scs/configs.py) contains the Flask blueprint with the main
  application logic such as the Flask view function responsible for loading and
  rendering the configuration files/templates.
* [errors.py](scs/errors.py) contains the Flask blueprint that error handling
  logic for SCS, such as formatting error responses as JSON rathern than HTML.
  (See section 4.3.1 for how to register and send error responses)
* [logging.py](scs/logging.py) contains the logging configuration, including
  Formatters for both the application and audit logs. (See section 4.3.2 for
  how to log to use the audit and application logs)
* [tools.py](scs/tools.py) contains common functions used throughout the SCS
  package
* [yaml.py](scs/yaml.py) contains the logic for YAML loading, including the
  default YAML constructors used by SCS. TODO: REFERENCE

User configuration files are validated during loading using the JSON schemas in
the 'scs/schemas' directory. If you want to add support for new properties to
any of these files, the schema needs to be updated.

Note that the schema also contains defaults for optional properties. The
fastjsonschema package used by SCS ensures that these defaults are
used in case the optional properties are not defined. For example, the
_DEFAULT_ENV inside [configs.py](scs/configs.py) is loaded directly from the
[scs-users.yaml schema](scs/schemas/scs-users.yaml), by validating an empty
dictionary. Changing any default settings should preferably be done by changing
the JSON-schema only.

### Debugging and Linting
This repository contains a [debugging configuration](.vscode/launch.json)
for Visual Studio Code. Please use Flake8 for linting your code, to make sure
it conforms to PEP8.

### Tests
If you make any changes to the code, please add to or update the tests
accordingly.

The tests for the SCS package are defined in the 'tests' directory, and can
be run using pytest. Please note that it's not possible to simply run
the `pytest` command, which loads all test files at once. Because the SCS
package uses global variables to store configuration, this will cause conflicts.
Therefore pytest should be run on each test_*.py file seperatly. The easiest
way to do this, is to run the test.sh script which also does some more
consistency checks:
```bash
# In case the environment is not installed or up-to-date
./install.dev.sh
source .env/bin/activate
# Run all tests:
./test.sh
```

All test files simply load the Flask app using one of the test configurations
found in the 'tests/data' directory. If you need to generate output files from
the tests, e.g. to test the logging, create a 'temp' directory (See e.g.
[test_logging.py](tests/test_logging.py)). Since it's in the .gitignore
file, the temp directory is never comitted.

### Docker Image
Assests specific to the Docker Image are inside the 'docker' directory. These
include:
* [config/](docker/config/): Directory containing a sample/default configuration that's
  copied to the Docker image
* [server.py](docker/server.py): Simple Python application that uses the
  cheroot HTTP server to serve the application.
* [validate.py](docker/validate.py): Python application that loads creates the
  Flask app with the user-configuration, and tests if all endpoints are
  working.
* [scs-validate.SCHEMA.yaml](docker/scs-validate.SCHEMA.yaml): The JSON schema
  to validate the configuration file of validate.py against. As described in
  4.1.2, the default property values are included in the JSON schema, and are
  loaded if certain properties, or the entire file, is omitted.

The default command of the Docker image is to start the server, as
configured in the [Dockerfile](Dockerfile). Users can change the command to
`python validate.py` to use the same image to validate their configuration
repository contents. The Docker image for this repository is built with CI/CD
(See configuration [here](.github/workflows/main.yml)) when git tags are pushed
to GitHub.