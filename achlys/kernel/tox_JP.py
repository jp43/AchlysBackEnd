from __future__ import with_statement

import sys
import os
import subprocess
import shutil
import argparse
import warnings
import ConfigParser

from achlys.kernel import docking

known_formats = ['.pdb', '.sdf']
known_systems = ['herg']

class AchlysError(Exception):
    pass

class AchlysProgram(object):

    def initialize(self, args):

        global known_systems

        config = ConfigParser.SafeConfigParser()
        config.read(args.config_file)    

        # check files related to the ligands
        if args.input_files_l:
            # get extension if file names provided are correct
            ext_l = self.get_format(args.input_files_l)
            if ext_l == '.pdb':
                input_files_l = args.input_files_l
                nligs = len(input_files_l)
            elif ext_l == '.sdf':
                # this is where the .sdf files should be converted in pdb files
                raise NotImplemented('.sdf format not supported yet')
            else:
                raise AchlysError("format of input files should be among " + ", ".join(known_formats))
        else:
            # look for an option in the config file
            if config.has_option('GENERAL', 'ligpath'):
                raise NotImplemented('ligpath config option not supported')
            else:
                raise AchlysError('No files for ligands provided')

        self.nligs = nligs
        self.ext_l = ext_l

        # check files related to the proteins
        if args.input_files_r:
            # get extension if file names provided are correct
            ext_r = self.get_format(args.input_files_r)
            input_files_r = args.input_files_r
            if ext_r == '.pdb':
                ntargets = len(input_files_r)
            else:
                raise AchlysError("Only .pdb format is supported now for files containing receptors")
        else:
            # look for an option in the config file
            if config.has_option('GENERAL', 'system'):
                system = config.get('GENERAL', 'system').lower()
                if system not in known_systems:
                    raise AchlysError("The system specified in the configuration file should one of " + ", ".join(known_systems))
                if system == 'herg':
                    achlysdir = os.path.realpath(docking.__file__)
                    dir_r = '/'.join(achlysdir.split('/')[:-6]) + '/share/hERG_data'
                    input_files_r = [dir_r + '/' + file for file in os.listdir(dir_r) if os.path.splitext(file)[1] == '.pdb']
                    ntargets = len(input_files_r)
            else:
                raise AchlysError('No files for targets provided')

        self.ntargets = ntargets
        self.ext_l = ext_l
        if ntargets == 1 and args.multi:
            warnings.warn("Only 1 target detected: disabling multi option is encouraged")

        # create directory for results
        workdir = 'results'
        shutil.rmtree(workdir, ignore_errors=True)
        os.mkdir(workdir)

        self.workdir = workdir
        curdir = os.getcwd()

        # copying required files
        for idx, file_l in enumerate(input_files_l):
            ligdir = workdir+'/lig%i'%idx
            os.mkdir(ligdir)

            # copying the files containing the ligands
            shutil.copyfile(file_l, ligdir + '/lig.pdb')
            
            # copying the files containing the targets
            for jdx, file_r in enumerate(input_files_r):
                os.mkdir(workdir + '/lig%i/target%i'%(idx,jdx))
                shutil.copyfile(file_r, workdir + '/lig%i/target%i/target.pdb'%(idx,jdx))

    def create_arg_parser(self):
        parser = argparse.ArgumentParser(description="Run Achlys Program..")
    
        parser.add_argument('-l',
            type=str,
            dest='input_files_l',
            nargs='*',
            help = 'Ligand coordinate file(s): .pdb, .sdf')

        parser.add_argument('-r',
            type=str,
            dest='input_files_r',
            nargs='*',
            help = 'Receptor coordinate file(s): .pdb')
 
        parser.add_argument('-n',
            type=int,
            dest='nmaxcpus',
            default=None,
            help='max number of CPUs')

        parser.add_argument('--multi',
            dest='multi',
            action='store_true',
            default=False,
            help='use one job array per ligand (the number of cpus used for each array is given by the number of targets)')

        parser.add_argument('-f',
            dest='config_file',
            required=True,
            help='config file containing some extra parameters')
    
        return parser
    
    def write_docking_job_array(self, script_name, ncpus, nligs, ntargets, config_file, multi=False):
    
        if multi:
            multi_flag = "--multi"
        else:
            multi_flag = ""

        jobname = os.path.splitext(script_name)[0]

        with open(script_name, 'w') as file:
            script ="""#$ -N %(jobname)s
#$ -q serial.q
#$ -l h_rt=168:00:00
#$ -t 1-%(ncpus)s:1
#$ -V
##$ -o /dev/null
##$ -e /dev/null
#$ -cwd
#$ -S /bin/bash

set -e

run_docking $((SGE_TASK_ID-1)) %(ncpus)s %(nligs)s %(ntargets)s -f %(config_file)s %(multi_flag)s
"""% locals()
            file.write(script)

    def write_post_docking_script(self, script_name, ncpus, nligs, ntargets, config_file):

        jobname = os.path.splitext(script_name)[0]

        with open(script_name, 'w') as file:
            script ="""#$ -N %(jobname)s
#$ -q achlys.q
#$ -l h_rt=168:00:00
#$ -V
#$ -cwd
#$ -S /bin/bash

set -e

postdocking %(ntargets)s -f %(config_file)s
"""% locals()
            file.write(script)

    def get_format(self, files):
        global known_formats

        nfiles = len(files)
        if nfiles > 1:
            formats = [os.path.splitext(name)[1] for name in files]
            format = formats[0]
            if not all(format == format_q for format_q in formats):
                raise AchlysError('filenames provided should have the same format')
    
        elif nfiles == 1:
            format = os.path.splitext(files[0])[1]

        return format
    
    def run(self):
 
        parser = self.create_arg_parser()
        args = parser.parse_args()
        self.initialize(args)

        curdir = os.getcwd()

        if args.multi:
            for idx in range(self.nligs): # submit one array job per ligand
                rundir = self.workdir + '/lig%i'%idx
                shutil.copyfile(args.config_file, rundir + '/' + args.config_file)

                os.chdir(rundir)
                # (A) submit docking script
                script_name = 'run_docking.sge'
                self.write_docking_job_array(script_name, self.ntargets, self.nligs, self.ntargets, args.config_file, multi=True)

                jobid = subprocess.check_output(['qsub', '-terse', script_name])
                jobid = jobid.split('.')[0]

                # (B) submit postdocking script
                script_name = 'post_docking.sge'
                self.write_post_docking_script(script_name, self.nligs, self.nligs, self.ntargets, args.config_file)

                subprocess.call(['qsub', '-hold_jid', jobid, script_name])
                os.chdir(curdir)

        else: # submit only one job array for all the ligands
            # number of CPUs used overall
            if args.nmaxcpus is None:
                ncpus = nligs
            else:
                ncpus = min(nligs, args.nmaxcpus)

            rundir = self.workdir
            shutil.copyfile(args.config_file, rundir + '/' + args.config_file)
            os.chdir(rundir)
            script_name = 'run_docking.sge'
            self.write_docking_job_array(script_name, ncpus, self.nligs, self.ntargets, args.config_file) 
            subprocess.call("qsub " + script_name, shell=True)

