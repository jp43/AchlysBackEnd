from __future__ import with_statement

import sys
import os
import subprocess
import tempfile
import shutil
import argparse
import ConfigParser
import logging
import time
import numpy as np

from achlys.kernel import docking

known_programs = ['namd']

class MMPBSAAchlysConfigError(Exception):
    pass

class MMPBSAAchlysConfig(object):

    def __init__(self, config_file):

        config = ConfigParser.SafeConfigParser()
        config.read(config_file)

        self.docking = docking.DockingConfig(config_file)

class MMPBSAAchlysWorker(object):

    def prepare_tleap_input_file(self, config, options=None):

        # write tleap input file
        with open('leap.in', 'w') as file:
            script ="""source leaprc.ff99SB
source leaprc.gaff
loadamberprep ligand.prepin
loadamberparams ligand.frcmod
t = loadpdb target.pdb
p = loadpdb complex.pdb
saveamberparm LIG ligand.prmtop ligand.inpcrd
saveamberparm t target.prmtop target.inpcrd
saveamberparm p complex.prmtop complex.inpcrd
quit"""% locals()
            file.write(script)

    def prepare_mmpbsa_input_file(self, config, options=None):

        # write mmpbsa input file
        with open('mm.in', 'w') as file:
            script ="""Sample input file for GB and PB calculation
&general
startframe=1, endframe=5000, interval=1,
verbose=2, keep_files=0,
/
&gb
igb=5, saltcon=0.150,
/"""% locals()
            file.write(script)

    def create_arg_parser(self):

        parser = argparse.ArgumentParser(description='Run Achlys MMPBSA simulation..')

        parser.add_argument('cpu_id',
            metavar='CPU ID',
            type=int,
            help='CPU ID')

        parser.add_argument('-f',
            dest='config_file',
            help='config file containing some extra parameters')

        return parser

    def prepare_mmpbsa(self, config):

        curdir = os.getcwd()
        workdir = 'mmpbsa'
        shutil.rmtree(workdir, ignore_errors=True)
        os.mkdir(workdir)
        os.chdir(workdir)

        water_and_ions = ['Na+', 'Cl-', 'WAT']
        # saving complex with non-ions non-water molecules
        with open('../startup/start.pdb', 'r') as startpdb:
            with open('complex.pdb', 'w') as cmplxpdb:
                for line in startpdb:
                    is_water_or_ion = [mol in line for mol in water_and_ions]
                    if not any(is_water_or_ion):
                        print >> cmplxpdb, line.replace('\n','')
                    else: break

        # saving target
        with open('complex.pdb', 'r') as cmplxpdb:
            with open('target.pdb', 'w') as targpdb:
                for line in cmplxpdb:
                    if 'LIG' not in line:
                        print >> targpdb, line.replace('\n','')
                    else: break

        # saving ligand
        with open('complex.pdb', 'r') as cmplxpdb:
            with open('ligand.pdb', 'w') as ligpdb:
                line = cmplxpdb.next()
                while 'LIG' not in line:
                    line = cmplxpdb.next()
                print >> ligpdb, line.replace('\n','')
                for line in cmplxpdb:
                    print >> ligpdb, line.replace('\n','')

        net_charge = np.loadtxt('../startup/charge.txt')
        # call antechamber
        subprocess.call('antechamber -i ligand.pdb -fi pdb -o ligand.prepin -fo prepi \
            -j 4 -at gaff -c gas -du y -s 1 -pf y -nc %.1f > antchmb.log'%net_charge, shell=True)
        # create starting structure
        subprocess.call('parmchk -i ligand.prepin -f prepi -o ligand.frcmod', shell=True)
        self.prepare_tleap_input_file(config)
        # call tleap to generate prmtop files
        subprocess.call('tleap -f leap.in', shell=True)

        # use ptraj to convert .dcd file to .mdcrd
        with open('ptraj.in', 'w') as prmfile:
            print >> prmfile, 'trajin  ../equ/equ.dcd 0 500 1'
            print >> prmfile, 'image origin center familiar com :1-1021'
            print >> prmfile, 'trajout run.mdcrd trajectory'

        subprocess.call('ptraj ../startup/start.prmtop < ptraj.in > ptraj.out', shell=True)

        self.prepare_mmpbsa_input_file(config)
        subprocess.call('MMPBSA.py -O -i mm.in -o mm.out -sp ../startup/start.prmtop -cp complex.prmtop -rp target.prmtop -lp ligand.prmtop -y run.mdcrd', shell=True)

    def run(self):

        parser = self.create_arg_parser()
        args = parser.parse_args()

        if args.cpu_id == 0:
            logging.basicConfig(filename='achlys.log',
                            filemode='a',
                            format="%(levelname)s:%(name)s:%(asctime)s: %(message)s",
                            datefmt="%H:%M:%S",
                            level=logging.DEBUG)

            tcpu1 = time.time()
            logging.info('Starting MMPBSA (pose %i)...'%args.cpu_id)

        config = MMPBSAAchlysConfig(args.config_file)

        curdir = os.getcwd()
        workdir = 'md-pose%i'%args.cpu_id
        os.chdir(workdir)

        self.prepare_mmpbsa(config)
        os.chdir(curdir) 

        if args.cpu_id == 0:
            tcpu2 = time.time()
            logging.info('MMPBSA done (pose %i). Total time needed: %i s.'%(args.cpu_id, tcpu2-tcpu1)) 
