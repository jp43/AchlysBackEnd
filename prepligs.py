import sys, os, shutil

# Function to count the structures in an SDF file
def count_structs_sdf(chem_filename):
    struct_count = 0
    in_mol = True
    in_header = True
    in_data = False
    header_line_num = 0
    HEADER_LINES = 4
    sdfile = open(chem_filename)
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


def do_prep_lig_sdf(chem_path):
    processed_chem_path = 'processed.sdf'
    os.system('babel -isdf %s -ch --gen3D -osdf %s' % (chem_path, processed_chem_path))
    return processed_chem_path


def do_prep_lig_smi(chem_path):
    processed_chem_path = 'processed.sdf'
    os.system('babel -ismi %s -ch --gen3D -osdf %s' % (chem_path, processed_chem_path))
    return processed_chem_path


chem_path = sys.argv[1]

# Prepare chemical input file

if chem_path.endswith('.sdf'):

    chem_path = do_prep_lig_sdf(chem_path)

elif chem_path.endswith('.smi') or chem_path.endswith('.txt'):

    chem_path = do_prep_lig_smi(chem_path)

else:

    print 'Unknown chemical file format'
    sys.exit()


# Output PDB files

num_structs = count_structs_sdf('processed.sdf')

shutil.copy('processed.sdf', 'chems.sdf')

os.system('mkdir pdb')

for i in xrange(0, num_structs):
    os.system('babel -isdf processed.sdf -f%d -l%d -opdb pdb/chem%d.pdb' % (i+1, i+1, i))

# Output PNG files

#os.system('mkdir png')
#
#for i in xrange(0, num_structs):
#    os.system('/pmshare/apps/openbabel-2.3.2/bin/babel -isdf processed.sdf -f%d -l%d -opng png/chem%d.png' % (i+1, i+1, i))


