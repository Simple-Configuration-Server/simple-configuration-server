# Simple Configuration Server
This repository contains the WIP code for the 'simple-configuration-server'.
This is a simple, centralized, configuration server, that hosts configuration
files as YAML, JSON or plain text from version controlled GIT repositories.
Since it seperates the secrets from the files itself, no secrets have to be
stored in version control.

The aim is to create a server that runs in a docker container, that is purely
configured through a set of yaml and/or plain text files, that can be modularly
combined to host complete configuration files for a server.

It includes a simple way to configure authentication on the server, version
configurations, and update them without downtime.

_Note that this repository currently contains work in progress code and tests_
