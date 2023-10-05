#!/bin/bash

# target directory
directory="/home/brussell/xtalk/run24"

# check if the target is not a directory
if [ ! -d "$directory" ]; then
    exit 1
fi

p="packet"

# loop through files in the target directory
for file in "$directory"/*; do
    if [ -f "$file" ]; then
	echo "$file"
	echo "${file}"
	echo "${#file}"
	prefix="${file:0:27}"
	echo "${prefix}"
	suffix="${file:27:89}"
	suffix="${suffix//raw}"
	echo "${suffix}"
	nname="$prefix$p$suffix"
	echo "${nname}"
	python3 /home/brussell/larpix-control/scripts/convert_rawhdf5_to_hdf5.py --input_filename $file --output_filename $nname
    fi
done
