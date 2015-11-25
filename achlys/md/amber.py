import sys
import os
import fileinput
import subprocess
import NAMD

def update_pdbfile(filename):
    for line in fileinput.input(filename, inplace=True):
        newline = line.replace('\n','')
        newline = newline.replace('Cl','CL') 
        newline = newline.replace('Br','BR')
        print newline

def correct_prmtop_file(filename):
    isperiodicity = False
    for line in fileinput.input(filename, inplace=True):
        if line.startswith("%FLAG DIHEDRAL_PERIODICITY"):
            isperiodicity = True        
        elif line.startswith("%FLAG"):
            isperiodicity = False
        newline = line.replace('\n','')
        if isperiodicity:
            newline = newline.replace('0.','1.')
        print newline

def run_antechamber(pdbfile, mol2file):
    """ use H++ idea of running antechamber multiple times with bcc's 
charge method to estimate the appropriate net charge!!"""

    logfile = 'antchmb.log'
    max_net_charge = 30
    net_charge = [0]
    for nc in range(max_net_charge):
        net_charge.extend([nc+1,-(nc+1)])

    for nc in net_charge:
        iserror = False
        subprocess.call('antechamber -i %s -fi pdb -o %s -fo mol2 -at gaff -c bcc -nc %i -du y -pf y > %s'%(pdbfile, mol2file, nc, logfile), shell=True, executable='/bin/bash')
        with open(logfile, 'r') as lf:
            for line in lf:
                if 'Error' in line:
                    iserror = True
        if not iserror:
            lignc = nc
            break

    if not iserror:
        with open('lignc.dat', 'w') as ncf:
            print >> ncf, lignc 
    else:
        raise ValueError("No appropriate net charge was found to run antechamber's bcc charge method")

    return lignc

def run_parmchk(mol2file, frcmodfile):
    """ run parmchk to generate frcmod file""" 
    subprocess.check_call('parmchk -i %s -f mol2 -o %s'%(mol2file, frcmodfile), shell=True, executable='/bin/bash')

def run_startup(config, namd=False):

    if config.withlig:
        # modify lig.pdb to meet amber convention
        update_pdbfile('lig.pdb')
        update_pdbfile('complex.pdb')

        # call antechamber & parmchk
        lignc = run_antechamber('lig.pdb','lig.mol2')
        run_parmchk('lig.mol2', 'lig.frcmod')
    else:
        lignc = 0

    netcharge = lignc 
    run_tleap(config, 'leap.in', netcharge=netcharge)

    # check box dimensions
    update_box_dimensions(config)

    # once the .pdb and .prmtop files are created, check p
    if namd:
        correct_prmtop_file('start.prmtop')
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


def run_tleap(config, leapin, netcharge=0):
    """run tleap"""

    prepare_tleap_input_file(config, netcharge=netcharge, **config.amber_options)
    subprocess.check_call('tleap -f %s > leap.log'%leapin, shell=True, executable='/bin/bash')

def prepare_tleap_input_file(config, netcharge=0, addions=True, **kwargs):

        if config.withlig:
            lines_lig = """LIG = loadmol2 lig.mol2
loadamberparams lig.frcmod"""
        else:
            lines_lig = ""

        nnas = 148
        ncls = 148
        if netcharge < 0:
            ncls -= abs(netcharge)
        elif netcharge > 0:
            nnas -= netcharge

        if addions:
            lines_addions = """addions p Na+ %(nnas)s Cl- %(ncls)s
charge p"""% locals()
        else:
            lines_addions = ""

        with open('leap.in', 'w') as file:
            script ="""source leaprc.ff99SB
source leaprc.gaff
%(lines_lig)s
p = loadPdb complex.pdb
charge p
solvatebox p TIP3PBOX 10
%(lines_addions)s
saveAmberParm p start.prmtop start.inpcrd
savepdb p start.pdb
quit"""% locals()
            file.write(script)
