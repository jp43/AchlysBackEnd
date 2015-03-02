import sys, os, os.path, math, numpy

# Paths to tools
MGLTOOLS_PATH = '/Users/pwinter/Tools/mgltools'
MGLTOOLS_UTIL_PATH = MGLTOOLS_PATH + '/MGLToolsPckgs/AutoDockTools/Utilities24'

# Working directory and working filenames
WORKDIR = 'work'
VINACONFIG = 'config.vina'
VINAOUT = 'out.vina'

# Vina config file template
VINACONFIG_TEMPLATE = """receptor = %sqt
ligand = %s.pdbqt
center_x = %f
center_y = %f
center_z = %f
size_x = %f
size_y = %f
size_z = %f
exhaustiveness = %d
seed = %d
cpu = 4
num_modes = 10
"""


# Parameters for Vina
EFFORT = 8
SEED = 107

# Path to data directory
# This stores data that will be reused between runs
DATADIR = 'data'

# Receptor and binding site definitions
RECEPTOR = 'hERG-conformations_1.pdb'
RECEPTOR_PDBQT = RECEPTOR + 'qt'
RECEPTOR_PATH = DATADIR + '/' + RECEPTOR
CENTER_X = 6.866
CENTER_Y = 8.825
CENTER_Z = 2.155
SIZE_X = 30.0
SIZE_Y = 30.0
SIZE_Z = 30.0

# Tox prediction parameters
AFFINITY_THRESHOLD = -5.0
DISTANCE_THRESHOLD = 5.0
CRITICAL_X = 6.866
CRITICAL_Y = 8.825
CRITICAL_Z = 2.155

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

# Function for hERG blocking computation
def predict_blocker(affinity, distance):
    if affinity < AFFINITY_THRESHOLD and distance < DISTANCE_THRESHOLD:
        return 'Probable'
    else:
        return 'Improbable'

# Function to count the structures in an SDF file
def count_structs(chem_filename):
    return int(pipetext("grep '$$$$' %s | wc -l" % chem_filename).strip())

# Function to get the name of structure i in an SDF file
def get_struct_name(chem_filename, chem_i):
    chem_name = pipetext('babel -isdf -f %d -l %d %s -otxt 2>/dev/null' % 
            (chem_i, chem_i, chem_filename))
    chem_name = chem_name.strip()
    return chem_name

# Function to get the affinity from a vina output file
def get_affinity(vinaout_filename):
    try:
        vinaout = open(vinaout_filename)
    except IOError:
        print 'Error opening %s' % vinaout_filename
        sys.exit()
    affinity = 999.0
    for line in vinaout:
        if line.startswith('   1'):
            affinity = float(line.split()[1].strip())
            break
    vinaout.close()
    return affinity

# Function to get the distance from a vina pdbqt output file
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

# Function to write results to a file
def write_results(results, out_filename):
    if os.path.isfile(out_filename):
        print 'File %s already exists' % out_filename
        sys.exit()
    try:
        outfile = open(out_filename, 'w')
    except IOError:
        print 'Error opening %s' % out_filename
        sys.exit()
    outfile.write('Chemical Name,Affinity,Distance,hERG Blocker\n')
    for chem_name in results:
        affinity, distance, prediction = results[chem_name]
        outfile.write('%s,%.1f,%.1f,%s\n' % 
                (chem_name, affinity, distance, prediction))
    outfile.close()


# MAIN PROGRAM CODE STARTS HERE

# Check that required command line arguments are provided
if len(sys.argv) != 3:
    print 'Usage: %s chem_filename out_filename' % (sys.argv[0])
    sys.exit()

# Read the command line arguments
chem_filename = sys.argv[1]
out_filename = sys.argv[2]

# Check that the input file exists and the output file does not exist
if not os.path.isfile(chem_filename):
    print 'File %s does not exist' % chem_filename
    sys.exit()
if os.path.isfile(out_filename):
    print 'File %s already exists' % out_filename
    sys.exit()

# Find the number of chemical structures
num_chem = count_structs(chem_filename)

# Create the working directory
cmd = 'rm -rf %s' % WORKDIR
status = os.system(cmd)
if status != 0:
    print 'Command "%s" did not exit without errors' % cmd
    sys.exit()

try:
    os.mkdir(WORKDIR)
except OSError:
    print 'Error creating directory %s' % WORKDIR
    sys.exit()

# Prepare the receptor
runadt('prepare_receptor4.py -r %s -o %s/%sqt' %
        (RECEPTOR_PATH, WORKDIR, RECEPTOR))

# Dict for storing the results
chems = []
results = {}

# Iterate over each ligand
for chem_i in xrange(1, num_chem + 1):

    # Create work dir for this ligand and copy the receptor to it
    workdir = '%s/%d' % (WORKDIR, chem_i)
    try:
        os.mkdir(workdir)
    except OSError:
        print 'Error creating directory %s' % workdir
        sys.exit()
    cmd = 'cp %s/%sqt %s/%d/%sqt' % (WORKDIR, RECEPTOR, WORKDIR, chem_i, 
            RECEPTOR)
    status = os.system(cmd)
    if status != 0:
        print 'Command "%s" did not exit without errors' % cmd
        sys.exit()
            
    # Find the name of the current ligand
    chem_name = get_struct_name(chem_filename, chem_i)
    chems.append(chem_name)

    # Prepare the ligand
    cmd = 'babel -isdf -f %d -l %d %s -opdb %s/%d/%s.pdb 2>/dev/null' % \
            (chem_i, chem_i, chem_filename, WORKDIR, chem_i, chem_name)
    status = os.system(cmd)
    if status != 0:
        print 'Command "%s" did not exit without errors' % cmd
        sys.exit()
    runadt('prepare_ligand4.py -l %s/%d/%s.pdb -o %s/%d/%s.pdbqt' % 
            (WORKDIR, chem_i, chem_name, WORKDIR, chem_i, chem_name))
    
    # STEP 1: DOCKING

    # Create the Vina input file
    vinaconfig_filename = '%s/%d/%s' % (WORKDIR, chem_i, VINACONFIG)
    if os.path.isfile(vinaconfig_filename):
        print 'File %s already exists' % vinaconfig_filename
        sys.exit()
    try:
        config_file = open(vinaconfig_filename, 'w')
    except:
        print 'Error opening %s' % vinaconfig_filename
        sys.exit()
    config_file.write(VINACONFIG_TEMPLATE % (RECEPTOR, chem_name, CENTER_X, 
            CENTER_Y, CENTER_Z, SIZE_X, SIZE_Y, SIZE_Z, EFFORT, SEED))
    config_file.close()
    
    # Run Vina
    os.chdir('%s/%d' % (WORKDIR, chem_i))
    cmd = 'vina --config %s >%s\n' % (VINACONFIG, VINAOUT)
    status = os.system(cmd)
    if status != 0:
        print 'Command "%s" did not exit without errors' % cmd
        sys.exit()
    
    # Read the Vina results, get the affinity
    affinity = get_affinity(VINAOUT)
    
    # Read the Vina pose, get the distance
    distance = get_distance(chem_name)
    
    # Predict hERG blocking
    prediction = predict_blocker(affinity, distance)
    
    # Store the results
    results[chem_name] = (affinity, distance, prediction)

    # Return to the initial directory
    os.chdir('../..')


# Write the results report
write_results(results, out_filename)

