### JJRunner

Run remote jenkins jobs locally.

You need:
  * Install ``python3-git`` and ``python3-jenkins`` packages.
  * export ``JJR_USER`` and ``JJR_PASS`` variables with credentials to access to CI website
  * add a gpg key without passphrase
    * export DEBEMAIL and DEBFULLNAME variables accordingly with the key
    * add the key to gpg keyrings of lxc images used to build packages

  * add a ``$HOME/monotone`` folder
  * add a ``$HOME/gem_ubuntu_repo`` folder

All the parameters defined in the job are inherited with their default value.

Using a string describing a flat json structure you can override values for any interactive job parameters and environment variables.

```
$ # an example of calls used to build locally and upload
$ # to an experimental launchpad repository all the engine packages stack
$ jjrunner.py -a '{"GEM_MASTER_BRANCH": "jjrunner", "GEM_SET_DEBUG": "true", "build_for_ubuntu_trusty": "false", "build_for_ubuntu_xenial": "true"}' master_oq-python

$ jjrunner.py -a '{"GEM_MASTER_BRANCH": "jjrunner", "GEM_SET_DEBUG": "true", "build_for_ubuntu_trusty": "false", "build_for_ubuntu_xenial": "true", "JOB_NAME": "master_oq-libs" }' zdevel_oq-libs

$ jjrunner.py -a '{"GEM_TEST_FOR_JJRUNNER": "true", "GEM_JENKINS_REASON": "Started by timer", "GEM_LAUNCHPAD_REPO": "test4", "GEM_MASTER_BRANCH": "jjrunner", "GEM_SET_DEBUG": "true", "run_dev_tests": "false", "build_for_ubuntu_trusty": "true" }' master_oq-engine
```

#### jobs_checker.sh
This script allow to check ``zdevel_`` and ``master_`` prefixed Jenkins jobs differences and send email if some pair is different.

##### cron configuration

To automate the checks you can use cron with a command line like this:
```
1 * * * * export PATH=<jjrunner path>:$PATH && export ADMIN_MAIL="<admins emails list>" && export JJR_USER=<username> && export JJR_PASS=<password> && jobs_checker.sh
```
