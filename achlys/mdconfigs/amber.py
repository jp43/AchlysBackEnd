import subprocess
import NAMD

def run_startup(config, namd=False):

    # call antechamber
    subprocess.call('antechamber -i lig.pdb -fi pdb -o lig.mol2 -fo mol2 -at gaff -c gas -du y -pf y > antchmb.log', shell=True)
    # create starting structure
    subprocess.call('parmchk -i lig.mol2 -f mol2 -o lig.frcmod', shell=True)
    prepare_tleap_input_file()
    subprocess.call('tleap -f leap.in > leap.log', shell=True)

    # check box dimensions
    update_box_dimensions(config)

    # use leap.log to find the dimensions of the box
    with open('leap.log', 'r') as logfile:
        for line in logfile:
            if line.startswith('Total unperturbed charge'):
                newline = line.replace('\n','').split()
                netcharge = float(newline[-1])

    prepare_tleap_input_file(netcharge=netcharge)
    subprocess.call('tleap -f leap.in > leap.log', shell=True)

    if namd:
        NAMD.create_constrained_pdbfile()

def update_box_dimensions(config):

    # use leap.log to find the dimensions of the box
    with open('leap.log', 'r') as logfile:
        for line in logfile:
            line_s = line.strip()
            if line_s.startswith('Total bounding box'):
                box = map(float,line_s.split()[-3:])

    config.box = box
    config.pmegridsize = [int(size/0.9) if int(size/0.9)%2 == 0 else int(size/0.9) + 1 for size in box]

def prepare_tleap_input_file(netcharge=0):

        nnas = int(70)
        ncls = int(70 + netcharge)

        # write tleap input file
        with open('leap.in', 'w') as file:
            script ="""source leaprc.ff99SB
source leaprc.gaff
LIG = loadmol2 lig.mol2
loadamberparams lig.frcmod
p = loadPdb complex.pdb
charge p
solvatebox p TIP3PBOX 10
addions p Na+ %(nnas)s Cl- %(ncls)s
charge p
saveAmberParm p start.prmtop start.inpcrd
savepdb p start.pdb
quit"""% locals()
            file.write(script)
