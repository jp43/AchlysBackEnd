from __future__ import with_statement

import os
import sys
import time
import shutil
import subprocess

from achlys.tools import ssh

def write_startup_job_script(checkjob):

    ressource = checkjob.docking_settings['ressource']

    scoring_functions = checkjob.docking_settings['scoring_functions']

    scoring_functions_flag = ""
    if scoring_functions:
        scoring_functions_flag = ' -s ' + ' '.join(scoring_functions)
    nposes = checkjob.nposes

    with open('run_startup.sh', 'w') as file:
        script ="""#!/bin/bash
#SBATCH --time=0-02:00
#SBATCH --partition=largemem
#SBATCH --job-name="startup"
#SBATCH --cpus-per-task=1

source ~/.bash_profile

# (A) prepare files for md startup
runanlz -w iso1/target*/%(scoring_functions_flag)s

# (B) run md startup
for posedir in pose{1..%(nposes)s}; do 
  cd $posedir
  prepare_md.py -l ligand.mol2 -r target.pdb -st prep -namd -addions -c none
  echo $? > status.out
  cd ..
done"""% locals()
        file.write(script)

def submit_startup(checkjob, ligs_idxs):

    jobid = checkjob.jobid
    ressource = checkjob.docking_settings['ressource']
    path = ssh.get_remote_path(jobid, ressource)

    submitcommand = ssh.get_submit_command(ressource)
    firstcommand = ssh.get_first_command(ressource)

    # create results directory on the remote machine (pharma)
    status = subprocess.check_output(ssh.coat_ssh_cmd("ssh %s 'if [ ! -f %s/run_startup.py ]; then echo 1; else echo 0; fi'"%(ressource,path)),\
        shell=True, executable='/bin/bash')
    isfirst = int(status)

    if isfirst == 1:
        write_startup_job_script(checkjob)
        subprocess.call(ssh.coat_ssh_cmd("scp run_startup.sh %s:%s/."%(ressource,path)), shell=True, executable='/bin/bash')
        os.remove('run_startup.sh')

    # prepare md startup jobs
    ligs_idxs_s = ' '.join(map(str, ligs_idxs))
    scriptname = 'submit_startup.sh'
    with open(scriptname, 'w') as file:
        script ="""#!/bin/bash 
source ~/.bash_profile
cd %(path)s

for idx in %(ligs_idxs_s)s; do
  cd lig$((idx+1))
  %(submitcommand)s ../run_startup.sh # submit job
  cd ..
done"""% locals()
        file.write(script)

    # submit jobs
    subprocess.call(ssh.coat_ssh_cmd("ssh %s '%s bash -s' < %s"%(ressource,firstcommand,scriptname)), shell=True, executable='/bin/bash')
    status = ['running' for idx in range(len(ligs_idxs))]

    return status

def write_check_startup_script(scriptname, path, ligs_idxs, nposes):

    ligs_idxs_s = ' '.join(map(str, ligs_idxs))

    with open(scriptname, 'w') as file:
        script ="""source ~/.bash_profile
cd %(path)s

# check the status of each startup job
for idx in %(ligs_idxs_s)s; do
  ligdir=lig$((idx+1))
  status=0
  for posedir in $ligdir/pose{1..%(nposes)s}; do
    filename=$posedir/status.out
    if [[ -f $filename ]]; then
      num=`cat $filename`
      if [ $num -ne 0 ]; then # job ended with an error
        status=1
      fi
    elif [ $status -ne 1 ]; then # job is still running
      status=-1
    fi
  done
  echo $status
done"""% locals()
        file.write(script)

def check_startup(checkjob, ligs_idxs):

    jobid = checkjob.jobid
    ressource = checkjob.docking_settings['ressource']
    path = ssh.get_remote_path(jobid, ressource)
    firstcommand = ssh.get_first_command(ressource)

    scriptname = 'check_startup.sh'
    write_check_startup_script(scriptname, path, ligs_idxs, checkjob.nposes)

    output =  subprocess.check_output(ssh.coat_ssh_cmd("ssh %s '%s bash -s' < %s"%(ressource,firstcommand,scriptname)),\
        shell=True, executable='/bin/bash')
    status = ssh.get_status(output)

    return status

def write_md_job_script(checkjob):

    jobid = checkjob.jobid
    ressource_startup = checkjob.docking_settings['ressource']
    path_startup = ssh.get_remote_path(jobid, ressource_startup)
    firstcommand_startup = ssh.get_first_command(ressource_startup)

    ressource = checkjob.md_settings['ressource']
    path = ssh.get_remote_path(jobid, ressource)

    ssh_cmd = ssh.coat_ssh_cmd("""ssh -C %(ressource_startup)s \"%(firstcommand_startup)s cd %(path_startup)s/lig${lig_id}; tar -cf - pose${pose_id} --exclude=\\\"status.out\\\"\" | `cd ..; tar -xf -`"""% locals())

    with open('run_md.sh', 'w') as file:
        script ="""#!/bin/sh
# @ job_name           = md-achlys
# @ job_type           = bluegene
# @ error              = $(job_name).$(Host).$(jobid).err
# @ output             = $(job_name).$(Host).$(jobid).out
# @ bg_size            = 64
# @ wall_clock_limit   = 24:00:00
# @ bg_connectivity    = Torus
# @ queue 

# (A) prepare files for md
cd $PWD
lig_id=`echo $PWD | grep -o 'lig.*' | sed -n s/lig//p | cut -d/ -f1`
pose_id=`echo $PWD | grep -o 'pose.*' | sed -n s/pose//p`
%(ssh_cmd)s

# (B) run files for md
cd ligand
python ../../../run_md.py min equil md -f ../../../config.ini --ncpus 1024 --bgq --withlig
echo $? > status.out\n"""% locals()
        file.write(script)

def submit_md(checkjob, ligs_idxs):

    jobid = checkjob.jobid
    ressource = checkjob.md_settings['ressource']
    path = ssh.get_remote_path(jobid, ressource)

    nposes = checkjob.nposes

    status = subprocess.check_output(ssh.coat_ssh_cmd("ssh %s 'if [ ! -d %s ]; then mkdir %s; echo 1; else echo 0; fi'"%(ressource,path,path)), shell=True, executable='/bin/bash')
    isfirst = int(status)

    if isfirst:
        write_md_job_script(checkjob)
        achlysdir = os.path.realpath(__file__)
        py_md_scripts = '/'.join(achlysdir.split('/')[:-1]) + '/{run_md.py,NAMD.py,amber.py}'
        subprocess.call(ssh.coat_ssh_cmd("scp config.ini run_md.sh %s %s:%s/."%(py_md_scripts,ressource,path)), shell=True, executable='/bin/bash')

    # prepare md jobs
    ligs_idxs_s = ' '.join(map(str, ligs_idxs))
    scriptname = 'submit_md.sh'
    with open(scriptname, 'w') as file:
        script ="""source ~/.bash_profile
cd %(path)s

for idx in %(ligs_idxs_s)s; do
  ligdir=lig$((idx+1))
  mkdir $ligdir
  for pose_id in `seq 1 %(nposes)s`; do
    posedir=$ligdir/pose${pose_id}
    mkdir $posedir
    cd $posedir
    llsubmit ../../run_md.sh
    cd ../..
  done
done"""% locals()
        file.write(script)

    subprocess.call(ssh.coat_ssh_cmd("ssh %s 'bash -s' < %s"%(ressource,scriptname)), shell=True, executable='/bin/bash')
    status = ['running' for idx in range(len(ligs_idxs))]
    return status

def write_check_md_script(scriptname, path, ligs_idxs, nposes):

    ligs_idxs_s = ' '.join(map(str, ligs_idxs))

    with open(scriptname, 'w') as file:
        script ="""source ~/.bash_profile
cd %(path)s

# check the status of each md job
for idx in %(ligs_idxs_s)s; do
  ligdir=lig$((idx+1))
  status=0
  for posedir in $ligdir/pose{1..%(nposes)s}; do
    filename=$posedir/ligand/status.out
    if [[ -f $filename ]]; then
      num=`cat $filename`
      if [ $num -ne 0 ]; then # job ended with an error
        status=1
      fi
    elif [ $status -ne 1 ]; then # job is still running
      status=-1
    fi
  done
  echo $status
done"""% locals()
        file.write(script)

def check_md(checkjob, ligs_idxs):

    jobid = checkjob.jobid
    ressource = checkjob.md_settings['ressource']
    path = ssh.get_remote_path(jobid, ressource)

    scriptname = 'check_md.sh'
    write_check_md_script(scriptname, path, ligs_idxs, checkjob.nposes)

    output = subprocess.check_output(ssh.coat_ssh_cmd("ssh %s 'bash -s' < %s"%(ressource,scriptname)), shell=True, executable='/bin/bash')
    status = ssh.get_status(output)

    return status
