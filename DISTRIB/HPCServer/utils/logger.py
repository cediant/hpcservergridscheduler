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

import inspect
import time

import smtplib
from email.MIMEMultipart import MIMEMultipart
from email.MIMEBase import MIMEBase
from email.MIMEText import MIMEText
from email.Utils import COMMASPACE, formatdate
from email import Encoders
import os
import types

import Ice
import IceGrid


CBUFFER_SIZE = 10

DEBUG = 10
INFO = 30
NORMAL = 50
WARNING = 60
CRITICAL = 80

masks = { 'debug':DEBUG , 'info':INFO , 'normal':NORMAL , 'warning':WARNING , 'critical':CRITICAL }
levelnames = { DEBUG:'debug' , INFO:'info' , NORMAL:'normal' , WARNING:'warning' , CRITICAL:'critical' }

def __function__():
        caller = inspect.stack()[1]
        return caller[3]

def __line__():
        caller = inspect.stack()[1]
        return int (caller[2])

class Cbuffer:
        """
        This class instances a dictiorary of size 
        items. The behavior is like a regular
        circular buffer for avoid to grow beyon of
        size limit. The older item is delted when
        the buffer is full and replaced for the new.
        """
        def __init__(self, size):
                self._nitems = size
                self._buffer = {}
                self._index = []
        
        def insert(self, timestamp, message):
                if len(self._index) == self._nitems:
                        del self._buffer[self._index[0]]
                        del self._index[0]

                self._index.append(timestamp)
                self._buffer[timestamp] = message

        def dump(self):
                items = self._buffer.items()
                items.sort()
                logger.log.msg( logger.NORMAL , items )

        def get(self):
                items = self._buffer.items()
                items.sort()
                out_string = ''
                for i in xrange(len(items)):
                        out_string += " " + \
                         time.asctime(time.localtime(items[i][0])) + \
                        " %s" % items[i][1] + "\n"

                return out_string

#
# Special logger facility.
# 
class Logger:

        def __init__(self, filename = None):
                if filename:
                        self._fd = open(filename, 'a')
                else:
                        self._fd = None

                self._loglevel = NORMAL
                self._logmask= NORMAL
                self._cbuffer = Cbuffer(CBUFFER_SIZE)

        def setlogmask(self, logmask):
		if masks.has_key( logmask ) :
               		self._logmask = masks[ logmask ]
		elif '__int__' in dir(logmask) :
                	self._logmask = int(logmask)

        def write(self, message):
		self.msg( NORMAL , message )

        def msg(self, loglevel, message, function = None, line = None):
                if loglevel >= self._logmask:
                        timestamp = time.time()
                        if self._fd:
				if levelnames.has_key( loglevel ) :
                                	levelname = levelnames[loglevel]
				else :
                                	levelname = "%s" % loglevel
                                cadformated = \
                                        "%s %s %s\n" % \
                                        ( time.asctime(time.localtime(timestamp)) , levelname , message )
                                self._fd.write(cadformated)
                                self._fd.flush()

                        self._cbuffer.insert(timestamp, message)

        def showbuffer(self):
                self._cbuffer.dump()

        def getbuffer(self):
                return self._cbuffer.get()

        def sendlogbymail(self, to, subject, text, jobid, serversmtp1, serversmtp2, files=[] ):

                # raises error if false
                if type(to) is not types.ListType :
			to = to.split(",")
                assert type(files) == list
		hostname = os.uname()[1]
                fro = "executor@%s" % hostname
                
                msg = MIMEMultipart()
		
                msg['From'] = fro
                msg['To'] = COMMASPACE.join(to)
                msg['Date'] = formatdate(localtime=True)
		msg['Subject'] = subject 
		msg['Model'] = "##"+jobid.split()[1]+"##"

                msg.attach(MIMEText(text))
		loglines = "\nContenido del fichero de log:\n%s" % self.getbuffer()
                msg.attach(MIMEText(loglines))

                #for file in files:
                #        part = MIMEBase('application', "octet-stream")
                #        part.set_payload(open(file,"rb").read())
                #        Encoders.encode_base64(part)
                #        part.add_header('Content-Disposition', 'attachment; filename="%s"'
                #                % os.path.basename(file))
                #        msg.attach(part)
                try:
		 smtp = smtplib.SMTP(serversmtp1)
                 smtp.sendmail(fro, to, msg.as_string())
                 smtp.close()
                except:
                 print "No se puede conectar con el servidor smtp %s" %(serversmtp1)
		 print "Intentando con servidor smtp %s" %(serversmtp2)
		 try:
		   smtp = smtplib.SMTP(serversmtp2)                 
                   smtp.sendmail(fro, to, msg.as_string())
                   smtp.close()
                 except:
                  print "No se puede conectar con ninguno de los servidores"


log = None

