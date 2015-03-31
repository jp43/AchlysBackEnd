#!/bin/bash

set -e

rm -rf pdbqt_r

for i in `seq 1 9`; do
  prepare_receptor4.py -r data/hERG-conformations_0$i.pdb
done

for i in `seq 10 45`; do
  prepare_receptor4.py -r data/hERG-conformations_$i.pdb
done

mkdir pdbqt_r
mv *.pdbqt pdbqt_r/
