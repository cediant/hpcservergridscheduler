#!/bin/bash

rm file.out

while read A; do
  [ $A == "}}" ] && break
  echo $A 
done >> file.out

sed -i -e '/{/d' file.out

cp AsianOption.in AsianOption.m
sed -i '/%PATTERN/r file.out' AsianOption.m

RESULT=$(octave --silent AsianOption.m)
PARSE=$(echo ${RESULT} | sed 's/=//g')

echo "{{ $PARSE }}"
