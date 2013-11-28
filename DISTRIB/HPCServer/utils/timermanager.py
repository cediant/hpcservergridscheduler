# Copyright (C) 2012  CEDIANT <info@cediant.es>
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, see <http://www.gnu.org/licenses/>.

import os , sys
import threading

import random
import time

class PeriodicJob :
	""" timermanager.PeriodicJob(5,printea,("uno","dos")) """

	def __init__ ( self , interval , application , args=() ) :
		if application( *args ) :
			sleeptime = random.uniform(-5,5)
			thr = threading.Timer( interval + sleeptime , PeriodicJob , args=(interval,application,args) )
			thr.setDaemon(True)
			thr.start()

