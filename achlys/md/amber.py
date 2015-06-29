import sys

import subprocess
import NAMD

def run_startup(config, namd=False):

    if config.withlig:
        # call antechamber
        subprocess.check_call('antechamber -i lig.pdb -fi pdb -o lig.mol2 -fo mol2 -at gaff -c gas -du y -pf y > antchmb.log', shell=True)
        # create starting structure
        subprocess.check_call('parmchk -i lig.mol2 -f mol2 -o lig.frcmod', shell=True)
    prepare_tleap_input_file(config)
    subprocess.check_call('tleap -f leap.in > leap.log', shell=True)

    # check box dimensions
    update_box_dimensions(config)

    # use leap.log to find the dimensions of the box
    with open('leap.log', 'r') as logfile:
        for line in logfile:
            if line.startswith('Total unperturbed charge'):
                newline = line.replace('\n','').split()
                netcharge = float(newline[-1])

    prepare_tleap_input_file(config, netcharge=netcharge)
    subprocess.check_call('tleap -f leap.in > leap.log', shell=True)

    if namd:
        NAMD.create_constrained_pdbfile()

def update_box_dimensions(config):

    # use leap.log to find the dimensions of the box
    with open('leap.log', 'r') as logfile:
        for line in logfile:
            line_s = line.strip()
            if line_s.startswith('Total bounding box'):
                box = map(float,line_s.split()[-3:])

    frac_pmegridsize = 0.9

    config.box = [size + 2.0 for size in box]
    config.pmegridsize = [int(size/frac_pmegridsize) if int(size/frac_pmegridsize)%2 == 0 else int(size/frac_pmegridsize) + 1 for size in config.box]

def prepare_tleap_input_file(config, netcharge=0):

        # write tleap input file
        if config.withlig:
            lines_lig="""LIG = loadmol2 lig.mol2
loadamberparams lig.frcmod"""
        else:
            lines_lig=""

        #nnas = int(70)
        #ncls = int(70 + netcharge)
        #addions p Na+ %(nnas)s Cl- %(ncls)s

        with open('leap.in', 'w') as file:
            script ="""source leaprc.ff99SB
source leaprc.gaff
%(lines_lig)s
p = loadPdb complex.pdb
charge p
solvatebox p TIP3PBOX 10
charge p
saveAmberParm p start.prmtop start.inpcrd
savepdb p start.pdb
quit"""% locals()
            file.write(script)
