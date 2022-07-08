# Simple Configuration Server (SCS)
The simple configuration server allows you to host directories containing
configuration files or variables over HTTP(S). When used in it's simplest
form, it functions as little more than a basic file server, although it
contains further features that allow you to keep configuration variables and
secrets completely seperate, thereby enabling users to version-control 
ccomplete configurations, for example in git, seperate from any secrets.

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

## Basic Example
To show some of the things SCS can do, here's a basic example.

If you have the following directories and files:
```
config/
    database/
        create_users.json  # Simple example of using ninja2 templating
            >   [
            >   {% for user in users %}
            >       {"username": "{{ user.username }}", "password": "{{ user.password }}"}{% if not loop.last %},{% endif %}
            >   
            >   {% endfor %}
            >   ]
        create_users.json.scs-env.yaml
            >   template:
            >       context:
            >           users: !scs-secret 'database-users.yaml'
            >   response:
            >       headers:
            >           Content-Type: application/json
    server1/
        environment  # Just a plain text variable
            >   production
        scs-env.yaml
            >   template:
            >       context:
            >           server_number: 1
            >   response:
            >       headers:
            >           Content-Type: text/plain
        ip-address  # All jinja2 templating features can be used
            >   172.16.48.{{ 10 + server_number }}
        db-config.json  # Uses variables from the common and secrets files
            >   {
            >     "ip": "{{ database.host }}",
            >     "port": {{ database.port }},
            >     "username": {{ username }},
            >     "password": {{ password }},
            >   }
        db-config.json.scs-env.yaml
            >   template:
            >       context:
            >           database: !scs-common 'global.yaml#database'
            >           username: !scs-secret 'database-users.yaml#[0].username'
            >           password: !scs-secret 'database-users.yaml#[1].password'
            >   response:
            >       headers:
            >           Content-Type: application/json
        db-config.json.template  # By setting template.enabled: false, template rendering for a endpoint or directory can be disabled
            > (Same contents as db-config.json)
        db-config.json.template.scs-env.yaml
            >   template:
            >       enabled: false
common/
    global.yaml
        >   database:
        >       host: 172.16.48.55
        >       port: 1234
secrets/
    database-users.yaml
        >   - username: server-1
        >     password: password1
        >   - username: server-2
        >     password: password2
    scs-tokens.yaml
        > example-user: example-user-token
scs-configuration.yaml
    >   directories:
    >       common: !scs-expand-env ${SCS_CONFIG_DIR}/common
    >       config: !scs-expand-env ${SCS_CONFIG_DIR}/config
    >       secrets: &secrets-dir !scs-expand-env ${SCS_CONFIG_DIR}/secrets
    >   logs:
    >   audit:
    >       stdout:
    >       level: INFO
    >   application:
    >       stdout:
    >       level: INFO
    >   auth:
    >       options:
    >           users_file: !scs-expand-env ${SCS_CONFIG_DIR}/scs-users.yaml
    >           directories:
    >               secrets: *secrets-dir
    >           networks:
    >               private_only: true
    >               whitelist:
    >                  - 127.0.0.1/32
    >           max_auth_fails_per_15_min: 10
scs-users.yaml
    > - id: example-user
    >   token: !scs-secret 'scs-tokens.yaml#example-user'
    >   has_access:
    >       to_paths:
    >          - /configs/*
    >       from_networks:
    >          - 127.0.0.1/32
```
Set your SCS_CONFIG_DIR environment varialbe to the root directory, and run
flask.

Then you can access the endpoints under config/ (except the ones ending with
scs-env.yaml) using simple HTTP(S) requests:
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
