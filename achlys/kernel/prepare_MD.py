from __future__ import with_statement

import sys
import os
import subprocess
import shutil
import argparse
import time
import ConfigParser

import amber
import NAMD

known_programs = ['namd']
known_steps = ['startup', 'min', 'equil', 'md']

class MDConfigError(Exception):
    pass

class MDConfig(object):

    def __init__(self, args):

        config = ConfigParser.SafeConfigParser()
        config.read(args.config_file)

        self.system = config.get('GENERAL', 'system').lower()

        if config.has_option('MD', 'program'):
            program = config.get('MD', 'program').lower()
            if program not in known_programs:
                raise MDConfigError('program option should be one of ' + ', '.join(known_programs))
            self.program = program
        else:
            self.program = 'namd'

        if self.program == 'namd':
            if config.has_section('AMBER'):
                self.amber_options = dict(config.items('AMBER'))
            else:
                self.amber_options = {}
            if config.has_section('NAMD'):
                self.namd_options = dict(config.items('NAMD'))
            else:
                self.namd_options = {}

        steps = {}
        for step in args.steps:
            if step not in known_steps:
                raise ValueError("Step unknown: %s"%step)
        for step in known_steps:
            if step in args.steps:
                steps[step] = True
            else:
                steps[step] = False

        self.steps = steps
        self.check_starting_files(args)

    def check_starting_files(self, args):

        steps = self.steps

        if steps['startup'] or steps['min'] or steps['equil']:
            if not os.path.isdir('common'):
                raise MDConfigError('folder "common" not found!')

        if steps['startup']:
            if not os.path.exists('common/lig.pdb'):
                raise MDConfigError('file "common/lig.pdb" not found!')

            elif not os.path.exists('common/complex.pdb'):
                raise MDConfigError('file "common/complex.pdb" not found!')

        if not steps['startup'] and (steps['min'] or steps['equil']):
            if not os.path.exists('common/leap.log'):
                raise MDConfigError('file "common/leap.log" not found!')

            elif not os.path.exists('common/posres.pdb'):
                raise MDConfigError('file "common/posres.pdb" not found!')

        if not steps['min'] and steps['equil']:
            if not os.path.exists('min/end-min.pdb'):
                raise MDConfigError('file "min/end-min" not found!')

class MDWorker(object):

    def create_arg_parser(self):

        parser = argparse.ArgumentParser(description='Run Achlys MD simulation..')

        parser.add_argument('steps',
            type=str,
            help='step (startup, min, equil)',
            nargs='+')

        parser.add_argument('--ncpus',
            metavar='ncpus',
            type=int,
            help='total number of cpus used')

        parser.add_argument('-f',
            dest='config_file',
            help='config file containing some extra parameters')

        parser.add_argument('--build',
            dest='build',
            action='store_true',
            default=False,
            help='build MD folders')

        parser.add_argument('--bgq',
            dest='bgq',
            action='store_true',
            default=False,
            help='run on BlueGene/Q')

        return parser

    def run_startup(self, config):

        curdir = os.getcwd()
        if config.program == 'namd':
            os.chdir('common') 
            amber.run_startup(config, namd=True)
            os.chdir(curdir)

    def prepare_minimization_no_startup(self, config):

        curdir = os.getcwd()
        if config.program == 'namd':
            os.chdir('common')
            amber.update_box_dimensions(config)
            os.chdir(curdir)

    def run_minimization(self, args, config):
        curdir = os.getcwd()
        if config.program == 'namd':
            shutil.rmtree('min', ignore_errors=True)
            os.mkdir('min')
            os.chdir('min')
            NAMD.run(args, config, 'min')
            os.chdir(curdir)

    def run_nvt(self, args, config):
        curdir = os.getcwd()
        if config.program == 'namd':
            shutil.rmtree('nvt', ignore_errors=True)
            os.mkdir('nvt')
            os.chdir('nvt')
            NAMD.run(args, config, 'nvt')
            os.chdir(curdir)

    def run_npt(self, args, config):
        curdir = os.getcwd()
        if config.program == 'namd':
            shutil.rmtree('npt', ignore_errors=True)
            os.mkdir('npt')
            os.chdir('npt')
            NAMD.run(args, config, 'npt')
            os.chdir(curdir)

    def run_md(self, args, config):
        curdir = os.getcwd()
        if config.program == 'namd':
            NAMD.run(args, config, 'md')
            os.chdir(curdir)
 
    def run(self):

        parser = self.create_arg_parser()
        args = parser.parse_args()

        config = MDConfig(args)

        if config.steps['startup']:
            self.run_startup(config)
        elif config.steps['min'] or config.steps['equil'] or config.steps['md']:
            self.prepare_minimization_no_startup(config)

        if config.steps['min']:
            self.run_minimization(args, config)

        if config.steps['equil']:
            self.run_nvt(args, config)
            self.run_npt(args, config)

        if config.steps['md']:
            self.run_md(args, config)

if __name__ == '__main__':
    MDWorker().run()
