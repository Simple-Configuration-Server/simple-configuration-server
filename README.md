# Simple Configuration Server (SCS)
The simple configuration server allows you to host directories containing
configuration files or variables over HTTP(S). When used in it's simplest
form, it functions as little more than a basic file server, although it
contains further features that allow you to keep configuration variables and
secrets completely seperate, thereby enabling users to version-control 
complete configurations, for example in git, seperate from any secrets.

Other features include:
* **Jinja2 Templates**: In addition to hosting simple files, templates allow
  you to dynamically render configuration files/variables. Thereby adding the
  ability to define variables used accross multiple endpoints centrally, and
  reference them in multiple configuration file templates.
* **POST requests with template variables**: Clients can send one or more
  template variables via POST requests, to include server-specific configuration
  parameters in returned configuraiton files, such as path to specific
  directories on machines.
* **Simple User Authentication**: The built-in user authentication system
  uses a simple file-based configuration, but allows fine-grained control over
  the urls users can access, and the IP-addresses/Subnets they can access them
  from.
* **Extendability**: At it's core, SCS is already a powerfull system, but
  inside the 'scs-configuration.yaml' file you can further configure:
    1. A custom Flask blueprint to use for authentication, instead of the
       system mentioned above
    2. Additional YAML tag constructors
    3. Additional Flask blueprints
    4. Additional template extensions for Jinja2

## 1 Basic Example
Below is an example directory structure that can be used as input for the SCS,
illustrating some of the basic features of the SCS:
```
.
├── common  # Common config variables are referenced using the !scs-common YAML tag
│   └── global.yaml
|       >   database:
|       >       host: 172.16.48.55
|       >       port: 1234
|
├── secrets  # Secrets are referenced using the !scs-secret YAML tag
│   ├── database-users.yaml
|   |   >   - username: server-1
|   |   >     password: password1
|   |   >   - username: server-2
|   |   >     password: password2
|   |
│   └── scs-tokens.yaml
|       > example-user: example-user-token
|
├── config
│   ├── database
│   │   ├── create_users.json  # Example of using jinja2 templating
|   |   |   >   [
|   |   |   >   {% for user in users %}
|   |   |   >       {"username": "{{ user.username }}", "password": "{{ user.password }}"}{% if not loop.last %},{% endif %}
|   |   |   >   
|   |   |   >   {% endfor %}
|   |   |   >   ]
|   |   |
│   │   └── create_users.json.scs-env.yaml  # scs-env.yaml files define the environment/config for an endpoint
|   |       >   template:
|   |       >       context:
|   |       >           users: !scs-secret 'database-users.yaml'
|   |       >   response:
|   |       >       headers:
|   |       >           Content-Type: application/json
|   |
│   └── server1
│       ├── db-config.json  # Uses common variables and secrets (See scs-env file below)
|       |   >   {
|       |   >     "ip": "{{ database.host }}",
|       |   >     "port": {{ database.port }},
|       |   >     "username": {{ username }},
|       |   >     "password": {{ password }},
|       |   >   }
|       |
│       ├── db-config.json.scs-env.yaml
|       |   >   template:
|       |   >       context:
|       |   >           database: !scs-common 'global.yaml#database'
|       |   >           username: !scs-secret 'database-users.yaml#[0].username'
|       |   >           password: !scs-secret 'database-users.yaml#[1].password'
|       |   >   response:
|       |   >       headers:
|       |   >           Content-Type: application/json
|       |
│       ├── db-config.json.template
|       |   > (Same as db-config.json)
|       |
│       ├── db-config.json.template.scs-env.yaml  # Disable templating to host original file contents
|       |   >   template:
|       |   >       enabled: false
|       |
│       ├── environment  # Plain text variable, without any configuration
|       |   > production
|       |
│       ├── ip-address
|       |   >   172.16.48.{{ 10 + server_number }}
|       |
│       └── scs-env.yaml  # scs-env files can also be defined for complete directories (and children)
|           >   template:
|           >       context:
|           >           server_number: 1
|           >   response:
|           >       headers:
|           >           Content-Type: text/plain
|
├── scs-configuration.yaml  # Configuration of SCS itself
|   >   directories:
|   >       common: !scs-expand-env ${SCS_CONFIG_DIR}/common
|   >       config: !scs-expand-env ${SCS_CONFIG_DIR}/config
|   >       secrets: &secrets-dir !scs-expand-env ${SCS_CONFIG_DIR}/secrets
|   >   logs:
|   >   audit:
|   >       stdout:
|   >       level: INFO
|   >   application:
|   >       stdout:
|   >       level: INFO
|   >   auth:
|   >       options:
|   >           users_file: !scs-expand-env ${SCS_CONFIG_DIR}/scs-users.yaml
|   >           directories:
|   >               secrets: *secrets-dir
|   >           networks:
|   >               private_only: true
|   >               whitelist:
|   >                  - 127.0.0.1/32
|   >           max_auth_fails_per_15_min: 10
|
└── scs-users.yaml  # User definitions used by the scs.auth module
    > - id: example-user
    >   token: !scs-secret 'scs-tokens.yaml#example-user'
    >   has_access:
    >       to_paths:
    >          - /configs/*
    >       from_networks:
    >          - 127.0.0.1/32
```
After setting the SCS_CONFIG_DIR environment variable to the root directory of
the above and starting SCS, the configuration can be accessed
using simple HTTP(S) reqeusts:

```
> curl http://localhost:5000/configs/database/create_users.json --header "Authorization: Bearer example-user-token"
[
    {"username": "server-1", "password": "password1"},
    {"username": "server-2", "password": "password2"}
]
> curl http://localhost:5000/configs/server1/environment --header "Authorization: Bearer example-user-token"
production
> curl http://localhost:5000/configs/server1/ip-address --header "Authorization: Bearer example-user-token"
172.16.48.11
> curl http://localhost:5000/configs/server1/db-config.json --header "Authorization: Bearer example-user-token"
{
"ip": "172.16.48.55",
"port": 1234,
"username": server-1,
"password": password2,
}
> curl http://localhost:5000/configs/server1/db-config.json.template --header "Authorization: Bearer example-user-token"
{
"ip": "{{ database.host }}",
"port": {{ database.port }},
"username": {{ username }},
"password": {{ password }},
}
```

Because SCS allows you to fully seperate the secrets from the actual
configuration files, configurations hosted using the SCS can be be completely
stored in GIT repositories. An example of what such a repository would look
like, including a more elaborate illustration of SCS features and a recipe for
using GitLab CI/CD to build docker images that include your configuration can
be found in the [example-scs-configuration](https://gitlab.com/Tbro/example-scs-configuration)
repository.

## 2 Configuration
To serve a set of configuration files/variables using SCS, you will need:
1. A config directory, containing the files/templates that should be served
2. A common directory, containing yaml files with common configuration elements (Can be empty)
3. A secrets directory, containing secrets, such as passwords, used in configuration files (Optional)
4. scs-configuration.yaml, containing the configuration of the server itself
5. scs-users.yaml, containing SCS user definitions (Optional; Only if the built-in auth module is used)
6. scs-validate.yaml, containing configuration to validate configurations (Optional; Only if validate.py is used to validate the configuration)

Examples of these are included in the 'Basic Example' above and included in the
[example-scs-configuration](https://gitlab.com/Tbro/example-scs-configuration)
repository.

### 2.1 Config Directory
The contents of this directory are served by the SCS, with the exception of
files with names that end with 'scs-env.yaml', which contain environment
configurations for specific endpoints, or entire directories. The URL structure
of the SCS is derived from the folder structure inside your config directory.

#### 2.1.1 *scs-env.yaml Files
Using scs-env.yaml files is optional, but allows you to configure the
templating system, limit the allowed requests and control the responses of each
endpoint. Below is a full example of all options that can be set in a
*scs-env.yaml file:
```yaml
template:
  context:  # Variables passed for templating
    variable: value
    common_variable: !scs-common 'global.yaml#var_array.[5]'
    secret: !scs-secret 'system-users.yaml#user.password'
  rendering_options:  # Override the default jinja rendering options from scs-configuration.yaml
    lstrip_blocks: false
  enabled: true  # To host simple files, templating can also be disabled

request:
  methods:  # Allowed methods
    - GET
    - POST
  schema:   # Schema used to validate POST request JSON body
    type: object
    additionalProperties: false
    required:
      - memory_size
    properties:
      memory_size:
        type: integer

response:
  status: 200  # Set the default status of the response
  headers:  # Set headers on the response
    Content-Type: text/plain
```
The schema this file should adhere to inclused more extensive descriptions for
each property, and can be found [here](scs/schemas/scs-env.yaml). Note that
this schema also defines the defaults for each property, used when properties
are not defined. All properties in scs-env files are optional, but empty
scs-env files should be omitted.

Note that, in case you simply want to host the files in your config directory,
without using any of the templating features, you can simply place the
following scs-env.yaml file in the root of the config dir:
```yaml
template:
  enabled: false
```

As mentioned, *scs-env.yaml files can apply to entire directories or to
specific endpoints (files) only. Multiple scs-env files can apply to same
endpoint, in which case properties defined in the more specific scs-env.yaml
file, override properties in the less specific one. For example, consider the
following example:
```
.
├── root_endpoint.json
├── root_endpoint.json.scs-env.yaml
├── scs-env.yaml
└── subdirectory
    ├── scs-env.yaml
    ├── sub_endpoint2
    ├── sub_endpoint2.scs-env.yaml
    └── sub_enpoint
```
The './scs-env.yaml' applies to all endpoints and the './subdirectory/scs-env.yaml'
applies to all endpoints in the subdirectory. For example for
'./root_endpoint.json' the following scs-env files are used:
1. './scs-env.yaml'
2. './root_endpoint.json.scs-env.yaml'

Similairly, the following apply to './subdirectory/sub_endpoint2':
1. './scs-env.yaml'
2. './subdirectory/scs-env.yaml'
3. './subdirectory/sub_endpoint2.scs-env.yaml'

Values of type Object(/dict) of more specific scs-env files update the contents
of less specific ones. Values with other data types are replaced, in case a
more specific scs-env file defines them also. E.g. considering scs-env files for
'./root_endpoint.json' have the following contents:
1. **./scs-env.yaml**
   ```yaml
   template:
     context:
       key1: general
       key2: general
   response:
     status: 200
     headers:
       Content-Type: text/plain
   ```
2. **./root_endpoint.json.scs-env.yaml**
   ```yaml
   template:
     context:
       key2: specific
   response:
     status: 418
     headers:
      X-TeaType: Rooibos
   ```

Then the configuration for the endpoint would look like (excl. default values):
```yaml
template:
  context:
    key1: general
    key2: specific
response:
  status: 418
  headers:
    Content-Type: text/plain
    X-TeaFlavor: Rooibos
```

#### 2.1.2 URL structure
All files inside the config directory are used as server endpoints, except the
ones with names ending with scs-env.yaml. The files are served under the
/configs endpoint. The example file structure from 2.1.1 would expose the
following endpoints:
```
/configs/root_endpoint.json
/configs/subdirectory/sub_endpoint
/configs/subdirectory/sub_endpoint2
```

### 2.2 Common Directory
Use the 'common' directory to store yaml files with configuration variables
that should be used by multiple endpoints. In case you're using
git for version control, you can also checkout [git submodules](https://git-scm.com/book/en/v2/Git-Tools-Submodules)
in subfolders of this directory, so you can include YAML configuration files
from other git repositories.

You can reference common variables from scs-env.yaml files, using the
'!scs-common' YAML tag. For example, given the following common directory
layout:
```
.
└── global.yaml
    > global_object:
    >   key: value
    > global_array:
    >   - value1
    >   - value2
```
These can be referenced from scs-env files, like:
```yaml
template:
  context:
    object: !scs-common 'global.yaml#global_object'
    key: !scs-common 'global.yaml#global_object.key'
    array: !scs-common 'global.yaml#global_array'
    array_item: !scs-common 'global.yaml#global_array.[0]'
```

_Note: Since dots are used as a level seperator in the relative references,
it's advised not to use keys containing dots in these files. By default, the
SCS will produce an error on startup if this is the case. If you need keys with
dots, disable this check by setting 'environments.reject_keys_containing_dots'
to false in scs-configuration.yaml (See section 2.4)_

### 2.3 Secrets Directory
This directory works just like the 'common' directory described above. By
defining secrets in a seperate directory, you can completely seperate your
secrets from the configuration files itself, meaning you can safely store
the rest of the configuration (everything, except the Secrets Directory
and optionally the User Definitions) in a git repository.

Every time a user requests an endpoint that exposes 1 or more secrets, the
user and the requested secrets are logged in the audit log.

Use the '!scs-secret' YAML tag to reference secrets files and variables in
the secrets directory.

### 2.4 Server Configuration (scs-configuration.yaml)
The scs-configuration.yaml file defines the configuration of the server itself.
The following is an example of a complete configuration:
```yaml
directories:  # Discussed in secions 2.1 to 2.3
  common: !scs-expand-env ${SCS_CONFIG_DIR}/common
  config: !scs-expand-env ${SCS_CONFIG_DIR}/config
  secrets: &secrets-dir !scs-expand-env ${SCS_CONFIG_DIR}/secrets

environments:
  cache: true
  reject_keys_containing_dots: true

templates:
  cache: true
  validate_on_startup: true
  rendering_options: {}

logs:
  audit:
    file:
      path: /var/log/scs/audit.log.jsonl
      max_size_mb: 1
      backup_count: 5
      level: INFO
  application:
    stdout:
      level: INFO
  # Optionally, define an alternative string to use for the 'source' field in
  # the logs (default: scs)
  # source_name: scs

auth:
  # By default the scs.auth.bp flask blueprint is used for authentication
  # blueprint: scs.auth.bp
  options:
    users_file: !scs-expand-env ${SCS_CONFIG_DIR}/scs-users.yaml
    directories:
      secrets: *secrets-dir
    networks:
      private_only: true
      whitelist:
      - 127.0.0.1/32
      - 172.16.134.0/24
    max_auth_fails_per_15_min: 10

extensions:
  constructors: []
    # - name: scs.dummy_constructors.GeneratePhraseConstructor
    #   options:
    #     startswith: 'This is great because:'
  blueprints: []
    # - name: scs.dummy_blueprint.bp
    #   options:
    #     print_all_requests: true
  jinja2: []
    # - name: scs.jinja_extensions.GreatExtension
```
Note that only the 'directories', 'logs' and 'auth' top-level properties are
required. A full description of the format of this file, including the defaults
that are used if properties are not defined, can be found in the
[scs-configuration.yaml schema](scs/schemas/scs-configuration.yaml).

#### 2.4.1 Environment Configuration
By default `environments.cache` is true, meaning scs-env.yaml files are only
loaded once at startup. If you make changes to these files, with this set to
true, you'll have to restart the server.

The `environments.reject_keys_containing_dots` is discussed in the final
paragraph of section 2.2.

#### 2.4.2 Templates Configuration
By default, `templates.cache` is true, meaning that if you change endpoint
files for which templating is enabled (default), you need to restart the server
for the changes to take effect.

If `templates.validate_on_startup` is enabled (default), all environment files
and templates are loaded once, to verify that the syntax of these files are
correct. Please note that if you have endpoints which depend on variables
being passed via POST requests, without a backup value defined in the
`template.context`, loading of these templates may fail.

`templates.rendering_options` sets the default rendering options for jinja2
templates (See options [here](https://jinja.palletsprojects.com/en/3.0.x/api/#jinja2.Environment.overlay)).
Note that the [configuration file schema](scs/schemas/scs-configuration.yaml)
already defines global defaults. If you want to override the defaults, you need
to specify new values for these. Setting an empty object for this will still
cause the default settings to be applied. If you need to use alternative
rendering_options for specific endpoints, you can also define
`template.rendering_options` in specific scs-env.yaml file, which is used to
update the globally defined options.

#### 2.4.3 Logs Configuration
The SCS creates 2 different logs:
1. `audit` logs: These contain audit events of the following types (stored
   in the event.type field):
   * `config-loaded`: An authorized user loaded a config file
   * `secrets-loaded`: An authorized user loaded secrets
   * `unauthenticated`: An unauthenticted client tried to access and endpoint
   * `rate-limited`: An IP address was rate-limited because of too many
     authentication attempts
   * `unauthorized-ip`: An authenticated user tried to access the SCS from an
     unauthorized ip address
   * `unauthorized-path`: An authenticated user tried to access an unautorized
     path
2. `application` logs: These contain general application logs, such as internal
   errors of the SCS

_Note that the set of audit event types listed under (1) can be extended by
third party modules, see section 'development'_

The SCS produces logs in the JSON-lines format by default. Please see the
AppLogFormatter and AuditLogFormatter classes in the
[logging module](scs/logging.py) for the exact format of these.

Using the configuration file you can set the logs to either output to a
file, which is auto-rotated by SCS. Use this in combination with a log
centralization agent, like Elastic Filebeat, to centralize your logs. For an
example on how to do this, please see the 'recipes' section below.

Alternatively you can simply output the logs to the console, by setting the
stdout option. In this case you can for example see the logs via the
`docker logs` command.

#### 2.4.4 Auth configuration
Use the `auth.blueprint` setting to define the flask blueprint you want to
use for user-authentication. When omitted, the default 'scs.auth.bp' will be
used.

The `auth.options` object is passed directly to the blueprint as the
BluePrintSetupState.options attribute. The below discusses the available
options for the builtin auth module.

`auth.options.users_file` defines the location of scs-users.yaml (see section
2.5). The `directories.secrets` defines the directory to be referenced
using the `!scs-secret` YAML tag inside the scs-users.yaml file. If you want
to use the same folder when other secrets are kept, you can simply use a YAML
anchor, as illustrated in the example.

`auth.options.networks.private_only` can be set to 'true' to ensure data
on the server can only be accessed from internal subnets.
`auth.options.networks.whitelist` must be set, to indicate what IPs or subnets
are allowed to access the server. It's advised to define this as restrive as
possible. Please note that regardless of these settings, it's a good idea to
use a firewall to controll access to the server. Although unauthorized IPs are
not authorized to access any data, their requests can still flood the server, possibly causing denial of service.

The `auth.options.max_auth_fails_per_15_min` defines the maximum number of
requests allowed per IP address with false authentication credentials. In
combination with the network whitelist, this should reduce the chances of
successfully brute-forcing the user authentication system. Even if attackers
can spoof all IP addresses, this will limit the authentication attempts per 15
minutes to the value of this property times the size of your whitelisted
network(s).

#### 2.4.5 Extensions Configuration
By defining extensions, you can further extend the functionality of SCS at
runtime. The `extensions.constructors` property allows users to define
additional YAML tag constructors, which can then be used from within
scs-env.yaml files. An example would be to load a tag constructor that
retrieves secrets from 3rd party secret stores.

By adding `extensions.blueprints`, additional Flask blueprints can be loaded
at runtime. Flask blueprints can add functionality to process requests or
responses, e.g. to add custom logging or add specific headers to responses.

By adding `extensions.jinja2`, you can load extensions to the templating
system, so you can use custom functions inside the templates.

Development considerations for these extensions are defined in the section
'Development' of this README.

### 2.5 User Definitions (scs-users.yaml)
This file is only required if you're using the builtin `scs.auth` module for
authentication (default). As mentioned in section 2.4.4 you can set the
location of this file inside the scs-configuration.yaml file.

A singe-user scs-users.yaml would look like:
```yaml
- id: example-user
  token: !scs-secret 'scs-tokens.yaml#example-user'
  has_access:
      to_paths:
        - /configs/*
      from_networks:
        - 127.0.0.1/32
```
All properties are required, as defined in the [schema](scs/schemas/scs-users.yaml).

You always have to whitelist both the 'paths' as well as the
'from_networks' for each user. You can use '*' as a wildcard character in the
paths. Note that the 'from_networks' have to be subset of the globally allowed
IPs that are defined at `auth.options.networks.whitelist` in
scs-configuration.yaml. If you want to re-use parts like 'from_networks', use
[YAML anchors](https://docs.gitlab.com/ee/ci/yaml/yaml_optimization.html#anchors).

If you want to put your scs-users.yaml in a git repository, seperate the
secrets as in the example above. Note, as listed in section 2.4.4, the
!scs-secret YAML tag refers to the `auth.options.directories.secrets` rather
than `directories.secrets` (though you can set these to the same value).

### 2.6 Validation Script Configuration (scs-validate.yaml)
This configuration file does not apply to the server itself, but to the
[validate.py script](docker/validate.py). This script is included inside the
SCS docker image, and is aimed to be used inside CI/CD pipelines of
respositories, to validate if configurations are valid, by loading the server,
and testing the responses of each endpoint.

Below is a full example of this file:
```yaml
endpoints:
  /configs/cluster_name: false
  /configs/custer_name_redirect:
    request:
      method: GET
    response:
      status: 301
      headers:
        Location: /configs/cluster_name
      text: 'validate against this'
  /configs/test.json:
    response:
      json:
        validate: true
        against: true
        this: true
        object: true
  /configs/test.yaml:
    response:
      yaml:
        validate: true
        against: true
        this: true
        object: true
  /configs/*.yml:
    response:
      format: yaml
      headers:
        Content-Type: application/x-yaml

scs_configuration:
  extensions:
    constructors:
      - name: scs.yaml.SCSSimpleValueConstructor
        options:
            tag: '!cloud-dependent-tag'
            value: A default value to return for this tag

handle_errors: false

allow_secrets: false
```
The full schema for this file can be found [here](docker/scs-validate.SCHEMA.yaml).
Note that, since all properties of this file are optional, validate.py can
also be run if this file is omitted.

The `handle_errors` property defines if internal errors should be handled or
raised. In case you want to test if specific endpoints returns a 500 status
code , set this to 'true'.

Set `allow_secrets` to true, in case the configuration you're testing includes
secrets. Note that this is not advised, and therefore this is set to 'false' by
default.

#### 2.6.1 Endpoints
The `endpoints` property allows you to define test/validation
configurations for one or more endpoints. Just like with the 'from_paths' of
scs-users.yaml, wildcards can be used to define endpoints. Note that if
'endpoints' is omitted from the configuration, or if some endpoints are not
defined under 'endpoints', these are validated using the default configuration
(Request Method GET; Response status code < 400). If you don't want to validate
an endpoint, you need to specifically disable it, by setting 'false' instead of
an object.

In case an endpoint both matches a specific url in this configuration, as
well as a pattern with a wildcard, both configurations are used, but settings
in the longer pattern/url (more specfic) override settings in the shorter
pattern/url(less specific). In the above example, `/configs/test.yaml` both
matches the pattern as the specific configuration. This means (1) the yaml
format is validated, (2) the Content-Type response header is validated and (3)
the contents are compared to the object given for the 'yaml:' key. (In this
specific case, point 3 would already have enabled the 'format' validation also)

#### 2.6.2 SCS Configuration
The `scs_configuration` property allows you to override parts of
'scs-configuration.yaml' during validation. The following changes are
applied by default: (1) logs are directed to stdout and  (2) the auth blueprint
is disabled. You can override this default logging configuration for the
validation script by defining a custom `scs_configuration.logs` property.

You can also use this property as illustrated at the top, to override custom
YAML tag constructors, e.g. in case you've specified a cloud-dependent
constructor in your default configuration. Note the the built-in `!scs-secret`
tag is overriden by default during validation (it generates random strings) so
secrets are not required for validation.

## 3 Deployment
There are two ways to use the SCS to host your configuration: 
1. Using the official SCS Docker image
2. By cloning this repository and installing SCS locally

Because of it's simplicitly and ease of updating, deploying SCS using Docker
is the preferred method. Local installation is not recommended.

### 3.1 Docker
The SCS Docker image is published in the GitLab Container Registry of this
repository.

The simplest way to deploy the SCS with your configuration is to
use the Docker-image as-is, and use bind-mounts to set your configuration and
SSL keys on it, as illusted in the below example docker-compose.yml file:
```
version: "3.9"

services:
  server:
    image: registry.gitlab.com/tbro/simple-configuration-server:1.0.0
    volumes:
      # If all configuration, except secrets, are in a repository:
      - ./configuration-repository/configuration:/etc/scs/configuration
      # The secrets are mounted to a seperate directory. Set directories.secrets
      # in scs-configuration.yaml accordingly
      - ./.local/secrets:/etc/scs/secrets
      # When SCS_DISABLE_SSL=0 (default) you need to mount your cert (chain) and
      # private key
      - ./.local/ssl/cert-chain.crt:/etc/ssl/certs/scs.crt
      - ./.local/ssl/private-key.key:/etc/ssl/private/scs.key
    environment:
      - SCS_CONFIG_DIR=/etc/scs/configuration
      # The following can be ommitted, since it's the default value. It's
      # recommended to only disable SSL when using a reverse proxy, like NGINX,
      # for SSL termination
      - SCS_DISABLE_SSL=0
    ports:
      - 3000:80
```
Alternatively, you can use CI/CD inside your configuration data repository to
build an image that includes the configuration (except the secrets) as
illustrated in the [example-scs-configuration](https://gitlab.com/Tbro/example-scs-configuration)
repository.

### 3.2 Local Installation
Although not recommended, you can install SCS locally, by cloning this
repository. Below is a basic example of using uWSGI to run the application.
You will need:

* A unix operating system (Windows should work, but not with below steps)
* Python 3.10 needs to be installed (Test using `python3.10 --version`)

Now:
1. Create a .local subdirectory: `mdkir -p .local`
2. Create an app.py file inside the .local directory, with the following
   contents:
    ```python
    import scs

    app = scs.create_app()
    ```
3. Open a terminal (bash) in the root directory of this repository, and do:
    ```bash
    ./install.sh
    source .env/bin/activate
    pip install uwsgi
    export PYTHONPATH=$(pwd)
    # Choose appropriate directories, make sure they exist
    export SCS_CONFIG_DIR=/etc/scs
    export SCS_LOG_DIR=/var/log/scs
    # Now start the app from uWSGI
    cd .local
    uwsgi -s /tmp/scs.sock --manage-script-name --mount /=app:app
    ```

uWSGI should now be running the SCS application. For further documentation, for
example on how to configure NGINX, please look at the [Flask documentation](https://flask.palletsprojects.com/en/2.0.x/deploying/uwsgi/).
