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

known_programs = ['namd']

class MMPBSAAchlysConfigError(Exception):
    pass

class MMPBSAAchlysConfig(object):

    def __init__(self, config_file):

        config = ConfigParser.SafeConfigParser()
        config.read(config_file)

class MMPBSAAchlysWorker(object):

    def prepare_tleap_input_file(self, config, options=None):

        # write tleap input file
        with open('leap.in', 'w') as file:
            script ="""source leaprc.ff99SB
source leaprc.gaff
LIG = loadmol2 lig.mol2
loadamberparams lig.frcmod
t = loadpdb target.pdb
p = loadpdb complex.pdb
saveamberparm LIG lig.prmtop lig.inpcrd
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

        parser.add_argument('-f',
            dest='config_file',
            help='config file containing some extra parameters')

        return parser

    def do_mmpbsa(self, config):

        water_and_ions = ['Na+', 'Cl-', 'WAT']
        # saving complex with non-ions non-water molecules
        with open('../common/start.pdb', 'r') as startpdb:
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
            with open('lig.pdb', 'w') as ligpdb:
                line = cmplxpdb.next()
                while 'LIG' not in line:
                    line = cmplxpdb.next()
                print >> ligpdb, line.replace('\n','')
                for line in cmplxpdb:
                    print >> ligpdb, line.replace('\n','')

        # call antechamber
        subprocess.check_call('antechamber -i lig.pdb -fi pdb -o lig.mol2 -fo mol2 -at gaff -c gas -du y -pf y > antchmb.log', shell=True)
        # create starting structure
        subprocess.check_call('parmchk -i lig.mol2 -f mol2 -o lig.frcmod', shell=True)
        self.prepare_tleap_input_file(config)
        subprocess.check_call('tleap -f leap.in > leap.log', shell=True)

        # use ptraj to convert .dcd file to .mdcrd
        with open('ptraj.in', 'w') as prmfile:
            print >> prmfile, 'trajin  md.dcd 0 250 1'
            print >> prmfile, 'image origin center familiar com :1-1021'
            print >> prmfile, 'trajout run.mdcrd trajectory'

        subprocess.call('ptraj ../common/start.prmtop < ptraj.in > ptraj.out', shell=True)

        self.prepare_mmpbsa_input_file(config)
        subprocess.call('mpirun -np 16 MMPBSA.py.MPI -O -i mm.in -o mm.out -sp ../common/start.prmtop -cp complex.prmtop -rp target.prmtop -lp lig.prmtop -y run.mdcrd', shell=True)

    def run(self):

        parser = self.create_arg_parser()
        args = parser.parse_args()

        config = MMPBSAAchlysConfig(args.config_file)
        self.do_mmpbsa(config)
