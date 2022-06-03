# Log Centralization using Filebeat and ElasticSearch
This folder contains an example filebeat and docker configuration to centralize
the application and audit logs from SCS.

The examples in this directory are tested with Filebeat 8.2.0, as configured
in the dockerfile.

## Contents
* **module/scs**: Contains a filebeat module that enables Filebeat to read SCS
  application and audit logs, and ship them to ElasticSearch
* **modules.d/scs.yml**: Configuration for the module. Allows users to enable
  the centralization of application and audit logs seperately, and to set
  different paths to read the logs from.
* **fields.APPEND.yml**: Contains a filebeat 'fields.yml' section that contains
  the configuration for the 'scs.*' fields in SCS. The ingest pipelines of the
  module take care of transforming the fields from the JSON logs to the correct
  fields in ES
* **dockerfile**: An example docker built file for an filebeat image that can
  read SCS logs. It implements the filebeat module from this directory, and
  appends the contents of fields.APPEND.yml to the fields.yml in the image.

## Example Usage
*Note: The configuration in this directory only serves as an example, and is
not production-ready. Please adapt it to suit your deployment*

To test filebeat locally, first build the image, for example:
`docker build . -t filebeat-scs`.

Then you can add a service for filebeat to the'docker-compose' file, described
in the main README of this repository:
```yaml
filebeat:
    image: filebeat-scs
    environment:
      - ELASTICSEARCH_HOSTS=${ELASTICSEARCH_HOSTS:?error}
    volumes:
      - scs-logs:/var/log/scs
```

For more information on running Filebeat in docker, look [here](https://www.elastic.co/guide/en/beats/filebeat/8.2/running-on-docker.html)