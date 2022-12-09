# Simple Configuration Server: Security
The SCS is meant to be both simple and secure by design, and the configuration
of SCS is aimed at providing sensible defaults.

In case you do find security problems with the system, section 1 describes
how to report them. Section 2 describes how information about
vulnerabilities is shared with SCS users, and contains an overview of
previously found security issues. Section 3 describes the security
considerations for users to deploy SCS in their environment.

## 1 Reporting Vulnerabilities
Report any vulnerability using the process described below. This process
applies to vulnerabilities found in the Core SCS features and official Docker
images, of which the source-code and configuration are included in this
repository. This process also applies to any vulnerabilities that originate
from dependencies used by SCS. Vulnerabilities found in third party
exentions to SCS are not covered, and should be reported to their respective
maintainers instead.

Please report vulnerabilities you find in either the latest version of SCS
or in previous releases (In case these are not listed in the table of section
2 of this document).

When investigating and communicating vulnerabilities, please consider the
following:
* Do you best to avoid privacy violations, destruction of data, and
  interruption or degradation of services that use the SCS
* Provide a reasonable amount of time to resolve vulnerabilities prior to
  disclosing the issue to the public or a third-party.

When reporting a vulnerability, please submit the following:
* A detailed report of the issue, with reproducible steps and a clearly
  defined impact
* When the vulnerability affects a specific release, please reproduce the issue
  using an official SCS Docker image, and report the version number.
* When the vulnerability affects a non-versioned release (e.g. the latest
  code on main branch), please include the git commit hash, and the output of
  the `pip freeze` command in your report

Vulnerabilities must be reported by [creating a new issue](https://gitlab.com/tom-brouwer/simple-configuration-server/-/issues/new)
in the GitLab issue tracker, rather than on GitHub. GitLab is used for this,
instead of GitHub, because it supports confidential issues. All vulnerabilities
reported via GitLab **must be marked as confidential** before sumission.

## 2 Sharing Vulnerabilities
Minor vulnerabilities that are unlikely to have an immediate impact on existing
deployments, will be made public after a successfull fix is available for the
issue. In case reported vulnerabilities are likely to already be exploited in
existing SCS deployments, vulnerability information, including information
about possible migigations may be shared before an official fix is available,
to notify users of the risk.

All vulnerabilities that can be remotely exploited are assigned a CVE ID.
It is therefore advised that all users with active SCS deployments subscribe
to receive notifications from a vulnerability database (e.g. [VulDB](https://vuldb.com/))
to make sure they are notified in case new CVE IDs related to SCS are registered.

The below table contains an overview of previously found vulnerabilities in
SCS:
| Identifier | Affected Versions | More Information | Solution |
| :--------- | :---------------- | :--------------- | :------- |

## 3 Securing SCS Deployments
By default, the SCS provides a reasonable amount of protection from
unauthorized access of your data by enabling you to restrict the authorizations
of individual users, and by applying rate-limits to prevent brute-foricing.
Please note the following when deploying SCS:

* **Secure Transfer**: When transferring data such as secrets to a machine or
  service, always use encrypted connections (e.g SSH/HTTPS)
* **Keep Secrets Seperately**: It's recommended to seperate your secrets
  by creating a seperate 'secrets' folder, and applying the '!scs-secret' tag
  to reference them inside scs-env.yaml files. If you define secrets directly
  inside scs-env.yaml files, but you misspell the name of the file so it
  doesn't end   with 'scs-env.yaml', your secrets will be directly
  available to end-users via an additional endpoint.
* **Secure File-System**: Since 'secrets' are stored in yaml files by default,
  put measures in place to prevent unauthorized access of the file-system:
    * Never store secrets on machines that are used by others
    * Use file-system permissions in UNIX to set the correct owner (`chown`)
      and allow only read/write access to the owner (`chmod 600`) to prevent
      compromised other processes from being able to access the data
    * If you're using a system like Kubernetes or Docker Swarm, use the
      built-in secrets management features to expose the secrets files to the
      containers.
* **Use HTTPS**: Even on private networks, it's best to use HTTPS
  to prevent man-in-the-middle attacks. If you're not hosting the system under
  a domain, you can use self-signed certificates, and configure it's public key
  as trusted on the clients. (E.g. generate as described [here](https://www.digitalocean.com/community/tutorials/how-to-create-a-self-signed-ssl-certificate-for-nginx-in-ubuntu-22-04)
  and use the --cacert option in curl).
* **Use a Firewall**: Although IPs may not be whitelisted in SCS, SCS still has
  to process their requests before rejecting them. This means even non-globally
  whitelisted IPs can be used for a DOS attack. Therefore, especially for
  deployments that are open to public networks, also use an IP whitelist in
  your firewall, to prevent unauthorized IPs from being able to contact the
  server.
* **Apply Restrictive Authorizations**: If you're using the default 'scs.auth'
  module for Authentication/Authorization, make sure that your settings are
  restrictive: (1) You should only (globally) whitelist networks that are
  owned by you, and (2) Users should only be able to access the paths they
  need, from their own IPs. For example, if you create users for each server
  in your environment, only the IP of that server should be whitelisted for the
  user, and not the entire subnet. Also, the user should only be able to
  access paths relevant for the systems on that server. Restricting
  the globally whitelisted IPs additionally ensures that brute-force attacks
  are less likely to be succesful, since rate-limits apply per IP.
* **Disable Infinite Restarts**: Since rate-limiting is tracked in-memory,
  it is reset after a restart. In case the system automatically restarts after
  a crash an infinite amount of times, this behaviour can be exploited to
  effectively by-pass the rate-limiter. Limit the number of restarts of the
  system to prevent this.
* **Archive and Monitor Audit Logs**: For file-based logs, SCS uses a rotating
  file handler to prevent the file-system from overflowing. To be able to trace
  access attempts and access to secrets, make sure logs are archived before
  this happens, for example by using the log centralization strategy described
  in the [documentation](https://simple-configuration-server.github.io/docs/deployment/log-centralization).
  By streaming the audit logs to a database, you can enable monitoring, for
  example to receive notifications in case many failed access attempts are
  detected in a short period of time.
