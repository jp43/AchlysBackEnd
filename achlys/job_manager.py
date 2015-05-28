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

STEP_INIT_DONE = 0
STEP_PREP = 1
STEP_DOCK = 2
STEP_MD = 3
STEP_MMPBSA = 4
STEP_ANALYSIS = 5

STATUS_DONE = 'DONE'

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
            ext_l = self.get_format(args.input_files_l)
            if ext_l == '.pdb':
                input_files_l = args.input_files_l
                nligs = len(input_files_l)
                # This code assumes only one structure in each PDB file
                # That is normally the case but the PDB format allows multiple MODELs
            elif ext_l == '.sdf':
                input_files_l = args.input_files_l
                # I will support multiple SDF files each with multiple structures
                nligs = 0
                for input_file_path in input_files_l:
                    nligs += struct_tools.count_structs_sdf(input_file_path)
            elif ext_l == '.mol':
                # .mol is used for MDL MOLfile format but also some other chemical formats
                # MDL MOLfile format is similar to MDL SDFile format but only 1 structure per file
                # (SDF is a container for multiple MOL)
                input_files_l = args.input_files_l
                nligs = len(input_files_l)
            elif ext_l == '.smi' or ext_l == '.txt':
                # SMILES files sometimes have the .txt extension
                # But .txt could also be used for many other formats
                # I will support multiple SMILES files each with multiple structures
                nligs = 0
                for input_file_path in input_files_l:
                    nligs += struct_tools.count_structs_smi(input_file_path)
            else:
                raise StartJobError("format of input files should be among " + ", ".join(known_formats))
        else:
            # look for an option in the config file
            if config.has_option('GENERAL', 'ligpath'):
                raise NotImplemented('ligpath config option not supported')
            else:
                raise StartJobError('No files for ligands provided')

        self.nligs = nligs
        self.input_files_l = input_files_l
        self.ext_l = ext_l

        # check files related to the targets
        if args.input_files_r:
            # get extension if file names provided are correct
            ext_r = self.get_format(args.input_files_r)
            input_files_r = args.input_files_r
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

        self.ntargets = ntargets
        self.input_files_r = input_files_r
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

        # create hidden files to put intermediate scripts
        os.mkdir(workdir+'/.scripts')

        ## copy ligand files
        #for idx, file_l in enumerate(self.input_files_l):
        #    dir_l = workdir+'/lig%i'%idx
        #    # make ligand directory
        #    os.mkdir(dir_l)
        #    # copy file 
        #    shutil.copyfile(file_l,dir_l+'/lig%i'%idx+self.ext_l)
        #    # copy current step
        #    stf = open(dir_l+'/step', 'w')
        #    stf.write('%d' % STEP_INIT_DONE)
        #    stf.close()
        
        # I convert everything to SDF format

        ext_l = self.get_format(self.input_files_l)
        lig_idx = 0
        for file_l in self.input_files_l:
            if ext_l == '.pdb':
                dir_l = workdir+'/lig%i'%lig_idx
                # make ligand directory
                os.mkdir(dir_l)
                # Convert and copy file
                os.system('babel -ipdb %s -osdf %s 2>/dev/null' % 
                        (file_l, dir_l+'/lig%i'%lig_idx+self.ext_l))
                # copy current step
                stf = open(dir_l+'/step', 'w')
                stf.write('%d' % STEP_INIT_DONE)
                stf.close()
                lig_idx += 1
            elif ext_l == '.sdf':
                nligs_sdf = struct_tools.count_structs_sdf(file_l)
                for idx_sdf in range(nligs_sdf):
                    dir_l = workdir+'/lig%i'%lig_idx
                    # make ligand directory
                    os.mkdir(dir_l)
                    # Convert and copy file
                    os.system('babel -isdf %s -f%d -l%d -osdf %s 2>/dev/null' % 
                            (file_l, idx_sdf+1, idx_sdf+1, dir_l+'/lig%i'%lig_idx+self.ext_l))
                    # copy current step
                    stf = open(dir_l+'/step', 'w')
                    stf.write('%d' % STEP_INIT_DONE)
                    stf.close()
                    lig_idx += 1
            elif ext_l == '.mol':
                dir_l = workdir+'/lig%i'%lig_idx
                # make ligand directory
                os.mkdir(dir_l)
                # Convert and copy file
                os.system('babel -imol %s -osdf %s 2>/dev/null' % 
                        (file_l, dir_l+'/lig%i'%lig_idx+self.ext_l))
                # copy current step
                stf = open(dir_l+'/step', 'w')
                stf.write('%d' % STEP_INIT_DONE)
                stf.close()
                lig_idx += 1
            elif ext_l == '.smi' or ext_l == '.txt':
                nligs_smi = struct_tools.count_structs_sdf(file_l)
                for idx_smi in range(nligs_smi):
                    dir_l = workdir+'/lig%i'%lig_idx
                    # make ligand directory
                    os.mkdir(dir_l)
                    # Convert and copy file 
                    os.system('babel -ismi %s -f%d -l%d -osmi %s 2>/dev/null' % 
                            (file_l, idx_smi+1, idx_smi+1, dir_l+'/lig%i'%lig_idx+self.ext_l))
                    # copy current step
                    stf = open(dir_l+'/step', 'w')
                    stf.write('%d' % STEP_INIT_DONE)
                    stf.close()
                    lig_idx += 1
            else:
                raise StartJobError("format of input files should be among " + ", ".join(known_formats))


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
        subprocess.call('(crontab -l ; echo "* * * * * check_job --id %s")| crontab'%self.jobid, shell=True)
        print '%s' % self.jobid

class CheckJobError(Exception):
    pass

class CheckJob(object):

    def initialize(self, args):

        self.jobid = args.jobid
        self.basejobdir = '/home/pwinter/Achlys/jobs/'
        self.workdir = self.basejobdir + 'job_' + self.jobid

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

        current_step = []
        # check current step
        for lig_idx in range(nligs):
            with open(self.workdir+'/lig%i/step'%lig_idx, 'r') as stf:
                current_step.append(int(stf.next()))
        self.current_step = current_step

    # I've changed how this work, now it updates the step file to given step
    # I don't assume that each ligand will advance by 1 step each time it is called
    def update_step_file(self, lig_id, step):

        with open('lig%i/step'%lig_id, 'w') as file_l:
            print >> file_l, step

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

        logfile = open(self.basejobdir+'checkjoblog', 'a')
        logfile.write('Running checkjob for %s at %s\n' % (self.jobid, datetime.datetime.now()))
        logfile.close()

        os.chdir(self.workdir)

        # If a ligand is in step STEP_INIT_DONE, submit a prep job
        for lig_id in range(self.nligs):
            if self.current_step[lig_id] == STEP_INIT_DONE:
                prep.submit_prep_job(self.jobid, lig_id, submit_on='local')
                self.update_step_file(lig_id, STEP_PREP)
                self.current_step[lig_id] = STEP_PREP
            
        # If a ligand is in step STEP_PREP, check if prep is done
        prep_status_list = []
        for lig_id in range(self.nligs):
            if self.current_step[lig_id] == STEP_PREP:
                prep_status_list.append(prep.check_prep_job(self.jobid, lig_id, submit_on='local'))
            else:
                prep_status_list.append('NOT_IN_PREP_STEP')
        
        # If all ligands are processed, then submit docking job and advance to STEP_DOCK
        if all(prep_status == 'DONE' for prep_status in prep_status_list):
            docking.submit_docking_job(self.jobid, self.nligs, self.ntargets, submit_on='pharma')
            self.current_step[lig_id] = STEP_DOCK
            self.update_step_file(lig_id, STEP_DOCK)
        
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

