#!/bin/bash

echo "["
df "$@" | sed 1d | awk '{if (NR!=1) {printf ",\n"};printf "  { \"size\": "$2", \"used\": "$3", \"available\": "$4", \"path\": \""$6"\"}";}'
echo
echo "]"
