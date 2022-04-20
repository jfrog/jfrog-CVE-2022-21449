#!/bin/bash


if [[ $(which zipgrep) ]]; then


if [ $# -ne 1 ]; 
    then echo "usage: cve__2022_21449.sh root_folder"
    exit
fi;

shopt -s globstar
for x in $1/**/*.jar; do
    if [[ $(zipgrep withECDSA $x 2>/dev/null) ]]; then
      echo $x "may use ECDSA - may be vulnerable";
    fi;
done

exit

fi;

echo "Please install zipgrep (unzip package in Debian)"


