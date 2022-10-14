# Contributing to SCS Development
Anyone can contribute new features or fixes to the simple configuration
server, or the Docker configuration of SCS. You can use the GitHub issue
tracker to report bugs or request new features, and use pull-requests
to submit source-code changes.

_Note that the process of developing the SCS, and the tools to use, are
described in the 'development' section of the [README](README.md)_

## 1 Bug Reports and Feature Requests
Always start by creating an issue in the issue tracker. Before
doing so, please consider the following:
* **Bug reports**: When reporting a bug, make sure to report (1) the SCS
  version or git commit hash in which you found the bug, (2) the exact steps to
  reproduce it, and (3), in case you're not using the Official Docker image:
  Include information about your environment, such as your OS version and
  output of the `pip freeze` command
* **Feature requests**: This repository only contains the core SCS
  functionality and Docker image configuration. Any feature requests made in
  this repository should directly relate to these, and requested features
  should be relevant for (close-to) all SCS use-cases. Consider implementing
  features that are only relevant for a fraction of SCS users using custom
  Flask blueprints, YAML constructors or Jinja extensions, as
  described in the 'development' section of the [README](README.md).

Note that if you request a completely new feature, it's expected that you're
willing to contribute to the source-code of the SCS (See section 2)

## 2 Contributing Code
_Note: Any contribution must comply with the terms-and-conditions set-out in
section 3 of this document_

Before starting to develop a bug-fix or new feature, make sure to create an
issue first, as described in section 1. This ensures that (1) there is
only one person or group of persons, developing a feature, rather than
multiple people developing the same thing side-by-side, and (2) people are not
submitting pull-requests for changes that will never be added to the
source-code. Please wait for a response from a maintainer before submitting
a pull-request. Pull-requests not linked to an issue will be ignored.

The general process of contributing a new feature is as follows:
1. Create a fork of this repository under your own account, and create a new
   branch based on main, e.g.:
   ```bash
   git switch main
   git switch -c "feature/xxxxxxxx"
   ```
   Add both your forked repository, as well as the official repository
   as remotes to your local clone, so you can pull changes from the official
   repository, and push them to your forked repository.
2. Develop your changes in the new branch (See the 'development' section of the
   [README](README.md) for more info)
3. When finished, check the following:
     - [ ] The change is tested by adding new tests
     - [ ] Tests run successfully
     - [ ] The change is documented
     - [ ] There are no linting errors and all functions contain type
           annotations
4. Consider squashing your commits, so the change covers only 1 commit
   (as described [here](https://stackoverflow.com/questions/5189560/how-do-i-squash-my-last-n-commits-together0)).
   Only use multiple commits if otherwise you'd be implementing multiple
   changes in one commit. Also note that the commit message should be formatted
   according to the guidelines [here](https://google.github.io/eng-practices/review/developer/cl-descriptions.html).
5. Switch to main branch and pull the latest commits from the official
   repository.
6. Switch to your feature branch and run `git rebase main`. Resolve any
   conflicts that arise.
7. Create a pull-requests in this repository, and make sure no merge conflicts
   are detected. Make sure to link the pull-request to the issue in the issue
   tracker.

Note that if a maintainer reviews your work and requests changes, you'll
have to repeat steps 5 and 6, to make sure there are no merge conflicts.

## 3 Terms and Conditions
Any contibutions that you submit for inclusion in the project, shall be
included under the terms of the Apache Software License (As noted in section 5
of the [LICENSE](LICENSE) file).

By submitting your contributions you confirm that you comply with the terms
defined in the [Developer Certificate of Origin](https://developercertificate.org/),
a copy of which is provided below:
```
Developer Certificate of Origin
Version 1.1

Copyright (C) 2004, 2006 The Linux Foundation and its contributors.

Everyone is permitted to copy and distribute verbatim copies of this
license document, but changing it is not allowed.


Developer's Certificate of Origin 1.1

By making a contribution to this project, I certify that:

(a) The contribution was created in whole or in part by me and I
    have the right to submit it under the open source license
    indicated in the file; or

(b) The contribution is based upon previous work that, to the best
    of my knowledge, is covered under an appropriate open source
    license and I have the right under that license to submit that
    work with modifications, whether created in whole or in part
    by me, under the same open source license (unless I am
    permitted to submit under a different license), as indicated
    in the file; or

(c) The contribution was provided directly to me by some other
    person who certified (a), (b) or (c) and I have not modified
    it.

(d) I understand and agree that this project and the contribution
    are public and that a record of the contribution (including all
    personal information I submit with it, including my sign-off) is
    maintained indefinitely and may be redistributed consistent with
    this project or the open source license(s) involved.
```
