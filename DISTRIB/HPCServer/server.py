#!/home/executor/Ice/python2.4/bin/python
# vim: set fileencoding=utf8
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


"""
Es el unico ejecutable y el programa principal.

Implementa la aplicacion y los servants de Ice, y esta diseñado para
ser lanzado a traves del proceso icegridnode, a peticion del registry.
"""

import time
import os, sys, traceback
import urllib
import logging

import Ice
import IceGrid

import tempfile
import zipfile

import utils
utils.log = utils.Logger('%s/HPCServer.log' % os.environ['HOME'] )

#############################################
## Version original de la aplicacion con   ##
## el unico cambio del archivo de log que  ##
## pasara a llamarse LOG_Original.log      ##
#############################################

Ice.loadSlice("execservant.ice")
import HPCServer

from scheduler import *


from asyncThreads import *
		
logger = logging.getLogger("HPCServer")


def DeployError ( input , reason , job , servant ) :
	"""Transforma los errores de despliegue a un formato que entiende typhon"""
	jobid = input.split("\n")[0][2:]
	text = "JOBID : %s\n" % jobid
	text += "NODE : %s\n" % job["nodename"]
	text += "ERROR : %s\n" % reason
	output = "{{%s\n*ERROR*\n%s" % ( jobid , text )
	mailfiles = []
	output += "\n}}\n"
	if job.has_key('errormail') :
		subject = "%s : Deployment error for %s @ %s" % ( servant.environment , jobid[2:] , job["nodename"] )
		pid = os.fork()
                if pid:
                    # we are the parent
                    os.waitpid(pid, 0) # make sure the child process gets cleaned up
                else:
                    # we are the child
                    utils.log.sendlogbymail( job["errormail"], subject, "%s\n" % text , jobid[2:], job["smtp1"], job["smtp2"], mailfiles )
		    os._exit(2)

	return output


class JobAd ( dict ):
	"""Diccionario utilizado para representar internamente un trabajo."""

	def __init__ ( self , input_string , callback ) :
		"""Se guarda el callback en una variable interna, y se extraen los
identificadores del trabajo de la primera linea del input.
Tambien se incializan los timestamps que se utilizan para marcar
diferentes estados de la evolucion del trabajo."""
		dict.__init__( self )
		self.__cb = callback
		
		try:
			header = input_string.splitlines()[0]		
			header = header.replace("{{","")
			session_and_model , self["model"] = header.split(' ',1)
			self["sessionid"] , self["jobid"] = session_and_model.split('-',1)
		except:
			self["jobid"] = ""
			self["sessionid"] = ""
			self["model"] = ""
		
		
		self["workinput"] = input_string
		self["starttime"] = -1
		self["startrunningtime"] = -1
		self["endtime"] = -1

	def response ( self , message ) :
		self.__cb.ice_response( message )

	def performance ( self ) :
		"""Devuelve un string con los timestamps de los diferentes momentos
de la evolucion del trabajo"""
		output = [ self["model"] , self["ameba_version"] , self["priority"] , self["nodename"] ]
		output.append( str(self["submittime"]) )
		output.append( str(self["starttime"]) )
		output.append( str(self["startrunningtime"]) )
		output.append( str(self["endtime"]) )
		return " ".join( output )

	
class ExecServantI(HPCServer.ExecServant):
	"""Implementacion de los metodos del interfaz definido en el slice.
Tambien gestiona el despliegue de nuevas versiones."""

	def __init__( self , ic ) :
		"""Durante la instanciacion del servant se determinan algunas
propiedades internas. Si no hay configurado un numero explicito
de cores, se determinan a partir de la informacion de icegridnode.
Se inicializa el bloqueo que impide el despliegue simultaneo de
varios ameba.zip, y se instancia el thread de ejecucion."""

		properties = ic.getProperties()
		self.environment = properties.getProperty("Environment")
		self._deploy_lock = threading.Lock()

		app_name = self.ice_id().split('::')[1]
		servant_id = properties.getProperty("Ice.Admin.ServerId")
                nodename = servant_id[len(app_name)+1:]

                locator = properties.getProperty("Ice.Default.Locator")

                registry_str = "%s/Registry" % locator.split("/")[0]
                registry_prx = ic.stringToProxy(registry_str)
                try:
                        registry = IceGrid.RegistryPrx.checkedCast(registry_prx)
                except Exception, ex:
                        secondaryRegistry = locator.split("-h")[2]
                        secondaryRegistry = secondaryRegistry.split(" -p")[0]
                        registry_str = "\"%s/Registry-Secondary%s\"" % ( locator.split("/")[0], secondaryRegistry )
                        registry_prx = ic.stringToProxy(registry_str)
                        try:
                                registry = IceGrid.RegistryPrx.checkedCast(registry_prx)
                               	logger.info("Primary Registry Down. Connected to Secondary Registry: %s" % ( secondaryRegistry ))
                        except Exception, ex:
                                raise Exception(  "Unable to Connect to either Primary or Secondary Registry" )

                admin_session = registry.createAdminSession("user", "passwd")
		admin = IceGrid.AdminPrx.checkedCast(admin_session.getAdmin())
		self.info = admin.getNodeInfo(nodename)

		if not properties.getPropertyAsInt("Cpus") :
			properties.setProperty( "Cpus" , "%d" % self.info.nProcessors )

		self._job_queue = AmebaAsyncThread( ic , properties )
		self._job_queue.start()

	def unzip ( self , ameba_root , version , baseurl ) :
		"""Despliega una nueva version de ameba a partir de una url. Descarga
el zip y lo descomprime en el directorio adecuado, comprobando que
se incluye una unica version de ameba cuya version es la correcta,
y que existe el fichero 'ameba' y es ejecutable.
En caso de errores se borra completamente la version desplegada."""

		zipname = "/ameba%s.zip" % version
		schema , urlpath = urllib.splittype( baseurl + zipname )
		urlpath = "%s:%s" % ( schema , os.path.normpath( urlpath ) )
		urlobj = urllib.urlopen( urlpath )
		urlfile = tempfile.TemporaryFile()
		urlfile.write( urlobj.read() )
		urlfile.seek(0)
		zipobj = zipfile.ZipFile( urlfile , 'r' )

		versiondir = "%s/" % version
		os.makedirs( os.path.join( ameba_root , version ) )
		dirlist = []
		try :
			for info in zipobj.infolist() :
				if info.external_attr & pow(2,4) :
					logger.info( "unzip : found dir %s" % info.filename )
					if not info.filename.startswith( versiondir ) :
						logger.warning( "Version mismatch on ZIP file. Declares %s but contains %s" % ( version , info.filename ) )
						raise Exception( "Version mismatch on ZIP file. Declares %s but contains %s" % ( version , info.filename ) )
					if info.filename != versiondir :
						dirname = os.path.join( ameba_root , info.filename[:-1] )
						os.mkdir( dirname )
						dirlist.insert( 0 , dirname )
						logger.info( "unzip :           done" )
				elif info.external_attr & pow(2,31) :
					logger.info( "unzip : found file %s" % info.filename )
					if not info.filename.startswith( versiondir ) :
						logger.warning( "Version mismatch on ZIP file. Declares %s but contains %s" % ( version , info.filename ) )
						raise Exception( "Version mismatch on ZIP file. Declares %s but contains %s" % ( version , info.filename ) )
# There is no mode on the ZipInfo data
# What about creating the requied path elements if any parent directory does not exist
					fd = os.open( os.path.join( ameba_root , info.filename ) , os.O_CREAT | os.O_WRONLY )
					os.write(fd, zipobj.read(info.filename) )
					os.close(fd)
					logger.info( "unzip :            created" )
				else :
					logger.warning("Corrupted zipfile : Unknown attrs for %s : %s - %s\n" % ( info.filename , info.internal_attr , info.external_attr ) )
					raise Exception( "Corrupted zipfile : Unknown attrs for %s : %s - %s\n" % ( info.filename , info.internal_attr , info.external_attr ) )
			if not os.path.exists( os.path.join( ameba_root , version , "ameba" ) ) :
				logger.warning( "Executable %s not included" % os.path.join( ameba_root , version , "ameba" ) )
				raise Exception( "Executable %s not included" % os.path.join( ameba_root , version , "ameba" ) )
			if not os.path.isfile( os.path.join( ameba_root , version , "ameba" ) ) :
				logger.warning( "Ameba executable is not a file" )
				raise Exception( "Ameba executable is not a file" )
			if not os.stat( os.path.join( ameba_root , version , "ameba" ) ).st_mode & 0100 :
				logger.warning( "Ameba binary has no exec permission" )
				raise Exception( "Ameba binary has no exec permission" )
# Clean on caller ???
			dirlist.reverse()
			for dirname in dirlist :
				if not os.listdir( dirname ) :
					os.rmdir( dirname )
		except Exception , ex :
			logger.warning( "Cleaning directory" )
			for file in os.listdir( os.path.join( ameba_root , version ) ) :
				if os.path.isfile( os.path.join( ameba_root , version , file ) ) :
					os.unlink( os.path.join( ameba_root , version , file ) )
			os.removedirs( os.path.join( ameba_root , version ) )
			raise( ex )
		except :
			logger.warning( "Cleaning directory" )
			for file in os.listdir( os.path.join( ameba_root , version ) ) :
				if os.path.isfile( os.path.join( ameba_root , version , file ) ) :
					os.unlink( os.path.join( ameba_root , version , file ) )
			os.removedirs( os.path.join( ameba_root , version ) )
			raise( "Unknown exception while deploying" )

	def destroy ( self ) :
		"""Detiene la cola de ejecucion"""
		self._job_queue.destroy()
		self._job_queue.join()

	def gExec_async(self,cb,input_string,current):
		"""Recibe los trabajos enviados desde los clientes, instanciando un
objeto JobAd con el input, cambiando algunas de sus propiedades
en base al contexto recibido.
Si la version de ameba que se solicita no esta desplegada, se
descarga y despliega, en un segmento bloqueado para evitar multiples
despliegues de una misma version.
Una vez que realizadas estas tareas, el trabajo se envia al thread
de ejecucion."""
		job = JobAd(input_string,cb)
		properties = current.adapter.getCommunicator().getProperties()
		job["nodename"] = self.info.name
		job["adaptername"] = properties.getProperty("HPCServerAdapter.AdapterId")[len(properties.getProperty("Ice.Admin.ServerId"))+1:]
		
		if current.ctx.has_key("errormail"):
			job["errormail"] = current.ctx["errormail"]
		else :
			job["errormail"] = properties.getProperty("ReportMail")

		if not current.ctx.has_key("ameba_version"):
			cb.ice_response( DeployError( input_string , "context keyword missing : ameba_version" , job , self ) )
			return

		ameba_root = os.path.join( properties.getProperty("EXEHOME") , properties.getProperty("AMEBADIR") )

		job["ameba_version"] = current.ctx["ameba_version"]
		if current.ctx.has_key("smtp1"):
			job["smtp1"] = current.ctx["smtp1"]
		else:
                        job["smtp1"] = ""
		if current.ctx.has_key("smtp2"):
			job["smtp2"] = current.ctx["smtp2"]
		else:
		 	job["smtp2"] = ""
		if current.ctx.has_key("job_timeout"):
			job["job_timeout"] = current.ctx["job_timeout"]
		if current.ctx.has_key("ameba_timeout"):
                        job["ameba_timeout"] = current.ctx["ameba_timeout"]

		if not os.path.isdir( os.path.join( ameba_root , job["ameba_version"] ) ) :
			if not current.ctx.has_key("url") :
				cb.ice_response( DeployError( input_string , "context keyworkd missing : url for version %s" % job["ameba_version"] , job , self ) )
				return
			try :
				self._deploy_lock.acquire()
				try :
					# Volvemos a comprobar, por si el anterior propietario del bloqueo ha desplegado esta version
					if not os.path.isdir( os.path.join( ameba_root , job["ameba_version"] ) ) :
						logger.info( "Downloading version %s from %s" % ( job["ameba_version"] , current.ctx["url"] ) )
						self.unzip( ameba_root , job["ameba_version"] , current.ctx["url"] )
						logger.info( "Version %s deployed" % job["ameba_version"] )
				finally :
					self._deploy_lock.release()
			except Exception , ex :
				logger.warning( "Deploy exception for ameba %s from %s :\n%s" % ( job["ameba_version"] , current.ctx["url"] , ex ) )
				cb.ice_response( DeployError( input_string , "Deploy exception for ameba %s from %s :\n%s" % ( job["ameba_version"] , current.ctx["url"] , ex ) , job , self ) )
				return
			except :
				logger.warning( "Unexpected deploy exception for ameba %s from %s" % ( job["ameba_version"] , current.ctx["url"] ) )
				#TODO:revisar
				#traceback.print_exc(20,utils.log)
				cb.ice_response( DeployError( input_string , "Unexpected deploy exception for ameba %s from %s" % ( job["ameba_version"] , current.ctx["url"] ) , job , self ) )
				return

		if current.ctx.has_key("prio"):
			job["priority"] = current.ctx["prio"]

		if current.ctx.has_key("testing"):
			job["testing"] = current.ctx["testing"]
			job["submittime"] = current.ctx["submittime"]

		self._job_queue.add(job)

class ExecServerApplication(Ice.Application):
	"""Clase encargada de interacionar con los servants, Ice y el registry."""

	def run(self,args):
		"""Instancia el servant, y el adaptador, siguiendo los metodos
habituales de Ice. """

		ic = self.communicator()
		logFile = "/home/executor/LOG_Original.log"
		
		if (ic.getProperties().getProperty("LogDir")) :
			logFile = ic.getProperties().getProperty("LogDir")
		logLevel = logging.INFO
		if (ic.getProperties().getProperty("LogLevel")) :
			if (ic.getProperties().getProperty("LogLevel") == "DEBUG"):
				logLevel = logging.DEBUG
			elif (ic.getProperties().getProperty("LogLevel") == "INFO"):
                                logLevel = logging.INFO
                        elif (ic.getProperties().getProperty("LogLevel") == "WARNING"):
                                logLevel = logging.WARNING
                        elif (ic.getProperties().getProperty("LogLevel") == "ERROR"):
                                logLevel = logging.ERROR
		logging.basicConfig(level=logLevel, format='%(asctime)s - %(levelname)s\t- %(module)s:%(lineno)d\t===>  %(message)s', filename=logFile, filemode='a')
		logger.info("\n\n")
		logger.info("#################################################")
	        logger.info("####         ##     HPCSERVER    ##          ####")
	        logger.info("#################################################")
	        logger.info("")
		logger.info( "Starting ExecServerApplication" )

		serv_thread = ExecServantI( ic )
		# FIXME: adapter name and identity should be taken from registry
		adapter = ic.createObjectAdapter("HPCServerAdapter")
		ident = ic.stringToIdentity("HPCServerServant")
		adapter.add(serv_thread, ident)

		adapter.activate()
		ic.waitForShutdown()
		serv_thread.destroy()
		logger.info( "Stopping ExecServer" )


if (__name__=="__main__"):
	app = ExecServerApplication()
	app.main(sys.argv)
