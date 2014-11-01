#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright (c) 2012, 2014 SMHI

# Author(s):

#   Martin Raspaud <martin.raspaud@smhi.se>

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""Testing publishing from posttroll.
"""

from posttroll.publisher import Publish
from posttroll.message import Message
from time import sleep
from datetime import datetime

msgs = [
    """pytroll://PDS/0/norrköping/dev/polar/direct_readout file safusr.u@lxserv248.smhi.se 2014-08-27T07:57:53.0 v1.01 application/json {"satellite": "TERRA", "format": "PDS", "start_time": "2014-08-27T07:57:53", "level": "0", "orbit_number": 78142, "uri": "ssh://safe.smhi.se//san1/polar_in/direct_readout/eos/lvl0/P0420064AAAAAAAAAAAAAA14239075753001.PDS", "number": 1, "instrument": "modis", "end_time": "2014-08-27T08:08:35", "filename": "P0420064AAAAAAAAAAAAAA14239075753001.PDS", "type": "binary"}""",
    """pytroll://PDS/0/norrköping/dev/polar/direct_readout file safusr.u@lxserv248.smhi.se 2014-08-27T07:57:53.0 v1.01 application/json {"satellite": "TERRA", "format": "PDS", "start_time": "2014-08-27T07:57:53.0", "level": "0", "orbit_number": 78142, "uri": "ssh://safe.smhi.se//san1/polar_in/direct_readout/eos/lvl0/P0420064AAAAAAAAAAAAAA14239075753000.PDS", "number": 0, "instrument": "modis", "end_time": "2014-08-27T08:08:35", "filename": "P0420064AAAAAAAAAAAAAA14239075753000.PDS", "type": "binary"}""",
]

with Publish("receiver", 0, ["PDS", ]) as pds_pub:
    while True:
        # msg = Message('/oper/polar/direct_readout/norrköping', "info",
        # "the time is now " + str(datetime.now())).encode()
        # idx = np.random.randint(0,3)
        # msg = TEST_MSG[idx]
        # hrpt_pub.send(msg)
        # pds_pub.send(msg)
        # print msg
        for msg in msgs:
            pds_pub.send(msg)
            sleep(3)

        # sleep(30)
        # msg = Message('/oper/polar/direct_readout/norrköping', "info",
        #               "the time is now " + str(datetime.now())).encode()
        # pds_pub.send(msg)
        # print msg
        # sleep(0.5)
        break
