from __future__ import with_statement

import os
import sys
import time
import tempfile
import shutil
import subprocess

from achlys.tools import ssh

def write_mmpbsa_job_script(checkjob):

    jobid = checkjob.jobid
    nposes = checkjob.nposes

    ressource_md = checkjob.md_settings['ressource']
    path_md = ssh.get_remote_path(jobid, ressource_md)

    mmpbsa_settings = checkjob.mmpbsa_settings
    ressource = mmpbsa_settings['ressource']
    walltime = mmpbsa_settings['walltime']
    path = ssh.get_remote_path(jobid, ressource)

    scriptname = 'run_mmpbsa.pbs'
    if ressource == 'pharma':
        ssh_cmd = ssh.coat_ssh_cmd("""ssh -C %(ressource_md)s \"cd %(path_md)s; tar -cf - lig${lig_id}/pose$((SGE_TASK_ID-1))/{md.dcd,common} --exclude=\\\"status1.out\\\" --exclude=\\\"status2.out\\\"\" | cd ..; tar -xf -`"""% locals())
        with open(scriptname, 'w') as file:
            script ="""#$ -N mmpbsa-achlys
#$ -q achlys.q,parallel.q
#$ -l h_rt=%(walltime)s
#$ -cwd
#$ -t 1-%(nposes)s:1
#$ -pe smp 2
#$ -S /bin/bash

export AMBERHOME=/pmshare/amber/amber12-20120918
export PATH=$AMBERHOME/bin:/opt/openmpi/1.6/gcc/bin:$PATH
export LD_LIBRARY_PATH=$AMBERHOME/lib64:/opt/openmpi/1.6/gcc/lib:$LD_LIBRARY_PATH
export PYTHONPATH=/opt/mgltools/1.5.4/MGLToolsPckgs:$HOME/achlys/lib/python2.7/site-packages:$HOME/local/lib/python2.7/site-packages:$PYTHONPATH
lig_id=`echo $PWD | grep -o lig.* | sed -n s/lig//p`

# (A) prepare files for mmpbsa
dir=$PWD
%(ssh_cmd)s
echo $? > status1.out
cd $PWD

mkdir pose$((SGE_TASK_ID-1))/mmpbsa
cd pose$((SGE_TASK_ID-1))/mmpbsa

# (B) run mmpbsa
python ../../../run_mmpbsa.py -f ../../../config.ini
echo $? > status.txt
"""% locals()
            file.write(script)
    elif ressource == 'grex':
        ssh_cmd = ssh.coat_ssh_cmd("""ssh -C %(ressource_md)s \"cd %(path_md)s; tar -cf - lig${lig_id}/pose*/{md.dcd,common} --exclude=\\\"status1.out\\\" --exclude=\\\"status2.out\\\"\" | `cd ..; tar -xf -`"""% locals())
        with open(scriptname, 'w') as file:
            script ="""#!/bin/bash 
#PBS -l walltime=%(walltime)s
#PBS -l mem=12gb
#PBS -l nodes=1:ppn=6
#PBS -q default
#PBS -N mmpbsa-achlys

cd $PBS_O_WORKDIR
lig_id=`echo $PWD | grep -o lig.* | sed -n s/lig//p`

# (A) prepare files for mmpbsa
%(ssh_cmd)s
echo $? > status1.out

cd $PBS_O_WORKDIR
# (B) run mmpbsa
for i in `seq 1 %(nposes)s`; do
  j=$((i-1))
  mkdir pose$j/mmpbsa
  cd pose$j/mmpbsa
  python ../../../run_mmpbsa.py -f ../../../config.ini -n 6
  echo $? > status2.out
  cd ../../
done

#python ../analysis.py -f ../config.ini
"""% locals()
            file.write(script)

def submit_mmpbsa(checkjob, ligs_idxs):

    jobid = checkjob.jobid
    nposes = checkjob.nposes
    mmpbsa_settings = checkjob.mmpbsa_settings
    ressource = mmpbsa_settings['ressource']
    path = ssh.get_remote_path(jobid, ressource)

    # create job folder if does not exist
    status = subprocess.check_output(ssh.coat_ssh_cmd("ssh %s 'if [ ! -f %s/run_mmpbsa.py ]; then if [ ! -d %s ]; then mkdir %s; fi; echo 1; else echo 0; fi'"\
                 %(ressource, path, path, path)), shell=True, executable='/bin/bash')

    isfirst = int(status)

    if isfirst == 1:
        write_mmpbsa_job_script(checkjob)
        achlysdir = os.path.realpath(__file__)
        py_mmpbsa_scripts = '/'.join(achlysdir.split('/')[:-1]) + '/run_mmpbsa.py'
        py_mmpbsa_scripts += ' ' + '/'.join(achlysdir.split('/')[:-1]) + '/../tools/analysis.py'

        subprocess.call(ssh.coat_ssh_cmd("scp config.ini run_mmpbsa.pbs %s %s:%s/."%(py_mmpbsa_scripts,ressource,path)), shell=True, executable='/bin/bash')
        os.remove('run_mmpbsa.pbs')

    ligs_idxs_str = ' '.join(map(str, ligs_idxs))

    # Prepare mmpbsa
    scriptname = 'submit_mmpbsa.sh'
    with open(scriptname, 'w') as file:
        script ="""source ~/.bash_profile
cd %(path)s

# submit jobs
for lig_id in %(ligs_idxs_str)s; do
  if [[ ! -d lig$lig_id ]]; then
    mkdir lig$lig_id
  fi
  cd lig$lig_id
  qsub ../run_mmpbsa.pbs # submit job
  cd ..
done"""% locals()
        file.write(script)

    subprocess.call(ssh.coat_ssh_cmd("ssh %s 'bash -s' < %s"%(ressource,scriptname)), shell=True, executable='/bin/bash')
    status = ['running' for idx in range(len(ligs_idxs))]

    return status

def write_check_mmpbsa_script(scriptname, path, ligs_idxs):

    ligs_idxs_str = ' '.join(map(str, ligs_idxs))

    with open(scriptname, 'w') as file:
        script ="""source ~/.bash_profile
cd %(path)s

for lig_id in %(ligs_idxs_str)s; do
  # check status of each docking
  status=0
  for posdir in lig${lig_id}/pose*; do
    if [ -d $posdir ]; then
      filename=$posdir/mmpbsa/status2.out 
      if [ -f $filename ]; then
        num=`cat $filename`
        if [ $num -ne 0 ]; then
          status=1
        fi
      else # the mmpbsa simulation is still running
        status=-1
      fi
    fi
  done
  echo $status
  if [ $status -eq 0 ]; then
    cd lig${lig_id}
    python ../analysis.py -f ../config.ini
    cd ..
  fi
done"""% locals()
        file.write(script)

def check_mmpbsa(checkjob, ligs_idxs):

    jobid = checkjob.jobid
    mmpbsa_settings = checkjob.mmpbsa_settings
    ressource = mmpbsa_settings['ressource']
    path = ssh.get_remote_path(jobid, ressource)

    scriptname = 'check_mmpbsa.sh'
    write_check_mmpbsa_script(scriptname, path, ligs_idxs)
    output = subprocess.check_output(ssh.coat_ssh_cmd("ssh %s 'bash -s' < %s"%(ressource,scriptname)), shell=True, executable='/bin/bash')
    status = ssh.get_status(output)

    ligs_done_idxs = [ligs_idxs[idx] for idx in range(len(ligs_idxs)) if status[idx] == 'done']

    if ligs_done_idxs:
        if len(ligs_done_idxs) == 1:
            ligs_done_idxs_bash = str(ligs_done_idxs[0])
        else:
            ligs_done_idxs_bash = '{' + ','.join(map(str,ligs_done_idxs)) + '}'

        subprocess.call(ssh.coat_ssh_cmd("ssh -C %s \"cd %s; tar -cf - lig%s/{mob.pdb,mob-bp.pdb,lig2.info}\" | `cd ../job_%s; tar -xf -` "%(ressource,path,ligs_done_idxs_bash,jobid)), shell=True, executable='/bin/bash')

    return status
