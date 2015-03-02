import os, sys, random, time, csv

# Init random number generator
SEED = 754855
random.seed(SEED)

# Parameters for toxicity prediction method
DOCK_MAX_AFFINITY = 100#-6 #kcal/mol
DOCK_MIN_CLUSTER = 0.25
DOCK_MAX_HITS = 7
MD_TIME = 10000 #ps
MMPBSA_TIME = 5000 #ps
MMPBSA_STEP = 10 #ps
TOX_ENERGY_MAX = -25 #kcal/mol
TOX_DIST_MAX = 3.5 #angstroms
CRITICAL_X = 6.866
CRITICAL_Y = 8.825
CRITICAL_Z = 2.155

# Paths
# Working directory and working filenames
DATADIR = 'data'
WORKDIR = 'tox_work'
PARAMDIR = 'params'

# Load parameters from parameter file
param_file = open(PARAMDIR + 'params.csv')
param_reader = csv.reader(param_file, 'rU')
for row in param_reader:
    key = row[0]
    value = float(row[1])
    if key == 'SEED':
        SEED = value
    elif key == 'DOCK_MAX_AFFINITY':
        DOCK_MAX_AFFINITY = value
    elif key == 'DOCK_MIN_CLUSTER':
        DOCK_MIN_CLUSTER = value
    elif key == 'DOCK_MAX_HITS':
        DOCK_MAX_HITS = value
    elif key == 'MD_TIME':
        MD_TIME = value
    elif key == 'MMPBSA_TIME':
        MMPBSA_TIME = value
    elif key == 'MMPBSA_STEP':
        MMPBSA_STEP = value
    elif key == 'TOX_ENERGY_MAX':
        TOX_ENERGY_MAX = value
    elif key == 'TOX_DIST_MAX':
        TOX_DIST_MAX = value
    elif key == 'CRITICAL_X':
        CRITICAL_X = value
    elif key == 'CRITICAL_Y':
        CRITICAL_Y = value
    elif key == 'CRITICAL_Z':
        CRITICAL_Z = value
param_file.close()

# Function to run a shell command and return the output
def pipetext(cmd):
    pipe = os.popen(cmd)
    if pipe == None:
        print 'Pipe from command %s did not open' % cmd
        sys.exit()
    text = pipe.next()
    status = pipe.close()
    if status != None:
        print 'Command "%s" did not exit without errors' % cmd
        sys.exit()
    return text

def dock(lig_id, rec_id):
    affinity = random.random() * -10
    cluster_size = random.random()
    pose_path = '/dev/null'
    success = True
    return success, affinity, cluster_size, pose_path

def do_md(lig_id, rec_id):
    traj_path = '/dev/null'
    success = True
    return success, traj_path

def do_mmpbsa(traj_id):
    energy = random.random() * -100
    conformation = '/dev/null'
    success = True
    return success, energy, conformation

# Function to count the structures in an SDF file
def count_structs(chem_filename):
    return int(pipetext("grep '$$$$' %s | wc -l" % chem_filename).strip())

# Function to get the name of structure i in an SDF file
def get_struct_name(chem_filename, chem_i):
    chem_name = pipetext('babel -isdf -f %d -l %d %s -otxt 2>/dev/null' % 
            (chem_i, chem_i, chem_filename))
    chem_name = chem_name.strip()
    return chem_name

def calc_distance(conformation):
    return random.random() * 10


def get_distance(chem_name):
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
    outfile.write('Chemical Name,Energy,Distance,Prediction\n')
    for result in final_result_list:
        lig_id, energy, distance, prediction = result
        lig_name = lig_name_dict[lig_id]
        outfile.write('%s,%.1f,%.1f,%s\n' % (lig_name, energy, distance, prediction))
    outfile.close()


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
        success, traj_path = do_md(rec_id, pose_path)
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
    distance = calc_distance(conformation)

    # STEP 6: Assign blocker prediction
    if energy < TOX_ENERGY_MAX and distance < TOX_DIST_MAX:
        prediction = 'Blocker'
    else:
        prediction = 'Non-blocker'
        
    return (energy, distance, prediction)




# Setup

# Check that required command line arguments are provided
if len(sys.argv) != 3:
    print 'Usage: %s chem_filename out_filename' % (sys.argv[0])
    sys.exit()

# Read the command line arguments
chem_path = sys.argv[1]
out_path = sys.argv[2]

# Check that the input file exists and the output file does not exist
if not os.path.isfile(chem_path):
    print 'File %s does not exist' % chem_path
    sys.exit()
if os.path.isfile(out_path):
    print 'File %s already exists' % out_path
    sys.exit()

# Find the number of chemical structures
num_chem = count_structs(chem_path)

# Create the working directory
#cmd = 'rm -rf %s' % WORKDIR
#status = os.system(cmd)
#if status != 0:
#    print 'Command "%s" did not exit without errors' % cmd
#    sys.exit()
try:
    os.mkdir(WORKDIR)
except OSError:
    print 'Error creating directory %s' % WORKDIR
    sys.exit()

# Find the number and names of chemical structures
lig_id_list = []
lig_path_dict = {}
lig_name_dict = {}
num_chem = count_structs(chem_path)
for lig_id in xrange(0, num_chem):
    lig_id_list.append(lig_id)
    lig_name = get_struct_name(chem_path, lig_id + 1)
    lig_name_dict[lig_id] = lig_name
    lig_path_dict[lig_id] = '/dev/null'

rec_id_list = []
rec_path_dict = {}
for rec_id in xrange(0, 3):
    rec_id_list.append(rec_id)
    rec_path_dict[rec_id] = 'data/hERG-conformations_%d.pdb' % rec_id

start = time.clock() 

# Predict toxicity for each ligand
final_result_list = []
for lig_id in lig_id_list:
    energy, distance, prediction = do_prediction(lig_id, rec_id_list)
    final_result_list.append((lig_id, energy, distance, prediction))

elapsed = time.clock()
elapsed = elapsed - start
print 'elapsed=%.2f sec' % elapsed

# Output blocker predictions
write_results(final_result_list, out_path)



