import os
import sys
import argparse
import subprocess
import glob

def create_arg_parser():

    parser = argparse.ArgumentParser(description='Back to Step..')

    parser.add_argument('--ligid',
        dest='lig_id',
        nargs='*',        
        type=str,
        help='Ligand IDs')

    parser.add_argument('--id',
        dest='job_id',
        type=str,
        help='Job ID')

    return parser

def run():

    parser = create_arg_parser()
    args = parser.parse_args()
    
    if args.job_id:
        jobdir = 'job_' + args.job_id
        if not os.path.isdir(jobdir):
            raise IOError('directory ' + jobdir + ' does not exist!!!')
    else:
        jobdirs = glob.glob('job_*')
        if len(jobdirs) == 1:
            jobdir = jobdirs[0]
        else:
            raise ValueError('Many or no job directories found! You might want \
    to consider option id to indicate which job directory you want to deal with!')
    
    step_old = args.lig_id
    
    if args.step_old:
        script = """#!/bin/bash
for file in %(jobdir)s/lig*/step.out; do
  str=`cat $file`
  if [[ $str == *"%(step_old)s"* ]]; then
    echo "%(step_new)s" > $file
  fi
done""" % locals()
    else:
        script = """#!/bin/bash
for file in %(jobdir)s/lig*/step.out; do
  echo "%(step_new)s" > $file
done"""% locals()
    
    tmpfile = 'tmp.sh'
    
    with open(tmpfile, 'w') as tmpf: 
        tmpf.write(script)
    
    subprocess.call("bash " + tmpfile, shell=True)
    os.remove(tmpfile)
