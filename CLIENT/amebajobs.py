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

import random

jobstring = {}

jobstring["diary"] = """{{%06d-%07d-%s MTrigger
	S0 = %s;
	X = %s;
	mu = %s;
	sig = %s;
	r = %s;
	dt = %s/365;
	etime = %s;
}}
"""

jobstring["month"] = """{{%06d-%07d-%s Rainbow
	S0 = %s;
	X = %s;
	mu = %s;
	sig = %s;
	r = %s;
	dt = %s/12;
	etime = %s;
}}
"""

jobstring["anual"] = """{{%06d-%07d-%s PUTCANCES
	S0 = %s;
	X = %s;
	mu = %s;
	sig = %s;
	r = %s;
	dt = %s;
	etime = %s;
}}
"""

jobstring["week"] = """{{%06d-%07d-%s Putcancel
	S0 = %s;
	X = %s;
	mu = %s;
	sig = %s;
	r = %s;
	dt = %s/52;
	etime = %s;
}}
"""

def construct_job( ( sessid , sessid1 ) , seq=1 , type=None , S0=50 , X=0.1 , mu=0.0 , sig=0.0 , r=0.0 , dt=1, etime=0.0 ) :
    if type is None :
        types = jobstring.keys()
        index = int( len(types) * random.random() )
        type = types[index]
    return jobstring[type] % ( sessid , sessid1 , seq , S0, X, mu, sig, r, dt, etime)

if __name__ == '__main__':
    for i in range(5) :
        job = construct_job(None,i)
        print job.split('\n')[0]

