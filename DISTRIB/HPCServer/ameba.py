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
Encapsulacion del ejecutable ameba

En este modulo incluimos las clases y funciones que trabajan de forma
directa con el proceso calculador, ejecutado por el sistema operativo
y que es quien procesa el trabajo enviado.
"""

import os
import traceback
import threading
import time
import popen2
import select
import sys
import utils
import signal
import IceGrid
import logging

logger = logging.getLogger("HPCServer")

def AmebaError ( input , reason , job , ameba , pid=None ) :
	"""Transforma los errores de ejecucion a un formato que entiende typhon."""
	jobid = input.split("\n")[0][2:]
	text = "JOBID : %s\n" % jobid
	text += "NODE : %s\n" % job["nodename"]
	text += "VERSION : %s\n" % ameba.getVersion()
	text += "ERROR : %s\n" % reason
	output = "{{%s\n*ERROR*\n%s" % ( jobid , text )
	crashfile = None
	mailfiles = []
	if pid :
		output += "\n"
		output += "**  octave_crash_dump.%s  **\n" % pid
		crashfile = "%s/octave_crash_dump.%s" % ( os.environ['HOME'] , pid )
		if os.path.isfile( crashfile ) :
			mailfiles.append( crashfile )
			fd = open( crashfile , 'r' )
			for line in fd :
				output += line
			fd.close()
		else :
			logger.warning( "MATHLAB DUMP FILE NOT FOUND on %s" % crashfile )
			output += "\nMATHLAB DUMP FILE NOT FOUND on %s\n\n" % crashfile
	output += "\n}}\n"
	if job.has_key('errormail') :
		subject = "%s : Ameba error for %s @ %s" % ( ameba.environment , jobid[2:] , job["nodename"] )
                pid = os.fork()
		if pid:
		    # we are the parent
		    os.waitpid(pid, 0) # make sure the child process gets cleaned up
		else:
		    # we are the child
		    utils.log.sendlogbymail( job["errormail"], subject, "%sINPUT :\n%s\n" % ( text , input), jobid,job["smtp1"], job["smtp2"], mailfiles )		    
		    os._exit(2)		   
			
	if crashfile :
		if os.path.isfile( crashfile ) :
			os.unlink( crashfile )
	
	return output

class AmebaProcess :
	"""Encapsula la ejecucion de ameba a traves de un objeto Popen3
y gestiona la interaccion con el mismo. En particular, esta
encargado de capturar las excepciones en ejecucion y formatearlas
para typhon."""

	def __init__ ( self , properties  , amebaVersion , unregister_callback , cpuid=-1 ) :
		"""El constructor fija la version de ameba que se va a ejecutar,
e inicializa variables auxiliares como el nombre del entorno.
Es posible especificar de forma explicita una CPU a la que fijar
el ameba que se va a arrancar, aunque el comportamiento por
defecto es permitir al sistema operativo mover el proceso sin
restricciones. Se utiliza un objeto de tipo Event para marcar
cuando el proceso ameba subyacente esta disponible para realizar
mas calculos. Tambien se instancia un objeto Timer, encargado de
desencadenar la destruccion del objeto tras un tiempo de
inactividad."""
		self.amebaVersion = amebaVersion
		
		self.environment = properties.getProperty("Environment")
		#self.serverId = properties.getProperty("Ice.ServerId")
		self.props = properties
		self.cpuid = cpuid
		self.destroy = unregister_callback
		self.child = None
		self._available = threading.Event()
		
		self.ttl = 60.0 * int( properties.getPropertyWithDefault("AmebaTimeout","5") )
		self._available.set()
		self.timer = threading.Timer( self.ttl , self.stop )
		self.timer.start()
		self.timeout = 60.0 * int( properties.getPropertyWithDefault("JobTimeout","3") )
		self.start()

	def getVersion ( self ) :
		"""Devuelve la version de ameba asociada al objeto"""
		return self.amebaVersion

	def start ( self ) :
		"""Arranca el proceso ameba, instanciando el objeto Popen3. Se
utiliza un metodo separado de la instanciacion del AmebaProcess
para poder relanzar el proceso ante ciertas condiciones de error."""
		mcrRoot = os.path.join( self.props.getProperty("EXEHOME") , self.props.getProperty("MCRROOT") )
		#mcrPath = "%s/bin/glnx86:%s/runtime/glnx86" % ( mcrRoot , mcrRoot )
		mcrPath = "%s" % mcrRoot 
		if os.environ.has_key("LD_LIBRARY_PATH") :
			mcrPath += ":%s" % os.environ['LD_LIBRARY_PATH']
		amebaRoot = os.path.join( self.props.getProperty("EXEHOME") , self.props.getProperty("AMEBADIR") )
		os.environ['MCRROOT'] = mcrRoot
		if self.cpuid == -1 :
			os.chdir( amebaRoot + "/" + self.getVersion() )
			self.child = popen2.Popen3( "LD_LIBRARY_PATH=%s ./ameba.sh" % mcrPath , True )
		else :
			os.chdir( amebaRoot + "/" + self.getVersion() )
			self.child = popen2.Popen3( "LD_LIBRARY_PATH=%s taskset -c %s ./ameba.sh" % ( mcrPath , self.cpuid ) , True )
		logger.info( "Starting ameba %s with pid %s. Octave binary from %s" % ( self.getVersion() , self.child.pid , mcrRoot ) )


	def stop ( self , autoexclude=True ) :
		"""Este metodo se invoca desde el timer de inactividad. Cierra el
canal de comunicacion hacia el proceso ameba, e invoca al metodo
de cierre del ameba. El argumento opcional controla si se ejecuta
el callback de destruccion, que se encarga de eliminar el objeto
del pool de calculadores disponibles."""
		if self.timer : self.timer.cancel()
		self.timer = None
		self.child.tochild.close()
		self.close()
		endcode = self.child.wait()
		if endcode != 0 : utils.log.msg( utils.NORMAL , "Ameba closed with errors" % endcode )
		logger.info( "Stopped ameba %s with pid %s" % ( self.getVersion() , self.child.pid ) )
		if autoexclude : self.destroy( self )

	def close ( self ) :
		"""Cierra los canales de comunicacion desde el proceso ameba
subyacente, capturando los errores generados."""
		outtext = self.child.fromchild.read()
		if outtext : logger.debug( "Closing output %s" % outtext )
		errtext = self.child.childerr.read()
		if errtext : logger.debug( "Closing errors %s" % errtext )

	def feed ( self , job ) :
		"""Es el metodo principal, y encapsula la interaccion real con ameba.
Extrae el input, y lo envia al stdin del proceso subyacente, entrando
en un bucle que espera la recepcion en los canales de salida. Una vez
que se ha recibido el output de todas las operaciones, se sale del
bucle y se devuelve el resultado, reiniciando el timer de inactividad.
Las excepciones son capturadas y se devuelven como un output convencional,
convenientemente formateado para ser entendido por typhon."""
		input = job["workinput"]
		if self.timer : self.timer.cancel()
		self.timer = None
		self._available.clear()
		try :
			logger.info("Input job %s" % input)
			self.child.tochild.write(input)
			self.child.tochild.flush()
		except Exception, ex :
			logger.warning( "The process was dead, restarting" )
			# FIXME: Should we raise something here ?
			self.close()
			self.start()
			try :
				self.child.tochild.write( input )
				self.child.tochild.flush()
			except IOError , ex :
				logger.error( "Cannot restart : %s" % ex )
				self._available.set()
				return AmebaError ( input , "Cannot restart : %s" % ex , job , self )
			except :
				logger.error( "Unexpected exception while restarting" )
				traceback.print_exc(20,utils.log)
				self._available.set()
				return AmebaError( input , "Unexpected exception while restaring" , job , self )

		timeout = self.timeout
		if job.has_key("job_timeout"):
			timeout = 60.0 * int( job["job_timeout"] )
		nops = input.count("{{")
		ret = ""	
		while nops :
			rfd, wfd, efd = select.select( [self.child.fromchild],[],[self.child.childerr],timeout)
		
			# FIXME: Should we restart on errors ?
			# Usage of read() method from the file object does not work
			# Maybe the reason is that we are using unidirectional file objects in
			# opposite direction
			#	resul = rfd[0].read( 16384 )
			if rfd :
				resul = os.read( rfd[0].fileno() , 16384 )
				if not resul:
					logger.error( "broken pipe, reinicio de ameba" )
					ret = AmebaError( input , "broken pipe" , job , self , self.child.pid )
					self.start()
					break
				nops -= resul.count("}}") 
				ret += resul

			if efd :
				resul = os.read( efd[0].fileno() , 16384 )
				if resul.count("CTF") > 0:
					logger.warning( "Warning: %s" % resul )
					continue
				else:
					logger.error( "Error en la ejecucion del programa: %s" % resul )
					ret = AmebaError( input , "Error en la ejecucion : %s" % resul , job , self , self.child.pid )
					self.start()
					break

			if not rfd and not efd:
				logger.error( "timeout " )
				ret = AmebaError( input , "timeout" , job , self , self.child.pid )
				self.start()
				break

		self._available.set()
		self.timer = threading.Timer( self.ttl , self.stop )
		self.timer.start()
		
		return ret

	def wait ( self ) :
		"""Espera a que finalize la ejecucion del trabajo actual. Solo
se invoca desde el destructor del objeto AmebaAsyncThread que
realizo la instanciacion."""
		self._available.wait()

class AmebaJobThread ( threading.Thread ) :
	"""Clase a cargo de unir la cola de ejecucion y el calculador. Se
Se trata de un thread de ejecucion utilizado para calcular un
unico trabajo. Esta encargado de enviar el resultado a typhon."""

	def __init__( self , ameba_process , job , lock , pool ) :
		"""Realiza la inicializacion, almacenando todas las variables
que seran utilizadas en ejecucion.
Como fase final, se comienza la ejecucion del thread."""
		threading.Thread.__init__(self)

		self.ameba_process = ameba_process
		self._pool = pool
		self._job = job
		self._lock = lock
		self.start()
		
		
	def run(self):
		"""Lanza el trabajo, capturando la salida y enviando el output
mediante el callback de Ice. Una vez terminado, devuelve el
objeto AmebaProcess al pool de ejecucion y libera el bloqueo
correspondiente.
Si el contexto indica que es un trabajo de test, en lugar del
output de ameba se envia informacion sobre rendimiento."""
				
		try :
			try :
				ret = self.ameba_process.feed(self._job)
				if self._job.has_key( "testing" ) :
					ret = self._job.performance()
				self._job.response(ret)
			finally :
				self._pool.append( self.ameba_process )
				self._lock.release()
		except IOError, ex:
			##Tipo de error lanzado por problemas de memoria.
			logger.error( "Unexpected IOError while running job : %s" % ex )
                        self._job.response( AmebaError ( self._job["workinput"] , "Unexpected IOError while running job : %s" % ex , self._job , self.ameba_process ) )

		except Exception , ex :
			logger.error( "Unexpected exception while running job : %s" % ex )
			self._job.response( AmebaError ( self._job["workinput"] , "Unexpected exception while running job : %s" % ex , self._job , self.ameba_process ) )
		except :
			logger.error( "Unknown exception while running job" )
			traceback.print_exc(20,utils.log)
			self._job.response( AmebaError ( self._job["workinput"] , "Unknown exception while running job" , self._job , self.ameba_process ) )


