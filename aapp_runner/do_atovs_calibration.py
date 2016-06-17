#!/home/users/satman/current/bin/python
# -*- coding: utf-8 -*-

# Copyright (c) 2016

# Author(s):

#   Trygve Aspenes

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

"""Run the calibration script from AAPP for TOVS or ATOVS
Relay on several other steps before this can be DONE
"""

import os
import logging

from helper_functions import run_shell_command

LOG = logging.getLogger(__name__)

def do_atovs_calibration(process_config, timestamp):

    #This function relays on beeing in a working directory
    current_dir = os.getcwd() #Store the dir to change back to after function complete
    os.chdir(process_config['working_directory'])

    #calibration_location = "-c -l"
    if "".join(process_config['a_tovs']) == 'TOVS':
        cmd = "msucl {0} -s {1} -d {2:%Y%m%d} -h {2:%H%M} -n {3:05d} {4}".format(process_config['calibration_location'],
                                                                                 process_config['platform'],
                                                                                 timestamp,
                                                                                 process_config['orbit_number'],
                                                                                 process_config['msun_file'])
        try:
            status, returncode, std, err = run_shell_command(cmd)
        except:
            LOG.error("Command {} failed.".format(cmd))
        else:
            if returncode != 0:
                LOG.error("Command {} failed with return code {}.".format(cmd, returncode))
                return False
            else:
                LOG.info("Command {} complete.".format(cmd))
                
    elif "".join(process_config['a_tovs']) == 'ATOVS':
        if process_config['process_amsua']:
            cmd = "amsuacl {0} -s {1} -d {2:%Y%m%d} -h {2:%H%M} -n {3:05d} {4}".format(process_config['calibration_location'],
                                                                                       process_config['platform'],
                                                                                       timestamp,
                                                                                       process_config['orbit_number'],
                                                                                       process_config['amsua_file'])
            try:
                status, returncode, std, err = run_shell_command(cmd)
            except:
                LOG.error("Command {} failed.".format(cmd))
            else:
                if returncode != 0:
                    LOG.error("Command {} failed with return code {}.".format(cmd, returncode))
                    return False
                else:
                    LOG.info("Command {} complete.".format(cmd))

        if process_config['process_amsub']:
            amsub_script = "mhscl"
            if int(process_config['platform'][4:6]) <= 17:
                amsu_script = "amsubcl"
                
            cmd = "{0} {1} -s {2} -d {3:%Y%m%d} -h {3:%H%M} -n {4:05d} {5}".format(amsub_script,
                                                                                   process_config['calibration_location'],
                                                                                   process_config['platform'],
                                                                                   timestamp,
                                                                                   process_config['orbit_number'],
                                                                                   process_config['amsub_file'])
            try:
                status, returncode, std, err = run_shell_command(cmd)
            except:
                LOG.error("Command {} failed.".format(cmd))
            else:
                if returncode != 0:
                    LOG.error("Command {} failed with return code {}.".format(cmd, returncode))
                    return False
                else:
                    LOG.info("Command {} complete.".format(cmd))


    else:
        LOG.error("Unknown A|TOVS key string: {}".format("".join(process_config['a_tovs'])))
        return False

    #Change back after this is done
    os.chdir(current_dir)

    LOG.info("do_atovs_calibration complete!")
    return True