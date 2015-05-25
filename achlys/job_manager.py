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

from achlys import docking

known_formats = ['.pdb', '.sdf']
known_systems = ['herg']

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
            elif ext_l == '.sdf':
                # this is where the .sdf files should be converted in pdb files
                raise NotImplemented('.sdf format not supported yet')
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

        # copy ligand files
        for idx, file_l in enumerate(self.input_files_l):
            dir_l = workdir+'/lig%i'%idx
            # make ligand directory
            os.mkdir(dir_l)
            # copy file 
            shutil.copyfile(file_l,dir_l+'/lig%i'%idx+self.ext_l)
            # copy current step
            stf = open(dir_l+'/step', 'w')
            stf.write('0')
            stf.close()

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
        #subprocess.call('(crontab -l ; echo "*/10 * * * * check_job --id %i")| crontab'%self.jobid)

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

        current_step = []
        # check current step
        for lig_idx in range(nligs):
            with open(self.workdir+'/lig%i/step'%lig_idx, 'r') as stf:
                current_step.append(int(stf.next()))
        self.current_step = current_step

    def update_step_file(self, lig_id, step):

        with open('lig%i/step'%lig_id, 'w') as file_l:
            print >> file_l, step+1

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

        os.chdir(self.workdir)

        # if all the ligands are in step 0, submit docking scripts
        if all(step == 0 for step in self.current_step):
            docking.submit_docking_job(self.jobid, self.nligs, self.ntargets, submit_on='pharma')
            for lig_id in range(self.nligs):
                self.update_step_file(lig_id, 0)

        # check ligands in step 1
        ligs_idxs = [idx for idx, step in enumerate(self.current_step) if step == 1]
        if ligs_idxs:
            docking.check_docking(self.jobid, ligs_idxs, self.ntargets, submitted_on='pharma')
        #for lig_id, step in enumerate(self.current_step):
        #    if step == 1: # docking is running

        #    elif step == 2: # MD is running
        #        raise NotImplemented("step 2 not implemented")
        #        # check MD current status

        #    elif step == 3: # MMPBSA is running
        #        raise NotImplemented("step 3 not implemented")

        #    elif step == 4:
        #        raise NotImplemented("step 4 not implemented")

        os.chdir('..')
