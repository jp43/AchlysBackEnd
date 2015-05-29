import os
import sys
import subprocess
import shutil

def create_constrained_pdbfile():

    with open('start.pdb', 'r') as startfile:
        with open('posres.pdb', 'w') as posresfile:
            for line in startfile:
                if line.startswith(('ATOM', 'HETATM')):
                    atom_name = line[12:16].strip()
                    res_name = line[17:20].strip()
                    if 'WAT' in res_name: # water molecules
                        newline = line[0:30] + '%8.3f'%0.0 + line[38:]
                    elif 'LIG' in res_name: # atoms of the ligand
                        if atom_name.startswith(('C', 'N', 'O')):
                            newline = line[0:30] + '%8.3f'%50.0 + line[38:]
                        else:
                            newline = line[0:30] + '%8.3f'%0.0 + line[38:]
                    else: # atoms of the protein
                        if atom_name in ['C', 'CA', 'N', 'O']:
                            newline = line[0:30] + '%8.3f'%50.0 + line[38:]
                        else:
                            newline = line[0:30] + '%8.3f'%0.0 + line[38:]
                else:
                    newline = line
                print >> posresfile, newline.replace('\n','')

def write_minimization_config_file(config, nstepsmin=5000, temperature=310.0, amber=True, **kwargs):

    box = config.box

    boxx = box[0]
    boxy = box[1]
    boxz = box[2]

    pmegridsize = config.pmegridsize

    pmegridsizex = pmegridsize[0]
    pmegridsizey = pmegridsize[1]
    pmegridsizez = pmegridsize[2]

    if amber:
        input_files_prms = """cwd                .
amber              yes
coordinates        ../common/start.pdb
parmfile           ../common/start.prmtop
paraTypeXplor      off"""

    else:
        input_files_prms = """cwd                .
structure           ../common/start.psf
coordinates         ../common/start.pdb"""


    with open('min.conf', 'w') as file:
        script ="""# Energy minimization

# adjustable parameters
set temperature    %(temperature)s
set outputname     min
set nsteps         %(nstepsmin)s

# input files parameters
%(input_files_prms)s

# starting from scratch
temperature       $temperature

# output files parameters
outputName          $outputname
restartfreq         1000
DCDUnitCell         yes
dcdfreq             $nsteps
outputEnergies      $nsteps

# Force-Field Parameters
exclude             scaled1-4
switching           on
switchdist          10
cutoff              12
outputPairlists     100

# Integrator Parameters
timestep            2.0
rigidBonds          all

# PME (for full-system periodic electrostatics)
PME                 yes
PMEInterpOrder      4
PMEGridSizeX        %(pmegridsizex)i
PMEGridSizeY        %(pmegridsizey)i
PMEGridSizeZ        %(pmegridsizez)i

cellBasisVector1     %(boxx)5.3f       0           0
cellBasisVector2       0        %(boxy)5.3f        0
cellBasisVector3       0          0        %(boxz)5.3f

# Minimization
minimize           $nsteps"""% locals()
        file.write(script)


def run_minimization(ncpus, config):

    write_minimization_config_file(config, **config.namd_options)
    subprocess.call('mpirun -np ' + str(ncpus) + ' namd2 min.conf', shell=True)

    # use ptraj to convert .dcd file to .pdb
    with open('ptraj.in', 'w') as prmfile:
        print >> prmfile, 'trajin  min.dcd 1 1 1'
        print >> prmfile, 'trajout run.pdb PDB'
    subprocess.call('ptraj ../common/start.prmtop < ptraj.in > ptraj.out', shell=True)
    shutil.move('run.pdb.1', 'end-min.pdb')


def write_nvt_config_file(config, nstepsnvt=5000, nrunsnvt=10, temperature=310, amber=True, **kwargs):

    pmegridsize = config.pmegridsize

    pmegridsizex = pmegridsize[0]
    pmegridsizey = pmegridsize[1]
    pmegridsizez = pmegridsize[2]

    if amber:
        input_files_prms = """cwd                .
amber              yes
coordinates        ../min/end-min.pdb
parmfile           ../common/start.prmtop
paraTypeXplor      off"""

    else:
        input_files_prms = """cwd                .
structure           ../common/start.psf
coordinates         ../min/end-min.pdb"""

    with open('nvt.conf', 'w') as file:
        script ="""# NVT equilibration

set temperature      %(temperature)s
set outputname       nvt
set nsteps           %(nstepsnvt)s
set nruns            %(nrunsnvt)s
set temperature_min  250.0

# input files prms
%(input_files_prms)s

# starting from Restart Files
set inputname      ../min/min
binCoordinates     $inputname.coor
binVelocities      $inputname.vel  
extendedSystem 	   $inputname.xsc

# output files parameters
outputName          $outputname
binaryoutput	    yes
restartfreq         $nsteps
dcdfreq             [expr {$nruns*$nsteps}]
outputEnergies      [expr {$nruns*$nsteps}]

# Force-Field Parameters
exclude             scaled1-4
switching           on
switchdist          10
cutoff              12
outputPairlists     100

# Integrator Parameters
timestep            2.0
rigidBonds          all

# PME (for full-system periodic electrostatics)
PME                 yes
PMEGridSizeX        %(pmegridsizex)i
PMEGridSizeY        %(pmegridsizey)i
PMEGridSizeZ        %(pmegridsizez)i

# No constant pressure, since we will do constant volume simulation
constraints         on
consref             ../min/end-min.pdb
conskfile           ../common/posres.pdb
conskcol            X

# Constant Temperature Control (NVT)
langevin            on
langevinDamping     5
langevinHydrogen    off

# Heat using rescaling
for { set i 0 } { $i < $nruns } { incr i 1 } {
  langevinTemp [expr {($temperature-$temperature_min)*(double($i)/$nruns) + $temperature_min}];
  run $nsteps
}"""% locals()
        file.write(script)

def run_nvt(ncpus, config):

    write_nvt_config_file(config, **config.namd_options)
    subprocess.call('mpirun -np ' + str(ncpus) + ' namd2 nvt.conf', shell=True)

    # use ptraj to convert .dcd file to .pdb
    with open('ptraj.in', 'w') as prmfile:
        print >> prmfile, 'trajin  nvt.dcd 1 1 1'
        print >> prmfile, 'trajout run.pdb PDB'
    subprocess.call('ptraj ../common/start.prmtop < ptraj.in > ptraj.out', shell=True)
    shutil.move('run.pdb.1', 'end-nvt.pdb')

def write_npt_config_file(config, nstepsnpt=5000, temperature=310, amber=True, **kwargs):

    pmegridsize = config.pmegridsize

    pmegridsizex = pmegridsize[0]
    pmegridsizey = pmegridsize[1]
    pmegridsizez = pmegridsize[2]

    if amber:
        input_files_prms = """cwd             .
amber              yes
coordinates        ../nvt/end-nvt.pdb
parmfile           ../common/start.prmtop
paraTypeXplor      off"""

    else:
        input_files_prms = """cwd                .
structure           ../common/start.psf
coordinates         ../nvt/end-nvt.pdb"""

    with open('npt.conf', 'w') as file:
        script ="""# NPT equilibration

set temperature      %(temperature)s
set outputname       npt
set nsteps           %(nstepsnpt)s

# input files prms
%(input_files_prms)s

# starting from Restart Files
set inputname      ../nvt/nvt
binCoordinates     $inputname.coor
binVelocities      $inputname.vel  
extendedSystem     $inputname.xsc

# output files parameters
outputName          $outputname
binaryoutput        yes
restartfreq         $nsteps
dcdfreq             $nsteps
outputEnergies      $nsteps

# Force-Field Parameters
exclude             scaled1-4
switching           on
switchdist          10
cutoff              12
outputPairlists     100

# Integrator Parameters
timestep            2.0
rigidBonds          all

# PME (for full-system periodic electrostatics)
PME                 yes
PMEGridSizeX        %(pmegridsizex)i
PMEGridSizeY        %(pmegridsizey)i
PMEGridSizeZ        %(pmegridsizez)i

# No constant pressure, since we will do constant volume simulation
constraints         on
consref             ../nvt/end-nvt.pdb
conskfile           ../common/posres.pdb
conskcol            X

# Constant temperature control (NVT)
langevin            on
langevinDamping     5
langevinTemp        $temperature
langevinHydrogen    off

# constant pressure (NPT)
LangevinPiston		 on
LangevinPistonTarget	 1.01325
LangevinPistonPeriod	 200
LangevinPistonDecay	 100
LangevinPistonTemp	 $temperature

run $nsteps"""% locals()
        file.write(script)

def run_npt(ncpus, config):

    write_npt_config_file(config, **config.namd_options)
    subprocess.call('mpirun -np ' + str(ncpus) + ' namd2 npt.conf', shell=True)

    # use ptraj to convert .dcd file to .pdb
    with open('ptraj.in', 'w') as prmfile:
        print >> prmfile, 'trajin  npt.dcd 1 1 1'
        print >> prmfile, 'trajout run.pdb PDB'
    subprocess.call('ptraj ../common/start.prmtop < ptraj.in > ptraj.out', shell=True)
    shutil.move('run.pdb.1', 'end-npt.pdb')
