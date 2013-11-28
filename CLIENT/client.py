#!/home/executor/Ice/python2.4/bin/python
# Copyright (C) 2012  CEDIANT <info@cediant.es>
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License v2
# as published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, see <http://www.gnu.org/licenses/>.

import os, time
import sys, traceback, Ice, IceGrid
import threading
import random

SLICE_CONTRACT = os.environ['HOME'] + "/DISTRIB/HPCServer/execservant.ice"
#CONFIG_FILE = os.environ['HOME'] + "/config"
CONFIG_FILE = "client.cfg"

DEFAULT_PRIO = "5"
BASE_VERSION = "364"
ALTERNATE_VERSION = "364"

import amebajobs

Ice.loadSlice(SLICE_CONTRACT)
import HPCServer


def random_prio ( max_prio=10 ) :
	return int( max_prio * random.random() )

def step_prio ( max_prio=10 ) :
	priolist = range(max_prio,0,-1)
	top = 0
	for i in priolist :
		top += i
	prio = int( top * random.random() )
	for i in priolist :
		limit += i
		if prio < limit :
			break
	return i - 1

import math

def stats ( values ) :
	avg , err = 0.0 , 0.0
	for v in values :
		avg += v
		err += v * v
	avg /= len(values)
	err /= len(values)
	err -= avg * avg
	return avg , math.sqrt( err )


class AMI_HPCServer_AsyncgExec(Ice.Object):

	def __init__(self,name,application):
		self.name = name
		self.application = application

	def ice_response(self, result):
		self.application.cond.acquire()
		try:
		#	print "Terminada operacion con resultado [%s]" % result 
			if self.application.detailfile : self.application.detailfile.write( "%s %s\n" % ( result , time.time() ) )
			self.application.jobs-=1
			if self.application.jobs==0:
				self.application.cond.notify()
		finally:
			self.application.cond.release()

		print result

	def ice_exception(self,ex):
		self.application.cond.acquire()
		try:
			self.application.jobs-=1
			if self.application.jobs==0:
				self.application.cond.notify()
			print "excepcion --- %s" % ex
		finally:
			self.application.cond.release()
	


class ExecClientApp(Ice.Application):
	def __init__(self):
		self.jobs = 0
		self.cond = threading.Condition()
		self.detailfile = None
		
	
	def launchOperation(self,input_string,prio):
		try:
			ic = self.communicator()
			base = ic.stringToProxy("HPCServerServant")
                        #base = ic.stringToProxy("HPCServerServant:default -p 10000")
			e_servant = HPCServer.ExecServantPrx.checkedCast(base)
		except Ice.NotRegisteredException:
			print "%s : couldn't find a `::HPCServer::HPCServerServant' object." % self.appName()
			return False
		
		try:
			ctx={}
			if prio == "random" :
				ctx["prio"] = "%s" % random_prio( 10 )
			else :
				ctx["prio"] = prio
			if ameba_percent :
				if ameba_percent < int(100*random.random()) :
					ctx["ameba_version"] = ALTERNATE_VERSION
				else :
					ctx["ameba_version"] = BASE_VERSION
			elif ameba_range :
				 ctx["ameba_version"] = "%s" % int( 10 + ameba_range * random.random() )
			else :
				ctx["ameba_version"] = BASE_VERSION
			#ctx["testing"] = "No"
			ctx["submittime"] = "%s" % time.time()
			ctx["url"] = "http://01cnbtlgridp:21000/deploy/"
			ctx["errormail"] = "gfernandez@cediant.es"
                        ctx["smtp1"] = "01cnbtlgridp:25"
	
			## AMI + AMD
			#print "lanzada operacion"			
			self.cond.acquire()
			try:
				callback = AMI_HPCServer_AsyncgExec(input_string,self)
				e_servant.gExec_async(callback,input_string,ctx)  # Asynchronous call	
				self.jobs+=1
			finally:
				self.cond.release()
					
		except:
			traceback.print_exc()
			return False
		
		return True
	
	def constructInput(self,prio,clientid):

		operationid = int( 10000000 * random.random() )
		for i in range( pack * ncores ) :
			input = amebajobs.construct_job((clientid,operationid),i)
			if not self.launchOperation(input,prio) :
				print "Job was not submitted"
				return False

		self.cond.acquire()
		try:
			while self.jobs:
				self.cond.wait()
		finally:
			self.cond.release()

		return True
			

	def evaluateFile(self,file_path,prio):
				
		if not os.path.exists(file_path):
			return False
		try:
			f = open(file_path,'r')
			request_list = f.read().split("{{")[1:]
			f.close()
		except:
			print "No se pudo leer el fichero %s" % file_path

		#send operations to ameba file
		for i in range(len(request_list)):
		#	print "Lanzando operacion %d" % i
			if not self.launchOperation("{{"+request_list[i],prio):
				return False
		
		#wait for jobs termination.(AMI+AMD Issue)
		self.cond.acquire()
		try:
			while self.jobs:
				self.cond.wait()
		finally:
			self.cond.release()
			
		return True
		

	def run(self,args):
		service_name = "HPCServerServant"
		
		ic = None
		ic = self.communicator()
		# This is probably a bug somewhere, but is required to handle connection loss
		ic.getProperties().setProperty( "Ice.ThreadPool.Client.SizeMax" , "20" )
		
		# Launch file section
		#---------------------------------------
		
		file_name = None
		if len(sys.argv) > 1 :
			aux_name = sys.argv[1]
			if os.path.exists(aux_name):
				file_name=aux_name
		
		if len(sys.argv) > 2 :
			prio = sys.argv[2]
		else:
			prio = DEFAULT_PRIO
		
		init_time = time.time()
		
		subtotals = []
		summary = open( outfile + ".out" , 'w' )
		summary.write( "# args : %s\n" % sys.argv )
		summary.write( "# cores : %s\n" % ncores )
		if file_name is None :
			summary.write( "# pack : %s\n" % pack )
		else :
			summary.write( "# input_file : %s\n" % file_name )
		for i in range( npacks ) :
			self.detailfile = open( os.path.join( outfile , "%s.out" % i ) , 'w' )
			starttime = time.time()
		
			if file_name is None :
				clientid = int( 1000000 * random.random() )
				self.constructInput(prio,clientid)
			else :
				self.evaluateFile(file_name,prio)

			subtotal = time.time() - starttime
			subtotals.append( subtotal )
			summary.write( "%s %s %s %s\n" % ( i , subtotal , ameba_percent , ameba_range ) )
			self.detailfile.close()
			self.detailfile = None
		summary.close()
			
		if ic :
			try:
				ic.destroy()
			except:
				traceback.print_exc()

		avg , err = stats( subtotals )
		print "%s %s %s %s %s %s" % ( header , time.time() - init_time , avg , err , ameba_percent , ameba_range )
		
		return True


header = "AVERAGE"
outfile = "output"
ncores = 8
pack = 30
npacks = 10
ameba_percent = False
ameba_range = False

if (__name__ == "__main__"):

	if len(sys.argv) > 1 and sys.argv[1] == "--pack" :
		sys.argv.pop(1)
		pack = int(sys.argv.pop(1))

	if len(sys.argv) > 1 and sys.argv[1] == "--npacks" :
		sys.argv.pop(1)
		npacks = int(sys.argv.pop(1))

	if len(sys.argv) > 1 and sys.argv[1] == "--ameba-percent" :
		sys.argv.pop(1)
		ameba_percent = int(sys.argv.pop(1))

	if len(sys.argv) > 1 and sys.argv[1] == "--ameba-range" :
		sys.argv.pop(1)
		ameba_range = int(sys.argv.pop(1))

	if ameba_percent :
		ameba_range = False

	if len(sys.argv) > 1 and sys.argv[1] == "--suffix" :
		sys.argv.pop(1)
		header = sys.argv.pop(1)
		outfile = os.path.join( outfile , header )
	os.makedirs( outfile )

	app = ExecClientApp()
	ret = app.main(sys.argv,CONFIG_FILE)
	sys.exit(ret)
	

