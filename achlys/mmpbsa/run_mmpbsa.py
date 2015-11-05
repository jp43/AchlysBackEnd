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

class MMPBSAConfigError(Exception):
    pass

class MMPBSAConfig(object):

    def __init__(self, config_file):

        config = ConfigParser.SafeConfigParser()
        config.read(config_file)
        self.config = config

class MMPBSAWorker(object):

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
igb=2, saltcon=0.150,
/"""% locals()
            file.write(script)

    def create_arg_parser(self):

        parser = argparse.ArgumentParser(description='Run  MMPBSA simulation..')

        parser.add_argument('-f',
            dest='config_file',
            help='config file containing some extra parameters')

        parser.add_argument('-n',
            dest='ncpus',
            type=int,
            help='number of CPUs')

        return parser

    def do_mmpbsa(self, config, ncpus):

        water_and_ions = ['Na+', 'Cl-', 'WAT']

        startpdb = '../common/start.pdb'
        if not os.path.isfile(startpdb):
            raise IOError('file %s does not exist' %startpdb)

        # saving complex with non-ions non-water molecules
        with open('../common/start.pdb', 'r') as startpdb:
            with open('complex.pdb', 'w') as cmplxpdb:
                for line in startpdb:
                    is_water_or_ion = [mol in line for mol in water_and_ions]
                    if not any(is_water_or_ion):
                        print >> cmplxpdb, line.replace('\n','')
                    else: break

        # saving protein alone
        with open('complex.pdb', 'r') as cmplxpdb:
            with open('target.pdb', 'w') as targpdb:
                for line in cmplxpdb:
                    if 'LIG' not in line:
                        print >> targpdb, line.replace('\n','')
                    else: break

        # saving ligand alone
        # in principle, lig.pdb and lig.mol2 already exist
        # but lig.pdb can be corrupted that's why we extract
        # the structure from start.pdb and run tleap again
        with open('complex.pdb', 'r') as cmplxpdb:
            with open('lig.pdb', 'w') as ligpdb:
                line = cmplxpdb.next()
                while 'LIG' not in line:
                    line = cmplxpdb.next()
                print >> ligpdb, line.replace('\n','')
                for line in cmplxpdb:
                    print >> ligpdb, line.replace('\n','')

        # check for lignc.dat exists
        datfile = '../common/lignc.dat'
        if os.path.isfile(datfile):
            f = open(datfile)
            lignc = int(f.next())
            f.close()
        else:
            raise IOError('file %s does not exist'%datfile)

        subprocess.check_call('antechamber -i lig.pdb -fi pdb -o lig.mol2 -fo mol2 -at gaff -c bcc -nc %i -du y -pf y > antchmb.log'%lignc, shell=True)
        subprocess.check_call('parmchk -i lig.mol2 -f mol2 -o lig.frcmod', shell=True)

        self.prepare_tleap_input_file(config)
        subprocess.check_call('tleap -f leap.in > leap.log', shell=True)

        self.prepare_mmpbsa_input_file(config)
        subprocess.call('mpiexec -n %i MMPBSA.py.MPI -O -i mm.in -o mm.out -sp ../common/start.prmtop -cp complex.prmtop -rp target.prmtop -lp lig.prmtop -y md.dcd'%ncpus, shell=True)

    def run(self):

        parser = self.create_arg_parser()
        args = parser.parse_args()

        config = MMPBSAConfig(args.config_file).config
        self.do_mmpbsa(config, args.ncpus)

if __name__ == '__main__':
    MMPBSAWorker().run()
