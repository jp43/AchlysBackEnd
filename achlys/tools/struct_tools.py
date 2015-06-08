import os

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

def count_structs_smi(chem_filename):
    smifile = open(chem_filename)
    struct_count = 0
    for line in smifile:
        line = line.strip()
        if line != '':
            struct_count += 1
    smifile.close()
    return struct_count

def count_structs(chem_filename):
    if chem_filename.endswith('.sdf'):
        return count_structs_sdf(chem_filename)
    elif chem_filename.endswith('.smi') or chem_filename.endswith('.txt'):
        return count_structs_smi(chem_filename)
    else:
        return 0

def get_chem_names(chem_lib_path):
    cmd = 'babel -isdf %s -otxt' % chem_lib_path
    pipe = os.popen(cmd)
    if pipe == None:
        return []
    chem_name_list = []
    text_list = pipe.readlines()
    for text in text_list:
        chem_name_list.append(text.strip())
    return chem_name_list
