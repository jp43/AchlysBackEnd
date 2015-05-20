import sys, os, os.path, random, time, csv, shutil, socket

# Function to run a shell command and return the output
def pipetext(cmd):
    pipe = os.popen(cmd)
    if pipe == None:
        print 'Pipe for command %s did not open' % cmd
        sys.exit()
    text = pipe.next()
    status = pipe.close()
    if status != None:
        print 'Command %s did not exit without errors' % cmd
        sys.exit()
    return text

# Function to count the structures in an SDF file
def count_structs(chem_filename):
    struct_count = 0
    in_mol = True
    in_header = True
    in_data = False
    header_line_num = 0
    HEADER_LINES = 4
    sdfile = open(sys.argv[1])
    for line in sdfile:
        line = line.rstrip()
        if in_mol:
            if in_header:
                header_line_num += 1
                if header_line_num == HEADER_LINES:
                    in_header = False
            elif line == 'M  END':
                in_mol = False
        else:
            if line.startswith('>'):
                in_data = True
            elif in_data:
                if line == '':
                    in_data = False
            elif line == '$$$$':
                struct_count += 1
                in_mol = True
                in_header = True
                header_line_num = 0
    sdfile.close()
    return struct_count

# Function to get the name of structure i in an SDF file
def get_struct_name(chem_filename, chem_i):
    chem_name = pipetext('babel -isdf -f %d -l %d %s -otxt 2>/dev/null' % 
            (chem_i, chem_i, chem_filename))
    chem_name = chem_name.strip()
    return chem_name

# Assign system specific variables
hostname = socket.gethostname()
if hostname == 'turtle.local':
    MGLTOOLS_PATH = '/Users/pwinter/Tools/mgltools'
    MGLTOOLS_UTIL_PATH = '/Users/pwinter/Tools/mgltools/MGLToolsPckgs/AutoDockTools/Utilities24'
    AUTOGRID_EXE = '/usr/local/bin/autogrid4'
    AUTODOCK_EXE = '/usr/local/bin/autodock4'
    AMBERHOME = '/Users/pwinter/Tools/amber14'
    AMBER_BIN = '/Users/pwinter/Tools/amber14/bin'
    PARAMDIR = '/Users/pwinter/Achlys/git/AchlysBackEnd/params'
    DATADIR = '/Users/pwinter/Achlys/git/AchlysBackEnd/data'
elif hostname == 'silence':
    MGLTOOLS_PATH = '/usr/local/mgltools'
    MGLTOOLS_UTIL_PATH = '/usr/local/mgltools/MGLToolsPckgs/AutoDockTools/Utilities24'
    AUTOGRID_EXE = '/usr/local/bin/autogrid4'
    AUTODOCK_EXE = '/usr/local/bin/autodock4'
    AMBERHOME = '/home/pwinter/amber14'
    AMBER_BIN = '/home/pwinter/amber14/bin'
    PARAMDIR = '/home/achlys/AchlysBackEnd/params'
    DATADIR = '/home/achlys/AchlysBackEnd/data'
elif hostname.startswith('bl220-c') or hostname in ['head01', 'head02']:
    MGLTOOLS_PATH = '/opt/mgltools/1.5.4'
    MGLTOOLS_UTIL_PATH = '/opt/mgltools/1.5.4/MGLToolsPckgs/AutoDockTools/Utilities24'
    AUTOGRID_EXE = '/opt/autodock/4.2.3/bin/autogrid4'
    AUTODOCK_EXE = '/opt/autodock/4.2.3/bin/autodock4'
    AMBERHOME = '/pmshare/amber/amber12-20120918'
    AMBER_BIN = '/pmshare/amber/amber12-20120918/bin'
    PARAMDIR = '/nfs/r510-2/pwinter/achlys2/AchlysBackEnd/params'
    DATADIR = '/nfs/r510-2/pwinter/achlys2/AchlysBackEnd/data'
else:
    print 'Unsupported system'
    sys.exit()

# Directorites and filenames
BASEDIR = os.getcwd()
WORKDIR = '%s/tox_work' % BASEDIR
PARAMFILE = 'quick_params.csv'
RECEP_NAME = 'hERG-conformations_%02d.pdb'
GPF = '%s/autodock/quick_grid.gpf' % PARAMDIR
DPF = '%s/autodock/quick_dock.dpf' % PARAMDIR

# Default parameters for toxicity prediction method
SEED = 754855
NUM_RECEPTORS = 10
DOCK_CENTER_X = 6.861
DOCK_CENTER_Y = 8.825
DOCK_CENTER_Z = 2.155
DOCK_BOX_X = 23.8
DOCK_BOX_Y = 23.8
DOCK_BOX_Z = 23.8
DOCK_SPACING = 0.238
DOCK_MAX_AFFINITY = 100#-6 #kcal/mol
DOCK_MIN_CLUSTER = 0.25
DOCK_MAX_HITS = 5
MD_TIME = 10000 #ps
MMPBSA_TIME = 5000 #ps
MMPBSA_STEP = 10 #ps
TOX_ENERGY_MAX = -25 #kcal/mol
TOX_DIST_MAX = 3.5 #angstroms
CRITICAL_X = 6.866
CRITICAL_Y = 8.825
CRITICAL_Z = 2.155

# Load parameters from parameter file
#param_file = open('%s/%s' % (PARAMDIR, PARAMFILE), 'rU')
#param_reader = csv.reader(param_file)
#for row in param_reader:
#    key = row[0]
#    value = float(row[1])
#    if key == 'SEED':
#        SEED = int(value)
#    elif key == 'NUM_RECEPTORS':
#        NUM_RECEPTORS = int(value)
#    elif key == 'DOCK_CENTER_X':
#        DOCK_CENTER_X = float(value)
#    elif key == 'DOCK_CENTER_Y':
#        DOCK_CENTER_Y = float(value)
#    elif key == 'DOCK_CENTER_Z':
#        DOCK_CENTER_Z = float(value)
#    elif key == 'DOCK_BOX_X':
#        DOCK_BOX_X = float(value)
#    elif key == 'DOCK_BOX_Y':
#        DOCK_BOX_Y = float(value)
#    elif key == 'DOCK_BOX_Z':
#        DOCK_BOX_Z = float(value)
#    elif key == 'DOCK_SPACING':
#        DOCK_SPACING = float(value)
#    elif key == 'DOCK_MAX_AFFINITY':
#        DOCK_MAX_AFFINITY = float(value)
#    elif key == 'DOCK_MIN_CLUSTER':
#        DOCK_MIN_CLUSTER = float(value)
#    elif key == 'DOCK_MAX_HITS':
#        DOCK_MAX_HITS = int(value)
#    elif key == 'MD_TIME':
#        MD_TIME = float(value)
#    elif key == 'MMPBSA_TIME':
#        MMPBSA_TIME = float(value)
#    elif key == 'MMPBSA_STEP':
#        MMPBSA_STEP = float(value)
#    elif key == 'TOX_ENERGY_MAX':
#        TOX_ENERGY_MAX = float(value)
#    elif key == 'TOX_DIST_MAX':
#        TOX_DIST_MAX = float(value)
#    elif key == 'CRITICAL_X':
#        CRITICAL_X = float(value)
#    elif key == 'CRITICAL_Y':
#        CRITICAL_Y = float(value)
#    elif key == 'CRITICAL_Z':
#        CRITICAL_Z = float(value)
#param_file.close()

# Initialize random number generator
random.seed(SEED)

# Check number of command line arguments provided
if len(sys.argv) != 3:
    print 'Usage: %s chem_filename out_filename' % (sys.argv[0])
    sys.exit()
    
# Assign command line arguments to variables
chem_path = sys.argv[1]
out_path = sys.argv[2]

# Check that the input file exists and the output file does not exist
if not os.path.isfile(chem_path):
    print 'File %s does not exist' % chem_path
    sys.exit()
if os.path.isfile(out_path):
    print 'File %s already exists' % out_path
    sys.exit()

# Create working directory
try:
    os.mkdir(WORKDIR)
except OSError:
    print 'Error creating directory %s' % WORKDIR
    sys.exit()

# Count the number of chemical structures
num_chem = count_structs(chem_path)

# Find the names of the chemical structures
lig_id_list = []
lig_name_dict = {}
for lig_id in xrange(0, num_chem):
    lig_id_list.append(lig_id)
    lig_name = get_struct_name(chem_path, lig_id + 1)
    lig_name_dict[lig_id] = lig_name

# Find the number of receptors and their paths
rec_id_list = []
rec_path_dict = {}
for rec_id in xrange(0, NUM_RECEPTORS):
    rec_id_list.append(rec_id)
    rec_filename = RECEP_NAME % (rec_id + 1)
    rec_path_dict[rec_id] = '%s/%s' % (DATADIR, rec_filename)

# Function to run an AutoDockTools script
def runadt(cmd):
    bash_script_filename = 'run_adt_python_script.sh'
    bash_script_template = '#!/bin/bash\nsource %s/bin/mglenv.sh\n%s/%s'
    if os.path.isfile(bash_script_filename):
        print 'File %s already exists' % bash_script_filename
        sys.exit()
    try:
        bash_script_file = open(bash_script_filename, 'w')
    except IOError:
        print 'Error opening %s' % bash_script_filename
        sys.exit()
    bash_script_file.write(bash_script_template % (MGLTOOLS_PATH, 
            MGLTOOLS_UTIL_PATH, cmd))
    bash_script_file.close()
    cmd_bash = 'bash %s >/dev/null' % bash_script_filename
    status = os.system(cmd_bash)
    if status != 0:
        print 'Command "%s" did not exit without errors' % cmd_bash
        sys.exit()
    try:
        os.remove(bash_script_filename)
    except OSError:
        print 'Error removing file %s' % bash_script_filename
        sys.exit()

def dock(lig_id, rec_id):
    
    # Convert ligand from SDF to PDB
    dock_work_dir = '%s/dock_lig%d_rec%d' % (WORKDIR, lig_id, rec_id)
    os.mkdir(dock_work_dir)
    os.chdir(dock_work_dir)
    os.system('babel -f%d -l%d -isdf %s -opdb %s 2>/dev/null' % 
            (lig_id + 1, lig_id + 1, '%s/chems.sdf' % BASEDIR, '%s/lig.pdb' % dock_work_dir))
    
    # Convert ligand from PDB to PDBQT
    runadt('prepare_ligand4.py -l %s -o %s' % 
            ('%s/lig.pdb' % dock_work_dir, '%s/lig.pdbqt' % dock_work_dir))
    
    # Convert receptor from PDB to PDBQT
    receptor_path = rec_path_dict[rec_id]
    runadt('prepare_receptor4.py -r %s -o %s' %
            (receptor_path, '%s/target.pdbqt' % dock_work_dir))
    
    # Create docking input files (.gpf & .dpf)
    #shutil.copyfile(GPF, '%s/grid.gpf' % dock_work_dir)
    #shutil.copyfile(DPF, '%s/dock.gpf' % dock_work_dir)
    npts_x = int(round(DOCK_BOX_X / DOCK_SPACING))
    npts_y = int(round(DOCK_BOX_Y / DOCK_SPACING))
    npts_z = int(round(DOCK_BOX_Z / DOCK_SPACING))
    runadt('prepare_gpf4.py -l lig.pdbqt -r target.pdbqt -o grid.gpf -p npts="%d,%d,%d" -p gridcenter="%.3f,%.3f,%.3f" -p spacing=%.3f' %
            (npts_x, npts_y, npts_z, DOCK_CENTER_X, DOCK_CENTER_Y, DOCK_CENTER_Z, DOCK_SPACING))
    #Fix the .gpf problem (needs spaces not commas )
    gpf_file = open('grid.gpf')
    gpf_fixed_file = open('gridfixed.gpf', 'w')
    for line in gpf_file:
        if line.startswith('npts') or line.startswith('gridcenter'):
            line = line.replace(',', ' ')
        gpf_fixed_file.write(line)
    gpf_file.close()
    gpf_fixed_file.close()
    os.system('mv gridfixed.gpf grid.gpf')
    runadt('prepare_dpf4.py -l lig.pdbqt -r target.pdbqt -o dock.dpf -p ga_num_generations=27 -p ga_num_evals=2500')
    
    # Run AutoGrid
    #os.system('%s -p %s -l grid.glg 2>/dev/null' % (AUTOGRID_EXE, GPF))
    
    # Run AutoDock
    #os.system('%s -p %s -l dock.dlg 2>/dev/null' % (AUTODOCK_EXE, DPF))
    
    #Get the best conformation
    #http://autodock.scripps.edu/faqs-help/faq/is-there-a-way-to-save-a-protein-ligand-complex-as-a-pdb-file-in-autodock
#    complex_file = open('complex.pdb', 'w')
#    receptor_file = open(receptor_path)
#    for line in receptor_file:
#        if line.startswith('ATOM') or line.startswith('HETATM') or line.startswith('TER'):
#            complex_file.write(line)
#        if line.startswith('ATOM') or line.startswith('HETATM'):
#            serial = int(line[6:11])
#    dock_dlg = open('dock.dlg')
#    atom_index = serial + 1
#    for line in dock_dlg:
#        line = line.strip()
#        if not line.startswith('DOCKED'):
#            continue
#        line = line[8:]
#        if line.startswith('TER'):
#            break
#        if not line.startswith('ATOM'):
#            continue
#        line = line[0:66]
#        line = 'HETATM' + line[6:]
#        line = line[0:21] + 'X' + line[22:]
#        line = '%s%6d%s' % (line[0:6], atom_index, line[11:])
#        complex_file.write('%s\n' % line)
#        atom_index += 1
#    complex_file.write('TER\n')
#    complex_file.write('END\n')
#    dock_dlg.close()
#    complex_file.close()
    #os.system('babel -ipdb %s -opdb %s 2>/dev/null' % ('%s/complex.pdb' % dock_work_dir, '%s/complex.pdb' % dock_work_dir))
            
    pose_path = '%s/complex.pdb' % dock_work_dir
    
    print 'Done dock for lig_id=%d rec_id=%d' % (lig_id, rec_id)

    affinity = random.random() * -10
    cluster_size = random.random()
    success = True
    return success, affinity, cluster_size, pose_path

def do_md(lig_id, rec_id, pose_path):
    
    #Create MD working directory
    md_work_dir = '%s/md_lig%d_rec%d' % (WORKDIR, lig_id, rec_id)
    os.mkdir(md_work_dir)
    os.chdir(md_work_dir)
    
    #Copy required files to MD directory
    shutil.copyfile('%s/amber/leap.in' % PARAMDIR, '%s/leap.in' % md_work_dir)
    shutil.copyfile('%s/namd/quick_min.conf' % PARAMDIR, '%s/min.conf' % md_work_dir)
    shutil.copyfile('%s/namd/quick_heat.conf' % PARAMDIR, '%s/heat.conf' % md_work_dir)
    shutil.copyfile('%s/namd/quick_equ.conf' % PARAMDIR, '%s/equ.conf' % md_work_dir)
    dock_work_dir = '%s/dock_lig%d_rec%d' % (WORKDIR, lig_id, rec_id)
    shutil.copyfile('%s/lig.pdb' % dock_work_dir, '%s/lig.pdb' % md_work_dir)
    #shutil.copyfile('%s/complex.pdb' % dock_work_dir, '%s/complex.pdb' % md_work_dir)
    
    #Prepare system for MD using AmberTools
#    os.system('export AMBERHOME=%s ; %s/antechamber -i lig.pdb -fi pdb -o lig.prepin -fo prepi -j 4  -s 2 -at gaff -c gas -du y -s 2 -pf y -nc 1' % (AMBERHOME, AMBER_BIN))
#    os.system('export AMBERHOME=%s ; %s/parmchk -i lig.prepin -f prepi -o lig.frcmod' % (AMBERHOME, AMBER_BIN))
#    os.system('export AMBERHOME=%s ; %s/tleap -f leap.in' % (AMBERHOME, AMBER_BIN))
    
    #Create ref-heat file
#    complex_file = open('complex.pdb')
#    refheat_file = open('ref-heat.pdb', 'w')
#    for line in complex_file:
#        if line.startswith('ATOM'):
#            if line[12:16].strip() in ['CA', 'N', 'O']:
#                line = line[0:30] + '%8.3f' % 50.0 + line[38:]
#            else:
#                line = line[0:30] + '%8.3f' % 0.0 + line[38:]
#            line = line[0:38] + '%8.3f' % 0.0 + '%8.3f' % 0.0 + line[55:]
#        refheat_file.write(line)
#    complex_file.close()
#    refheat_file.close()

    #Do MD with namd
    #os.system('export LD_LIBRARY_PATH=/opt/openmpi/1.6/intel/lib:/nfs/r510-2/opt/intel/composer_xe_2013.3.163/compiler/lib/intel64:/nfs/r510-2/opt/intel/composer_xe_2013.3.163/mpirt/lib/intel64:/nfs/r510-2/opt/intel/composer_xe_2013.3.163/ipp/../compiler/lib/intel64:/nfs/r510-2/opt/intel/composer_xe_2013.3.163/ipp/lib/intel64:/opt/intel/mic/coi/host-linux-release/lib:/opt/intel/mic/myo/lib:/nfs/r510-2/opt/intel/composer_xe_2013.3.163/compiler/lib/intel64:/nfs/r510-2/opt/intel/composer_xe_2013.3.163/mkl/lib/intel64:/nfs/r510-2/opt/intel/composer_xe_2013.3.163/tbb/lib/intel64/gcc4.4 ; /opt/openmpi/1.6/intel/bin/mpirun /opt/namd/2.9/bin/namd2 min.conf')

    print 'Done MD for lig_id=%d rec_id=%d' % (lig_id, rec_id)

    traj_path = '/dev/null'
    success = True
    return success, traj_path

def do_mmpbsa(traj_id):
    energy = random.uniform(-60,-12)
    conformation = '/dev/null'
    success = True
    return success, energy, conformation

def get_distance(conformation):
    return random.uniform(1.2,4.2)

    cmd = 'babel -f 1 -l 1 -ipdbqt %s_out.pdbqt -opdb %s_out.pdb 2>/dev/null' \
            % (chem_name, chem_name)
    status = os.system(cmd)
    if status != 0:
        print 'Command "%s" did not exit without errors' % cmd
        sys.exit()
    try:
        pdbout = open('%s_out.pdb' % chem_name)
    except IOError:
        print 'Error opening %s' % ('%s_out.pdb' % chem_name)
        sys.exit()
    xs = []
    ys = []
    zs = []
    for line in pdbout:
        if line.startswith('ATOM') or line.startswith('HETATM'):
            xs.append(float(line[30:38]))
            ys.append(float(line[38:46]))
            zs.append(float(line[46:54]))
    pdbout.close()
    xd = numpy.mean(xs) - CRITICAL_X
    yd = numpy.mean(ys) - CRITICAL_Y
    zd = numpy.mean(zs) - CRITICAL_Z
    distance = math.sqrt(xd * xd + yd * yd + zd * zd)
    return distance

# Khaled's Toxicity Prediction Method
def do_prediction(lig_id, rec_id_list):

    # STEP 1: Dock
    dock_result_list = []
    for rec_id in rec_id_list:
        success, affinity, cluster_size, pose_path = dock(lig_id, rec_id)
        if not success:
            prediction_dict[lig_id] = 'DOCK_FAIL'
            continue
        dock_result_list.append((rec_id, affinity, cluster_size, pose_path))

    # STEP 2: Rank docking results
    dock_hit_list = []
    dock_result_list.sort(key=lambda x:x[1])
    result_index = 0
    hit_count = 0
    while result_index < len(dock_result_list) and hit_count < DOCK_MAX_HITS:
        rec_id, affinity, cluster_size, pose_path = dock_result_list[result_index]
        if affinity < DOCK_MAX_AFFINITY and cluster_size > DOCK_MIN_CLUSTER:
            dock_hit_list.append((rec_id, pose_path))
            hit_count += 1
        result_index += 1

    # STEP 3: MD
    md_result_list = []
    for hit in dock_hit_list:
        rec_id, pose_path = hit
        success, traj_path = do_md(lig_id, rec_id, pose_path)
        if not success:
            prediction_dict[lig_id] = 'MD_FAIL'
            continue
        md_result_list.append((traj_path,))

    # STEP 4: MMPBSA
    mmpbsa_result_list = []
    for md_result in md_result_list:
        traj_path = md_result[0]
        success, energy, conformation = do_mmpbsa(traj_path)
        if not success:
            prediction_dict[lig_id] = 'MMPBSA_FAIL'
            continue
        mmpbsa_result_list.append((energy, conformation))
    mmpbsa_result_list.sort(key=lambda x:x[1])

    # STEP 5: Calculate energies and distances
    energy, conformation = mmpbsa_result_list[0]
    distance = get_distance(conformation)

    # STEP 6: Assign blocker prediction
    if energy < TOX_ENERGY_MAX and distance < TOX_DIST_MAX:
        prediction = 'Blocker'
    else:
        prediction = 'Non-blocker'
        
    return (energy, distance, prediction)

# Write final results to a file
def write_results(final_result_list, out_filename):
    if os.path.isfile(out_filename):
        print 'File %s already exists' % out_filename
        sys.exit()
    try:
        outfile = open(out_filename, 'w')
    except IOError:
        print 'Error opening %s' % out_filename
        sys.exit()
    outfile.write('Chemical Name,Energy,Distance,Prediction,STATUS\n')
    for result in final_result_list:
        lig_id, energy, distance, prediction = result
        lig_name = lig_name_dict[lig_id]
        outfile.write('%s,%.1f,%.1f,%s,DONE\n' % (lig_name, energy, distance, prediction))
    outfile.close()

# Predict toxicity for each ligand
start = time.clock() 
final_result_list = []
for lig_id in lig_id_list:
    energy, distance, prediction = do_prediction(lig_id, rec_id_list)
    final_result_list.append((lig_id, energy, distance, prediction))
elapsed = time.clock()
elapsed = elapsed - start
print 'wall_time=%.2f sec' % elapsed

os.chdir(BASEDIR)

# Output blocker predictions
write_results(final_result_list, out_path)

# Write DONE file
done_path = '%s/DONE' % (BASEDIR)
os.system('touch %s' % done_path)

