from __future__ import with_statement

import sys
import os
import subprocess
import shutil
import tempfile
import argparse
import warnings
import ConfigParser
import uuid
import glob
import time
import datetime

from achlys import docking
from achlys import prep
from achlys import struct_tools

known_formats = ['.pdb', '.sdf', '.mol', '.smi', '.txt']
known_systems = ['herg']

known_steps = ['init', 'dock', 'md', 'mmpbsa', 'analysis']

class StartJobError(Exception):
    pass

class StartJob(object):

    def initialize(self, args):
        global known_formats
        global known_systems

        config = ConfigParser.SafeConfigParser()
        config.read(args.config_file)    

        # check files related to the ligands
        if args.input_files_l:
            # get extension if file names provided are correct
            input_files_l = args.input_files_l
            ext_l = self.get_format(args.input_files_l)
            if ext_l == '.pdb':
                # This code assumes only one structure in each PDB file
                # That is normally the case but the PDB format allows multiple MODELs
                nligs = len(args.input_files_l)
            elif ext_l == '.sdf':
                # I will support multiple SDF files each with multiple structures
                nligs = 0
                for input_file_path in args.input_files_l:
                    nligs += struct_tools.count_structs_sdf(input_file_path)
            elif ext_l == '.mol':
                # .mol is used for MDL MOLfile format but also some other chemical formats
                # MDL MOLfile format is similar to MDL SDFile format but only 1 structure per file
                # (SDF is a container for multiple MOL)
                nligs = len(args.input_files_l)
            elif ext_l == '.smi' or ext_l == '.txt':
                # SMILES files sometimes have the .txt extension
                # But .txt could also be used for many other formats
                # I will support multiple SMILES files each with multiple structures
                nligs = 0
                for input_file_path in args.input_files_l:
                    nligs += struct_tools.count_structs_smi(input_file_path)
            else:
                raise StartJobError("format of input files should be among " + ", ".join(known_formats))
        else:
            # look for an option in the config file
            if config.has_option('GENERAL', 'ligpath'):
                raise NotImplemented('ligpath config option not supported')
            else:
                raise StartJobError('No files for ligands provided')

        self.input_files_l = input_files_l
        self.nligs = nligs
        self.ext_l = ext_l

        # check files related to the targets
        if args.input_files_r:
            input_files_r = args.input_files_r
            # get extension if file names provided are correct
            ext_r = self.get_format(input_files_r)
            if ext_r == '.pdb':
                ntargets = len(input_files_r)
            else:
                raise StartJobError("Only .pdb format is supported now for files containing receptors")
        else:
            # look for an option in the config file
            if config.has_option('GENERAL', 'system'):
                system = config.get('GENERAL', 'system').lower()
                if system not in known_systems:
                    raise StartJobError("The system specified in the configuration file should one of " + ", ".join(known_systems))
                if system == 'herg':
                    achlysdir = os.path.realpath(__file__)
                    dir_r = '/'.join(achlysdir.split('/')[:-5]) + '/share/hERG_data'
                    input_files_r = [dir_r + '/' + file for file in os.listdir(dir_r) if os.path.splitext(file)[1] == '.pdb']
                    ntargets = len(input_files_r)
                    ext_r = '.pdb'
            else:
                raise StartJobError('No files for targets provided')

        self.input_files_r = input_files_r
        self.ntargets = ntargets
        self.ext_r = ext_r

        self.jobid = self.create_job_directory(args)

    def create_job_directory(self, args):

        # creating job ID
        jobid = str(uuid.uuid4())
        jobid = jobid.split('-')[0]

        # creating job directory
        workdir = 'job_' + jobid
        self.workdir = workdir
        os.mkdir(workdir)

        # copy ID
        idf = open(workdir+'/job_ID', 'w')
        idf.write(jobid)
        idf.close()

        # copy config file
        shutil.copyfile(args.config_file, workdir +'/config.ini')
        
        # convert everything to SDF format
        ext_l = self.get_format(self.input_files_l)
        lig_idx = 0
        for file_l in self.input_files_l:
            dir_l = workdir+'/lig%i'%lig_idx
            # make ligand directory
            os.mkdir(dir_l)
            if ext_l == '.pdb':
                # Convert and copy file
                os.system('babel -ipdb %s -osdf %s 2>/dev/null' %(file_l, dir_l+'/lig%i'%lig_idx+self.ext_l))
            elif ext_l == '.sdf':
                nligs_sdf = struct_tools.count_structs_sdf(file_l)
                for idx_sdf in range(nligs_sdf):
                    # Convert and copy file
                    os.system('babel -isdf %s -f%d -l%d -osdf %s 2>/dev/null' \
                        %(file_l, idx_sdf+1, idx_sdf+1, dir_l+'/lig%i'%lig_idx+self.ext_l))
                    # copy current step
            elif ext_l == '.mol':
                # Convert and copy file
                os.system('babel -imol %s -osdf %s 2>/dev/null' % (file_l, dir_l+'/lig%i'%lig_idx+self.ext_l))
            elif ext_l == '.smi' or ext_l == '.txt':
                nligs_smi = struct_tools.count_structs_sdf(file_l)
                for idx_smi in range(nligs_smi):
                    # Convert and copy file 
                    os.system('babel -ismi %s -f%d -l%d -osmi %s 2>/dev/null' \
                        %(file_l, idx_smi+1, idx_smi+1, dir_l+'/lig%i'%lig_idx+self.ext_l))

            # copy current step
            stf = open(dir_l+'/step.out', 'w')
            stf.write('start step 0 (init)')
            stf.close()
            lig_idx += 1

        # copy targets
        dir_r = workdir+'/targets'
        os.mkdir(dir_r)
        for idx, file_r in enumerate(self.input_files_r):
            shutil.copyfile(file_r,dir_r+'/target%i'%idx+self.ext_r)

        return jobid

    def create_arg_parser(self):
        parser = argparse.ArgumentParser(description="Run StartJob...")
    
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
        parser.add_argument('-f',
            dest='config_file',
            required=True,
            help='Config file containing the parameters of the procedure')
    
        return parser

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
        # start cron job
        #subprocess.call('(crontab -l ; echo "* * * * * check_job --id %s")| crontab'%self.jobid, shell=True)
        print '%s' % self.jobid

class CheckJobError(Exception):
    pass

class CheckJob(object):

    def initialize(self, args):

        self.jobid = args.jobid
        self.workdir = 'job_' + self.jobid

        # check number of ligands
        nligs = 0
        for dir_l in glob.glob(self.workdir+'/lig*'):
            nligs += 1
        self.nligs = nligs

        # check number of targets
        ntargets = 0
        for file_r in glob.glob(self.workdir+'/targets/*'):
            ntargets += 1
        self.ntargets = ntargets

        status = []
        steps = []

        # check current step
        for lig_idx in range(nligs):
            with open(self.workdir+'/lig%i/step.out'%lig_idx, 'r') as stf:
                line = stf.next().split()
                status.append(line[0])
                steps.append(int(line[2]))

        self.status = status
        self.steps = steps

    def update_step(self, lig_id, status_lig):

        step_lig = self.steps[lig_id]

        if step_lig == known_steps[-1] and status_lig == 'done':
            new_step_lig = step_lig
            new_status_lig = 'done' # the procedure is done
        elif status_lig == 'done':
            new_step_lig = step_lig + 1
            new_status_lig = 'start'
        elif status_lig == 'error': # error encounter
            new_step_lig = step_lig
            new_status_lig = 'error'
        elif status_lig == 'running': # job still running
            new_step_lig = step_lig
            new_status_lig = 'running'

        with open('lig%i/step.out'%lig_id, 'w') as file:
            print >> file, new_status_lig + ' step ' + str(new_step_lig)  + ' (%s)'%known_steps[step_lig]

        self.steps[lig_id] = new_step_lig
        self.status[lig_id] = new_status_lig

    def create_arg_parser(self):
        parser = argparse.ArgumentParser(description="Run CheckJob...")

        parser.add_argument('--id',
            dest='jobid',
            type=str,
            required=True,
            help='Job ID')
        return parser

    def run(self):
    
        parser = self.create_arg_parser()
        args = parser.parse_args()
        self.initialize(args)

        #logfile = open(self.basejobdir+'checkjoblog', 'a')
        #logfile.write('Running checkjob for %s at %s\n' % (self.jobid, datetime.datetime.now()))
        #logfile.close()

        os.chdir(self.workdir)

        # If a ligand is in step 0, submit a prep job
        for lig_id in range(self.nligs):
            if self.steps[lig_id] == 0:
                if self.status[lig_id] == 'start':
                    status_lig = prep.submit_prep_job(self.jobid, lig_id, submit_on='local') 
                    self.update_step(lig_id, status_lig)
                if self.status[lig_id] == 'running':
                    status_lig = prep.check_prep_job(self.jobid, lig_id, submit_on='local')
                    self.update_step(lig_id, status_lig)
        
        # If all ligands are done with step 0, then submit docking job and advance to step 1
        if all([self.status[lig_id] == 'start' and self.steps[lig_id] == 1 for lig_id in range(self.nligs)]):
            status = docking.submit_docking_job(self.jobid, self.nligs, self.ntargets, submit_on='pharma')
            for lig_id in range(self.nligs):
                self.update_step(lig_id, status)
        
        ## check ligands in step STEP_DOCK
        #ligs_idxs = [idx for idx, step in enumerate(self.current_step) if step == STEP_PREP]
        #if ligs_idxs:
        #    docking.check_docking(self.jobid, ligs_idxs, self.ntargets, submitted_on='pharma')
            
        #for lig_id, step in enumerate(self.current_step):
        #    if step == STEP_DOCK: # docking is running

        #    elif step == STEP_MD: # MD is running
        #        raise NotImplemented("step STEP_MD not implemented")
        #        # check MD current status

        #    elif step == STEP_MMPBSA: # MMPBSA is running
        #        raise NotImplemented("step STEP_MMPBSA not implemented")

        #    elif step == STEP_ANALYSIS:
        #        raise NotImplemented("step STEP_ANALYSIS not implemented")

        
        os.chdir('..')

