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
import itertools as it

from achlys.docking import docking_manager
from achlys.md import md_manager
from achlys.mmpbsa import mmpbsa_manager
from achlys.tools import prep
from achlys.tools import struct_tools

known_steps = { 1 : ('docking', 'docking.docking_manager'),
    2 : ('startup', 'md.md_manager'),
    3 : ('md', 'md.md_manager'),
    4 : ('mmpbsa','mmpbsa.mmpbsa_manager')}

known_prep_ressources = ['local']
known_docking_ressources = ['pharma', 'hermes']
known_md_ressources = ['bgq']
known_mmpbsa_ressources = ['pharma', 'grex']

class StartJobError(Exception):
    pass

class StartJob(object):

    def initialize(self, args):
        global known_formats
        global known_systems

        jobid = self.create_job_directory(args)

        if os.path.splitext(args.config_file)[-1] == '.ini':
            config = ConfigParser.SafeConfigParser()
            config.read(args.config_file)    
        else:
            raise IOError('config file must be of .ini type')

        input_files_l = []
        for idx, file_l in enumerate(args.input_files_l):
            input_files_l.append(os.path.abspath(file_l))
        prep.prepare_compounds(input_files_l, jobid)

        input_files_r = []
        if args.input_files_r:
            for idx, file_r in enumerate(args.input_files_r):
                input_files_r.append(os.path.abspath(file_r))
        prep.prepare_targets(input_files_r, jobid)

        return jobid

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

        return jobid

    def create_arg_parser(self):

        parser = argparse.ArgumentParser(description="Run StartJob...")
    
        parser.add_argument('-l',
            type=str,
            dest='input_files_l',
            nargs='*',
            required = True,
            help = 'Ligand structure file(s): .sdf, .smi')
 
        parser.add_argument('-r',
            type=str,
            dest='input_files_r',
            nargs='*',
            help = 'Receptor structure file(s): .pdb')

        parser.add_argument('-f',
            dest='config_file',
            required=True,
            help='Config file with parameters')

        return parser

    def run(self):

        parser = self.create_arg_parser()
        args = parser.parse_args()
        jobid = self.initialize(args)

        print 'Job %s started' % jobid

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
        self.parse_config(self.workdir+'/config.ini')

        status = []
        steps = []
        # check current step
        for idx in range(nligs):
            with open(self.workdir+'/lig%i/step.out'%(idx+1), 'r') as stf:
                line = stf.next().split()
                status.append(line[0])
                steps.append(int(line[2]))

        self.status = status
        self.steps = steps

    def parse_config(self, config_file):

        self.config_file = config_file
        config = ConfigParser.SafeConfigParser()
        config.read(config_file)

        # set the number of poses
        nposes = 5
        if config.has_section('GENERAL'):
            if config.has_option('GENERAL', 'nposes'):
                nposes = config.getint('GENERAL', 'nposes')
        self.nposes = nposes

        self.docking_settings = {'ressource': 'pharma'}
        scoring_functions = []
        if config.has_section('RESCORING'):
            if config.has_option('RESCORING', 'program'):
                scoring_functions = config.get('RESCORING', 'program').split(',')
        self.docking_settings['scoring_functions'] = scoring_functions

        self.md_settings = {'ressource': 'bgq'}
        self.mmpbsa_settings = {'ressource': 'pharma'}

    def update_step(self, lig_id, status_lig):

        step_lig = self.steps[lig_id]

        if step_lig == 4 and status_lig == 'done':
            new_step_lig = step_lig
            new_status_lig = 'done' # the procedure is done
        elif status_lig == 'done':
            new_step_lig = step_lig + 1
            new_status_lig = 'start'
        elif status_lig == 'error': # error encountered
            new_step_lig = step_lig
            new_status_lig = 'error'
        elif status_lig == 'running': # job still running
            new_step_lig = step_lig
            new_status_lig = 'running'

        with open('lig%i/step.out'%(lig_id+1), 'w') as file:
            print >> file, new_status_lig + ' step ' + str(new_step_lig)  + ' (%s)'%known_steps[new_step_lig][0]

    def create_arg_parser(self):
        parser = argparse.ArgumentParser(description="Run CheckJob...")

        parser.add_argument('--id',
            dest='jobid',
            type=str,
            required=True,
            help='Job ID')
        return parser

    def check_step(self, step_checked, status_checked):

        ligs_idxs = [idx for idx, [step, status] in enumerate(it.izip(self.steps, self.status)) if step == step_checked and status == status_checked]

        if ligs_idxs:
            # get module name
            step_name = known_steps[step_checked][0]
            module_name = known_steps[step_checked][1]

            # get function suffix
            if status_checked == 'start':
                func_suffix = 'submit_'
            elif status_checked == 'running':
                func_suffix = 'check_'
            else:
                raise ValueError('status should be either start or running when trying to run a step')

            func_name = func_suffix + step_name
            func = getattr(sys.modules['achlys.'+module_name], func_name)

            status = func(self, ligs_idxs)
            for idx, lig_id in enumerate(ligs_idxs):
                self.update_step(lig_id, status[idx])

    def run(self):
    
        parser = self.create_arg_parser()
        args = parser.parse_args()
        self.initialize(args)

        os.chdir(self.workdir)

        for step in range(1,5): 
            for status in ['start', 'running']:
                self.check_step(step, status)

        os.chdir('..')
