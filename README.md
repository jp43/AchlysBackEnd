# hERG Mode-of-Binding (MOB) program

The **hERG MOB** program is used to estimate the most probable binding mode and binding 
energy of compounds regarding the Human ether-a-go-go-related gene (hERG) potassium 
channel. The software uses a combination of docking programs, molecular dynamics (MD) 
simulations, Poisson Boltzmann Surface Area (PBSA) and Generalized Born Surface Area 
(GBSA) to provide the best predictions about how your compounds bind to the channel.

The **hERG MOB** package includes two executables:

* **startjob** which is used *once* to initiate the job
  
* **checkjob** which should be used periodically after the *startjob* command has been run
to go through all the steps of the program 

## Quick overview

### The *startjob* command

Running *startjob* will initiate the hERG MOB program. Typing *startjob -h* on a terminal
will provide information about the input files needed to run the command.

```
startjob -h
usage: startjob [-h] -l [INPUT_FILES_L [INPUT_FILES_L ...]]
                [-r [INPUT_FILES_R [INPUT_FILES_R ...]]] -f CONFIG_FILE

Run StartJob...

optional arguments:
  -h, --help            show this help message and exit
  -l [INPUT_FILES_L [INPUT_FILES_L ...]]
                        Ligand structure file(s): .sdf, .smi
  -r [INPUT_FILES_R [INPUT_FILES_R ...]]
                        Receptor structure file(s): .pdb
  -f CONFIG_FILE        Config file with parameters
```

*  The ligand input files (-l flag) should contain exactly one structure each. In case 
multiple structures need to be investigated, multiple files should be provided. Only .sdf 
and .smi formats are supported. A combination of .sdf and .smi files may also be specified
as inputs.

* Files containing the protein structures (-r flag) should be of .pdb format but are
not mandatory. By default, the program will use eight representative structures of the hERG
ion channel generated from previous published work (for more information, see the following 
[link] (https://www.ncbi.nlm.nih.gov/pubmed/25127758))

* The configuration file (-f flag) includes all the parameters used all along the execution
of the hERG MOB program and should be of .ini format. An example of contents that can be
found in the configuration file is:

```
[DOCKING]
program = autodock, vina, dock
rescoring = yes
minimize = yes
cleanup = yes

[RESCORING]
program = autodock, vina

[AUTODOCK]
ga_run = 20
spacing = 0.4

[VINA]
num_modes = 20

[DOCK]
nposes = 20

[SITE]
center = 3.966, 8.683, 11.093
boxsize = 30.0, 30.0, 30.0

[NAMD]
;temperature
temperature = 310.0
;parameters for minimization
nstepsmin = 20000
;parameters for NVT
nstepsnvt = 1000
nrunsnvt = 50
;parameters for NPT
nstepsnpt = 50000
;parameters for MD
nsteps = 1000000
outputfreq = 5000
```

* What startjob does: it creates a directory named job_XXXXXXXX where XXXXXXXX is a random
combination of 8 letters or numbers that stands for the job ID. For each ligand file
specified via the startjob command (-l flag), a folder named ligY -- where Y is the
number of the ligand as it was passed through the startjob command -- is created within the
job directory which includes the following items:

	- a file called ligand.info containing information about the compound: its original
name as specified in the original ligand file (.sdf and .smi), and the location (absolute 
path) of the file.

	- a file called step.out specifying which step of the **hERG MOB** algorithm is being
currently performed. After the startjob command has been run, the contents of every file 
step.out file should be the same, i.e,

```
start step 1 (docking)
```

meaning that the first step (docking) is about to start but is not yet running. 
Running the docking step and the next steps is performed by running the checkjob command 
(see below). There are 4 steps overall in the **hERG MOB** algorithm as listed in the 
section "Workflow". Each step is either in *start*, *running*, *error* or *done* state.


Besides creating all the required folders, executing *startjob* will run the ligprep 
command to generate all the possible 3D protonated structures of each compound. Assuming 
the original input ligand file is *ligand.sdf*, the ligprep command will look like:

```
ligprep -WAIT -ph 7.0 -pht 2.0 -i 2 -s 8 -t 4 -isd ligand.sdf -omae ligand.mae
```

The ligand.mae (Maestro file) is then converted to the .mol2 format. The partial charges
are assigned by using the antechamber program available within the AMBER package. The 
gasteiger method is used.


### The *checkjob* command

*checkjob* should be used to run any step of the **hERG MOB** algorithm. *checkjob* will
first scan the step.out file of every compound in order to determine its current status 
and decide which step should be performed. Whenever a given step needs to be run, executing 
*checkjob* will submit specific scripts to the job scheduler of the corresponding remote 
machine (see list of remote machine used for every step in the **Workflow** section). For 
that reason, the *checkjob* command should finish rapidly (no more than a few minutes). 
Depending on the new step and new status of each compound, the corresponding step.out files 
are updated at the end of the *checkjob*.

Unless errors are identified, *checkjob* needs to be run periodically until the entire
workflow of the **hERG MOB** algorithm has completed.

Only the job ID should be provided as an argument of the *checkjob* command as is noticed 
when typing *checkjob -h* on a terminal:

```
checkjob -h
usage: checkjob [-h] --id JOBID

Run CheckJob...

optional arguments:
  -h, --help  show this help message and exit
  --id JOBID  Job ID 
  
```

As the final step (i.e., mmpbsa) has finished normally, executing the *checkjob* command
will create two folders within the corresponding lig directory, i.e., *mmpbsa* and *mmgbsa*. 
Those folders contain the best poses as predicted by the PBSA (pbsa/pbsa.pdb) and the GBSA 
methods (pbsa/pbsa.pdb) as well as the corresponding binding energies (pbsa/pbsa.out for 
PBSA and gbsa/gbsa.out for GBSA).

## Workflow


* **Step 0 Preparation (performed by executing the startjob command)**:

	- generation of 3D structures 

* **Step 1 Docking**:

  1\. Docking

		- Autodock, Vina and DOCK6 are used (~ 20 poses generated per software)
       
		- Same binding box as Khaled's

  2\. Minimization
   
		- minimization of the poses with AMBER
       
		- minimization is performed in-vacuo by restraining the protein atoms
       
		- the partial charges obtained at the end of the docking procedure are kept for 
		the minimization

  3\. Rescoring
   
		- Autodock and Vina scores are computed/recomputed for each pose
       
		- the scores are rescaled in order to have unit variance and zero mean
       
		- an averaged score is computed S = (S_autodock + S_vina)/2 for each pose
       

* **Step 2 Startup (fast)**

	1. Clustering analysis
   
		- the minimized poses (point 2 of the docking step) are clustered using a distance 
		cutoff of 2.0 A.
       
		- for each cluster generated, a score is computed based on its population, the best
		average score S (see rescoring section above) and the number of softwares involved. 
		N.B.: This score was reported to predict 72% of correct poses for a set 194 
		complexes.
       
		- the representative poses of the best five clusters are kept for the next step

	2. Preparation of the selected poses for MD

		- The antechamber and leap programs of the AMBER package are used
       
		- The corresponding structures are set in a box and solvated. Na+ and Cl- ions are 
		added (with concentration 0.15M) making sure the system is neutralized.
       

* **Step 3 Molecular Dynamics**:

	1. The whole MD workflow is performed using NAMD from the prepared structures of the
	previous step
    
	2. Minimization (40ps)
    
	3. NVT equilibration (100ps), the temperature is gradually increased to 310.K

	4. NPT equilibration (100ps), the pressure is set 1bar
    
	5. MD production run (2ns), a trajectory of 200 frames, saving one frame every 5000 
	steps, is generated.
    

* Step 4 PBSA/GBSA:

    1. Preparation
    
       - the files required for MMPBSA are generated using the ante-MMPBSA tool available 
    within the AMBER package.

    2. PBSA/GBSA
    

### List of remote machines used for every step

- step 0 Preparation (Local machine)

- step 1 docking (Pharmamatrix)

- step 2 startup (Pharmamatrix)

- step 3 md (BGQ)

- step 4 mmpbsa (Pharmamatrix)
