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

This project is developed in the [Python programming language](https://www.python.org/about/)
using the [Flask Framework](https://flask.palletsprojects.com/), and
makes extensive use of Flask's default [Jinja templating engine](https://jinja.palletsprojects.com/).
[PyYAML](https://pyyaml.org/) is used for loading and saving YAML files,
and [Fast JSON schema](https://horejsek.github.io/python-fastjsonschema/) is
used to validate loaded files using JSON schemas. The Docker image uses the
[Cheroot HTTP Server](https://cheroot.cherrypy.dev/en/latest/).

## 1 Basic Example
Below is an example directory structure that can be used as input for the SCS,
illustrating some of the basic features of the SCS:
```
.
├── common/  # Common config variables are referenced using the !scs-common YAML tag
│   └── global.yaml
|       >   database:
|       >       host: 172.16.48.55
|       >       port: 1234
|
├── secrets/  # Secrets are referenced using the !scs-secret YAML tag
│   ├── database-users.yaml
|   |   >   - username: server-1
|   |   >     password: password1
|   |   >   - username: server-2
|   |   >     password: password2
|   |
│   └── scs-tokens.yaml
|       > example-user: example-user-token
|
├── config/
│   ├── database/
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
│   └── server1/
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
|   >               whitelist:
|   >                  - 127.0.0.1/32
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
using simple HTTP(S) requests:

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
using GitHub Workflows to build docker images that include your configuration
can be found in the [example-scs-configuration](https://github.com/simple-configuration-server/example-configuration)
repository.

## 2 Configuration
This section describes how to configure the SCS. To serve a set of
configuration files/variables using SCS, you will need:
1. A config directory, containing the files/templates that should be served
2. A common directory, containing yaml files with common configuration elements
   (Can be empty)
3. A secrets directory, containing secrets, such as passwords, used in
   configuration files (Optional)
4. scs-configuration.yaml, containing the configuration of the server itself
5. scs-users.yaml, containing SCS user definitions (Optional; Only if the
   built-in auth module is used)
6. scs-validate.yaml, containing the validation script settings (Optional; Only
   if validate.py is used to validate the configuration)

Examples of these are illustrated in the basic example (section 1) and included
in the [example-scs-configuration](https://github.com/simple-configuration-server/example-configuration)
repository.

### 2.1 Config Directory
The contents of this directory are served by the SCS, with the exception of
files with names that end with 'scs-env.yaml'. These files contain environment
configurations for specific endpoints, or entire directories. The URL structure
of the SCS is derived from the folder structure inside your config directory.

#### 2.1.1 *scs-env.yaml Files
Using scs-env.yaml files is optional, but allows you to configure the
templating system, validation of requests and the responses of each endpoint.
Below is a full example of all options that can be set in a
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
This files should adhere to the schema found [here](scs/schemas/scs-env.yaml),
which also includes more extensive descriptions of each proeprty. Note that
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

Values of type Object (dict) of more specific scs-env files update the contents
of less specific ones. Values with other data types are replaced, in case a
more specific scs-env file defines them also. For example, considering the
scs-env files for './root_endpoint.json' have the following contents:
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
/configs endpoint. The example file structure from section 2.1.1 would expose
the following endpoints:
```
/configs/root_endpoint.json
/configs/subdirectory/sub_endpoint
/configs/subdirectory/sub_endpoint2
```

### 2.2 Common Directory
Use the 'common' directory to store yaml files with configuration variables
that should be used by multiple endpoints. In case you're using
git for version control, you can also checkout [git submodules](https://git-scm.com/book/en/v2/Git-Tools-Submodules)
in subfolders of this directory, which gives you the option to include YAML
configuration files from other git repositories.

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

_Note: Since dots are used as a level seperator in relative references,
it's advised not to use keys containing dots in these files. By default, the
SCS will raise an error on startup if this is the case. If you need keys with
dots, disable this check by setting 'environments.reject_keys_containing_dots'
to false in scs-configuration.yaml (See section 2.4)_

### 2.3 Secrets Directory
This directory works just like the 'common' directory described above. By
defining secrets in a seperate directory, you can completely seperate your
secrets from the configuration files itself, meaning you can safely store
the rest of the configuration (everything, except the Secrets Directory
and optionally also the User Definitions) in a git repository.

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

The `environments.reject_keys_containing_dots` is discussed in the last
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
`template.rendering_options` in scs-env.yaml files, which is used to
update the globally defined options for specific endpoints.

#### 2.4.3 Logs Configuration
The SCS creates 2 types of logs:
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
example on how to do this, please see the 'deployment' section.

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

`auth.options.networks.private_only` is 'true' by default, and ensures data
on the server can only be accessed from internal subnets.
`auth.options.networks.whitelist` must be set, to indicate what IPs or subnets
are allowed to access the server. It's advised to define this as restrive as
possible. Please note that regardless of these settings, it's a good idea to
use a firewall to controll access to the server. Although unauthorized IPs are
not authorized to access any data, their requests can still flood the server,
possibly causing denial of service.

The `auth.options.max_auth_fails_per_15_min` defines the maximum number of
requests allowed per IP address with false authentication credentials (10
by default). In combination with the network whitelist, this should reduce the
chances of successfully brute-forcing the user authentication system. Even if
attackers can spoof all IP addresses, this will limit the authentication
attempts per 15 minutes to the value of this property times the size of your
whitelisted network(s).

#### 2.4.5 Extensions Configuration
You can define extensions to load at run-time, to extend the core-functionality
of SCS using third party packages. For a description of the different types of
extensions that are supported, including considerations for development of
these, see section 4.3.

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
repositories to validate if configurations are valid, by loading the server,
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
the contents are compared to the object given for the 'yaml:' key.

#### 2.6.2 SCS Configuration
The `scs_configuration` property allows you to override parts of
'scs-configuration.yaml' during validation. The following changes are
applied by default: (1) logs are directed to stdout and  (2) the auth blueprint
is disabled. You can override the default logging configuration for the
validation script by defining a custom `scs_configuration.logs` property.

You can also use this property, as illustrated in the example, to override
custom YAML tag constructors, for example when you're using a cloud-dependent
constructor in your configuration. Note that the built-in `!scs-secret`
tag is overriden by default during validation (it generates random strings) so
secrets are not required for validation.

## 3 Deployment
There are two ways to use the SCS to host your configuration: 
1. Using the official SCS Docker image
2. By cloning this repository and installing SCS locally

Because of it's simplicitly and ease of updating, deploying SCS using Docker
is the preferred method. Local installation is not recommended.

In addition to deploying SCS, you can also use logging agents to stream the
logs to a central logging database. Section 3.3 includes an example
where Elastic Filebeat is used to stream the logs to ElasticSearch.

For security considerations related to the deployement of the SCS, please
see section 3 of [SECURITY.md](SECURITY.md).

### 3.1 Docker
The SCS Docker image is published in the GitLab Container Registry of this
repository.

_Note that future versions are set to be published in the GitHub Container
Registry. After the first release on GitHub, the below link is updated
accordingly_

The simplest way to deploy the SCS with your configuration is to
use the Docker-image as-is, and use bind-mounts to set your configuration and
SSL keys on it, as illusted in the below example docker-compose.yml file:
```yaml
version: "3.9"

services:
  server:
    image: registry.gitlab.com/tom-brouwer/simple-configuration-server:1.0.2
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
      # Use a docker-volume for the logs (In case you use e.g. Filebeat, as
      # Described in section 3.3)
      - scs-logs:/var/log/scs
    environment:
      - SCS_CONFIG_DIR=/etc/scs/configuration
      # The following 2 variables can be omitted if the default values are
      # used.
      #
      # It's recommended to only disable SSL when using a reverse proxy,
      # like NGINX, for SSL termination
      - SCS_DISABLE_SSL=0
      #
      # Set the reverse proxy count >= 1 if you're using a reverse proxy that
      # sets the X-Forwarded-For header. This means the 'X-Forwarded-For'
      # header is used as the Remote Address, rather than the IP of the proxy
      # itself. The count indicates how many values should be in the
      # X-Forwarded-For headers. If you use multiple proxies, this may be
      # higher than one.
      - SCS_REVERSE_PROXY_COUNT=0
    ports:
      - 3000:80
    restart: on-failure:5
```
Alternatively, you can use CI/CD inside your configuration data repository to
build an image that includes your configuration (except the secrets) as
illustrated in the [example-scs-configuration](https://github.com/simple-configuration-server/example-configuration)
repository.

### 3.2 Local Installation
Although not recommended, you can install SCS locally, by cloning this
repository. Below is a basic example of using uWSGI to run the application.
You will need:

* A unix operating system (Windows should work, but not with below steps)
* Python 3.10 needs to be installed (Test using `python3.10 --version`)

Then:
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

### 3.3 Log Centralization
The [examples/filebeat folder](examples/filebeat/) contains a Docker
configuration for using Filebeat to stream SCS logs to an ElasticSearch
instance. Use the [Dockerfile](examples/filebeat/dockerfile) to build a
container image based on the official Filebeat Docker image, that
additionally includes:
* An 'scs' Filebeat Module
* Fields.yml configuration for SCS log contents

In the [file thats appended to fields.yml](examples/filebeat/fields.APPEND.yml)
you can see the names of the fields that are created by the
[SCS filebeat module](examples/filebeat/module/scs/), and used in ElasticSearch,
in addition to the default ECS field names. The
[configuration file for the module](examples/filebeat/modules.d/scs.yml)
can be changed to disable/enable streaming of specific logs, and change their
paths inside the container. To built the image, run:
```bash
docker build . -t filebeat-scs
```

To use it, add the following service to the 'services' section of the
Docker compose file (Section 3.1):
```yaml
filebeat:
    image: filebeat-scs
    environment:
      # See https://www.elastic.co/guide/en/beats/filebeat/8.2/running-on-docker.html
      # for more configuration options
      - output.elasticsearch.hosts=${ELASTICSEARCH_HOSTS:?error}
    volumes:
      # The logs are shared between the containers using a Docker volume
      - scs-logs:/var/log/scs
```

## 4 Development
This section discusses how to work on the SCS core or Docker container
configuration, as well as how extensions or a 3rd party auth blueprint for the
SCS can be developed.

_Note: For the process and checklist of contributing changes to this
repository, please see [CONTRIBUTING.md](CONTRIBUTING.md). If you find any
security issues, please use the process described in [SECURITY.md](SECURITY.md)
to report them_

### 4.1 SCS Core

#### 4.1.1 Preparation
To work on the core SCS code, you'll need to:

* A unix operating system (Windows should also work, but not using these steps)
* Python 3.10 installed (Test using `python3.10 --version`)

After cloning the repository locally:
1. Open a terminal in the root directory
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
#### 4.1.2 Structure
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

#### 4.1.3 Debugging and Linting
Note that this repository contains a [debugging configuration](.vscode/launch.json)
for Visual Studio Code.

Please use Flake8 for linting your code, to make sure it conforms to PEP8.

#### 4.1.4 Testing
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

Run the `./enable_githooks.sh` once to make sure the pre-commit githook of the
repository is run on commit. This runs the same code as above.

All test files simply load the Flask app using one of the test configurations
found in the 'tests/data' directory. If you need to generate output files from
the tests, e.g. to test the logging, create a 'temp' directory (See e.g.
[test_logging.py](tests/test_logging.py)). Since it's in the .gitignore
file, the temp directory is never comitted.

### 4.2 Docker Image
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

### 4.3 Extensions
The SCS is designed to be extended with additional functionality at runtime.
The following types of extensions are supported:

* **YAML Constructors**: YAML constructors allow you to add support for
  additional YAML tags to the SCS. Imagine for example you'd want to include
  secrets from a 3rd party secret store in your scs-env.yaml file, you can
  create a constructor that uses a tag like `!third-party-secret` to
  refer to these secrets. Users can pass initialization options to constructors
  from the configuration file, such as credentials for a third party service
  used by the contructor.
* **Flask Blueprints**: Flask Blueprints allow you to add functionality to the
  request/response handling of the system, for example to create custom
  request logs, or add CORS support to the system.
* **Jinja Extensions**: Jinja extensions allow you to add functions that can
  be used within configuration file templates.

The development of each of these extensions is described in sections 4.3.3 to
4.3.5. These extensions can also make use of existing SCS functions, for
example to ensure properly formatted errors are returned in a JSON response
(4.3.1) and to use the builtin logging functionality (4.3.2).

#### 4.3.1 Custom Error Responses
Use the [scs.errors](scs/errors.py) module from inside other modules to add
custom error responses to SCS. There are 2 types of errors that can be
registered with the scs.errors module:
1. Errors based on response codes and error IDs, triggered using abort()
2. Errors based on Exceptions raised in the code

You can use the first type to explicitly return errors for certain conditions,
by:
1. Registering the status code, error id and error message combination
   with the scs.errors module:
    ```python
    from scs import errors

    errors.register(
      code=429,
      id_='auth-rate-limited',
      message='Rate limited due to too many false auth attempts from this ip',
    )
    ```
2. Using the flask.abort function somewhere in your code:
   ```python
   from flask import abort

   abort(429, description={'id': 'auth-rate-limited'})
   ```

The second option is to capture exceptions that are raised inside the code, and
return a 500 error message with an explaination:
1. Create a custom error class (optional) and register it (or alternatively,
   register existing exceptions):
    ```python
    from scs import errors

    class CustomException(Exception):
      pass

    errors.register_exception(
      exception_class=CustomException,
      id_='custom-exception-occurred',
      message='A custom exception occured'
    )
2. Raise the exception:
    ```python
    raise CustomException('Exception occured')
    ```

In this case a 500 status code is returned when the exception is encountered,
and the provided id and message are returned as JSON.

Note that it's good practice to include your package name inside the error id,
since otherwise these may overlap with errors registered by other modules. For
further examples on how to use the above error handling, also take a look at
the SCS source code, since errors and exceptions are registered by multiple
built-in SCS modules.

#### 4.3.2 Using Logging
The [scs.logging](scs/logging.py) module enables you to:
1. Log custom audit events
2. Log to the SCS application log

To log custom audit events:
1. Add a custom audit event:
    ```python
    from scs import logging

    logging.register_audit_event(
      type_="custom-audit-event",
      level='INFO',
      message_template="User '{user}' has done {terrible_thing}"
    )
2. Use the 'add_audit_event' function added to the Flask.g object:
    ```python
    from Flask import g

    g.add_audit_event(
        event_type='custom-audit-event',
        # Any keyword arguments other the event_type can be used inside the
        # message template
        terrible_thing="something aweful",
    )
    ```

Note that, as with error ids, it's advised to include your package name into
the 'event_type' to prevent overlap with other extensions.

To log to the application log, use the builtin python logging module
as usual:
```python
import logging

logger = logging.getLogger(__name__)

logger.info('INFO message')
```

#### 4.3.3 YAML Constructors
If you develop YAML constructors, make sure that these inherit from the
SCSYamlTagConstructor class. Inside the constructor you can access the
path of the file itself, and change the 'resave' value on the loader,
to trigger SCS to resave a file with the constructed values (E.g. in case the
!scs-gen-secret tag is used, a secret is generated, and then saved in place of
the tag). A simple example:
```python
from scs.yaml import SCSYamlTagConstructor

class AddOwnPathConstructor(SCSYamlTagConstructor):
    """
    A YAML tag that is replaced by the path of the file itself

    Attributes:
      resave: Whether to save the generated value back to the file
    """
    # Note that self.tag can also be made dynamic, by setting it as input to
    # the init function
    tag = '!set-own-path'

    def __init__(self, *args, resave: bool, **kwargs):
        self.resave = resave
        super().__init__(*args, **kwargs)

    def construct(self, loader: Loader, node: Node) -> Any:
        # If resave is true, replace tag with value on first load.
        # Note that the 'resave' option removes any comments and additional
        # whitespace from the YAML file
        if self.resave:
          # Prevent setting it to false when self.resave=False, because another
          # constructor may have set it to True already...
          loader.resave = True
        return loader.filepath.as_posix()
```

This is confired from scs-configuration.yaml like:
```yaml
extensions:
  constructors:
    - name: mypackage.AddOwnPathConstructor
      options:
        resave: false
```

#### 4.3.4 Flask Blueprints
Any Flask Blueprint can be added from the extensions configuration. Use an
initialization function with the `bp.record` decorator, to capture any
options that are passed. A simple example:
```python
from flask import Blueprint

bp = Blueprint('custom-blueprint')

@bp.record
def init(setup_state: BlueprintSetupState):
    global blueprint_name
    opts = setup_state.options
    blueprint_name = opts['name']

@bp.after_app_request
def print_something(response: Response) -> Response:
    print(f'{blueprint_name}: This is executed after the app request')
    return response
```

This is configured from scs-configuration.yaml like:
```yaml
extensions:
  blueprints:
    - name: mypackage.mymodule.bp
      options:
        name: 'Great Blueprint!'
```

#### 4.3.5 Jinja Extensions
Note that, due to the design of Jinja extensions (See [docs](https://jinja.palletsprojects.com/en/3.0.x/extensions/#writing-extensions)), it's not possible to pass options to the
init method of an extension. However, by using the `templates.rendering_options`
property in scs-configuration.yaml, and/or  `template.rendering_options` in
scs-env files, users can extend the environment attributes, which can then be
used inside the extension. As a basic example:
```python
from jinja2.ext import Extension
import functools

def add_suffix(str_: str, *, suffix: str) -> str:
    """
    Add a suffix the end of a string
    """
    return str_ + suffix


class AddSuffixExtension(Extension):
    """
    Simple Extension that adds SCS to the end of a phrase
    """
    def __init__(self, environment):
        super().__init__(environment)
        suffix = environment.suffix_for_string
        environment.filters['add_suffix'] = functools.partial(
          add_suffix, suffix=suffix
        )
```

This is configured from scs-configuration.yaml like:
```yaml
templates:
  rendering_options:
    suffix_for_string: ' is the best!'

extensions:
  jinja2:
    - name: mypackage.AddSuffixExtension
```

### 4.4 Auth Blueprint
The same considerations as for blueprint extensions (section 4.3.4) apply to
developing an Auth Blueprint. You can use the built-in [scs.auth module](scs/auth.py)
source code as inspiration.
