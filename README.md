README file for HPCServer Grid Scheduler
=======================================


- System requeriments, and software versions used in this platform:

	CentOS 6.x x86_64
	Python 2.4.4
	ZeroC Ice (IceGrid 3.4.0 component)


HPCServer Grid Scheduler configuration step-by-step
==================================================

Primary Registry configuration
------------------------------

1 - Unprivileged user creation for security reasons.

adduser executor
su - executor

2 - Working dir of HPCServer Grid Scheduler:

mkdir Ice
cd Ice

3 - Install Python 2.4.4 the only tested platform:

wget http://www.python.org/ftp/python/2.4.4/Python-2.4.4.tar.bz2
tar xvjf Python-2.4.4.tar.bz2
cd  Python-2.4.4
./configure --prefix=/home/executor/Ice/python2.4
make
make install

4 -  IceGrid 3.4.0 deployment:

mkdir download && cd download
wget wget http://zeroc.com/download/Ice/3.4/Ice-3.4.0-rhel5-x86_64-rpm.tar.gz
tar xvzf Ice-3.4.0-rhel5-x86_64-rpm.tar.gz
cd /home/executor/Ice
rpm2cpio download/ice-3.4.0-1.rhel5.noarch.rpm | cpio -ivd
rpm2cpio download/ice-python-3.4.0-1.rhel5.x86_64.rpm | cpio -ivd
rpm2cpio download/ice-libs-3.4.0-1.rhel5.x86_64.rpm | cpio -ivd
rpm2cpio download/ice-servers-3.4.0-1.rhel5.x86_64.rpm | cpio -ivd
rpm2cpio download/ice-utils-3.4.0-1.rhel5.x86_64.rpm | cpio -ivd
rpm2cpio download/db48-4.8.24-1ice.rhel5.x86_64.rpm | cpio -ivd

rm -fr etc

5 - Minimal folder staff:

mkdir -p /home/executor/Ice/var/run /home/executor/Ice/var/lib/icegrid/registry /home/executor/Ice/var/lock/subsys

6 - Primary Registry configuration files:

cp -r liberacion-github/etc_config/primary-registry/etc /home/executor/Ice

7 - Running the Primary Registry:

[executor@host001 ]$ /home/executor/Ice/etc/init.d/icegridregistry start
Starting icegridregistry:                                  [  OK  ]


Secondary Registry configuration
--------------------------------

Repeat step from 1 to 5:

6 - Secondary Registry configuration files:

cp -r liberacion-github/etc_config/secondary-registry/etc /home/executor/Ice


7 - Running the Secondary Registry:

[executor@host002 ]$ /home/executor/Ice/etc/init.d/icegridregistry start
Starting icegridregistry:                                  [  OK  ]

Node configuration
------------------

Repeat step from 1 to 4:

5 - Minimal folder staff:

mkdir -p /home/executor/Ice/var/run /home/executor/Ice/var/lib/icegrid/node /home/executor/Ice/var/lock/subsys

6 - Execution Node configuration files:

cp -r liberacion-github/etc_config/node/etc /home/executor/Ice

7 - Running the Execution Node:

[executor@host003 ~]$ /home/executor/Ice/etc/init.d/icegridnode start
Starting icegridnode:                                      [  OK  ]


Testing the installation
------------------------

- Setting up the minimal enviroment:

ICEGRID_HOME=/home/executor
PYTHONPATH=$ICEGRID_HOME/Ice/usr/lib64/python2.4/site-packages/Ice/:$ICEGRID_HOME/Ice/python2.4/lib/python2.4/ 
LD_LIBRARY_PATH=$ICEGRID_HOME/Ice/usr/lib64/ 
PATH=$PATH:/home/executor/Ice/usr/bin/
export PYTHONPATH LD_LIBRARY_PATH PATH

- Checking the IceGrid components deployed:

[executor@host001 ~]$ cat config.cfg 
Ice.Default.Locator=HPCBanestoGrid/Locator:tcp -h host001 -p 4061

[executor@host001 ~]$ Ice/usr/bin/icegridadmin  --Ice.Config=config.cfg -u executor -p xxx
Ice 3.4.0  Copyright 2003-2010 ZeroC, Inc.
>>> registry list
Secondary host002
Master
>>> node list
host003
host004
>>> 

Application deployment
----------------------

cp -r DISTRIB /home/executor

DISTRIB/
├── HPCServer
│   ├── ameba.py
│   ├── asyncThreads.py
│   ├── execservant.ice
│   ├── scheduler.py
│   ├── server.py
│   └── utils
│       ├── __init__.py
│       ├── logger.py
│       └── timermanager.py
└── HPCServer.xml

cd DISTRIB
icepatch2calc HPCServer

icegridadmin --Ice.Config=../config.cfg -u executor -p xxx -e 'application add HPCServer.xml'
# icegridadmin --Ice.Config=../config.cfg -u executor -p xxx -e 'application remove HPCServer'

icegridadmin --Ice.Config=config.cfg -u grid -p xxx -e 'application list'
HPCServer

icegridadmin --Ice.Config=../config.cfg -u executor -p xxx -e 'server list'
HPCServer-host003
HPCServer-host004
HPCServer.IcePatch2


Octave framework configuration
------------------------------

yum install octave hdf5
ln -sf /usr/lib64/libhdf5.so.7 /usr/lib64/libhdf5.so.6

Node executor staff
-------------------

You have to deploy on each executor node this folder in order to run
the Monte Carlo pricing simulation with octave.

home/executor/ameba
└── 364
    ├── ameba.sh
    └── AsianOption.m

Client execution
---------------

cd CLIENT
sh directTest.sh

{{ putPrice  0.35879 callPrice  0.49347 }}
{{ putPrice  0.35819 callPrice  0.49189 }}
{{ putPrice  0.35677 callPrice  0.49583 }}
simple_1380107850 5.56776213646 5.56705594063 0.0 False False

Notes
-----

This sample of IceGrid from ZeroC Ice shows the execution of Monte Carlo Asian Pricing simulation
using Octave. The code is ready to set up different Octave enviroments.

If you have any questions, please feel free to send an to <info@cediant.es>
