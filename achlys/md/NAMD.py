import os
import sys
try:
    import ssh
except:
    from achlys.tools import ssh
import subprocess
import tempfile
import time
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

def preprocessing_md(args, config, step, extend=False, **kwargs):

    config_file_func_name = 'write_' + step + '_config_file'
    config_file_func = getattr(sys.modules[__name__], config_file_func_name)
    config_file_func(config, **config.namd_options)

def run(args, config, step):

    preprocessing_md(args, config, step, **config.namd_options)

    if args.build:
        return

    if args.bgq:
        namd_exe = '/home/j/jtus/preto/modules/NAMD_2.9_Source/BlueGeneQ-xlC-smp-qp/namd2'
        subprocess.check_call('runjob --np ' + str(args.ncpus) + ' --ranks-per-node=16 : ' + namd_exe + ' ' + step + '.conf', shell=True) 
    else:
        subprocess.check_call('mpirun --np ' + str(args.ncpus) + ' namd2 ' + step + '.conf', shell=True)

    postprocessing_md(args, config, step)

def postprocessing_md(args, config, step):

    dcd_file_name = step + '.dcd'
    if step != 'md':
        if args.bgq:
            subprocess.check_call('catdcd -o end-%s.pdb -s ../common/start.pdb -otype pdb %s.dcd'%(step,step), shell=True)
        else:
            with open('ptraj.in', 'w') as prmfile:
                print >> prmfile, 'trajin %s 1 1 1'%dcd_file_name
                print >> prmfile, 'trajout run.pdb PDB'
            subprocess.check_call('ptraj ../common/start.prmtop < ptraj.in > ptraj.out', shell=True)
            shutil.move('run.pdb.1', 'end-%s.pdb'%step)

def write_min_config_file(config, nstepsmin=5000, temperature=310.0, amber=True, **kwargs):

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
coordinates         ../common/start.pdb
structure           ../common/start.psf"""


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
margin              2.5

# Integrator Parameters
timestep            2.0
rigidBonds          all
fullElectFrequency  2
stepspercycle       10

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

def write_nvt_config_file(config, nstepsnvt=5000, nrunsnvt=10, temperature=310.0, amber=True, **kwargs):

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
coordinates         ../min/end-min.pdb
structure           ../common/start.psf"""

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
margin              5

# Integrator Parameters
timestep            2.0
rigidBonds          all
fullElectFrequency  2
stepspercycle       10

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

def write_npt_config_file(config, nstepsnpt=5000, temperature=310.0, amber=True, **kwargs):

    pmegridsize = config.pmegridsize

    pmegridsizex = pmegridsize[0]
    pmegridsizey = pmegridsize[1]
    pmegridsizez = pmegridsize[2]

    if amber:
        input_files_prms = """cwd                .
amber              yes
coordinates        ../nvt/end-nvt.pdb
parmfile           ../common/start.prmtop
paraTypeXplor      off"""

    else:
        input_files_prms = """cwd                .
coordinates         ../nvt/end-nvt.pdb
structure           ../common/start.psf"""


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
margin              5

# Integrator Parameters
timestep            2.0
rigidBonds          all
fullElectFrequency  2
stepspercycle       10

# PME (for full-system periodic electrostatics)
PME                 yes
PMEGridSizeX        %(pmegridsizex)i
PMEGridSizeY        %(pmegridsizey)i
PMEGridSizeZ        %(pmegridsizez)i

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

def write_md_config_file(config, nsteps=5000, outputfreq=5000, temperature=310.0, timestep=2.0, amber=True, extend=False, plumed=False, **kwargs):

    pmegridsize = config.pmegridsize

    pmegridsizex = pmegridsize[0]
    pmegridsizey = pmegridsize[1]
    pmegridsizez = pmegridsize[2]

    if plumed:
        plumed_prms = """
plumed on
plumedfile plumed.dat
"""
    else:
        plumed_prms = ""

    if extend:
        inputname= 'md'
    else:
        inputname = 'npt/npt'

    if amber:
        input_files_prms = """cwd                .
amber              yes
coordinates        npt/end-npt.pdb
parmfile           common/start.prmtop
paraTypeXplor      off"""

    else:
        input_files_prms = """cwd                .
coordinates         npt/end-npt.pdb
structure           common/start.psf"""


    with open('md.conf', 'w') as file:
        script ="""# Production run
%(plumed_prms)s
set temperature      %(temperature)s
set outputname       md
set nsteps           %(nsteps)s
set outputfreq       %(outputfreq)s

# input files prms
%(input_files_prms)s

# starting from Restart Files
set inputname      %(inputname)s
binCoordinates     $inputname.coor
binVelocities      $inputname.vel 
extendedSystem     $inputname.xsc

# output files parameters
outputName          $outputname
binaryoutput        yes
restartfreq         $outputfreq
dcdfreq             $outputfreq
outputEnergies      $nsteps

# Force-Field Parameters
exclude             scaled1-4
switching           on
switchdist          10
cutoff              12
outputPairlists     100
margin              5

# Integrator Parameters
timestep            %(timestep)s
rigidBonds          all
fullElectFrequency  2
stepspercycle       10

# PME (for full-system periodic electrostatics)
PME                 yes
PMEGridSizeX        %(pmegridsizex)i
PMEGridSizeY        %(pmegridsizey)i
PMEGridSizeZ        %(pmegridsizez)i

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
