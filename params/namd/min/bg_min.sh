#!/bin/sh
# @ job_name           = test
# @ job_type           = bluegene
# @ comment            = "BGQ Job By Size"
# @ error              = $(job_name).$(Host).$(jobid).err
# @ output             = $(job_name).$(Host).$(jobid).out
# @ bg_size            = 64
#@ wall_clock_limit   = 00:10:00
# @ bg_connectivity    = Torus
# @ step_name = step186
# @ queue
# Launch all BGQ jobs using runjob
module load namd
export namd2=/scinet/bgq/src/namd/NAMD_2.9_Source/BlueGeneQ-xlC-smp-qp/namd2        
runjob --np 1024 --ranks-per-node=16 --cwd=/gpfs/scratch/b/barakat/barakat/Screening-03-Jan15-Jim/Complexes/A_target_0_rank_5/min : /scinet/bgq/src/namd/NAMD_2.9_Source/BlueGeneQ-xlC-smp-qp/namd2 min.conf
