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


"""Threads principales

En este modulo se definen las clases que representan los threads
principales : el de ejecucion y el de mensajeria.
"""

import traceback
import threading
import time

import Ice , IceStorm

import utils

from ameba import *

from scheduler import *


#Ice.loadSlice( "hpcmonitor.ice" )
#import HPCMonitor

import logging
logger = logging.getLogger("HPCServer")


class AmebaAsyncThread(threading.Thread):
	"""Thread de ejecucion. Gestiona la cola de trabajos y el pool con
los calculadores. Esta a cargo de inicializar el thread de eventos.
Utiliza un semaforo para controlar que el numero de trabajos en
ejecucion no supere al numero de CPU disponibles, y crea nuevos
objetos AmebaProcess cuando se requieren."""

	def __init__( self , ic , properties ) :
		"""
Durante la inicializacion se instancia el thread de eventos
y el objeto scheduler que se utiliza como cola de trabajos.
Tambien se instancia el pool de calculadores y se inicializa
el semaforo cuya mision es contener el numero de amebas que
calculan de forma simultanea.
"""
		threading.Thread.__init__(self)
		
		sch_type = properties.getProperty("SchedulerType")
		logger.info( "Scheduler : %s" % sch_type )

		self._scheduler = SchedulerFactory().getScheduler(sch_type)
		self._running = True

		self.environment = properties.getProperty("Environment")

		self.properties = properties

		self.cpus = properties.getPropertyAsInt("Cpus")

		self.pool = []
		self._cond = threading.Condition()
		self._run_lock = threading.Semaphore(self.cpus)

	def free ( self ) :
		"""Devuelve la longitud del pool"""
		return len(self.pool)

	def busy ( self ) :
		"""Devuelve el numero de amebas calculando"""
		return self.cpus - self._run_lock._Semaphore__value

	def poolSize ( self ) :
		"""Devuelve el numero total de procesos ameba presente en el sistema"""
		return self.free() + self.busy()

	def run(self):
		"""
Se implementa el bucle principal, que espera la llegada de trabajos.

Cuando hay trabajos disponibles, se extraen de la cola y si no esta
completo el semaforo de control pasan a la fase de ejecucion.

Para ejecutar un trabajo, se busca en el pool algun objeto
AmebaProcess con la version requerida, y si se encuentra,
se saca fuera del pool, instanciandose un nuevo objeto con la
version precisa si no hay ninguno disponible.

Finalmente, con el trabajo y el ameba, se instancia un objeto del
tipo AmebaJobThread que realiza la ejecucion real.
"""
		while self._running:
			self._cond.acquire()
			if not self._scheduler.hasJobs():
				self._cond.wait()
			if not self._running :
				self._cond.release()
				break
			job = self._scheduler.schedule()
			self._cond.release()
			# FIXME : acquiring the run lock before releasing drastically reduces the rate of accepted jobs
			self._run_lock.acquire()
			for n in range( self.free() ) :
				if self.pool[n].getVersion() == job["ameba_version"] :
					ameba_process = self.pool.pop( n )
					break
			else :
				try :
					logger.info( "Starting AmebaProcess with version %s, pool size %s" % ( job["ameba_version"] , self.poolSize() ) )
					ameba_process = AmebaProcess( self.properties , job["ameba_version"] , self.remove )
				except Exception , ex :
					logger.warning( "AmebaProcess Exception : %s" % ex )
				except :
					traceback.print_exc(20,utils.log)
			try :
				AmebaJobThread( ameba_process , job , self._run_lock , self.pool )
			except Exception , ex :
				logger.warning( "AmebaJobThread Exception : %s" % ex )
			except :
				traceback.print_exc(20,utils.log)
		
	def add(self, job ) :
		"""Incluye un nuevo trabajo en la cola"""
		self._cond.acquire()
		try:
			self._scheduler.add(job)
			self._cond.notify()
		finally:
			self._cond.release()
				
	def remove ( self , ameba_process ) :
		"""Elimina un objeto AmebaProcess del pool"""
		logger.info( "Removing %s" % ameba_process )
		self.pool.remove( ameba_process )

	def destroy(self):
		"""Libera los recursos y para los AmebaProcess en ejecucion"""
		self._cond.acquire()
		self._scheduler.destroy()
		del self._scheduler
		try:
			self._running=False
			self._cond.notify()
		finally:
			self._cond.release()
		for ameba_process in self.pool :
			ameba_process.wait()
			# Is it possible to get an exception while stopping ??
			ameba_process.stop( False )

