#!/bin/sh
antechamber  -i hit.pdb -fi pdb -o hit.prepin -fo prepi -j 4  -s 2 -at gaff -c bcc -du y -s 2 -pf y -nc 1
parmchk -i hit.prepin -f prepi -o hit.frcmod
tleap -f leap.in
