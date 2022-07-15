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

### 2.3 Secrets Directory

### 2.4 scs-configuration.yaml

### 2.5 scs-users.yaml

### 2.6 scs-validate.yaml


## 3 Deployment
There are two ways to use the SCS to host your configuration: 
1. Using the official SCS Docker image
2. By cloning this repository and installing SCS locally

Because of it's simplicitly and ease of updating, deploying SCS using Docker
is the preferred way to deploy the SCS.

### 3.1 Docker
The SCS Docker image is published in the GitLab Container Registry for the
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
