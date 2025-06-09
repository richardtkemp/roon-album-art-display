#!/bin/bash

URL=https://hc-ping.com/aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa
confirm="curl -s -X POST --data"

if [[ "$1" == "good" ]] ; then
        ${confirm} "$2" "${URL}"
else
        ${confirm} "$2" "${URL}/fail"
fi

