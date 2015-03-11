ptraj ../common/start.prmtop ptraj_dcd_to_mdcrd
mkdir 02_MMPBSA_BE
cd 02_MMPBSA_BE
cp  /orc_lfs/scratch/khaled/Screening-03-Jan15-Jim/mm.in .
MMPBSA.py -O -i mm.in -o mm.out -sp ../../common/start.prmtop -cp ../complex.prmtop -rp ../target.prmtop -lp ../hit.prmtop -y ../run.mdcrd 
