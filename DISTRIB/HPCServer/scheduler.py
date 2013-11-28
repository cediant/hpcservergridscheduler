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
Modulo para definir los scheduler disponibles.

En este modulo se definen los schedulers y la factoria para generarlos.

El interfaz del scheduler consta de cuatro metodos
  - addJob/addRT , para añadir trabajos normales y de 'real time'
  - hasJobs , para averiguar si existen trabajos pendientes
  - schedule , para obtener el siguiente trabajo

"""

class SimpleScheduler:
	"""
Es la definicion del interfaz del scheduler y una implementacion
minima. Dispone de dos colas a las cuales podemos enviar trabajos,
una de ellas considerada como 'real time'. A la hora de extraer
elementos se vacia en primer lugar la ocla de 'real time', y los
trabajos se devuelven en el orden en que fueron incluidos.
"""

	def __init__ ( self , type="Simple" ):
		"""
El constructor define una variable con el nombre del scheduler,
y crea dos listas separadas para cada cola
"""
		self.type = type
		self.rt = []
		self.jobs = []
	
	def __str__(self):
		"""Devuelve un string descriptivo utilizado durante el debugging"""
		return "%s Queue [%s]\n" % ( self.type , self.jobs )

	def destroy(self):
		"""Destructor explicito para las listas internas"""
		del self.rt
		del self.jobs

	def hasJobs(self):
		"""Determina si existen trabajos pendientes"""
		if self.rt or self.jobs :
			return True
		return False

	def add(self,job):
		"""Metodo privado para añadir trabajos"""
		if job.get( "priority" ) == "rt" :
			self.addRT(job)
		else :
			self.addJob(job)

	def addJob(self,job):
		"""Añade un elemento a la cola de ejecucion"""
		self.jobs.append(job)

	def addRT(self,job):
		"""Añade un elemento a la cola de tiempo real"""
		self.rt.append(job)

	def schedule(self):
		"""Extrae el siguiente elemento de la cola"""
		if self.rt :
			return self.rt.pop(0)
		if self.jobs :
			return self.jobs.pop(0)
		return None


class SerialScheduler ( SimpleScheduler ) :
	"""
Extiende el scheduler basico con la inclusion de prioridades en la
cola principal. La cola de tiempo real sigue teniendo preferencia
absoluta, y las diferentes prioridades se vacian de forma secuencial,
de modo que no se devuelven trabajos de una cierta prioridad mientras
existan trabajos encolados con prioridad mayor
"""

	def __init__(self, type="Serial", max_prio=10):
		"""
El constructor acepta un argumento extra con la prioridad maxima,
e inicializa una lista separada para cada prioridad. Se crea tambien
una lista con las prioridades disponibles en orden inverso para
facilitar los loops de extraccion.
"""
		SimpleScheduler.__init__( self , "Serial" )
		self.max_prio = max_prio
		for i in range(self.max_prio):
			self.jobs.append([])
		self.revpriolist = range(self.max_prio)
		self.revpriolist.reverse()
	
	def __str__(self):
		"""String con mayor detalle, incluyendo la longitud de cada cola"""
		aux = ""
		for i in range(self.max_prio):
			aux += "%s Queue Priority %d [%s]\n" % ( self.type , i , self.jobs[i] )
		return aux

	def hasJobs(self):
		"""Comprueba el estado de cada prioridad"""
		if self.rt :
			return True
		for i in self.revpriolist:
			if self.jobs[i] :
				return True
		return False

	def addJob(self,job):
		"""
Sobrecargamos el metodo privado para extraer la prioridad
solicitada a partir del propio trabajo que encolamos. Se realizan
varias comprobaciones de consistencia en dicha prioridad y se
efectua su encolado real en la cola que le corresponde.
"""
		prio = job.get( "priority" , None )
		if prio is None :
			prio = int( self.max_prio / 2 )
			job["priority"] = "%s" % prio
		prio = int(prio)
		if prio < 0 :
			prio = 0
			job["priority"] = "0"
		elif prio >= self.max_prio :
			prio = self.max_prio - 1
			job["priority"] = "%s" % prio
		self.jobs[prio].append(job)

	def schedule(self):
		"""
Una vez comprobada la cola de tiempo real, se recorre cada prioridad
en orden inverso, parando en cuanto se encuentra el primer trabajo.
"""
		if self.rt :
			return self.rt.pop(0)
		for i in self.revpriolist :
			if self.jobs[i] :
				return self.jobs[i].pop(0)
		return None


class ProportionalPrioScheduler ( SerialScheduler ) :
	"""
Modifica el scheduler serial para evitar el estancamiento de trabajos.
En lugar de devolver el trabajo de mayor prioridad, la busqueda se
realiza sobre un rango de prioridades, que se incrementa cada vez que
se extrae un trabajo. De esta forma se da salida a trabajos de baja
prioridad, manteniendo una cierta preferencia sobre las prioridades
mayores.
"""

	def __init__(self, type="Proportional", max_prio=10):
		"""
El constructor instancia el objeto padre y define dos variables, que
se usan para determinar el rango de prioridades que sera examinado
en la proxima extraccion.
"""
		SerialScheduler.__init__( self , type , max_prio )
		self.bottom = self.max_prio - 1
		self.top = self.max_prio
	
	def initCounters(self):
		"""
Inicializa el rango de extraccion, fijando el extremo superior
a la maxima prioridad, y decrementando el inferior.
"""
		self.top = self.max_prio
		self.bottom = ( self.bottom - 1 ) % self.max_prio

	def schedule(self):
		"""
Para extraer un trabajo, recorremos el rango de prioridades actual
de forma descendente. Si se encuentra algun trabajo, se modifica
la prioridad superior para que en la proxima extraccion se de salida
a un trabajo de las prioridades que no se han llegado a comprobar.
Si se llega a la prioridad inferior sin haber encontrado ningun
trabajo, se decrementa el minimo y se repite la busqueda.
"""
		if self.rt :
			return self.rt.pop(0)
		while self.hasJobs():
			for p in range(self.top,self.bottom,-1) :
				prio = p - 1
				if self.jobs[prio] :
					self.top = prio
					return self.jobs[prio].pop(0)
			self.initCounters()
		return None


class SchedulerFactory:
	"""
Clase de tipo factoria, destinada a generar un cierto scheduler en
base a su nombre. El scheduler por defecto es el serial.
"""

	def getScheduler(self,sched_type=None):
		if sched_type == "serial" :
			return SerialScheduler()
		elif sched_type == "simple" :
			return SimpleScheduler()
		elif sched_type == "proportional" :
			return ProportionalPrioScheduler()
		else :
			return SerialScheduler()

