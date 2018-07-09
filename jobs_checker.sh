#!/bin/bash
set -e
# set -x
MAILCLI=mutt

export PATH=$HOME/git/jjrunner:$PATH
JOBS="oq-engine oq-libs oq-python oq-platform oq-platform2"

BDIR="$HOME/jobs_checker"

if [ ! -d "$BDIR" ]; then
    mkdir "$BDIR"
fi
cd "$BDIR"

touch /tmp/jobs_checker$$.ctx
failed=false
for job in $JOBS; do
    test -t 1 && echo "job $job ..." | tr -d '\n'
    for pfx in zdevel master; do
        jobname=${pfx}_${job}
        rm -rf "${jobname}"
        jjrunner.py -D "${jobname}"
    done
    echo "=== JOB: $job ===" &>>/tmp/jobs_checker$$.ctx
    echo "--- args ---" &>>/tmp/jobs_checker$$.ctx
    diff  <(sed 's/=.*//g;s/^#.*//g' "zdevel_${job}/args.sh") <( sed 's/=.*//g;s/^#.*//g' "master_${job}/args.sh") &>>/tmp/jobs_checker$$.ctx || failed=true
    for i in $(seq 0 100); do
        comname="com_$(printf "%02d" $i).sh"
        if [ ! -f "master_${job}/$comname" ]; then
            break
        fi
        echo "--- $comname ---" &>>/tmp/jobs_checker$$.ctx
        diff -u "zdevel_${job}/$comname" "master_${job}/$comname" &>>/tmp/jobs_checker$$.ctx || failed=true
    done
    test -t 1 && echo " done."
done

if [ "$failed" = "true" ]; then
    cat /tmp/jobs_checker$$.ctx | $MAILCLI -s "jobs_checker detects a difference" $ADMIN_MAIL
    test -t 1 && echo "Check found differences, a mail is sent."
else
    test -t 1 && echo "Differences not found, exit silently."
fi

rm /tmp/jobs_checker$$.ctx


