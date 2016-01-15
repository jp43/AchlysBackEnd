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

known_formats = ['.pdb', '.sdf', '.smi', '.txt']
known_systems = ['herg', 'herg-cut', 'herg-inactivated']

known_steps = { 0 : ('init', 'tools.prep_manager'),
    1 : ('docking', 'docking.docking_manager'),
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

        if os.path.splitext(args.config_file)[-1] == '.ini':
            config = ConfigParser.SafeConfigParser()
            config.read(args.config_file)    
        else:
            raise IOError('config file must be of .ini type')

        jobID = self.create_job_directory(args)

        input_files_l = args.input_files_l
        prep.check_ligand_files(input_files_l)
        prep.prepare_ligand_structures(input_files_l, jobID, config)




        #self.input_files_l = input_files_l
        sys.exit()






        #self.nligs = nligs
        #self.ext_l = ext_l

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
                    raise StartJobError("The system specified in the configuration file should be one of " + ", ".join(known_systems))
                if system == 'herg':
                    achlysdir = os.path.realpath(__file__)
                    dir_r = '/'.join(achlysdir.split('/')[:-6]) + '/share/hERG_data'
                    input_files_r = [dir_r + '/' + file for file in os.listdir(dir_r) if os.path.splitext(file)[1] == '.pdb']
                    ntargets = len(input_files_r)
                    ext_r = '.pdb'
                elif system == 'herg-cut':
                    achlysdir = os.path.realpath(__file__)
                    dir_r = '/'.join(achlysdir.split('/')[:-6]) + '/share/hERG_data_cut'
                    input_files_r = [dir_r + '/' + file for file in os.listdir(dir_r) if os.path.splitext(file)[1] == '.pdb']
                    ntargets = len(input_files_r)
                    ext_r = '.pdb'
                elif system == 'herg-inactivated':
                    achlysdir = os.path.realpath(__file__)
                    dir_r = '/'.join(achlysdir.split('/')[:-6]) + '/share/hERG_data_inactiv'
                    input_files_r = [dir_r + '/' + file for file in os.listdir(dir_r) if os.path.splitext(file)[1] == '.pdb']
                    ntargets = len(input_files_r)
                    ext_r = '.pdb'
            else:
                raise StartJobError('No files for targets provided')

        self.input_files_r = input_files_r
        self.ntargets = ntargets
        self.ext_r = ext_r

        self.jobid = self.create_job_directory(args)

    def create_ligand_files(self, args):
        pass

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

        #ext_l = self.get_format(self.input_files_l)
        #lig_idx = 0
        #for file_l in self.input_files_l:
        #    if ext_l == '.pdb':
        #        dir_l = workdir+'/lig%i'%lig_idx
        #        # make ligand directory
        #        os.mkdir(dir_l)
        #        # Copy file
        #        shutil.copyfile(file_l,dir_l+'/lig%i.pdb'%lig_idx)
        #        stf = open(dir_l+'/step.out', 'w')
        #        stf.write('start step 0 (init)')
        #        stf.close()
        #        lig_idx += 1
        #    elif ext_l == '.sdf':
        #        nligs_sdf = struct_tools.count_structs_sdf(file_l)
        #        for idx_sdf in range(nligs_sdf):
        #            dir_l = workdir+'/lig%i'%lig_idx
        #            # make ligand directory
        #            os.mkdir(dir_l)
        #            # Convert and copy file
        #            os.system('babel -isdf %s -f%d -l%d -osdf %s 2>/dev/null' % 
        #                    (file_l, idx_sdf+1, idx_sdf+1, dir_l+'/lig%i'%lig_idx+self.ext_l))
        #            # copy current step
        #            stf = open(dir_l+'/step.out', 'w')
        #            stf.write('start step 0 (init)')
        #            stf.close()
        #            lig_idx += 1
        #    elif ext_l == '.smi' or ext_l == '.txt':
        #        nligs_smi = struct_tools.count_structs_sdf(file_l)
        #        for idx_smi in range(nligs_smi):
        #            dir_l = workdir+'/lig%i'%lig_idx
        #            # make ligand directory
        #            os.mkdir(dir_l)
        #            # Convert and copy file 
        #            os.system('babel -ismi %s -f%d -l%d -osdf %s 2>/dev/null' % 
        #                    (file_l, idx_smi+1, idx_smi+1, dir_l+'/lig%i'%lig_idx+'.sdf'))
        #            # copy current step
        #            stf = open(dir_l+'/step.out', 'w')
        #            stf.write('start step 0 (init)')
        #            stf.close()
        #            lig_idx += 1
        #    else:
        #        raise StartJobError("format of input files should be among " + ", ".join(known_formats))

        # copy targets
        #dir_r = workdir+'/targets'
        #os.mkdir(dir_r)
        #for idx, file_r in enumerate(self.input_files_r):
        #    shutil.copyfile(file_r,dir_r+'/target%i'%idx+self.ext_r)

        return jobid

    def create_arg_parser(self):
        parser = argparse.ArgumentParser(description="Run StartJob...")
    
        parser.add_argument('-l',
            type=str,
            dest='input_files_l',
            nargs='*',
            required = True,
            help = 'Ligand structure file(s): .pdb, .sdf, .smi')
        parser.add_argument('-r',
            type=str,
            dest='input_files_r',
            nargs='*',
            help = 'Receptor structure file(s): .pdb')
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

        for inifile in glob.glob(self.workdir + '/*.ini'):
            config_file = inifile        
        self.parse_config(config_file)

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

    def parse_config(self, config_file):

        self.config_file = config_file
        config = ConfigParser.SafeConfigParser()
        config.read(config_file)

        # set the number of poses
        if config.has_section('GENERAL'):
            if config.has_option('GENERAL', 'nposes'):
                self.nposes = config.getint('GENERAL', 'nposes')
            else:
                self.nposes = 7

        # set docking settings
        docking_settings = {}
        if config.has_option('GENERAL', 'run_docking_on'):
            ressource = config.get('GENERAL', 'run_docking_on').lower()
            if ressource not in known_docking_ressources:
                raise ValueError("docking ressource option should be one of " + ", ".join(known_docking_ressources))
            docking_settings['ressource'] = ressource
        else:
            docking_settings['ressource'] = 'pharma'

        self.docking_settings = docking_settings

        # set docking settings
        md_settings = {}
        if config.has_option('GENERAL', 'run_md_on'):
            ressource = config.get('GENERAL', 'run_md_on').lower()
            if ressource not in known_md_ressources:
                raise ValueError("md ressource option should be one of " + ", ".join(known_md_ressources))
            md_settings['ressource'] = ressource
        else:
            md_settings['ressource'] = 'bgq'

        self.md_settings = md_settings

        # set mmpbsa settings 
        mmpbsa_settings = {}
        if config.has_option('GENERAL', 'run_mmpbsa_on'):
            ressource = config.get('GENERAL', 'run_mmpbsa_on').lower()
            if ressource not in known_mmpbsa_ressources:
                raise ValueError("mmpbsa ressource option should be one of " + ", ".join(known_mmpbsa_ressources))
            mmpbsa_settings['ressource'] = ressource
        else:
            mmpbsa_settings['ressource'] = 'pharma' 

        if mmpbsa_settings['ressource'] == 'grex':
            walltime = 60*self.nposes
            walltime_h = int(walltime/60)
            if walltime_h < 10:
                walltime_h_str = '0' + str(walltime_h)
            elif walltime_h >= 10 and walltime_h < 24:
                walltime_h_str = str(walltime_h)
            else:
                raise ValueError("Number of poses too big to be handled in a single job on Grex")
            walltime_m = walltime%60
            if walltime_m < 10:
                walltime_m_str = '0' + str(walltime_m)
            else:
                walltime_m_str = str(walltime_m)
            mmpbsa_settings['walltime'] = '%s:%s:00'%(walltime_h_str, walltime_m_str)
        elif mmpbsa_settings['ressource'] == 'pharma':
            mmpbsa_settings['walltime'] = '168:00:00'

        self.mmpbsa_settings = mmpbsa_settings

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

        with open('lig%i/step.out'%lig_id, 'w') as file:
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

        # If a ligand is in step 0, submit a prep job
        for lig_id in range(self.nligs):
            if self.steps[lig_id] == 0:
                if self.status[lig_id] == 'start':
                    status_lig = prep.submit_prep_job(self.jobid, lig_id, submit_on='local') 
                    self.update_step(lig_id, status_lig)
                if self.status[lig_id] == 'running':
                    status_lig = prep.check_prep_job(self.jobid, lig_id, submit_on='local')
                    self.update_step(lig_id, status_lig)
        
        for step in range(1,5): 
            for status in ['start', 'running']:
                self.check_step(step, status)

        os.chdir('..')

