#!/bin/bash

ICEGRID_HOME=/home/executor
PYTHONPATH=$ICEGRID_HOME/Ice/usr/lib64/python2.4/site-packages/Ice/:$ICEGRID_HOME/Ice/python2.4/lib/python2.4/ 
LD_LIBRARY_PATH=$ICEGRID_HOME/Ice/usr/lib64/ 

export PYTHONPATH LD_LIBRARY_PATH

#/home/executor/Ice/python2.4/bin/python client.py --npacks 10 --suffix simple_`date +%s` inputs/testSimple.input
/home/executor/Ice/python2.4/bin/python client.py --npacks 1 --suffix simple_`date +%s` inputs/testPricing.input
