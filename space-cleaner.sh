#!/bin/bash

dir="/mnt/dietpi_userdata/album_art/"
delete_max_fraction=0.1
delete_max_count=500

used=$(df / | tail -1 | awk '{ for(i=1; i<=NF; i++) if($i ~ /%/) { print $i; break; } }' | tr -d '%')
if [[ "$used" -lt 80 ]] ; then
	echo "Free space ${used}%, not doing anything"
	exit 0
fi

total_count=$(ls $dir | wc -l)
max_count_to_delete=$(echo "scale=0; ($total_count * $delete_max_fraction)/1" | bc -l)
count_to_delete=$(( $max_count_to_delete > $delete_max_count ? $delete_max_count : $max_count_to_delete ))

ls -t $dira/album_art_*.jpg | tail -n $count_to_delete | xargs rm -rf
echo "Freed space by deleting $count_to_delete older album art images"
