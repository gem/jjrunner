#!/usr/bin/env python3
from collections import OrderedDict
from jenkins import Jenkins
import os
import stat
from os.path import expanduser
import sys
from xml.etree import ElementTree
import argparse
import json
import tempfile
import re
import git
import subprocess
from subprocess import TimeoutExpired
import getpass

# TODO:
#    check if builtin_vars are used in config or in command
#    config: DONE - convert to dict
#            DONE - override with external values
#            save to file to be loaded by scripts
#    run scripts

builtin_vars = [
    "BRANCH_NAME", "CHANGE_ID", "CHANGE_URL", "CHANGE_TITLE", "CHANGE_AUTHOR",
    "CHANGE_AUTHOR_DISPLAY_NAME", "CHANGE_AUTHOR_EMAIL", "CHANGE_TARGET",
    "BUILD_NUMBER", "BUILD_ID", "BUILD_DISPLAY_NAME", "JOB_NAME",
    "JOB_BASE_NAME", "BUILD_TAG", "EXECUTOR_NUMBER", "NODE_NAME",
    "NODE_LABELS", "WORKSPACE", "JENKINS_HOME", "JENKINS_URL", "BUILD_URL",
    "JOB_URL", "GIT_COMMIT", "GIT_PREVIOUS_COMMIT",
    "GIT_PREVIOUS_SUCCESSFUL_COMMIT", "GIT_BRANCH", "GIT_LOCAL_BRANCH",
    "GIT_URL", "GIT_COMMITTER_NAME", "GIT_AUTHOR_NAME", "GIT_COMMITTER_EMAIL",
    "GIT_AUTHOR_EMAIL"]


def main():
    parser = argparse.ArgumentParser(description='Execute CI jobs locally')
    parser.add_argument('jobname',
                        help='name of the job that you want to run locally')
    parser.add_argument('--args', '-a',
                        help='JSON dictionary to override job arguments')
    parser.add_argument('--dryrun', '-d', action='store_true',
                        help=('dryrun with all command and parameters '
                              'saved in /tmp directory'))
    parser.add_argument('--reason', '-r', help=('override build reason'),
                        default=None)
    args = parser.parse_args()

    jobname = args.jobname
    print("ARGS: jobname: [%s], args [%s]" % (args.jobname, args.args))

    src = 'https://ci.openquake.org/'
    jjr_user = os.getenv('JJR_USER', None)
    jjr_pass = os.getenv('JJR_PASS', None)
    if jjr_user is None or jjr_pass is None:
        print("JJR_USER and/or JJR_PASS environment variables are not set")
        sys.exit(1)
    server = Jenkins(src, username=jjr_user, password=jjr_pass)
    job_conf = server.get_job_config(jobname)
    tree = ElementTree.fromstring(job_conf)

    configs = tree.find('properties').find(
        'hudson.model.ParametersDefinitionProperty').find(
            'parameterDefinitions')

    # collect params from job config
    params = OrderedDict()

    params['GEM_JENKINS_REASON'] = {
        'name': 'GEM_JENKINS_REASON',
        'desc': 'auto-generated'}
    if args.reason is None:
        params['GEM_JENKINS_REASON']['defa'] = (
            'Started by user %s' % getpass.getuser())
    else:
        params['GEM_JENKINS_REASON']['defa'] = args.reason

    params['JOB_NAME'] = {'name': 'JOB_NAME', 'defa': jobname,
                          'desc': 'auto-generated'}
    params['JENKINS_HOME'] = {'name': 'JENKINS_HOME', 'defa': expanduser("~"),
                              'desc': 'auto-generated'}
    params['BUILD_NUMBER'] = {'name': 'BUILD_NUMBER', 'defa': 1,
                              'desc': 'auto-generated'}
    try:
        g = git.cmd.Git(os.getcwd())
        params['GIT_BRANCH'] = {'name': 'GIT_BRANCH',
                                'defa': g.rev_parse('--abbrev-ref', 'HEAD'),
                                'desc': 'auto-generated'}
    except:
        print('WARNING: retrieve git informations failed')

    for config in configs:
        name = config.find('name').text
        desc = config.find('description').text
        if name == 'branch' and 'GIT_BRANCH' in params:
            defa = params['GIT_BRANCH']['defa']
        else:
            defa = config.find('defaultValue').text
        params[name] = {'name': name, 'desc': desc, 'defa': defa}

    # try to get builtin_var from environment
    for builtin_var in builtin_vars:
        if builtin_var in os.environ:
            params[builtin_var] = os.environ[builtin_var]

    # integrate params with
    if args.args:
        override_args = json.loads(args.args)
        if type(override_args) != dict:
            raise TypeError('overridden args must be in a JSON dict format')

        for key, value in override_args.items():
            prev = params.get(key, None)
            desc = ("%s (%s)" % (prev['desc'], "passed to jjrunner")
                    if prev else "Passed to jjrunner")
            params[key] = {'name': key, 'defa': value, 'desc': desc}

    # collect commands from job config
    commands = []
    commands_tree = tree.find('builders').getchildren()
    for command_tree in commands_tree:
        commands.append(command_tree.getchildren()[0].text)

    # check for missing built-in variables in the scripts
    for builtin_var in builtin_vars:
        if builtin_var in params:
            continue
        for command in commands:
            if re.search("\\b%s\\b" % builtin_var, command):
                print("WARNING: builtin var %s found in script\n%s" %
                      (builtin_var, command))

    f_args_inode, f_args_name = tempfile.mkstemp(
        prefix="jjrunner_args_", suffix=".sh")
    if args.dryrun is True:
        print("Arguments file: %s" % f_args_name)

    with os.fdopen(f_args_inode, mode="w") as f_args:
        for key, value in params.items():
            name = value['name']
            desc = value['desc']
            defa = value['defa']

            f_args.write("# %s\n" % desc)
            f_args.write("export %s=\"%s\"\n\n" % (name, defa))

    f_main_inode, f_main_name = tempfile.mkstemp(
        prefix="jjrunner_main_", suffix=".sh")

    f_main = os.fdopen(f_args_inode, mode="w")
    f_main.close()

    for idx, command in enumerate(commands):
        f_com_inode, f_com_name = tempfile.mkstemp(
            prefix="jjrunner_com_%02d_" % idx, suffix=".sh")
        f_com = os.fdopen(f_com_inode, "w")
        f_com.write(command)
        f_com.close()
        os.chmod(f_com_name, stat.S_IREAD | stat.S_IEXEC | stat.S_IWUSR)

        f_main = open(f_main_name, "w")
        f_main.write('#!/bin/bash\n. %s\n%s\n' %
                     (f_args_name, f_com_name))
        f_main.close()
        os.chmod(f_main_name, stat.S_IREAD | stat.S_IEXEC | stat.S_IWUSR)

        if args.dryrun is False:
            proc = subprocess.Popen(f_main_name)
            try:
                outs, errs = proc.communicate(timeout=3600)
            except TimeoutExpired:
                proc.kill()
                outs, errs = proc.communicate()
            os.unlink(f_com_name)
            if proc.returncode != 0:
                print("#---- command ----:\n%s\n#---- end command ----\n\n"
                      "Returned with errorcode %d\n" % (
                          command, proc.returncode))
                print("#---- stdout ----:\n%s\n" % outs)
                print("#---- stderr ----:\n%s\n" % errs)
                sys.exit(proc.returncode)
            else:
                print("#---- command ----:\n%s\n#---- end command ----\n\n"
                      "SUCCESS\n" % command)

        else:
            print("Command file:   %s" % f_com_name)

    if args.dryrun is False:
        os.unlink(f_args_name)

    sys.exit(0)

if __name__ == "__main__":
    main()
